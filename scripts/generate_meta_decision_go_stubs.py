from __future__ import annotations

from pathlib import Path
import importlib.util
import os
import shutil
import subprocess
import sys


def _resolve_go_plugin(name: str) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    try:
        gopath = subprocess.check_output(["go", "env", "GOPATH"], text=True).strip()
    except Exception:
        return None
    suffix = ".exe" if os.name == "nt" else ""
    for root in [part for part in gopath.split(os.pathsep) if part]:
        candidate = Path(root) / "bin" / f"{name}{suffix}"
        if candidate.exists():
            return str(candidate)
    return None


def main() -> int:
    if not importlib.util.find_spec("grpc_tools"):
        print("grpc_tools is not installed; go stub generation is blocked fail-closed.", file=sys.stderr)
        return 1

    protoc_gen_go = _resolve_go_plugin("protoc-gen-go")
    protoc_gen_go_grpc = _resolve_go_plugin("protoc-gen-go-grpc")
    if not protoc_gen_go or not protoc_gen_go_grpc:
        print("protoc-gen-go or protoc-gen-go-grpc is missing; go stub generation is blocked fail-closed.", file=sys.stderr)
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
        f"--plugin=protoc-gen-go={protoc_gen_go}",
        f"--plugin=protoc-gen-go-grpc={protoc_gen_go_grpc}",
        f"--go_out=paths=source_relative:{proto_root}",
        f"--go-grpc_out=paths=source_relative:{proto_root}",
        str(proto),
    ]
    return subprocess.call(command)


if __name__ == "__main__":
    raise SystemExit(main())
