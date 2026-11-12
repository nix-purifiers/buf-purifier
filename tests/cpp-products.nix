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
  consumer = package: field: ''
    PKG_CONFIG_PATH=${package}/lib/pkgconfig:$PKG_CONFIG_PATH c++ -fPIC -pie schema.cc $(PKG_CONFIG_PATH=${package}/lib/pkgconfig:$PKG_CONFIG_PATH pkg-config --cflags --libs proof) -ldl -o schema
    ./schema ${package}/lib/libproof${pkgs.stdenv.hostPlatform.extensions.sharedLibrary} ${pkgs.lib.getLib pkgs.protobuf}/lib/libprotobuf${pkgs.stdenv.hostPlatform.extensions.sharedLibrary} ${toString field} > "$out/schema${toString field}.txt"
  '';
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
        cat > CMakeLists.txt <<'CMAKE'
        cmake_minimum_required(VERSION 3.20)
        project(Consumer LANGUAGES CXX)
        set(CMAKE_POSITION_INDEPENDENT_CODE ON)
        find_package(proof 0.1.0 EXACT CONFIG REQUIRED)
        find_package(proof 0.1.0 EXACT CONFIG REQUIRED)
        add_executable(consumer consumer.cc)
        target_link_libraries(consumer PRIVATE proof::proof ''${CMAKE_DL_LIBS})
      CMAKE
        cmake -S . -B build
        cmake --build build
        ./build/consumer ${package}/lib/libproof${pkgs.stdenv.hostPlatform.extensions.sharedLibrary} > "$out/cmake.txt"
        test "$(cat "$out/cmake.txt")" = '42:7'
        cmp "$out/cmake.txt" "$out/pkgconfig.txt"
        cp ${./cpp-schema-consumer.cc} schema.cc
        ${consumer first 1}
        ${consumer second 2}
        if cmp -s "$out/schema1.txt" "$out/schema2.txt"; then exit 1; fi
        cp ${first}/cpp-products.json "$out/schema1.json"
        cp ${second}/cpp-products.json "$out/schema2.json"
    python3 ${./cpp-negative.py} ${../pkgs/buf-cpp-products/build.py} ${first} ${pkgs.protobuf}/bin/protoc ${pkgs.protobuf.dev}/include ${pkgs.stdenv.cc}/bin/c++ ${pkgs.stdenv.hostPlatform.extensions.sharedLibrary} "$out/negative.json"
  ''
