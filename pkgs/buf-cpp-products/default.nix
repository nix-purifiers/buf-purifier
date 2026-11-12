# SPDX-License-Identifier: MIT
{
  lib,
  runCommand,
  python,
  protobuf,
  stdenv,
  pkg-config,
  cmake,
}:
{ producer, cppPackage }:
let
  label = s: builtins.isString s && builtins.match "[A-Za-z0-9_][A-Za-z0-9_.+-]*" s != null;
  valid =
    builtins.isAttrs cppPackage
    &&
      builtins.attrNames cppPackage == [
        "name"
        "version"
      ]
    && label cppPackage.name
    && builtins.isString cppPackage.version
    && builtins.match "[A-Za-z0-9][A-Za-z0-9_.+-]*" cppPackage.version != null;
  package =
    runCommand "buf-${cppPackage.name}-cpp-${cppPackage.version}"
      {
        nativeBuildInputs = [
          python
          stdenv.cc
          pkg-config
          cmake
        ];
        buildInputs = [ protobuf ];
        passthru = {
          includeDirectory = "${package}/include";
          pkgConfigDirectory = "${package}/lib/pkgconfig";
          cmakePrefixPath = "${package}";
          abi = "c++";
        };
      }
      ''
        mkdir -p "$out/nix-support"
        echo ${protobuf.dev} > "$out/nix-support/propagated-build-inputs"
        python3 ${./build.py} ${producer} "$out" ${protobuf}/bin/protoc ${protobuf.dev}/include ${lib.escapeShellArg cppPackage.name} ${lib.escapeShellArg cppPackage.version} ${stdenv.cc}/bin/c++ ${stdenv.hostPlatform.extensions.sharedLibrary}
      '';
in
assert lib.assertMsg valid
  "buf-purifier: cppPackage requires a library name and version, with no additional options";
{
  inherit package;
  validated = true;
}
