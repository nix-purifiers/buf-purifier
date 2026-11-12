{
  lib,
  runCommand,
  writeText,
  python,
  purifier,
  nativeFetch,
  fetchgit,
  sdkVersion,
  tool,
  protobuf,
  python3Packages,
  gnutar,
  gzip,
  callPackage,
}@scope:
{
  src,
  lockFile ? src + "/buf-purifier.lock.json",
  fetchers ? { },
  schemaEntrypoints ? [ ],
  pythonPackage ? null,
  javaPackage ? null,
  goPackage ? null,
  goProjector ? null,
  goDependencies ? [ ],

  cppPackage ? null,
  rustPackage ? null,
  rustProjector ? null,
  nativeBuildInputs ? [ ],
  doCheck ? false,
  checkCommand ? "",
}:
let
  lock = purifier.checkLock (
    import ../../lib-overlays/default/read-lock.nix { inherit lib; } { inherit src lockFile; }
  );
  prepared = import ./environment.nix scope { inherit lock src fetchers; };
  source = lib.cleanSourceWith {
    inherit src;
    filter =
      path: type:
      !(builtins.elem (baseNameOf path) [
        ".git"
        ".buf-purifier"
        "gen"
        "result"
        "__pycache__"
      ]);
  };
  builtProject =
    runCommand "buf-project"
      {
        nativeBuildInputs = [
          tool
          protobuf
        ]
        ++ nativeBuildInputs;
      }
      ''
        cp -pr ${source} source
        chmod -R u+w source
        cd source
        export BUF_PURIFIER_FROZEN=1 BUF_CACHE_DIR="$TMPDIR/cache"
        mkdir -p "$BUF_CACHE_DIR/v3/modules"
        ${lib.concatMapStrings (e: ''
          mkdir -p "$BUF_CACHE_DIR/v3/modules/$(dirname ${lib.escapeShellArg e.path})"
          ln -s ${prepared.tree}/${e.path} "$BUF_CACHE_DIR/v3/modules/${e.path}"
        '') lock.entries}
        test -e ${prepared.output}/manifest.json
        mkdir -p "$out"
        ${lib.optionalString (javaPackage != null) ''
          test "$(command -v protoc)" = ${protobuf}/bin/protoc
          test "$(command -v buf)" = ${tool}/bin/buf
          protoc --version > "$out/native-protoc-version.txt"
          buf --version > "$out/native-buf-version.txt"
        ''}
        buf build --output "$out/image.binpb"
        buf export . --all --output "$out/schemas"
        buf lint
        if [ -f buf.gen.yaml ]; then
          buf generate --output "$out"
        fi
        ${lib.optionalString doCheck checkCommand}
        mkdir -p "$out/source"
        cp -pr ${source}/. "$out/source/"
      '';
  resourceProjections = purifier.resourceProjections {
    producer = builtProject;
    roots."." = "schemas";
    schema =
      if schemaEntrypoints == [ ] then
        null
      else
        {
          format = "protobuf";
          entrypoints = schemaEntrypoints;
        };
    inherit runCommand;
    python3 = python;
  };
  generatedPython = runCommand "buf-generated-python-sources" { nativeBuildInputs = [ protobuf ]; } ''
    mkdir -p "$out"
    cd ${resourceProjections.resources.directory}
    find . -name '*.proto' -print0 | sort -z | xargs -0 protoc -I . --python_out="$out"
    cat > "$out/pyproject.toml" <<'TOML'
    [build-system]
    requires = ["setuptools"]
    build-backend = "setuptools.build_meta"
    [project]
    name = ${builtins.toJSON pythonPackage.name}
    version = ${builtins.toJSON pythonPackage.version}
    dependencies = ["protobuf==${python3Packages.protobuf.version}"]
    [tool.setuptools.packages.find]
    where = ["."]
    namespaces = true
    TOML
  '';
  pythonBindings = python3Packages.buildPythonPackage {
    pname = pythonPackage.name;
    version = pythonPackage.version;
    src = generatedPython;
    pyproject = true;
    build-system = [ python3Packages.setuptools ];
    dependencies = [ python3Packages.protobuf ];
    doCheck = false;
  };
  projections =
    resourceProjections
    // lib.optionalAttrs (pythonPackage != null) (
      purifier.pythonProjections {
        producer = pythonBindings;
        repository = pythonBindings.dist;
        runtimeRepository = python3Packages.protobuf.dist;
        inherit runCommand;
        python3 = python;
      }
    )
    // lib.optionalAttrs (javaPackage != null) java.projections
    // lib.optionalAttrs (goPackage != null) { go = golang.repository; }
    // lib.optionalAttrs (cppPackage != null) { cpp = cpp.package; }
    // lib.optionalAttrs (rustPackage != null) { cargo = rust.repository; };
  golang = callPackage ../buf-go-products { } {
    producer = builtProject;
    inherit goPackage goProjector goDependencies;
  };
  rust = callPackage ../buf-rust-products { } {
    producer = builtProject;
    inherit rustPackage rustProjector;
  };
  cpp = callPackage ../buf-cpp-products { } {
    producer = builtProject;
    inherit cppPackage;
  };
  java = callPackage ./java-projections.nix { } {
    producer = builtProject;
    inherit javaPackage;
  };
  project = builtProject // {
    inherit projections;
  };
  release =
    runCommand "buf-native-release"
      {
        nativeBuildInputs = [
          gnutar
          gzip
        ];
      }
      ''
        mkdir -p "$out" source/project
        cp -pr ${source}/. source/project/
        chmod -R u+rwX source
        tar --sort=name --mtime=@1 --owner=0 --group=0 --numeric-owner -czf "$out/buf-source.tar.gz" -C source project
      '';
in
assert javaPackage == null || java.validated;
assert goPackage == null || golang.validated;

assert cppPackage == null || cpp.validated;
assert rustPackage == null || rust.validated;
assert
  pythonPackage == null
  || (
    builtins.isAttrs pythonPackage
    &&
      builtins.attrNames pythonPackage == [
        "name"
        "version"
      ]
    && builtins.isString pythonPackage.name
    && pythonPackage.name != ""
    && builtins.isString pythonPackage.version
    && pythonPackage.version != ""
  )
  || throw "buf-purifier: pythonPackage requires an explicit distribution name and version";
{
  packages = {
    default = project;
    inherit project;
    environment = prepared.output;
  }
  // lib.optionalAttrs (pythonPackage != null) {
    python-bindings = pythonBindings // {
      projections.python = projections.python;
    };
  }
  // lib.optionalAttrs (javaPackage != null) {
    java-bindings = java.bindings // {
      projections = java.projections;
    };
    java-runtime = java.runtimePackage;
  }
  // lib.optionalAttrs (goPackage != null) {
    go-bindings = golang.generated // {
      projections.go = golang.repository;
    };
    go-runtime = golang.runtime // {
      projections.go = golang.runtime;
    };
  }
  // lib.optionalAttrs (cppPackage != null) { cpp-bindings = cpp.package; }
  // lib.optionalAttrs (rustPackage != null) {
    rust-bindings = rust.generated // {
      projections.cargo = rust.repository;
    };
  };
  tests = project;
  inherit release projections;
  fetches = lock.entries;
}
