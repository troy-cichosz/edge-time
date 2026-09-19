import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime, timezone

from app.models import TimeObservation
from app.service import TimeEngine


class CaptureContextTests(unittest.TestCase):
    def make_settings(self, state_dir: str):
        return SimpleNamespace(
            state_dir=state_dir,
            attestation_key=str(Path(state_dir) / "identity.key"),
            priorities=["system"],
            authority_url="",
            authority_id="",
            allow_system_source=True,
            allow_holdover=True,
            max_uncertainty_ms=500.0,
            consistency_threshold_ms=500.0,
            freshness_stale_ms=5000.0,
            freshness_expired_ms=30000.0,
            effective_device_id="test-device",
            is_authority=False,
            http_timeout_seconds=1.0,
        )

    def test_capture_context_creates_signed_attestation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            engine = TimeEngine(self.make_settings(temp_dir))

            context = engine.capture_context()

            self.assertEqual(context.device_id, "test-device")
            self.assertEqual(context.selected_source, "system")
            self.assertEqual(context.freshness, "FRESH")
            self.assertEqual(context.synchronization_state, "SYNCHRONIZED")
            self.assertEqual(context.holdover_state, "NOT_HOLDOVER")
            self.assertEqual(context.attestation_sequence, 1)
            self.assertTrue(context.attestation_record_hash)
            self.assertTrue(context.attestation_signature)

            records = [
                line
                for line in Path(
                    temp_dir,
                    "attestations.jsonl",
                ).read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]

            self.assertEqual(len(records), 1)
            self.assertIn(
                str(context.context_id),
                records[0],
            )

    def test_freshness_states(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = self.make_settings(temp_dir)
            engine = TimeEngine(settings)

            now = 10_000_000_000
            observation = TimeObservation(
                source_id="test",
                source_type="test",
                utc=datetime.now(timezone.utc),
                uncertainty_ms=1.0,
                valid=True,
                observed_monotonic_ns=now,
                observed_wall_utc=datetime.now(timezone.utc),
            )

            state, age = engine.freshness_for(
                observation,
                now,
                settings,
            )
            self.assertEqual(state, "FRESH")
            self.assertEqual(age, 0.0)

            state, age = engine.freshness_for(
                observation,
                now + 6_000_000,
                settings,
            )
            self.assertEqual(state, "STALE")
            self.assertEqual(age, 6.0)

            state, age = engine.freshness_for(
                observation,
                now + 31_000_000,
                settings,
            )
            self.assertEqual(state, "EXPIRED")
            self.assertEqual(age, 31.0)

    def test_context_attestation_reference_matches_record(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            engine = TimeEngine(self.make_settings(temp_dir))
            context = engine.capture_context()

            lines = Path(
                temp_dir,
                "attestations.jsonl",
            ).read_text(encoding="utf-8").splitlines()

            self.assertEqual(len(lines), 1)
            record = __import__("json").loads(lines[0])

            self.assertEqual(
                record["context_id"],
                str(context.context_id),
            )
            self.assertEqual(
                record["record_hash"],
                context.attestation_record_hash,
            )


if __name__ == "__main__":
    unittest.main()
