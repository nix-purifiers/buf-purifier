import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

first, second, out, consumer_source, wrong_runtime = map(Path, sys.argv[1:])


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command, label, expected=0):
    result = subprocess.run([str(arg) for arg in command], capture_output=True, text=True)
    if label.endswith("-gradle"):
        # Keep the complete native console output in the Nix build log.
        # Wall-clock task timings do not belong in a reproducible receipt.
        print(result.stdout, end="", flush=True)
        (out / (label + ".resolved.txt")).write_text("\n".join(line for line in result.stdout.splitlines() if line.startswith("RESOLVED\t")) + "\n")
    else:
        (out / (label + ".stdout")).write_text(result.stdout)
    (out / (label + ".stderr")).write_text(result.stderr)
    assert result.returncode == expected, (label, result.returncode, result.stdout, result.stderr)
    if expected == 0:
        assert not result.stderr, (label, result.stderr)
    return result


receipts = []
for number, projection in enumerate((first, second), 1):
    spec = json.loads((projection / "spec.json").read_text())
    producer, runtime = map(Path, (spec["producer"], spec["runtime"]))
    model = json.loads((producer / "proof/model.json").read_text())
    runtime_model = json.loads((runtime / "proof/model.json").read_text())
    classes = Path("consumer" + str(number)); classes.mkdir()
    names = out / (str(number) + "-classes.txt")
    names.write_text("\n".join(name.removesuffix(".class").replace("/", ".") for name in sorted(model["classes"])) + "\n")
    native = producer / "bindings.jar"
    sdk = runtime / "protobuf-java.jar"
    assert sha(native) == model["jarSha256"] and sha(sdk) == runtime_model["jarSha256"]
    run(["javac", "--release", "17", "-cp", str(native) + ":" + str(sdk), "-d", classes, consumer_source], str(number) + "-javac")
    coordinate = spec["coordinate"]
    formats = []
    for format in ("maven", "ivy"):
        directory = Path("gradle" + str(number) + "-" + format); directory.mkdir()
        (directory / "settings.gradle").write_text("rootProject.name = 'protobuf-consumer'\n")
        repository = "maven { url = uri(" + json.dumps(spec["maven"]) + ") }"
        if format == "ivy":
            repository = "ivy { url = uri(" + json.dumps(spec["ivy"]) + "); patternLayout { ivy '[organisation]/[module]/[revision]/ivys/ivy.xml'; artifact '[organisation]/[module]/[revision]/jars/[artifact].[ext]' }; metadataSources { ivyDescriptor() } }"
        (directory / "build.gradle").write_text("repositories { " + repository + " }\n"
            + "configurations { proof }\ndependencies { proof " + json.dumps(coordinate) + " }\n"
            + "tasks.register('resolve') { doLast { configurations.proof.resolve().sort().each { println('RESOLVED\\t' + it.absolutePath) } } }\n")
        result = run(["gradle", "--offline", "--no-daemon", "--console=plain", "-g", str(directory / "home"), "-p", directory, "resolve"], str(number) + "-" + format + "-gradle")
        resolved = [Path(line.split("\t", 1)[1]) for line in result.stdout.splitlines() if line.startswith("RESOLVED\t")]
        assert len(resolved) == 2, resolved
        owned = next(p for p in resolved if p.name.startswith("answer-") or p.name == "answer.jar")
        support = next(p for p in resolved if p.name.startswith("protobuf-java-") or p.name == "protobuf-java.jar")
        assert sha(owned) == sha(native) and sha(support) == sha(sdk)
        cp = str(classes) + ":" + str(owned) + ":" + str(support)
        result = run(["java", "-cp", cp, "Consumer", owned, support, str(number), names], str(number) + "-" + format + "-java")
        origins = []
        resources = []
        for line in result.stdout.splitlines():
            if line.startswith("CLASS\t"):
                _, name, jar, digest = line.split("\t")
                expected = model["classes"].get(name, runtime_model["classes"].get(name))
                assert expected == digest, (name, expected, digest)
                with zipfile.ZipFile(jar) as archive:
                    assert hashlib.sha256(archive.read(name)).hexdigest() == digest
                origins.append({"entry": name, "jar": jar, "sha256": digest})
            if line.startswith("RESOURCE\t"):
                _, name, jar, digest = line.split("\t")
                expected = [value for key, value in runtime_model["runtimeProtoFiles"].items() if key.endswith("/" + name)]
                assert expected == [digest]
                with zipfile.ZipFile(jar) as archive:
                    assert hashlib.sha256(archive.read(name)).hexdigest() == digest
                resources.append({"entry": name, "jar": jar, "sha256": digest})
        assert len(origins) == len(model["classes"]) + 3
        assert len(resources) == 1
        formats.append({"format": format, "projectJar": str(owned), "runtimeJar": str(support),
                        "jarSha256": sha(owned), "runtimeJarSha256": sha(support), "classOrigins": origins, "resources": resources})
    # Fresh ordinary JVM fails without its real SDK runtime.
    result = subprocess.run(["java", "-cp", str(classes) + ":" + str(owned), "Consumer", str(owned), str(support), str(number), str(names)], capture_output=True, text=True)
    assert result.returncode and "NoClassDefFoundError" in result.stderr
    (out / (str(number) + "-missing-runtime.stderr")).write_text(result.stderr)
    # Dropping a genuinely compiled local schema dependency must also fail.
    broken = Path("missing-common" + str(number) + ".jar")
    with zipfile.ZipFile(owned) as source, zipfile.ZipFile(broken, "w") as target:
        for entry in source.infolist():
            if "/Common" not in entry.filename:
                target.writestr(entry, source.read(entry.filename))
    result = subprocess.run(["java", "-cp", str(classes) + ":" + str(broken) + ":" + str(support), "Consumer", str(broken), str(support), str(number), str(names)], capture_output=True, text=True)
    assert result.returncode and "NoClassDefFoundError" in result.stderr
    (out / (str(number) + "-missing-common.stderr")).write_text(result.stderr)
    receipts.append({"coordinate": coordinate, "projectJar": str(owned), "runtimeJar": str(support),
                     "jarSha256": sha(owned), "runtimeJarSha256": sha(support), "formats": formats})
assert receipts[0]["jarSha256"] != receipts[1]["jarSha256"]
assert receipts[0]["runtimeJarSha256"] == receipts[1]["runtimeJarSha256"]
with zipfile.ZipFile(receipts[0]["projectJar"]) as old, zipfile.ZipFile(receipts[1]["projectJar"]) as new:
    assert old.read("org/nixpurifiers/proof/v1/Common.class") != new.read("org/nixpurifiers/proof/v1/Common.class")
replacement = receipts[1]
result = subprocess.run(["java", "-cp", "consumer1:" + replacement["projectJar"] + ":" + replacement["runtimeJar"],
                         "Consumer", replacement["projectJar"], replacement["runtimeJar"], "1", str(out / "1-classes.txt")],
                        capture_output=True, text=True)
assert result.returncode and "schema field 2" in result.stderr
(out / "genuine-replacement.stderr").write_text(result.stderr)
expected = receipts[0]
result = subprocess.run(["java", "-cp", "consumer1:" + expected["projectJar"] + ":" + str(wrong_runtime / "protobuf-java.jar"),
                         "Consumer", expected["projectJar"], str(wrong_runtime / "protobuf-java.jar"), "1", str(out / "1-classes.txt")],
                        capture_output=True, text=True)
assert result.returncode and "ProtobufRuntimeVersionException" in result.stderr, result.stderr
(out / "real-sdk-mismatch.stderr").write_text(result.stderr)
wrong_model = json.loads((wrong_runtime / "proof/model.json").read_text())
(out / "real-sdk-mismatch.json").write_text(json.dumps({"runtime": str(wrong_runtime),
    "version": wrong_model["version"], "protoc": wrong_model["protoc"], "jarSha256": wrong_model["jarSha256"]}, indent=2) + "\n")
(out / "proof.json").write_text(json.dumps(receipts, indent=2) + "\n")
