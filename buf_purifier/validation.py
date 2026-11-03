"""Validate native selection documents; Buf owns dependency resolution."""

import hashlib
import json
from pathlib import Path
import re
import sys

import yaml


def config(root):
    value = yaml.safe_load((root / "buf.yaml").read_text())
    if value.get("version") != "v2":
        raise ValueError("The initial Buf integration requires a v2 workspace")
    if value.get("plugins"):
        raise ValueError("Check plugins need a locked Nix tool provider")
    for module in value.get("modules", []):
        path = Path(module["path"])
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("Workspace modules must stay inside the project")
    generation = root / "buf.gen.yaml"
    if generation.exists():
        gen = yaml.safe_load(generation.read_text())
        if gen.get("version") != "v2":
            raise ValueError("The initial code generation integration requires v2")
        for source in gen.get("inputs", []):
            directory = Path(source.get("directory", "/"))
            if directory.is_absolute() or ".." in directory.parts:
                raise ValueError("Generated inputs must be local workspace directories")
        for plugin in gen.get("plugins", []):
            if "protoc_builtin" not in plugin or any(
                k in plugin for k in ("local", "remote", "protoc_path")
            ):
                raise ValueError(
                    "Use protoc_builtin generators from the Nix SDK; other plugins need a Nix tool provider"
                )
    return value


def selection_inputs(root, extra=()):
    names = ["buf.yaml", *extra]
    if (root / "buf.lock").exists():
        names.append("buf.lock")
    if (root / "buf.gen.yaml").exists():
        names.append("buf.gen.yaml")
    result = {}
    for name in sorted(set(names)):
        path = root / name
        if (
            Path(name).is_absolute()
            or ".." in Path(name).parts
            or not path.is_file()
            or path.is_symlink()
        ):
            raise ValueError("Selection inputs must be regular project files")
        result[name] = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    return result


def native_lock(root):
    file = root / "buf.lock"
    value = yaml.safe_load(file.read_text()) if file.exists() else {"version": "v2"}
    value.setdefault("deps", [])
    return value


def validate(data, root):
    if data.get("version") != 1 or data.get("purifier") != "buf":
        raise ValueError("Unsupported Buf lock")
    config(root)
    native = native_lock(root)
    if native != data["native"] or native.get("version") != "v2":
        raise ValueError("Native Buf solution changed; update the lock")
    if selection_inputs(root, data["extraInputs"]) != data["inputs"]:
        raise ValueError("Selection inputs changed; update the lock")
    modules = native.get("deps", [])
    entries = data["entries"]
    if len(modules) != len(entries):
        raise ValueError("Buf module entries differ from the native solution")
    for module, entry in zip(modules, entries):
        name, commit, digest = module["name"], module["commit"], module["digest"]
        if (
            not re.fullmatch(r"[a-z0-9.-]+/[a-z0-9_-]+/[a-z0-9_-]+", name)
            or not re.fullmatch("[0-9a-f]{32}", commit)
            or not re.fullmatch("b5:[0-9a-f]{128}", digest)
        ):
            raise ValueError("Unsupported native Buf module identity")
        if (
            entry["buf"] != module
            or entry["path"] != "b5/" + name + "/" + commit
            or entry["url"] != "bsr:" + name + ":" + commit
            or entry["mirrors"] != []
        ):
            raise ValueError("Buf fetch differs from native module metadata")
    return data


if __name__ == "__main__":
    validate(json.loads(Path(sys.argv[1]).read_text()), Path(sys.argv[2]))
