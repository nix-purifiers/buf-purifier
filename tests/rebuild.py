"""Re-fetch each declared native module and verify its identical NAR contents."""

import json
from pathlib import Path
import subprocess

repo = Path(__file__).resolve().parent.parent
system = subprocess.check_output(
    ["nix", "eval", "--impure", "--raw", "--expr", "builtins.currentSystem"], text=True
).strip()
output = subprocess.check_output(
    [
        "nix",
        "build",
        "--no-link",
        "--print-out-paths",
        str(repo) + "#checks." + system + ".environment",
    ],
    text=True,
).strip()
manifest = json.loads((Path(output) / "manifest.json").read_text())
lock = json.loads((repo / "examples/minimal/buf-purifier.lock.json").read_text())
for entry in lock["entries"]:
    module = (Path(manifest["tree"]) / entry["path"]).resolve()
    drv = subprocess.check_output(
        ["nix-store", "-q", "--deriver", str(module)], text=True
    ).strip()
    subprocess.run(["nix-store", "--realise", drv, "--check"], check=True)
print("Native Buf module fetches reproduced identical cache trees")
