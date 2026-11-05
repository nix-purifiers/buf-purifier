# SPDX-License-Identifier: MIT
{ pkgs, projection }:
let
  python = pkgs.python3.withPackages (p: [ p.pip ]);
in
pkgs.runCommand "buf-generated-python-ordinary-pip"
  {
    nativeBuildInputs = [ python ];
  }
  ''
    export HOME="$TMPDIR/home" PIP_DISABLE_PIP_VERSION_CHECK=1
    mkdir -p "$HOME"
    python - <<'PY'
    import json, pathlib, zipfile
    modules = {m['name']: m for m in json.load(open('${projection.catalog}'))['modules']}
    assert set(modules) == {'proof-schemas', 'protobuf'}
    assert modules['proof-schemas']['version'].startswith('1.0.0+nix.')
    assert modules['protobuf']['version'] == '${pkgs.python3Packages.protobuf.version}'
    pathlib.Path('version').write_text(modules['proof-schemas']['version'])
    # A valid, available competing wheel must not displace the exact SDK runtime.
    import csv, hashlib, base64, io
    competitor = pathlib.Path('competitor')
    competitor.mkdir()
    entries = {
        'google/protobuf/__init__.py': b'__version__ = "99.0.0"\n',
        'protobuf-99.0.0.dist-info/METADATA': b'Metadata-Version: 2.1\nName: protobuf\nVersion: 99.0.0\n\n',
        'protobuf-99.0.0.dist-info/WHEEL': b'Wheel-Version: 1.0\nGenerator: native-competitor-fixture\nRoot-Is-Purelib: true\nTag: py3-none-any\n',
    }
    rows = [[name, 'sha256=' + base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b'=').decode(), len(data)]
            for name, data in entries.items()]
    rows.append(['protobuf-99.0.0.dist-info/RECORD', "", ""])
    record = io.StringIO()
    csv.writer(record).writerows(rows)
    entries['protobuf-99.0.0.dist-info/RECORD'] = record.getvalue().encode()
    with zipfile.ZipFile(competitor / 'protobuf-99.0.0-py3-none-any.whl', 'w') as archive:
        for name, data in sorted(entries.items()):
            archive.writestr(name, data)
    own = pathlib.Path('${projection}') / modules['proof-schemas']['wheels'][0]
    with zipfile.ZipFile(own) as archive:
        metadata, = [n for n in archive.namelist() if n.endswith('/METADATA')]
        assert b'Requires-Dist: protobuf==${pkgs.python3Packages.protobuf.version}' in archive.read(metadata)
    PY
    python -m pip --isolated download --no-index --find-links competitor --no-deps --dest available protobuf==99.0.0
    python -m pip --isolated install --no-index --find-links competitor --find-links ${projection} --target installed --report report.json "proof-schemas==$(cat version)"
    PYTHONPATH="$PWD/installed" python -S - <<'PY'
    import hashlib, json, pathlib, urllib.parse
    import google.protobuf, google._upb._message
    import importlib.metadata
    assert importlib.metadata.version("protobuf") == "${pkgs.python3Packages.protobuf.version}"
    from proof.v1.proof_pb2 import Proof
    from envoy.type.v3.percent_pb2 import FractionalPercent
    root = pathlib.Path('installed').resolve()
    assert pathlib.Path(google.protobuf.__file__).resolve().is_relative_to(root)
    assert pathlib.Path(google._upb._message.__file__).resolve().is_relative_to(root)
    message = Proof(answer=42, fraction=FractionalPercent(numerator=42))
    restored = Proof.FromString(message.SerializeToString())
    assert restored.answer == 42 and restored.fraction.numerator == 42
    assert google.protobuf.__version__ == '${pkgs.python3Packages.protobuf.version}'
    for item in json.load(open('report.json'))['install']:
        source = pathlib.Path(urllib.parse.unquote(urllib.parse.urlparse(item['download_info']['url']).path))
        assert source.parent == pathlib.Path('${projection}')
        assert item['download_info']['archive_info']['hashes']['sha256'] == hashlib.sha256(source.read_bytes()).hexdigest()
    PY
    touch $out
  ''
