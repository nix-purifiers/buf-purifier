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
}@scope:
{
  src,
  lockFile ? src + "/buf-purifier.lock.json",
  fetchers ? { },
  schemaEntrypoints ? [ ],
  pythonPackage ? null,
  nativeBuildInputs ? [ ],
  doCheck ? false,
  checkCommand ? "",
}:
let
  lock = purifier.checkLock (import ./read-lock.nix { inherit lib; } { inherit src lockFile; });
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
    );
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
  };
  tests = project;
  inherit release projections;
  fetches = lock.entries;
}
