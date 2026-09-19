import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from app.attestation import AttestationStore


class AttestationTests(unittest.TestCase):

    def make_settings(self, state_dir: str):
        return SimpleNamespace(
            state_dir=state_dir,
            attestation_key=str(
                Path(state_dir) / "identity.key"
            ),
        )

    def test_key_is_generated_and_persistent(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = self.make_settings(temp_dir)

            first = AttestationStore(settings)

            key_path = Path(settings.attestation_key)

            self.assertTrue(key_path.exists())
            self.assertEqual(
                key_path.stat().st_size,
                32,
            )

            first_public_key = first.public_key_b64()

            second = AttestationStore(settings)

            self.assertEqual(
                first_public_key,
                second.public_key_b64(),
            )

            mode = key_path.stat().st_mode & 0o777
            self.assertEqual(mode, 0o600)

    def test_attestation_is_signed_and_verifiable(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = self.make_settings(temp_dir)
            store = AttestationStore(settings)

            record = store.append(
                {
                    "record_type": "time_attestation",
                    "created_utc": "2026-09-16T00:00:00+00:00",
                    "device_id": "test-device",
                    "selected_source": "system",
                    "utc": "2026-09-16T00:00:00+00:00",
                    "monotonic_ns": 123456789,
                    "state": "SYNCHRONIZED",
                    "uncertainty_ms": 1.0,
                    "observations": [],
                }
            )

            self.assertEqual(record["sequence"], 1)
            self.assertIsNone(record["previous_hash"])
            self.assertTrue(record["record_hash"])
            self.assertTrue(record["signature"])
            self.assertTrue(record["public_key"])

            self.assertTrue(
                AttestationStore.verify_record(record)
            )

    def test_modified_payload_fails(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = self.make_settings(temp_dir)
            store = AttestationStore(settings)

            record = store.append(
                {
                    "record_type": "time_attestation",
                    "device_id": "test-device",
                    "utc": "2026-09-16T00:00:00+00:00",
                }
            )

            modified = dict(record)
            modified["device_id"] = "modified-device"

            self.assertFalse(
                AttestationStore.verify_record(modified)
            )

    def test_modified_signature_fails(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = self.make_settings(temp_dir)
            store = AttestationStore(settings)

            record = store.append(
                {
                    "record_type": "time_attestation",
                    "device_id": "test-device",
                }
            )

            modified = dict(record)
            modified["signature"] = (
                modified["signature"][:-2] + "AA"
            )

            self.assertFalse(
                AttestationStore.verify_record(modified)
            )

    def test_wrong_public_key_fails(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = self.make_settings(temp_dir)
            store = AttestationStore(settings)

            record = store.append(
                {
                    "record_type": "time_attestation",
                    "device_id": "test-device",
                }
            )

            other_settings = self.make_settings(
                os.path.join(temp_dir, "other")
            )
            other_store = AttestationStore(other_settings)

            modified = dict(record)
            modified["public_key"] = (
                other_store.public_key_b64()
            )

            self.assertFalse(
                AttestationStore.verify_record(modified)
            )

    def test_chain_and_sequence_are_verified(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = self.make_settings(temp_dir)
            store = AttestationStore(settings)

            first = store.append(
                {
                    "record_type": "time_attestation",
                    "device_id": "test-device",
                    "sequence_marker": "first",
                }
            )

            second = store.append(
                {
                    "record_type": "time_attestation",
                    "device_id": "test-device",
                    "sequence_marker": "second",
                }
            )

            self.assertEqual(first["sequence"], 1)
            self.assertEqual(second["sequence"], 2)
            self.assertEqual(
                second["previous_hash"],
                first["record_hash"],
            )

            self.assertTrue(
                AttestationStore.verify_chain_records(
                    [first, second]
                )
            )

            broken_sequence = dict(second)
            broken_sequence["sequence"] = 3

            self.assertFalse(
                AttestationStore.verify_chain_records(
                    [first, broken_sequence]
                )
            )

            broken_previous = dict(second)
            broken_previous["previous_hash"] = "0" * 64

            self.assertFalse(
                AttestationStore.verify_chain_records(
                    [first, broken_previous]
                )
            )

    def test_persisted_chain_verifies(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = self.make_settings(temp_dir)
            store = AttestationStore(settings)

            store.append(
                {
                    "record_type": "time_attestation",
                    "device_id": "test-device",
                }
            )

            store.append(
                {
                    "record_type": "time_attestation",
                    "device_id": "test-device",
                }
            )

            self.assertTrue(store.verify_chain())

            lines = Path(
                settings.state_dir,
                "attestations.jsonl",
            ).read_text(
                encoding="utf-8"
            ).splitlines()

            records = [
                json.loads(line)
                for line in lines
                if line.strip()
            ]

            self.assertEqual(len(records), 2)

    def test_sequence_file_is_reconciled_to_chain(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = self.make_settings(temp_dir)
            store = AttestationStore(settings)

            store.append(
                {
                    "record_type": "time_attestation",
                    "device_id": "test-device",
                }
            )
            store.append(
                {
                    "record_type": "time_attestation",
                    "device_id": "test-device",
                }
            )

            Path(
                settings.state_dir,
                "sequence",
            ).write_text("40", encoding="utf-8")

            recovered = AttestationStore(settings)

            self.assertEqual(
                Path(
                    settings.state_dir,
                    "sequence",
                ).read_text(encoding="utf-8"),
                "2",
            )

            third = recovered.append(
                {
                    "record_type": "time_attestation",
                    "device_id": "test-device",
                }
            )

            self.assertEqual(third["sequence"], 3)
            self.assertTrue(recovered.verify_chain())

    def test_trailing_nulls_are_backed_up_and_recovered(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = self.make_settings(temp_dir)
            store = AttestationStore(settings)

            first = store.append(
                {
                    "record_type": "time_attestation",
                    "device_id": "test-device",
                }
            )

            chain_path = Path(
                settings.state_dir,
                "attestations.jsonl",
            )
            original = chain_path.read_bytes()
            chain_path.write_bytes(original + b"\x00" * 64)

            Path(
                settings.state_dir,
                "sequence",
            ).write_text("40", encoding="utf-8")

            recovered = AttestationStore(settings)

            self.assertEqual(
                chain_path.read_bytes(),
                original,
            )
            self.assertEqual(
                recovered._read_chain_records()[-1]["record_hash"],
                first["record_hash"],
            )

            backups = list(
                Path(settings.state_dir).glob(
                    "attestations.jsonl.recovery-*.bak"
                )
            )

            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_bytes(), original + b"\x00" * 64)

            self.assertEqual(
                Path(
                    settings.state_dir,
                    "sequence",
                ).read_text(encoding="utf-8"),
                "1",
            )

            second = recovered.append(
                {
                    "record_type": "time_attestation",
                    "device_id": "test-device",
                }
            )

            self.assertEqual(second["sequence"], 2)
            self.assertEqual(
                second["previous_hash"],
                first["record_hash"],
            )
            self.assertTrue(recovered.verify_chain())

    def test_sequence_failure_after_chain_write_is_recovered_from_chain(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = self.make_settings(temp_dir)
            store = AttestationStore(settings)

            original_write_sequence = store._write_sequence

            def fail_sequence_write(sequence):
                raise OSError("simulated sequence persistence failure")

            store._write_sequence = fail_sequence_write

            with self.assertRaises(OSError):
                store.append(
                    {
                        "record_type": "time_attestation",
                        "device_id": "test-device",
                    }
                )

            store._write_sequence = original_write_sequence

            recovered = AttestationStore(settings)

            second = recovered.append(
                {
                    "record_type": "time_attestation",
                    "device_id": "test-device",
                }
            )

            self.assertEqual(second["sequence"], 2)
            self.assertTrue(recovered.verify_chain())

    def test_non_null_trailing_corruption_is_not_auto_repaired(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = self.make_settings(temp_dir)
            store = AttestationStore(settings)

            store.append(
                {
                    "record_type": "time_attestation",
                    "device_id": "test-device",
                }
            )

            chain_path = Path(
                settings.state_dir,
                "attestations.jsonl",
            )
            with chain_path.open("ab") as handle:
                handle.write(b"corrupt-tail")

            with self.assertRaises(json.JSONDecodeError):
                AttestationStore(settings)


if __name__ == "__main__":
    unittest.main()