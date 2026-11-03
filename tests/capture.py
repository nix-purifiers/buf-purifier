"""Capture through native Buf resolution, including transitive modules."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

repo = Path(__file__).resolve().parent.parent
sdk = Path(
    subprocess.check_output(
        ["nix", "build", str(repo) + "#", "--no-link", "--print-out-paths"], text=True
    ).strip()
)
with tempfile.TemporaryDirectory(prefix="buf native capture ") as temporary:
    root = Path(temporary) / "project"
    env = dict(os.environ, XDG_CACHE_HOME=str(Path(temporary) / "xdg-cache"))
    shutil.copytree(
        repo / "examples/minimal",
        root,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("gen", ".buf-purifier"),
    )
    companion = root / "buf-purifier.lock.json"
    companion.unlink()
    subprocess.run(
        [sdk / "bin/buf-purifier", "lock"], cwd=root, env=env, check=True, timeout=300
    )
    data = json.loads(companion.read_text())
    assert len(data["entries"]) >= 8
    assert any(e["buf"]["name"] == "buf.build/cncf/xds" for e in data["entries"])
    before = companion.read_bytes()
    subprocess.run([sdk / "bin/buf-purifier", "lock"], cwd=root, env=env, check=True)
    assert companion.read_bytes() == before
    subprocess.run(
        [sdk / "bin/buf", "build"], cwd=root, env=env, check=True, timeout=300
    )
    empty = Path(temporary) / "empty"
    empty.mkdir()
    (empty / "buf.yaml").write_text("version: v2\nmodules:\n  - path: .\n")
    (empty / "proof.proto").write_text(
        'syntax = "proto3";\npackage empty;\nmessage Proof {}\n'
    )
    subprocess.run(
        [sdk / "bin/buf-purifier", "lock"], cwd=empty, env=env, check=True, timeout=120
    )
    assert json.loads((empty / "buf-purifier.lock.json").read_text())["entries"] == []
    subprocess.run(
        [sdk / "bin/buf", "build"], cwd=empty, env=env, check=True, timeout=120
    )
print(
    "Native Buf resolver capture, transitive graph and dependency-free workspace passed"
)
