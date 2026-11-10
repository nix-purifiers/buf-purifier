"""Rebuild actual Buf, Java SDK, compiled bindings, both views and consumers."""
import json
from pathlib import Path
import subprocess

repo = Path(__file__).resolve().parent.parent
system = subprocess.check_output(["nix", "eval", "--impure", "--raw", "--expr", "builtins.currentSystem"], text=True).strip()
attributes = ["java-project", "java-project-v2", "java-runtime", "java-generated", "java-generated-v2", "java-bindings"]
outputs = subprocess.check_output(["nix", "build", "--no-link", "--print-out-paths",
                                  *[str(repo) + "#checks." + system + "." + name for name in attributes]], text=True).splitlines()
consumer = next(Path(p) for p in outputs if (Path(p) / "proof.json").exists())
roots = set(outputs)
proof = json.loads((consumer / "proof.json").read_text())
for version in proof:
    for format in version["formats"]:
        for key in ("projectJar", "runtimeJar"):
            roots.add("/".join(format[key].split("/")[:4]))
roots.add(json.loads((consumer / "real-sdk-mismatch.json").read_text())["runtime"])
derivers = sorted({subprocess.check_output(["nix-store", "-q", "--deriver", root], text=True).strip() for root in roots})
runtime_views = json.loads(subprocess.check_output([
    "nix", "eval", "--json", str(repo) + "#checks." + system + ".java-runtime.projections",
    "--apply", "p: [ p.maven.drvPath p.ivy.drvPath ]",
], text=True))
derivers = sorted(set(derivers) | set(runtime_views))
assert all(d.endswith(".drv") for d in derivers)
for derivation in derivers:
    print("Direct native rebuild", derivation, flush=True)
    subprocess.run(["nix", "build", "--no-link", "--rebuild", "-L", derivation + "^*"], check=True)
print("Actual native Java producer/runtime/compiled classes/projection/consumer rebuilds passed")
