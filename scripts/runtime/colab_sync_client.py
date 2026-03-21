from __future__ import annotations

import argparse
import hashlib
import hmac
import json
from pathlib import Path

import httpx


def load_payload(path: str) -> dict[str, object]:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def sign_payload(payload: dict[str, object], secret: str) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def push_payload(url: str, payload: dict[str, object], secret: str) -> dict[str, object]:
    signature = sign_payload(payload, secret)
    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            url,
            json=payload,
            headers={"x-cortex-colab-signature": signature},
        )
        response.raise_for_status()
        return response.json()


def main() -> int:
    parser = argparse.ArgumentParser(description="Push a verified Colab training result into Cortex.")
    parser.add_argument("payload", help="Path to the verified Colab payload JSON file.")
    parser.add_argument(
        "--url",
        default="http://127.0.0.1:8080/v1/training/colab/ingest",
        help="Cortex orchestrator ingestion URL.",
    )
    parser.add_argument(
        "--secret",
        required=True,
        help="Shared HMAC secret used to sign the Colab payload.",
    )
    args = parser.parse_args()

    payload = load_payload(args.payload)
    result = push_payload(args.url, payload, args.secret)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
