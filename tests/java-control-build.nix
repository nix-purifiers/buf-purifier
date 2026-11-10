{
  projectRoot,
  src,
  specFile,
  compilerMismatch ? false,
}:
(import ./java-build.nix {
  inherit projectRoot src compilerMismatch;
  javaPackage = builtins.fromJSON (builtins.readFile specFile);
}).packages.java-bindings
