from app.policy import ManifestSigner


def test_manifest_signer_signs_and_verifies() -> None:
    signer = ManifestSigner("hmac-sha256", "dev-key")
    manifest = signer.sign({"model_id": "m1", "tenant_scope": "t1"})
    assert signer.verify(manifest) is True


def test_manifest_signer_rejects_unsupported_algorithm() -> None:
    signer = ManifestSigner("hmac-sha256", "dev-key")
    manifest = {"algorithm": "ed25519", "body": {"model_id": "m1"}, "signature": "x"}
    assert signer.verify(manifest) is False

