"""Compile native Buf Java output with its compiler-matched SDK runtime."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile

import yaml


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(out, label, args):
    argv = [str(arg) for arg in args]
    result = subprocess.run(argv, text=True, capture_output=True)
    (out / "proof" / (label + ".command.json")).write_text(json.dumps({"argv": argv, "exit": result.returncode}, indent=2) + "\n")
    (out / "proof" / (label + ".stdout")).write_text(result.stdout)
    (out / "proof" / (label + ".stderr")).write_text(result.stderr)
    if result.returncode:
        raise ValueError(label + " failed: " + result.stdout + result.stderr)
    return result.stdout.strip()


def publish(out, group, artifact, version, jar, dependency=None):
    # The shared adapter retains native Ivy and projects its representable
    # dependency graph into Maven, with one identity for both views.
    directory = out / "repository" / group / artifact / version
    (directory / "ivys").mkdir(parents=True)
    (directory / "jars").mkdir()
    root = ET.Element("ivy-module", version="2.0")
    ET.SubElement(root, "info", organisation=group, module=artifact, revision=version)
    ET.SubElement(ET.SubElement(root, "configurations"), "conf", name="default", visibility="public")
    ET.SubElement(ET.SubElement(root, "publications"), "artifact", name=artifact, type="jar", ext="jar", conf="default")
    if dependency:
        group, name, revision = dependency
        ET.SubElement(ET.SubElement(root, "dependencies"), "dependency", org=group, name=name, rev=revision, conf="default->default")
    ET.ElementTree(root).write(directory / "ivys/ivy.xml", encoding="utf-8", xml_declaration=True)
    shutil.copyfile(jar, directory / "jars" / (artifact + ".jar"))


def compile_jar(out, sources, javac, jar, version, classpath=None, extra_files=None, module=None):
    classes = Path("classes")
    classes.mkdir()
    Path("sources.txt").write_text("\n".join('"' + str(p).replace('\\', '\\\\').replace('"', '\\"') + '"' for p in sorted(sources)) + "\n")
    args = [javac, "--release", "17", "-d", classes]
    if classpath:
        args += ["-cp", classpath]
    args += ["@sources.txt"]
    command(out, "javac", args)
    shutil.copyfile("sources.txt", out / "proof/javac-sources.txt")
    for relative, source in (extra_files or {}).items():
        destination = classes / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    manifest = "Manifest-Version: 1.0\nImplementation-Version: " + version + "\n"
    if module:
        manifest += "Automatic-Module-Name: " + module + "\n"
    Path("MANIFEST.MF").write_text(manifest + "\n")
    target = out / "bindings.jar"
    command(out, "jar", [jar, "--create", "--date=1980-01-01T00:00:02Z", "--file", target, "--manifest", "MANIFEST.MF", "-C", classes, "."])
    with zipfile.ZipFile(target) as archive:
        compiled = {name: hashlib.sha256(archive.read(name)).hexdigest() for name in sorted(archive.namelist()) if name.endswith(".class")}
        assert compiled
        assert all(int.from_bytes(archive.read(name)[6:8], "big") == 61 for name in compiled)
    return target, compiled


def runtime(out, source, protoc, javac, jar):
    versions = json.loads((source / "version.json").read_text())
    assert len(versions) == 1
    version = next(iter(versions.values()))
    actual = command(out, "protoc-version", [protoc, "--version"])
    assert actual == "libprotoc " + version["protoc_version"]
    java_version = version["languages"]["java"]
    text = (source / "java/core/src/main/java/com/google/protobuf/RuntimeVersion.java").read_text()
    constants = [re.search("OSS_" + part + r" = (\d+);", text).group(1) for part in ("MAJOR", "MINOR", "PATCH")]
    assert ".".join(constants) == java_version
    generated = out / "generated"
    generated.mkdir()
    protos = ["any", "api", "compiler/plugin", "descriptor", "duration", "empty", "field_mask", "java_features", "source_context", "struct", "timestamp", "type", "wrappers"]
    command(out, "protoc-runtime", [protoc, "-I" + str(source / "src"), "-I" + str(source / "java/core/src/main/resources"), "--java_out=" + str(generated), *["google/protobuf/" + name + ".proto" for name in protos]])
    sources = sorted((source / "java/core/src/main/java").glob("com/google/protobuf/*.java")) + sorted(generated.rglob("*.java"))
    proto_files = {}
    for name in protos:
        relative = "google/protobuf/" + name + ".proto"
        candidates = [source / "src" / relative, source / "java/core/src/main/resources" / relative]
        proto_files[relative] = next(p for p in candidates if p.is_file())
    target, compiled = compile_jar(out, sources, javac, jar, java_version,
                                   extra_files={"META-INF/LICENSE": source / "LICENSE", **proto_files},
                                   module="com.google.protobuf")
    shutil.copyfile(target, out / "protobuf-java.jar")
    publish(out, "com.google.protobuf", "protobuf-java", java_version, target)
    return {"kind": "compiler-matched-protobuf-java-runtime", "version": java_version, "protobufSource": str(source),
            "protoc": {"path": str(protoc), "version": actual}, "sourceVersionSha256": sha(source / "version.json"),
            "sourceFiles": {str(p): sha(p) for p in sorted(sources)},
            "runtimeProtoFiles": {str(p): sha(p) for p in sorted(proto_files.values())},
            "classes": compiled, "jarSha256": sha(target)}


def bindings(out, producer, runtime, spec_file, javac, jar):
    spec = json.loads(spec_file.read_text())
    config = producer / "source/buf.gen.yaml"
    plugins = yaml.safe_load(config.read_text())["plugins"]
    matches = [p for p in plugins if p.get("protoc_builtin") == "java" and p.get("out") == spec["sourceDirectory"]]
    if len(matches) != 1:
        raise ValueError("selected directory must belong to one native protoc_builtin: java output")
    root = (producer / spec["sourceDirectory"]).resolve(strict=True)
    if not root.is_relative_to(producer) or any(p.is_symlink() for p in root.rglob("*")):
        raise ValueError("generated Java output escapes its native producer")
    sources = sorted(root.rglob("*.java"))
    if not sources:
        raise ValueError("native Java output has no Java sources")
    model = json.loads((runtime / "proof/model.json").read_text())
    if (producer / "native-protoc-version.txt").read_text().strip() != model["protoc"]["version"]:
        raise ValueError("native Buf Java compiler disagrees with SDK runtime compiler")
    selected, duplicates = [], []
    for source in sources:
        relative = source.relative_to(root)
        sdk = runtime / "generated" / relative
        if sdk.exists():
            if source.read_bytes() != sdk.read_bytes():
                raise ValueError("generated SDK Java type disagrees with compiler-owned runtime: " + str(relative))
            duplicates.append({"native": str(source), "sdk": str(sdk), "sha256": sha(source)})
        else:
            if str(relative.with_suffix(".class")) in model["classes"]:
                raise ValueError("generated Java type collides with SDK runtime: " + str(relative))
            selected.append(source)
    if not selected:
        raise ValueError("selection contains only SDK runtime Java types")
    target, compiled = compile_jar(out, selected, javac, jar, spec["version"], runtime / "protobuf-java.jar")
    publish(out, spec["groupId"], spec["artifactId"], spec["version"], target, ("com.google.protobuf", "protobuf-java", model["version"]))
    return {"kind": "native-buf-generated-java", "selection": spec, "nativeProducer": str(producer),
            "nativeConfigSha256": sha(config), "nativeImageSha256": sha(producer / "image.binpb"),
            "nativeProtocVersion": (producer / "native-protoc-version.txt").read_text().strip(),
            "nativeBufVersion": (producer / "native-buf-version.txt").read_text().strip(),
            "runtime": str(runtime), "runtimeJarSha256": model["jarSha256"],
            "nativeSources": {str(p.relative_to(root)): sha(p) for p in sources},
            "sdkDuplicates": duplicates, "classes": compiled, "jarSha256": sha(target)}


if __name__ == "__main__":
    try:
        mode, output, *args = sys.argv[1:]
        out = Path(output)
        (out / "proof").mkdir(parents=True)
        paths = list(map(Path, args))
        model = runtime(out, *paths) if mode == "runtime" else bindings(out, *paths)
        model["javac"] = {"path": args[-2], "version": command(out, "javac-version", [paths[-2], "-version"])}
        (out / "proof/model.json").write_text(json.dumps(model, sort_keys=True, indent=2) + "\n")
    except (ValueError, OSError, AssertionError, KeyError) as error:
        raise SystemExit("buf-purifier: javaPackage: " + str(error))
