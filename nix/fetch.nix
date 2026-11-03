{
  lib,
  runCommand,
  tool,
  cacert,
}:
entry:
runCommand "buf-native-module"
  {
    nativeBuildInputs = [ tool ];
    outputHashMode = "recursive";
    outputHashAlgo = "sha256";
    outputHash = entry.hash;
    impureEnvVars = lib.fetchers.proxyImpureEnvVars;
    SSL_CERT_FILE = "${cacert}/etc/ssl/certs/ca-bundle.crt";
  }
  ''
    export HOME="$TMPDIR/home" BUF_CACHE_DIR="$TMPDIR/cache"
    mkdir -p "$HOME"
    if [ -n "''${NIX_SSL_CERT_FILE:-}" ]; then export SSL_CERT_FILE="$NIX_SSL_CERT_FILE"; fi
    buf export ${lib.escapeShellArg (entry.buf.name + ":" + entry.buf.commit)} \
      --exclude-imports --all --output "$TMPDIR/export" --timeout 120s
    cp -pr "$BUF_CACHE_DIR/v3/modules/${entry.path}" "$out"
  ''
