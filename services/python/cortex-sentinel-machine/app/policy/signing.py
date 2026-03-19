from __future__ import annotations

from hashlib import sha256
import hmac
import json


class ManifestSigner:
    """
    Fail-closed signer.
    In this environment only `hmac-sha256` is executable without extra crypto tooling.
    Any other algorithm is rejected.
    """

    SUPPORTED = {"hmac-sha256"}

    def __init__(self, algorithm: str, key_material: str) -> None:
        self.algorithm = algorithm
        self.key_material = key_material.encode("utf-8")

    def sign(self, body: dict[str, object]) -> dict[str, object]:
        if self.algorithm not in self.SUPPORTED:
            raise ValueError(f"unsupported signing algorithm: {self.algorithm}")
        payload = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
        signature = hmac.new(self.key_material, payload, sha256).hexdigest()
        return {"algorithm": self.algorithm, "body": body, "signature": signature}

    def verify(self, manifest: dict[str, object]) -> bool:
        algorithm = str(manifest.get("algorithm", ""))
        if algorithm not in self.SUPPORTED:
            return False
        body = manifest.get("body", {})
        if not isinstance(body, dict):
            return False
        payload = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
        expected = hmac.new(self.key_material, payload, sha256).hexdigest()
        return hmac.compare_digest(str(manifest.get("signature", "")), expected)
