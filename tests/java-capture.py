"""Fresh native Buf captures feed the ordinary Maven/Ivy Java consumers."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

repo = Path(__file__).resolve().parent.parent
sdk = Path(subprocess.check_output(["nix", "build", str(repo) + "#", "--no-link", "--print-out-paths"], text=True).strip())
with tempfile.TemporaryDirectory(prefix="buf Java native capture ") as temporary:
    roots = []
    for name in ("java-projection", "java-projection-v2"):
        root = Path(temporary) / name
        shutil.copytree(repo / "examples" / name, root, ignore=shutil.ignore_patterns("gen", ".buf-purifier"))
        original = json.loads((root / "buf-purifier.lock.json").read_text())
        (root / "buf-purifier.lock.json").unlink()
        subprocess.run([sdk / "bin/buf-purifier", "lock"], cwd=root, check=True, timeout=120)
        captured = json.loads((root / "buf-purifier.lock.json").read_text())
        assert captured == original
        roots.append(root)
    command = ["nix", "build", "--impure", "--no-link", "--print-out-paths", "--file",
               str(repo / "tests/java-consumer-build.nix"), "--argstr", "projectRoot", str(repo),
               "--argstr", "src1", str(roots[0]), "--argstr", "src2", str(roots[1])]
    output = subprocess.check_output(command, text=True).strip()
    assert len(json.loads((Path(output) / "proof.json").read_text())) == 2
print("Fresh native Buf captures replayed through Maven/Ivy Java consumers")
