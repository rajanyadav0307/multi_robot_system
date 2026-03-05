import re
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROTO_FILE = PROJECT_ROOT / "proto" / "fleetops.proto"
OUTPUT_DIR = PROJECT_ROOT / "grpc_api" / "generated"
GRPC_PY = OUTPUT_DIR / "fleetops_pb2_grpc.py"


def _patch_relative_imports():
    if not GRPC_PY.exists():
        return
    text = GRPC_PY.read_text(encoding="utf-8")
    updated = re.sub(
        r"^import fleetops_pb2 as fleetops__pb2$",
        "from . import fleetops_pb2 as fleetops__pb2",
        text,
        flags=re.MULTILINE,
    )
    GRPC_PY.write_text(updated, encoding="utf-8")


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        "-m",
        "grpc_tools.protoc",
        f"-I{PROTO_FILE.parent}",
        f"--python_out={OUTPUT_DIR}",
        f"--grpc_python_out={OUTPUT_DIR}",
        str(PROTO_FILE),
    ]
    proc = subprocess.run(cmd, cwd=PROJECT_ROOT)
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)

    _patch_relative_imports()
    print("Generated gRPC stubs in grpc_api/generated/")


if __name__ == "__main__":
    main()
