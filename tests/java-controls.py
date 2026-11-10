"""Reject wrong native output ownership and genuinely inconsistent SDKs."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

repo = Path(__file__).resolve().parent.parent
sdk = Path(subprocess.check_output(["nix", "build", str(repo) + "#", "--no-link", "--print-out-paths"], text=True).strip())
receipts = {}
with tempfile.TemporaryDirectory(prefix="buf Java controls ") as temporary:
    root = Path(temporary)
    for name, diagnostic in [
        ("wrong-directory", "must belong to one native protoc_builtin: java output"),
        ("non-java-generator", "must belong to one native protoc_builtin: java output"),
        ("sdk-mismatch", "native Buf Java compiler disagrees with SDK runtime compiler"),
        ("sdk-type-collision", "generated Java type collides with SDK runtime"),
    ]:
        source = root / name
        shutil.copytree(repo / "examples/java-projection", source, ignore=shutil.ignore_patterns("gen", ".buf-purifier"))
        spec = {"groupId": "org.nixpurifiers.proof", "artifactId": "answer", "version": "1.0.0", "sourceDirectory": "gen/java"}
        if name == "wrong-directory":
            spec["sourceDirectory"] = "gen/other"
        if name == "non-java-generator":
            config = source / "buf.gen.yaml"
            config.write_text(config.read_text().replace("protoc_builtin: java", "protoc_builtin: cpp"))
            # A real fresh native capture owns the changed generator selection.
            (source / "buf-purifier.lock.json").unlink()
            subprocess.run([sdk / "bin/buf-purifier", "lock"], cwd=source, check=True, timeout=120)
        if name == "sdk-type-collision":
            collision = source / "purifier/collision/v1/collision.proto"
            collision.parent.mkdir(parents=True)
            collision.write_text('syntax = "proto3";\npackage purifier.collision.v1;\noption java_package = "com.google.protobuf";\noption java_multiple_files = true;\nmessage GeneratedMessage { int32 value = 1; }\n')
        specification = root / (name + ".json")
        specification.write_text(json.dumps(spec))
        command = ["nix", "build", "--impure", "--no-link", "--file", str(repo / "tests/java-control-build.nix"),
                   "--argstr", "projectRoot", str(repo), "--argstr", "src", str(source),
                   "--argstr", "specFile", str(specification), "--arg", "compilerMismatch", "true" if name == "sdk-mismatch" else "false"]
        result = subprocess.run(command, text=True, capture_output=True, timeout=600)
        receipts[name] = {"command": command, "exit": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
        assert result.returncode and diagnostic in result.stderr, receipts[name]
    if os.environ.get("BUF_JAVA_CONTROL_REPORT"):
        Path(os.environ["BUF_JAVA_CONTROL_REPORT"]).write_text(json.dumps(receipts, indent=2) + "\n")
print("Four actual native Java output/SDK controls rejected as expected")
