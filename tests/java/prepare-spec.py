import json
from pathlib import Path
import sys

seed = json.loads(Path(sys.argv[1]).read_text())
catalog = json.loads(Path(seed.pop("catalog")).read_text())
owned = [m for m in catalog["modules"] if m["group"] == "org.nixpurifiers.proof" and m["name"] == "answer"]
runtime = [m for m in catalog["modules"] if m["group"] == "com.google.protobuf" and m["name"] == "protobuf-java"]
assert len(owned) == len(runtime) == 1 and len(catalog["modules"]) == 2
assert "-nix-" in owned[0]["version"] and "-nix-" in runtime[0]["version"]
seed["coordinate"] = ":".join(owned[0][key] for key in ("group", "name", "version"))
seed["runtimeCoordinate"] = ":".join(runtime[0][key] for key in ("group", "name", "version"))
Path(sys.argv[2]).write_text(json.dumps(seed, indent=2) + "\n")
