{
  pkgs,
  nixpkgsSrc,
  purifierSrc,
}:
pkgs.lib.makeScope pkgs.newScope (scope: {
  python = pkgs.python3.withPackages (p: [ p.pyyaml ]);
  tool = pkgs.callPackage ./toolchain.nix { };
  purifier = import (purifierSrc + "/nix/lib") { inherit (pkgs) lib; };
  sdkVersion = builtins.hashString "sha256" (
    builtins.toJSON {
      nixpkgs = toString nixpkgsSrc;
      source = toString pkgs.buf.src;
      protobuf = toString pkgs.protobuf.src;
      guard = builtins.hashFile "sha256" ../native/patch-native.py;
    }
  );
  nativePath = pkgs.lib.makeBinPath [
    scope.tool
    pkgs.protobuf
  ];
  nativeFetch = scope.callPackage ./fetch.nix { };
  cli = scope.callPackage ./cli.nix { inherit nixpkgsSrc purifierSrc; };
  buildBufProject = scope.callPackage ./build-project.nix { };
})
