"""Native descriptor/code generation and LSP with immutable transitive modules."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile

from editor import check as check_editor

repo = Path(__file__).resolve().parent.parent
sdk = Path(
    subprocess.check_output(
        ["nix", "build", str(repo) + "#", "--no-link", "--print-out-paths"], text=True
    ).strip()
)


def call(root, *args, env=None, expected=0):
    print("native", args, flush=True)
    result = subprocess.run(
        [sdk / "bin" / args[0], *args[1:]],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
        timeout=120,
    )
    assert result.returncode == expected, (args, result)
    return result


with tempfile.TemporaryDirectory(prefix="buf proof with spaces ") as temporary:
    temp = Path(temporary)
    root = temp / "project"
    shutil.copytree(
        repo / "examples/minimal",
        root,
        ignore=shutil.ignore_patterns("gen", ".buf-purifier"),
    )
    poison = temp / "host-cache"
    poison.mkdir()
    env = dict(
        os.environ,
        BUF_CACHE_DIR=str(poison),
        BUF_TOKEN="ignored-host-token",
        XDG_CACHE_HOME=str(temp / "xdg-cache"),
    )
    call(root, "buf", "build", "-o", "image.binpb", env=env)
    before = (root / "image.binpb").read_bytes()
    source = root / "proof/v1/proof.proto"
    original = source.read_text()
    source.write_text(original.replace("const = 42", "const = 43"))
    call(root, "buf", "build", "-o", "image.binpb", env=env)
    assert (root / "image.binpb").read_bytes() != before
    source.write_text(original)
    call(root, "buf", "build", "-o", "image.binpb", env=env)
    assert (root / "image.binpb").read_bytes() == before
    call(root, "buf", "lint", env=env)
    call(root, "buf", "generate", env=env)
    assert (root / "gen/proof/v1/proof.pb.cc").is_file()
    call(root, "buf", "format", "-w", env=env)
    check_editor(sdk / "bin", root, env)
    profile = next((root / ".buf-purifier").glob("*/environment-profile"))
    metadata = json.loads(profile.resolve().read_text())
    manifest = json.loads((Path(metadata["output"]) / "manifest.json").read_text())
    lock = json.loads((root / "buf-purifier.lock.json").read_text())
    assert len(lock["entries"]) == 8
    native_cache = Path(
        json.loads((profile.parent / "session.json").read_text())["cache"]
    )
    cache = native_cache / "v3/modules"
    for entry in lock["entries"]:
        alias = cache / entry["path"]
        assert alias.is_symlink() and str(alias.resolve()).startswith("/nix/store/")
    refs = subprocess.check_output(
        ["nix-store", "-q", "--requisites", str(profile.resolve())], text=True
    )
    assert str(sdk) in refs and manifest["tree"] in refs
    # Remove a required dependency link. Native code must fail before transport.
    missing = cache / lock["entries"][0]["path"]
    target = missing.resolve()
    missing.unlink()
    native = subprocess.run(
        [sdk / "bin/buf-purifier", "exec", "--", "sh", "-c", "true"],
        env=env,
        cwd=root,
        text=True,
        capture_output=True,
    )
    assert native.returncode == 0  # preparation repairs a missing immutable link
    original_tool = next(
        Path(p) / "bin/buf" for p in refs.splitlines() if p.endswith("-buf-1.73.0")
    )
    missing.unlink()
    frozen = dict(os.environ, BUF_CACHE_DIR=str(native_cache), BUF_PURIFIER_FROZEN="1")
    failed = subprocess.run(
        [original_tool, "build", "--timeout", "5s"],
        cwd=root,
        env=frozen,
        text=True,
        capture_output=True,
    )
    assert failed.returncode and "absent from the locked Nix cache" in failed.stderr, (
        failed
    )
    missing.symlink_to(target, target_is_directory=True)
    call(root, "buf", "dep", "update", env=env, expected=1)
    config_file = root / "buf.yaml"
    config_text = config_file.read_text()
    config_file.write_text(config_text + "\n# stale\n")
    assert (
        "Selection inputs changed"
        in call(root, "buf", "build", env=env, expected=1).stderr
    )
    config_file.write_text(config_text)
    subdir = root / "subdir"
    subdir.mkdir()
    call(subdir, "buf", "build", "..", env=env)
    call(temp, "buf", "build", str(root), env=env)
    companion = temp / "external.json"
    (root / "buf-purifier.lock.json").rename(companion)
    external = dict(
        env, BUF_PURIFIER_PROJECT=str(root), BUF_PURIFIER_LOCK=str(companion)
    )
    call(subdir, "buf", "build", "..", env=external)
    archive = Path(
        call(root, "buf-purifier", "bundle", "--lock", str(companion)).stdout.strip()
    )
    fake_gh = temp / "fake-gh"
    fake_gh.write_text(
        "#!/usr/bin/env python3\nimport pathlib,sys\n"
        "assert sys.argv[1:4]==['release','upload','v0.1.0']\n"
        "pathlib.Path(__file__).with_suffix('.uploaded').write_bytes(pathlib.Path(sys.argv[4]).read_bytes())\n"
    )
    fake_gh.chmod(0o755)
    call(
        root,
        "buf-purifier",
        "publish",
        "--lock",
        str(companion),
        "--tag",
        "v0.1.0",
        env=dict(os.environ, BUF_PURIFIER_GH=str(fake_gh)),
    )
    assert fake_gh.with_suffix(".uploaded").read_bytes() == archive.read_bytes()
    consumer = temp / "consumer"
    consumer.mkdir()
    with tarfile.open(archive) as tar:
        tar.extractall(consumer, filter="data")
    # The unmodified native consumer needs no purifier companion or wrapper.
    ordinary = dict(os.environ, BUF_CACHE_DIR=str(native_cache))
    subprocess.run(
        [original_tool, "build"], cwd=consumer / "project", env=ordinary, check=True
    )
    fallback = temp / "fallback"
    fallback.mkdir()
    assert "ordinary impure" in call(fallback, "buf", "--version").stderr
    fake = temp / "fake-native"
    fake.write_text("#!/bin/sh\nprintf native-out\nprintf native-err >&2\nexit 7\n")
    fake.chmod(0o755)
    python = next(
        str(Path(p) / "bin/python3")
        for p in refs.splitlines()
        if "-python3-" in p and p.endswith("-env")
    )
    direct = dict(
        os.environ,
        PYTHONPATH=str(sdk / "lib/buf-purifier"),
        BUF_PURIFIER_ORIGINAL=str(fake),
    )
    result = subprocess.run(
        [python, "-m", "buf_purifier.cli", "--native"],
        cwd=fallback,
        env=direct,
        text=True,
        capture_output=True,
    )
    assert (
        result.returncode == 7
        and result.stdout == "native-out"
        and result.stderr.endswith("native-err")
    ), result
print(
    "Native Buf build/generation/LSP, source edits, private caches, GC, source consumer and fallback passed"
)
