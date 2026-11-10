{
  projectRoot,
  src ? null,
  javaPackage ? import ./java/package.nix,
  compilerMismatch ? false,
}:
let
  f = builtins.getFlake projectRoot;
  pkgs = import f.inputs.nixpkgs {
    system = builtins.currentSystem;
    overlays = [ f.overlays.default ];
  };
  build =
    if compilerMismatch then
      pkgs.buf-purifier.buildBufProject.override { protobuf = pkgs.protobuf_35; }
    else
      pkgs.buf-purifier.buildBufProject;
in
build {
  src = if src == null then ../examples/java-projection else /. + src;
  inherit javaPackage;
}
