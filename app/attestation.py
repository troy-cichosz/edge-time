import base64, hashlib, json, os
from datetime import datetime, timezone
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from .models import Attestation

class AttestationStore:
    def __init__(self, settings):
        self.settings=settings
        Path(settings.state_dir).mkdir(parents=True, exist_ok=True)
        self.chain_file=Path(settings.state_dir)/"attestations.jsonl"
        self.seq_file=Path(settings.state_dir)/"sequence"
        self.key_path=Path(settings.attestation_key)
        self.key=None
        try:
            if self.key_path.exists():
                self.key=Ed25519PrivateKey.from_private_bytes(self.key_path.read_bytes())
        except Exception:
            self.key=None

    def _next_sequence(self):
        n=int(self.seq_file.read_text())+1 if self.seq_file.exists() else 1
        self.seq_file.write_text(str(n))
        return n

    def append(self, payload: dict):
        seq=self._next_sequence()
        previous=None
        if self.chain_file.exists():
            lines=self.chain_file.read_text().splitlines()
            if lines:
                previous=json.loads(lines[-1]).get("record_hash")
        payload.update({"sequence":seq,"previous_hash":previous})
        canonical=json.dumps(payload,sort_keys=True,separators=(",",":"),default=str).encode()
        record_hash=hashlib.sha256(canonical).hexdigest()
        signature=None; public_key=None
        if self.key:
            signature=base64.b64encode(self.key.sign(canonical)).decode()
            public_key=base64.b64encode(self.key.public_key().public_bytes(
                serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode()
        payload.update({"record_hash":record_hash,"signature":signature,"public_key":public_key})
        with self.chain_file.open("a") as f:
            f.write(json.dumps(payload,default=str)+"\n")
        return payload
