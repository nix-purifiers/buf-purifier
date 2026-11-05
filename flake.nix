{
  description = "Locked, Nix-resolved Protobuf modules for Buf";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  inputs.purifier = {
    url = "github:nix-purifiers/purifier";
    flake = false;
  };
  outputs =
    {
      self,
      nixpkgs,
      purifier,
    }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
      ];
      forAll = nixpkgs.lib.genAttrs systems;
      overlay = final: prev: {
        buf-purifier = import ./nix/scope.nix {
          pkgs = final;
          nixpkgsSrc = nixpkgs;
          purifierSrc = purifier;
        };
      };
      pkgsFor =
        system:
        import nixpkgs {
          inherit system;
          overlays = [ overlay ];
        };
    in
    {
      overlays.default = overlay;
      packages = forAll (system: {
        default = (pkgsFor system).buf-purifier.cli;
        cli = self.packages.${system}.default;
      });
      apps = forAll (system: {
        default = {
          type = "app";
          program = "${self.packages.${system}.default}/bin/buf-purifier";
          meta.description = "Lock native Buf modules";
        };
      });
      lib.buf-purifier.readLock = import ./nix/read-lock.nix { lib = nixpkgs.lib; };
      checks = forAll (
        system:
        let
          p = pkgsFor system;
          b = p.buf-purifier.buildBufProject {
            src = ./examples/minimal;
            schemaEntrypoints = [ "proof/v1/proof.proto" ];
            pythonPackage = {
              name = "proof-schemas";
              version = "1.0.0";
            };
            doCheck = true;
            checkCommand = ''test -s "$out/gen/proof/v1/proof.pb.cc"'';
          };
        in
        {
          inherit (b.packages) environment project;
          release = b.release;
          python-bindings = import ./tests/python-bindings.nix {
            pkgs = p;
            projection = b.projections.python;
          };
          schema = import ./tests/schema-consumer.nix {
            pkgs = p;
            projection = b.projections.resources;
          };
          resources = import ./tests/resource-consumer.nix {
            pkgs = p;
            projection = b.projections.resources;
          };
          cli = self.packages.${system}.default;
        }
      );
      formatter = forAll (system: (pkgsFor system).nixfmt-tree);
    };
}
