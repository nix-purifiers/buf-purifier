# SPDX-License-Identifier: MIT
{ pkgs, projector }:
let
  src = ../examples/go-external;
  foreign = pkgs.buf-purifier.buildBufProject {
    inherit src;
    goPackage = {
      modulePath = "example.org/foreign";
      entrypoints = [ "foreign/proof/v1/foreign.proto" ];
    };
    goProjector = projector;
  };
  owned = pkgs.buf-purifier.buildBufProject {
    inherit src;
    goPackage = {
      modulePath = "example.org/proof";
      entrypoints = [
        "purifier/proof/v1/common.proto"
        "purifier/proof/v1/answer.proto"
      ];
    };
    goProjector = projector;
    goDependencies = [ foreign.packages.go-bindings ];
  };
in
pkgs.runCommand "buf-go-external-module-consumer"
  {
    nativeBuildInputs = [
      pkgs.go
      pkgs.python3
    ];
    spec = builtins.toJSON {
      repository = toString owned.projections.go;
      foreignRepository = toString foreign.projections.go;
      foreignSource = "${foreign.packages.go-bindings}/module";
    };
    passAsFile = [ "spec" ];
  }
  ''
    python3 ${./go}/external.py "$specPath" "$out"
  ''
