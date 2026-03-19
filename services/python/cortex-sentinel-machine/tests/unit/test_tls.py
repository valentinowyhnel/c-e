from pathlib import Path
import shutil
import uuid

import pytest

from app.transport.tls import RotatingTLSState, TLSMaterialLoader


def test_tls_loader_rejects_missing_files() -> None:
    root = Path("test-artifacts") / f"tls-{uuid.uuid4().hex[:8]}"
    root.mkdir(parents=True, exist_ok=True)
    try:
        loader = TLSMaterialLoader(root / "server.crt", root / "server.key", root / "ca.crt")
        with pytest.raises(FileNotFoundError):
            loader.load()
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_tls_rotation_detects_fingerprint_change() -> None:
    root = Path("test-artifacts") / f"tls-{uuid.uuid4().hex[:8]}"
    root.mkdir(parents=True, exist_ok=True)
    cert = root / "server.crt"
    key = root / "server.key"
    ca = root / "ca.crt"
    try:
        cert.write_text("cert-v1", encoding="utf-8")
        key.write_text("key-v1", encoding="utf-8")
        ca.write_text("ca-v1", encoding="utf-8")
        state = RotatingTLSState(TLSMaterialLoader(cert, key, ca))
        changed_first, first = state.refresh()
        cert.write_text("cert-v2", encoding="utf-8")
        changed_second, second = state.refresh()
        assert changed_first is True
        assert changed_second is True
        assert first.fingerprint != second.fingerprint
    finally:
        shutil.rmtree(root, ignore_errors=True)
