import json
import os
from pathlib import Path
import tempfile

from .common import environment, load, run, write
from .validation import config, selection_inputs, native_lock


def capture(root, companion, update=False, extra=()):
    if companion.exists() and not update:
        load(root, companion)
        return
    previous = json.loads(companion.read_text()) if companion.exists() else {}
    extra = list(extra or previous.get("extraInputs", []))
    config(root)
    with tempfile.TemporaryDirectory(prefix="buf-capture-") as temporary:
        state = Path(temporary)
        env = environment(state)
        native = os.environ["BUF_PURIFIER_ORIGINAL"]
        run([native, "dep", "update"], cwd=root, env=env)
        solution = native_lock(root)
        run(
            [native, "build", "--output", str(state / "image.binpb")], cwd=root, env=env
        )
        entries = []
        for module in solution.get("deps", []):
            path = "b5/" + module["name"] + "/" + module["commit"]
            source = state / "cache/v3/modules" / path
            nar = run(["nix", "hash", "path", str(source)]).strip()
            entries.append(
                {
                    "path": path,
                    "url": "bsr:" + module["name"] + ":" + module["commit"],
                    "hash": nar,
                    "mirrors": [],
                    "buf": module,
                }
            )
        data = {
            "version": 1,
            "purifier": "buf",
            "sdk": os.environ["BUF_PURIFIER_SDK_VERSION"],
            "native": solution,
            "entries": entries,
            "inputs": selection_inputs(root, extra),
            "extraInputs": extra,
        }
        write(companion, json.dumps(data, indent=2, sort_keys=True) + "\n")
