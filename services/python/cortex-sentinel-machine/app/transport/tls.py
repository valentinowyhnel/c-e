from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path


@dataclass(slots=True)
class TLSMaterial:
    server_cert: bytes
    server_key: bytes
    client_ca: bytes
    fingerprint: str


class TLSMaterialLoader:
    def __init__(self, cert_path: Path, key_path: Path, ca_path: Path) -> None:
        self.cert_path = cert_path
        self.key_path = key_path
        self.ca_path = ca_path

    def load(self) -> TLSMaterial:
        missing = [str(path) for path in [self.cert_path, self.key_path, self.ca_path] if not path.exists()]
        if missing:
            raise FileNotFoundError(f"missing_tls_material:{','.join(missing)}")
        cert = self.cert_path.read_bytes()
        key = self.key_path.read_bytes()
        ca = self.ca_path.read_bytes()
        fingerprint = sha256(cert + key + ca).hexdigest()
        return TLSMaterial(server_cert=cert, server_key=key, client_ca=ca, fingerprint=fingerprint)


class RotatingTLSState:
    def __init__(self, loader: TLSMaterialLoader) -> None:
        self.loader = loader
        self.current: TLSMaterial | None = None

    def refresh(self) -> tuple[bool, TLSMaterial]:
        loaded = self.loader.load()
        changed = self.current is None or self.current.fingerprint != loaded.fingerprint
        self.current = loaded
        return changed, loaded
