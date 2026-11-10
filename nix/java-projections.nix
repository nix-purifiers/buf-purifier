{
  lib,
  runCommand,
  writeText,
  python,
  protobuf,
  jdk25,
  purifier,
  tool,
}:
{ producer, javaPackage }:
let
  coordinate = s: builtins.isString s && builtins.match "[A-Za-z0-9_][A-Za-z0-9_.-]*" s != null;
  valid =
    builtins.isAttrs javaPackage
    &&
      builtins.attrNames javaPackage == [
        "artifactId"
        "groupId"
        "sourceDirectory"
        "version"
      ]
    && builtins.all coordinate [
      javaPackage.groupId
      javaPackage.artifactId
      javaPackage.version
    ]
    && builtins.isString javaPackage.sourceDirectory
    && lib.hasPrefix "gen/" javaPackage.sourceDirectory
    && builtins.all (s: s != "" && s != "." && s != "..") (
      lib.splitString "/" javaPackage.sourceDirectory
    );
  runtime =
    runCommand "buf-protobuf-java-runtime"
      {
        nativeBuildInputs = [
          python
          protobuf
          jdk25
        ];
      }
      ''
        ${python}/bin/python3 ${./java-output.py} runtime "$out" ${protobuf.src} ${protobuf}/bin/protoc ${jdk25}/bin/javac ${jdk25}/bin/jar
      '';
  runtimeProjections = purifier.jvmProjections {
    producer = runtime;
    repository = "${runtime}/repository";
    formats = [
      "maven"
      "ivy"
    ];
    inherit runCommand;
    python3 = python;
    name = "buf-protobuf-java-runtime-projection";
  };
  runtimePackage = runtime // {
    projections = runtimeProjections;
  };
  spec = writeText "buf-java-package.json" (builtins.toJSON javaPackage);
  bindings =
    runCommand "buf-generated-java-bindings"
      {
        nativeBuildInputs = [
          python
          jdk25
        ];
      }
      ''
        ${python}/bin/python3 ${./java-output.py} bindings "$out" ${producer} ${runtime} ${spec} ${jdk25}/bin/javac ${jdk25}/bin/jar
      '';
  projections = purifier.jvmProjections {
    producer = bindings;
    repository = "${bindings}/repository";
    dependencies = [ runtimePackage ];
    formats = [
      "maven"
      "ivy"
    ];
    inherit runCommand;
    python3 = python;
    name = "buf-generated-java-projection";
  };
in
assert
  valid
  || throw "buf-purifier: javaPackage requires Maven coordinates and a native Java generator directory under gen/";
{
  validated = true;
  inherit bindings runtimePackage projections;
}
