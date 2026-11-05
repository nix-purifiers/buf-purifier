# SPDX-License-Identifier: MIT
{ pkgs, projection }:
let
  python = pkgs.python3.withPackages (p: [ p.protobuf ]);
in
pkgs.runCommand "ordinary-protobuf-consumer"
  {
    nativeBuildInputs = [
      python
      pkgs.protobuf
    ];
  }
  ''
    mkdir "$TMPDIR/generated"
    cd ${projection.directory}
    find . -name '*.proto' -print0 | sort -z | xargs -0 protoc -I . --python_out="$TMPDIR/generated"
    PYTHONPATH="$TMPDIR/generated" python - <<'PY'
    from proof.v1.proof_pb2 import Proof
    from envoy.type.v3.percent_pb2 import FractionalPercent
    message = Proof(answer=42, fraction=FractionalPercent(numerator=42))
    restored = Proof.FromString(message.SerializeToString())
    assert restored.answer == 42 and restored.fraction.numerator == 42
    PY
    touch $out
  ''
