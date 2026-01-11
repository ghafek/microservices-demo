#!/bin/bash -eu

cd "$(dirname "$0")"

PYTHON_BIN="python3"
if [[ -x "../../../.venv/bin/python" ]]; then
  PYTHON_BIN="../../../.venv/bin/python"
fi

"$PYTHON_BIN" -m grpc_tools.protoc \
  -I../../protos \
  --python_out=. \
  --grpc_python_out=. \
  ../../protos/demo.proto
