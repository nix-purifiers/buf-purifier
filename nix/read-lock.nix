{ lib }:
{
  src,
  lockFile ? src + "/buf-purifier.lock.json",
}:
let
  raw = if builtins.pathExists lockFile then builtins.fromJSON (builtins.readFile lockFile) else { };
  data = if builtins.isAttrs raw then raw else { };
  entries = data.entries or [ ];
  relative =
    s:
    builtins.isString s
    && s != ""
    && !(lib.hasPrefix "/" s)
    && !(builtins.elem ".." (lib.splitString "/" s));
  shape =
    (data.version or null) == 1
    && (data.purifier or null) == "buf"
    && builtins.isString (data.sdk or null)
    && (data.native.version or null) == "v2"
    && builtins.isList (data.native.deps or null)
    && builtins.isList entries
    && builtins.all (
      e:
      builtins.isAttrs e
      && builtins.isAttrs (e.buf or null)
      && builtins.isString (e.buf.name or null)
      && builtins.match "[a-z0-9.-]+/[a-z0-9_-]+/[a-z0-9_-]+" e.buf.name != null
      && builtins.isString (e.buf.commit or null)
      && builtins.match "[a-f0-9]{32}" e.buf.commit != null
      && builtins.isString (e.buf.digest or null)
      && builtins.match "b5:[a-f0-9]{128}" e.buf.digest != null
      && (e.path or null) == "b5/${e.buf.name}/${e.buf.commit}"
      && (e.url or null) == "bsr:${e.buf.name}:${e.buf.commit}"
      && (e.mirrors or null) == [ ]
      && builtins.isString (e.hash or null)
      && builtins.match "sha256-[A-Za-z0-9+/]{43}=" e.hash != null
    ) entries
    && builtins.isAttrs (data.inputs or null)
    && builtins.isList (data.extraInputs or null)
    && builtins.all relative data.extraInputs;
  valid =
    shape
    && map (e: e.buf) entries == data.native.deps
    && builtins.length entries == builtins.length (lib.unique (map (e: e.buf.name) entries))
    &&
      builtins.attrNames data.inputs == builtins.sort builtins.lessThan (
        lib.unique (
          [ "buf.yaml" ]
          ++ lib.optional (builtins.pathExists (src + "/buf.lock")) "buf.lock"
          ++ lib.optional (builtins.pathExists (src + "/buf.gen.yaml")) "buf.gen.yaml"
          ++ data.extraInputs
        )
      )
    && builtins.hasAttr "buf.yaml" data.inputs
    && builtins.all (
      name:
      relative name
      && builtins.pathExists (src + "/${name}")
      && builtins.hashFile "sha256" (src + "/${name}") == (data.inputs.${name}.sha256 or null)
    ) (builtins.attrNames data.inputs);
in
{
  purifier = "buf";
  inherit data entries;
  outputs = {
    packages = [
      "default"
      "environment"
      "project"
    ];
    tests = [ "default" ];
    release = [ "default" ];
  };
  problems = lib.optional (!valid) "Invalid or stale Buf lock; update the lock";
}
