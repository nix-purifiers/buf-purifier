{ buf, python3 }:
buf.overrideAttrs (old: {
  postPatch = (old.postPatch or "") + ''
    ${python3}/bin/python3 ${../native/patch-native.py}
    gofmt -w private/bufpkg/bufmodule/bufmodulecache/base_provider.go
  '';
})
