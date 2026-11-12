# SPDX-License-Identifier: MIT
{ pkgs, projector }:
let
  make =
    src:
    let
      args = { inherit src; };
      raw = pkgs.buf-purifier.buildBufProject args;
      built = pkgs.buf-purifier.buildBufProject (
        args
        // {
          rustPackage = {
            name = "proof_schemas";
            entrypoints = [
              "purifier/proof/v1/common.proto"
              "purifier/proof/v1/answer.proto"
            ];
          };
          rustProjector = projector;
        }
      );
    in
    assert raw.packages.project.drvPath == built.packages.project.drvPath;
    built;
  reject =
    options:
    !(builtins.tryEval
      (pkgs.buf-purifier.buildBufProject {
        src = ../examples/java-projection;
        rustPackage = options;
        rustProjector = projector;
      }).projections.cargo.drvPath
    ).success;
  a = make ../examples/java-projection;
  b = make ../examples/java-projection-v2;
  cases =
    map
      (p: {
        generated = toString p.packages.rust-bindings;
        repository = toString p.projections.cargo;
        producer = toString p.packages.rust-bindings.schemaProducer;
        rustSpec = p.packages.rust-bindings.rustSpec;
      })
      [
        a
        b
      ];
in
assert reject {
  name = "bad/name";
  entrypoints = [ "main.proto" ];
};
assert reject {
  name = "valid";
  entrypoints = [ "../outside.proto" ];
};
assert reject {
  name = "valid";
  entrypoints = [
    "main.proto"
    "main.proto"
  ];
};
pkgs.runCommand "buf-rust-native-crate-consumers"
  {
    nativeBuildInputs = [
      pkgs.python3
      pkgs.cargo
      pkgs.rustc
      pkgs.stdenv.cc
      pkgs.protobuf
    ];
    spec = builtins.toJSON {
      inherit cases;
      generator = ../pkgs/buf-rust-products/generate.py;
    };
    passAsFile = [ "spec" ];
  }
  ''
    export HOME="$TMPDIR/home" CARGO_HOME="$TMPDIR/cargo-home"
    mkdir -p "$HOME" "$CARGO_HOME"
    python ${./rust}/consume.py "$specPath" "$out"
  ''
