{
  lib,
  stdenvNoCC,
  makeWrapper,
  python,
  nix,
  gh,
  git,
  cacert,
  tool,
  protobuf,
  nativePath,
  sdkVersion,
  nixpkgsSrc,
  purifierSrc,
}:
stdenvNoCC.mkDerivation {
  pname = "buf-purifier";
  version = "0.1.0";
  src = ../.;
  nativeBuildInputs = [ makeWrapper ];
  dontBuild = true;
  installPhase = ''
    mkdir -p "$out/bin" "$out/lib/buf-purifier"
    cp -r buf_purifier nix native "$out/lib/buf-purifier/"
    install -m755 bin/buf-purifier "$out/bin/buf-purifier"
    ln -s ${protobuf}/bin/protoc "$out/bin/protoc"
    for file in realize release; do
      substituteInPlace "$out/lib/buf-purifier/nix/$file.nix" --replace-fail '@nixpkgs@' '${nixpkgsSrc}' --replace-fail '@purifier@' '${purifierSrc}'
    done
    wrapProgram "$out/bin/buf-purifier" \
      --prefix PATH : ${
        lib.makeBinPath [
          python
          nix
          gh
          git
        ]
      } \
      --set-default SSL_CERT_FILE ${cacert}/etc/ssl/certs/ca-bundle.crt \
      --set-default BUF_PURIFIER_GH ${gh}/bin/gh \
      --set BUF_PURIFIER_ORIGINAL ${lib.getExe tool} \
      --set BUF_PURIFIER_NATIVE_PATH ${lib.escapeShellArg nativePath} \
      --set BUF_PURIFIER_SDK_VERSION ${sdkVersion} \
      --set BUF_PURIFIER_SDK "$out"
    makeWrapper "$out/bin/buf-purifier" "$out/bin/buf" --add-flags --native
  '';
  meta = {
    description = "Native Buf with locked Nix-resolved Protobuf modules";
    homepage = "https://nix-purifiers.github.io/";
    license = lib.licenses.mit;
    platforms = [
      "x86_64-linux"
      "aarch64-linux"
    ];
    mainProgram = "buf-purifier";
  };
}
