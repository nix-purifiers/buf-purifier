# SPDX-License-Identifier: MIT
{
  lib,
  runCommand,
  writeText,
  python3,
  cargo,
  rustc,
  protobuf,
  protoc-gen-prost,
  protoc-gen-prost-crate,
}:
{
  producer,
  rustPackage,
  rustProjector,
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
    builtins.isAttrs rustPackage
    &&
      builtins.attrNames rustPackage == [
        "entrypoints"
        "name"
      ]
    && builtins.isString rustPackage.name
    && builtins.match "[A-Za-z][A-Za-z0-9_-]*" rustPackage.name != null
    && builtins.isList rustPackage.entrypoints
    && rustPackage.entrypoints != [ ]
    && lib.unique rustPackage.entrypoints == rustPackage.entrypoints
    && builtins.all (p: relative p && lib.hasSuffix ".proto" p) rustPackage.entrypoints;
  vendor =
    runCommand "protobuf-prost-sdk-vendor"
      {
        nativeBuildInputs = [
          cargo
          rustc
        ];
      }
      ''
        export HOME="$TMPDIR/home" CARGO_HOME="$TMPDIR/cargo-home"
        mkdir -p "$HOME" "$CARGO_HOME"
        cp -r ${protoc-gen-prost.src} sdk
        chmod -R u+w sdk
        mkdir -p sdk/.cargo
        substitute ${protoc-gen-prost.cargoDeps}/.cargo/config.toml sdk/.cargo/config.toml \
          --subst-var-by vendor ${protoc-gen-prost.cargoDeps}
        cd sdk
        cargo vendor --offline --locked --respect-source-config --versioned-dirs "$out" > "$TMPDIR/config.toml"
        mkdir -p "$out/.cargo"
        cp "$TMPDIR/config.toml" "$out/.cargo/config.toml"
      '';
  spec = writeText "buf-rust-products.json" (
    builtins.toJSON {
      inherit (rustPackage) name entrypoints;
      sdkSource = protoc-gen-prost.src;
      inherit vendor;
      protobuf = toString protobuf;
      include = "${protobuf.dev}/include";
      prost = toString protoc-gen-prost;
      crateGenerator = toString protoc-gen-prost-crate;
    }
  );
  generated =
    runCommand "buf-generated-rust-crate"
      {
        nativeBuildInputs = [
          python3
          cargo
          rustc
          protobuf
          protoc-gen-prost
          protoc-gen-prost-crate
        ];
        passthru = {
          schemaProducer = producer;
          rustSpec = spec;
        };
      }
      ''
        export HOME="$TMPDIR/home" CARGO_HOME="$TMPDIR/cargo-home"
        mkdir -p "$HOME" "$CARGO_HOME"
        python ${./generate.py} ${producer} "$out" ${spec}
      '';
  repository = rustProjector {
    src = "${generated}/crate";
    workspace = ".";
    inherit vendor;
    cargoLock = "${generated}/crate/Cargo.lock";
    entries = [ ];
    dependencies = [ ];
    name = "buf-rust-crate-repository";
  };
in
assert
  valid
  || throw "buf-purifier: rustPackage requires a Cargo name and explicit owned .proto entrypoints";
assert
  builtins.isFunction rustProjector
  || throw "buf-purifier: rustPackage requires an explicit native Cargo projector function";
{
  inherit generated repository vendor;
  validated = true;
}
