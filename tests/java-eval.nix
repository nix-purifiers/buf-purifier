{ pkgs }:
let
  build = pkgs.buf-purifier.buildBufProject;
  src = ../examples/java-projection;
  package = import ./java/package.nix;
  invalid = [
    (package // { sourceDirectory = "source/private"; })
    (package // { sourceDirectory = "gen/../outside"; })
    (package // { sourceDirectory = "gen//java"; })
    (package // { groupId = ""; })
    (package // { artifactId = "wrong/artifact"; })
    (package // { version = "invalid version"; })
    (package // { extra = true; })
  ];
  rejected =
    javaPackage:
    !(builtins.tryEval (build { inherit src javaPackage; }).packages.project.drvPath).success;
  defaults = build { inherit src; };
in
assert builtins.all rejected invalid;
assert !(defaults.packages ? java-bindings) && !(defaults.packages ? java-runtime);
assert !(defaults.projections ? maven) && !(defaults.projections ? ivy);
true
