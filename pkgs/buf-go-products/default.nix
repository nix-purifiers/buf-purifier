# SPDX-License-Identifier: MIT
{
  lib,
  runCommand,
  writeText,
  python,
  go,
  protobuf,
  protoc-gen-go,
  purifier,
}:
{
  producer,
  goPackage,
  goProjector,
  goDependencies ? [ ],
}:
let
  relative =
    s:
    builtins.isString s
    && s != ""
    && !(lib.hasPrefix "/" s)
    && builtins.all (p: p != "" && p != "." && p != "..") (lib.splitString "/" s)
    && !(lib.hasInfix "\\" s);
  valid =
    builtins.isAttrs goPackage
    &&
      builtins.attrNames goPackage == [
        "entrypoints"
        "modulePath"
      ]
    && builtins.isString goPackage.modulePath
    && builtins.match "[A-Za-z0-9][A-Za-z0-9./_+-]*" goPackage.modulePath != null
    && builtins.isList goPackage.entrypoints
    && goPackage.entrypoints != [ ]
    && lib.unique goPackage.entrypoints == goPackage.entrypoints
    && builtins.all (s: relative s && lib.hasSuffix ".proto" s) goPackage.entrypoints;
  inputs = purifier.projectInputs {
    dependencies = goDependencies;
    formats = [ "go" ];
  };
  sdkIdentity = runCommand "protobuf-go-runtime-identity" {
    source = protoc-gen-go.src;
    projector = goProjector;
  } "touch $out";
  runtimeRequest = writeText "protobuf-go-runtime-projection.json" (
    builtins.toJSON {
      identity = (purifier.inputIdentity sdkIdentity).hash;
      modules = [ (toString protoc-gen-go.src) ];
      repositories = [ ];
    }
  );
  runtime =
    runCommand "protobuf-go-runtime-module-proxy"
      {
        nativeBuildInputs = [ goProjector ];
        passthru.catalog = "${runtime}/.catalog";
      }
      ''
        go-purifier project-modules ${runtimeRequest} "$out"
      '';
  spec = writeText "buf-go-products.json" (builtins.toJSON goPackage);
  generated =
    runCommand "buf-generated-go-module"
      {
        nativeBuildInputs = [
          python
          go
          protobuf
          protoc-gen-go
        ];
      }
      ''
        export HOME="$TMPDIR/home" GOCACHE="$TMPDIR/cache" GOPATH="$TMPDIR/go" GOTOOLCHAIN=local GOWORK=off GOPROXY=off GOSUMDB=off
        mkdir -p "$HOME"
        python3 ${./generate.py} ${producer} "$out" ${spec} ${protobuf}/bin/protoc ${protobuf.dev}/include ${protoc-gen-go}/bin/protoc-gen-go ${go}/bin/go ${protoc-gen-go.src}
      '';
  identity = runCommand "buf-go-module-identity" {
    inherit generated runtime;
    projector = goProjector;
    repositories = map (i: i.repository) inputs;
  } "touch $out";
  request = writeText "buf-go-module-projection.json" (
    builtins.toJSON {
      identity = (purifier.inputIdentity identity).hash;
      modules = [ "${generated}/module" ];
      repositories = [ (toString runtime) ] ++ map (i: toString i.repository) inputs;
    }
  );
  repository =
    runCommand "buf-go-module-repository"
      {
        nativeBuildInputs = [ goProjector ];
        passthru.catalog = "${repository}/.catalog";
      }
      ''
        go-purifier project-modules ${request} "$out"
      '';
in
assert lib.assertMsg valid
  "buf-purifier: goPackage needs explicit modulePath and owned .proto entrypoints";
assert lib.assertMsg (
  goProjector != null && lib.isDerivation goProjector
) "buf-purifier: goPackage requires an explicit native Go purifier CLI as goProjector";
{
  inherit generated runtime repository;
  validated = true;
}
