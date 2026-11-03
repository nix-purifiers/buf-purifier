import json
import os
from pathlib import Path
import subprocess

from .validation import validate


def run(args, **kwargs):
    result = subprocess.run(args, text=True, capture_output=True, **kwargs)
    if result.returncode:
        raise ValueError(result.stdout + result.stderr)
    return result.stdout


def write(path, text):
    path = Path(path)
    if path.is_file() and path.read_text() == text:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text)
    temporary.replace(path)


def environment(state, frozen=False):
    env = dict(os.environ)
    for key in ("BUF_CACHE_DIR", "BUF_PURIFIER_FROZEN"):
        env.pop(key, None)
    cache = state / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    env["BUF_CACHE_DIR"] = str(cache)
    if frozen:
        env["BUF_PURIFIER_FROZEN"] = "1"
    env["PATH"] = os.environ["BUF_PURIFIER_NATIVE_PATH"] + os.pathsep + env["PATH"]
    return env


def load(root, companion):
    data = validate(json.loads(companion.read_text()), root)
    if data["sdk"] != os.environ["BUF_PURIFIER_SDK_VERSION"]:
        raise ValueError("Buf frontend SDK changed; update the lock")
    return data
