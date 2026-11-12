# SPDX-License-Identifier: MIT
{ pkgs, projector }:
let
  build =
    src:
    pkgs.buf-purifier.buildBufProject {
      inherit src;
      goPackage = {
        modulePath = "example.org/proof";
        entrypoints = [
          "purifier/proof/v1/common.proto"
          "purifier/proof/v1/answer.proto"
        ];
      };
      goProjector = projector;
    };
  a = build ../examples/go-projection;
  b = build ../examples/go-projection-v2;
  reject =
    config:
    !(builtins.tryEval
      (pkgs.buf-purifier.buildBufProject {
        src = ../examples/go-projection;
        goPackage = config;
        goProjector = projector;
      }).projections.go.drvPath
    ).success;
  cases =
    map
      (pair: {
        repository = toString pair.project.projections.go;
        runtimeSource = toString pkgs.protoc-gen-go.src;
        generated = "${pair.project.packages.go-bindings}/module";
        inherit (pair) field;
      })
      [
        {
          project = a;
          field = 1;
        }
        {
          project = b;
          field = 2;
        }
      ];
in
assert reject {
  modulePath = "example.org/proof";
  entrypoints = [ "../answer.proto" ];
};
assert reject {
  modulePath = "example.org/proof";
  entrypoints = [ ];
};
assert reject {
  modulePath = "example.org/proof";
  entrypoints = [ "purifier/proof/v1/answer.proto" ];
  flags = [ "--other" ];
};
assert
  a.packages.project.drvPath
  == (pkgs.buf-purifier.buildBufProject { src = ../examples/go-projection; })
  .packages.project.drvPath;
pkgs.runCommand "buf-go-native-module-consumers"
  {
    nativeBuildInputs = [
      pkgs.go
      pkgs.python3
    ];
    spec = builtins.toJSON cases;
    passAsFile = [ "spec" ];
  }
  ''
    python3 ${./go}/consume.py "$specPath" "$out"
    python3 ${./go}/negative.py ${../pkgs/buf-go-products/generate.py} ${a.packages.project} ${pkgs.protobuf}/bin/protoc ${pkgs.protobuf.dev}/include ${pkgs.protoc-gen-go}/bin/protoc-gen-go ${pkgs.go}/bin/go ${pkgs.protoc-gen-go.src} "$out/negative.json"
    test -s "$out/proof.json"
    test -s "$out/negative.json"
  ''
