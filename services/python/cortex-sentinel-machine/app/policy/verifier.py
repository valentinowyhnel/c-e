from __future__ import annotations

from hashlib import sha256
import hmac


class PolicyBundleVerifier:
    """Signed bundle verifier using deterministic shared material for local validation."""

    def __init__(self, public_material: str) -> None:
        self.public_material = public_material.encode("utf-8")

    def verify(self, bundle: dict[str, object]) -> bool:
        signature = str(bundle.get("signature", ""))
        body = {key: value for key, value in bundle.items() if key != "signature"}
        expected = hmac.new(self.public_material, repr(sorted(body.items())).encode("utf-8"), sha256).hexdigest()
        return hmac.compare_digest(signature, expected)

