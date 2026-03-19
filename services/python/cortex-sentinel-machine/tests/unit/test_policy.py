from hashlib import sha256
import hmac

from app.policy import CriticalActionGuard, PolicyBundleVerifier


def test_unsigned_policy_bundle_is_refused() -> None:
    verifier = PolicyBundleVerifier("pub-material")
    bundle = {"policy_id": "p1", "tenant_id": "t1", "issued_at": "2026-03-19T10:00:00Z", "signature": "bad"}
    assert verifier.verify(bundle) is False


def test_signed_policy_bundle_is_accepted() -> None:
    material = "pub-material"
    verifier = PolicyBundleVerifier(material)
    body = {"policy_id": "p1", "tenant_id": "t1", "issued_at": "2026-03-19T10:00:00Z"}
    signature = hmac.new(material.encode("utf-8"), repr(sorted(body.items())).encode("utf-8"), sha256).hexdigest()
    assert verifier.verify({**body, "signature": signature}) is True


def test_critical_action_without_cortex_token_is_refused() -> None:
    guard = CriticalActionGuard()
    assert guard.authorize(cortex_token=None, approved=True) is False
    assert guard.authorize(cortex_token="signed-token", approved=False) is False
    assert guard.authorize(cortex_token="signed-token", approved=True) is True

