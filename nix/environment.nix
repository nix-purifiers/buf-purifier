{
  lib,
  runCommand,
  fetchgit,
  writeText,
  python,
  purifier,
  nativeFetch,
  sdkVersion,
  ...
}:
{
  lock,
  src,
  fetchers ? { },
}:
let
  checked = purifier.checkLock lock;
  selectionSource = lib.fileset.toSource {
    root = src;
    fileset = lib.fileset.unions (
      map (name: src + "/${name}") (builtins.attrNames checked.data.inputs)
    );
  };
  validated = runCommand "buf-native-selection-validated" { } ''
    ${python}/bin/python3 ${../buf_purifier/validation.py} ${writeText "buf-lock.json" (builtins.toJSON checked.data)} ${selectionSource}
    touch "$out"
  '';
  nativeURLFetch =
    args:
    let
      matches = builtins.filter (e: e.hash == args.hash && builtins.elem e.url args.urls) checked.entries;
    in
    assert lib.assertMsg (builtins.length matches == 1) "Buf module fetch is ambiguous";
    nativeFetch (builtins.head matches);
  tree = purifier.tree (
    {
      name = "buf-locked-modules";
      entries = checked.entries;
      fetchurl = nativeURLFetch;
      inherit runCommand fetchgit writeText;
      python3 = python;
    }
    // fetchers
  );
  manifest = writeText "buf-environment.json" (
    builtins.toJSON {
      inherit tree;
      sdk = sdkVersion;
    }
  );
  output = runCommand "buf-locked-environment" { } ''
    test -e ${validated}
    mkdir -p "$out"
    ln -s ${manifest} "$out/manifest.json"
  '';
in
assert lib.assertMsg (checked.data.sdk == sdkVersion) "Buf SDK changed; update the lock";
{
  inherit tree output;
}
