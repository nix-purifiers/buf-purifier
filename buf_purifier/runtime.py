import fcntl
import hashlib
import json
import os
from pathlib import Path

from .common import environment, load, run, write


def prepare(root, companion):
    data = load(root, companion)
    generation = hashlib.sha256(
        companion.read_bytes() + os.environ["BUF_PURIFIER_SDK"].encode()
    ).hexdigest()[:20]
    state = root / ".buf-purifier" / generation
    state.mkdir(parents=True, exist_ok=True)
    expression = (
        "import "
        + json.dumps(
            os.environ["BUF_PURIFIER_SDK"] + "/lib/buf-purifier/nix/realize.nix"
        )
        + " {root="
        + json.dumps(str(root))
        + ";lockFile="
        + json.dumps(str(companion))
        + ";sdk="
        + json.dumps(os.environ["BUF_PURIFIER_SDK"])
        + ";}"
    )
    profile = Path(
        run(
            [
                "nix",
                "build",
                "--impure",
                "--expr",
                expression,
                "--out-link",
                str(state / "environment-profile"),
                "--print-out-paths",
            ]
        ).strip()
    )
    manifest = json.loads(
        (Path(json.loads(profile.read_text())["output"]) / "manifest.json").read_text()
    )
    if manifest["sdk"] != data["sdk"]:
        raise ValueError("Prepared Buf SDK differs from the lock")
    # Buf scans workspace directories for .proto files, including cache symlinks.
    # Keep dependency sources outside that scan.
    cache_home = Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache")))
    project_key = hashlib.sha256(str(root).encode()).hexdigest()[:20]
    cache_state = cache_home / "buf-purifier" / project_key / generation
    env = environment(cache_state, frozen=True)
    write(state / "session.json", json.dumps({"cache": env["BUF_CACHE_DIR"]}) + "\n")
    with (state / "initialization.lock").open("a") as guard:
        fcntl.flock(guard, fcntl.LOCK_EX)
        for entry in data["entries"]:
            alias = Path(env["BUF_CACHE_DIR"]) / "v3/modules" / entry["path"]
            target = Path(manifest["tree"]) / entry["path"]
            alias.parent.mkdir(parents=True, exist_ok=True)
            if not alias.is_symlink():
                if alias.exists():
                    raise ValueError(
                        "Unexpected writable dependency in private Buf cache"
                    )
                alias.symlink_to(target.resolve(), target_is_directory=True)
            elif alias.resolve() != target.resolve():
                raise ValueError("Private Buf cache differs from the locked Nix module")
    env["PATH"] = (
        str(Path(os.environ["BUF_PURIFIER_SDK"]) / "bin") + os.pathsep + env["PATH"]
    )
    return env
