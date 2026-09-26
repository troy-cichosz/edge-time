import base64
import hashlib
import json
import logging
import os
import shutil
import threading
import time
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


logger = logging.getLogger(__name__)


class AttestationStore:
    def __init__(self, settings):
        self.settings = settings

        state_dir = Path(settings.state_dir)
        state_dir.mkdir(parents=True, exist_ok=True)

        self.chain_file = state_dir / "attestations.jsonl"
        self.seq_file = state_dir / "sequence"
        self.key_path = Path(settings.attestation_key)

        self._lock = threading.Lock()

        self._recover_trailing_nulls()

        self.key = self._load_or_create_key()
        self._reconcile_sequence()

    def _load_or_create_key(self) -> Ed25519PrivateKey:
        if self.key_path.exists():
            raw = self.key_path.read_bytes()

            try:
                key = Ed25519PrivateKey.from_private_bytes(raw)
            except ValueError as exc:
                raise RuntimeError(
                    f"Invalid Ed25519 private key: {self.key_path}"
                ) from exc

            return key

        self.key_path.parent.mkdir(parents=True, exist_ok=True)

        key = Ed25519PrivateKey.generate()
        raw = key.private_bytes(
            serialization.Encoding.Raw,
            serialization.PrivateFormat.Raw,
            serialization.NoEncryption(),
        )

        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL

        fd = None

        try:
            fd = os.open(
                self.key_path,
                flags,
                0o600,
            )

            os.write(fd, raw)

        except FileExistsError:
            # Another process created the key between the existence
            # check and the create operation. Load the existing key.
            return self._load_existing_key()

        finally:
            if fd is not None:
                os.close(fd)

        os.chmod(self.key_path, 0o600)

        return key

    def _load_existing_key(self) -> Ed25519PrivateKey:
        raw = self.key_path.read_bytes()

        try:
            key = Ed25519PrivateKey.from_private_bytes(raw)
        except ValueError as exc:
            raise RuntimeError(
                f"Invalid Ed25519 private key: {self.key_path}"
            ) from exc

        return key

    def public_key_b64(self) -> str:
        public_key = self.key.public_key().public_bytes(
            serialization.Encoding.Raw,
            serialization.PublicFormat.Raw,
        )

        return base64.b64encode(public_key).decode()

    @staticmethod
    def canonical_bytes(payload: dict) -> bytes:
        signing_payload = {
            key: value
            for key, value in payload.items()
            if key not in {
                "record_hash",
                "signature",
                "public_key",
            }
        }

        return json.dumps(
            signing_payload,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode()

    def _read_chain_records(self) -> list[dict]:
        if not self.chain_file.exists():
            return []

        records = []

        for line in self.chain_file.read_text(
            encoding="utf-8"
        ).splitlines():
            if not line.strip():
                continue

            records.append(json.loads(line))

        if not self.verify_chain_records(records):
            raise RuntimeError(
                f"Attestation chain verification failed: "
                f"{self.chain_file}"
            )

        return records

    def _recover_trailing_nulls(self):
        if not self.chain_file.exists():
            return

        data = self.chain_file.read_bytes()

        if not data or not data.endswith(b"\x00"):
            return

        valid_end = len(data.rstrip(b"\x00"))

        # Only recover NUL padding that follows a complete JSONL record.
        # If the bytes before the NUL run do not end at a newline, the
        # corruption may include a partial/non-NUL record and must not be
        # silently discarded.
        if valid_end == 0 or data[valid_end - 1:valid_end] != b"\n":
            return

        backup = self.chain_file.with_name(
            f"{self.chain_file.name}.recovery-{time.time_ns()}.bak"
        )

        shutil.copy2(self.chain_file, backup)

        with self.chain_file.open("r+b") as handle:
            handle.truncate(valid_end)
            handle.flush()
            os.fsync(handle.fileno())

        logger.warning(
            "Recovered trailing NUL bytes from attestation chain; "
            "original state preserved at %s",
            backup,
        )

    def _write_sequence(self, sequence: int):
        temporary = self.seq_file.with_name(
            f"{self.seq_file.name}.tmp-{os.getpid()}"
        )

        try:
            with temporary.open("w", encoding="utf-8") as handle:
                handle.write(str(sequence))
                handle.flush()
                os.fsync(handle.fileno())

            os.replace(temporary, self.seq_file)

            try:
                directory_fd = os.open(
                    self.seq_file.parent,
                    os.O_RDONLY,
                )
            except OSError:
                directory_fd = None

            if directory_fd is not None:
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)

        finally:
            if temporary.exists():
                temporary.unlink()

    def _reconcile_sequence(self):
        records = self._read_chain_records()

        sequence = records[-1]["sequence"] if records else 0

        if self.seq_file.exists():
            value = self.seq_file.read_text().strip()

            try:
                persisted = int(value)
            except ValueError as exc:
                raise RuntimeError(
                    f"Invalid attestation sequence file: {self.seq_file}"
                ) from exc

            if persisted == sequence:
                return

        self._write_sequence(sequence)

        logger.warning(
            "Reconciled attestation sequence file to persisted chain "
            "sequence %s",
            sequence,
        )

    def _next_sequence(self, records: list[dict]) -> int:
        if not records:
            return 1

        return records[-1]["sequence"] + 1

    def _previous_hash(self, records: list[dict]):
        if not records:
            return None

        return records[-1].get("record_hash")

    def append(self, payload: dict):
        payload = dict(payload)

        with self._lock:
            records = self._read_chain_records()

            sequence = self._next_sequence(records)
            previous_hash = self._previous_hash(records)

            payload.update(
                {
                    "sequence": sequence,
                    "previous_hash": previous_hash,
                }
            )

            canonical = self.canonical_bytes(payload)

            record_hash = hashlib.sha256(canonical).hexdigest()

            signature = base64.b64encode(
                self.key.sign(canonical)
            ).decode()

            public_key = self.public_key_b64()

            payload.update(
                {
                    "record_hash": record_hash,
                    "signature": signature,
                    "public_key": public_key,
                }
            )

            with self.chain_file.open(
                "a",
                encoding="utf-8",
            ) as handle:
                handle.write(
                    json.dumps(
                        payload,
                        default=str,
                        separators=(",", ":"),
                    )
                    + "\n"
                )
                handle.flush()
                os.fsync(handle.fileno())

            self._write_sequence(sequence)

        return payload

    @staticmethod
    def verify_record(record: dict) -> bool:
        required = {
            "sequence",
            "previous_hash",
            "record_hash",
            "signature",
            "public_key",
        }

        if not required.issubset(record):
            return False

        canonical = AttestationStore.canonical_bytes(record)

        calculated_hash = hashlib.sha256(canonical).hexdigest()

        if calculated_hash != record["record_hash"]:
            return False

        try:
            public_key = Ed25519PublicKey.from_public_bytes(
                base64.b64decode(record["public_key"])
            )

            signature = base64.b64decode(record["signature"])

            public_key.verify(
                signature,
                canonical,
            )

        except (
            ValueError,
            TypeError,
            InvalidSignature,
        ):
            return False

        return True

    @classmethod
    def verify_chain_records(cls, records: list[dict]) -> bool:
        expected_sequence = 1
        previous_hash = None

        for record in records:
            if record.get("sequence") != expected_sequence:
                return False

            if record.get("previous_hash") != previous_hash:
                return False

            if not cls.verify_record(record):
                return False

            previous_hash = record.get("record_hash")
            expected_sequence += 1

        return True

    def verify_chain(self) -> bool:
        self._read_chain_records()
        return True
