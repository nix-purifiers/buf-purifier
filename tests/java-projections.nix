{
  pkgs,
  src1 ? ../examples/java-projection,
  src2 ? ../examples/java-projection-v2,
}:
let
  build =
    src: version:
    pkgs.buf-purifier.buildBufProject {
      inherit src;
      javaPackage = (import ./java/package.nix) // {
        inherit version;
      };
    };
  first = build src1 "1.0.0";
  second = build src2 "1.0.1";
  mismatched =
    pkgs.buf-purifier.callPackage ../nix/java-projections.nix { protobuf = pkgs.protobuf_35; }
      {
        producer = first.packages.project;
        javaPackage = import ./java/package.nix;
      };
  specification =
    built:
    pkgs.runCommand "buf-java-consumer-spec"
      {
        nativeBuildInputs = [ pkgs.python3 ];
        passAsFile = [ "seed" ];
        seed = builtins.toJSON {
          producer = toString built.packages.java-bindings;
          runtime = toString built.packages.java-runtime;
          maven = toString built.projections.maven;
          ivy = toString built.projections.ivy;
          catalog = built.projections.maven.catalog;
        };
      }
      ''
        mkdir -p "$out"
        python3 ${./java/prepare-spec.py} "$seedPath" "$out/spec.json"
      '';
in
assert import ./java-eval.nix { inherit pkgs; };
pkgs.runCommand "buf-java-projection-consumers"
  {
    nativeBuildInputs = [
      pkgs.python3
      pkgs.jdk25
      pkgs.gradle_8
    ];
  }
  ''
    set -euo pipefail
    export HOME="$TMPDIR/home"
    mkdir -p "$HOME" "$out"
    cp ${./java/Consumer.java} Consumer.java
    python3 ${./java/consumer.py} ${specification first} ${specification second} "$out" Consumer.java ${mismatched.runtimePackage}
  ''
