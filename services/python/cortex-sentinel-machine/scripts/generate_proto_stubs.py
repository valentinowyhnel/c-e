from __future__ import annotations

from pathlib import Path
import importlib.util
import subprocess
import sys


def main() -> int:
    if not importlib.util.find_spec("grpc_tools"):
        print("grpc_tools is not installed; stub generation is blocked fail-closed.", file=sys.stderr)
        return 1
    proto = Path("proto/sentinel_machine.proto")
    command = [
        sys.executable,
        "-m",
        "grpc_tools.protoc",
        f"-I{proto.parent}",
        f"--python_out={proto.parent}",
        f"--grpc_python_out={proto.parent}",
        str(proto),
    ]
    return subprocess.call(command)


if __name__ == "__main__":
    raise SystemExit(main())
