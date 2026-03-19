from __future__ import annotations

from base64 import urlsafe_b64decode, urlsafe_b64encode
from hashlib import sha256
from pathlib import Path
import json
import uuid

class EncryptedWALQueue:
    def __init__(self, path: Path, secret: str) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.secret = secret.encode("utf-8")

    def append(self, record: dict[str, object]) -> dict[str, object]:
        stored = {
            "record_id": str(uuid.uuid4()),
            "sent": False,
            **record,
        }
        token = self._encrypt(json.dumps(stored, sort_keys=True).encode("utf-8"))
        with self.path.open("ab") as handle:
            handle.write(token + b"\n")
        return stored

    def read_all(self) -> list[dict[str, object]]:
        if not self.path.exists():
            return []
        records: list[dict[str, object]] = []
        for line in self.path.read_bytes().splitlines():
            if not line:
                continue
            payload = self._decrypt(line)
            records.append(json.loads(payload))
        return records

    def pending(self) -> list[dict[str, object]]:
        return [record for record in self.read_all() if not record.get("sent", False)]

    def mark_sent(self, record_id: str) -> None:
        records = self.read_all()
        changed = False
        for record in records:
            if record.get("record_id") == record_id:
                record["sent"] = True
                changed = True
        if changed:
            self._rewrite(records)

    def depth(self) -> int:
        return len(self.pending())

    def _encrypt(self, payload: bytes) -> bytes:
        mask = self._mask(len(payload))
        ciphertext = bytes(left ^ right for left, right in zip(payload, mask, strict=False))
        return urlsafe_b64encode(ciphertext)

    def _decrypt(self, token: bytes) -> bytes:
        ciphertext = urlsafe_b64decode(token)
        mask = self._mask(len(ciphertext))
        return bytes(left ^ right for left, right in zip(ciphertext, mask, strict=False))

    def _mask(self, length: int) -> bytes:
        seed = sha256(self.secret).digest()
        chunks: list[bytes] = []
        counter = 0
        while sum(len(chunk) for chunk in chunks) < length:
            chunks.append(sha256(seed + counter.to_bytes(4, "big")).digest())
            counter += 1
        return b"".join(chunks)[:length]

    def _rewrite(self, records: list[dict[str, object]]) -> None:
        with self.path.open("wb") as handle:
            for record in records:
                token = self._encrypt(json.dumps(record, sort_keys=True).encode("utf-8"))
                handle.write(token + b"\n")
