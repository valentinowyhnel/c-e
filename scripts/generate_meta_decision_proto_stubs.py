from __future__ import annotations

from pathlib import Path
import importlib.util
import subprocess
import sys


def main() -> int:
    if not importlib.util.find_spec("grpc_tools"):
        print("grpc_tools is not installed; meta-decision stub generation is blocked fail-closed.", file=sys.stderr)
        return 1

    proto_root = Path("proto/meta_decision/v1")
    proto = proto_root / "meta_decision.proto"
    if not proto.exists():
        print(f"missing proto file: {proto}", file=sys.stderr)
        return 1

    command = [
        sys.executable,
        "-m",
        "grpc_tools.protoc",
        f"-I{proto_root}",
        f"--python_out={proto_root}",
        f"--grpc_python_out={proto_root}",
        str(proto),
    ]
    return subprocess.call(command)


if __name__ == "__main__":
    raise SystemExit(main())
