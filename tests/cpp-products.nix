# SPDX-License-Identifier: MIT
{ pkgs }:
let
  built = pkgs.buf-purifier.buildBufProject {
    src = ../examples/minimal;
    cppPackage = {
      name = "proof";
      version = "0.1.0";
    };
  };
  package = built.packages.cpp-bindings;
  reject =
    options:
    !(builtins.tryEval
      (pkgs.buf-purifier.buildBufProject {
        src = ../examples/minimal;
        cppPackage = options;
      }).packages.cpp-bindings.drvPath
    ).success;
  pair =
    src:
    (pkgs.buf-purifier.buildBufProject {
      inherit src;
      cppPackage = {
        name = "proof";
        version = "0.1.0";
      };
    }).packages.cpp-bindings;
  first = pair ../examples/java-projection;
  second = pair ../examples/java-projection-v2;
  consumer =
    package: field:
    pkgs.runCommand "buf-cpp-schema-${toString field}-consumer"
      {
        nativeBuildInputs = [
          pkgs.stdenv.cc
          pkgs.pkg-config
        ];
        buildInputs = [ package ];
      }
      ''
        mkdir "$out"
        cp ${./cpp-schema-consumer.cc} schema.cc
        c++ -fPIC -pie schema.cc $(pkg-config --cflags --libs proof) -ldl -o schema
        ./schema ${package}/lib/libproof${pkgs.stdenv.hostPlatform.extensions.sharedLibrary} ${pkgs.lib.getLib pkgs.protobuf}/lib/libprotobuf${pkgs.stdenv.hostPlatform.extensions.sharedLibrary} ${toString field} > "$out/proof.txt"
      '';
  firstConsumer = consumer first 1;
  secondConsumer = consumer second 2;
in
assert
  built.packages.project.drvPath == (pkgs.buf-purifier.buildBufProject { src = ../examples/minimal; })
  .packages.project.drvPath;
assert reject {
  name = "../proof";
  version = "0.1.0";
};
assert reject {
  name = "proof";
  version = "0.1.0";
  sourceDirectory = "arbitrary";
};
pkgs.runCommand "buf-cpp-package-consumers"
  {
    nativeBuildInputs = [
      pkgs.stdenv.cc
      pkgs.pkg-config
      pkgs.cmake
      pkgs.python3
    ];
    buildInputs = [ package ];
  }
  ''
        mkdir "$out"
        cp ${./cpp-consumer.cc} consumer.cc
        c++ -fPIC -pie consumer.cc $(pkg-config --cflags --libs proof) -ldl -o consumer
        ./consumer ${package}/lib/libproof${pkgs.stdenv.hostPlatform.extensions.sharedLibrary} > "$out/pkgconfig.txt"
        cp ${./cpp/CMakeLists.txt} CMakeLists.txt
        cmake -S . -B build
        cmake --build build
        ./build/consumer ${package}/lib/libproof${pkgs.stdenv.hostPlatform.extensions.sharedLibrary} > "$out/cmake.txt"
        test "$(cat "$out/cmake.txt")" = '42:7'
        cmp "$out/cmake.txt" "$out/pkgconfig.txt"
        cp ${firstConsumer}/proof.txt "$out/schema1.txt"
        cp ${secondConsumer}/proof.txt "$out/schema2.txt"
        if cmp -s "$out/schema1.txt" "$out/schema2.txt"; then exit 1; fi
        cp ${first}/cpp-products.json "$out/schema1.json"
        cp ${second}/cpp-products.json "$out/schema2.json"
    python3 ${./cpp-negative.py} ${../pkgs/buf-cpp-products/build.py} ${first} ${pkgs.protobuf}/bin/protoc ${pkgs.protobuf.dev}/include ${pkgs.stdenv.cc}/bin/c++ ${pkgs.stdenv.hostPlatform.extensions.sharedLibrary} "$out/negative.json"
    python3 ${./cpp/assert-proof.py} "$out"
  ''
