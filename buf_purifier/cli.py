import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from .capture import capture
from .common import load, run
from .runtime import prepare


def locate(project=None, companion=None, start=None):
    root = Path(
        project or os.environ.get("BUF_PURIFIER_PROJECT", start or Path.cwd())
    ).resolve()
    external = companion or os.environ.get("BUF_PURIFIER_LOCK")
    if external:
        return root, Path(external).resolve()
    if project or os.environ.get("BUF_PURIFIER_PROJECT"):
        return root, root / "buf-purifier.lock.json"
    for directory in [root, *root.parents]:
        if (directory / "buf-purifier.lock.json").exists():
            return directory, directory / "buf-purifier.lock.json"
    return root, root / "buf-purifier.lock.json"


def main_impl():
    args = sys.argv[1:]
    if args and args[0] == "--native":
        rest = args[1:]
        start = None
        if (
            len(rest) > 1
            and rest[0]
            in (
                "build",
                "lint",
                "breaking",
                "generate",
                "export",
                "format",
                "ls-files",
                "stats",
            )
            and not rest[1].startswith("-")
            and Path(rest[1]).is_dir()
        ):
            start = Path(rest[1])
        root, companion = locate(start=start)
        if not companion.exists():
            print(
                "buf-purifier: no lockfile; using ordinary impure buf", file=sys.stderr
            )
            os.execv(
                os.environ["BUF_PURIFIER_ORIGINAL"],
                [os.environ["BUF_PURIFIER_ORIGINAL"], *rest],
            )
        if rest[:2] in (["dep", "update"], ["dep", "prune"]) or rest[:2] == [
            "registry",
            "cc",
        ]:
            raise ValueError(
                "Change the native configuration and run buf-purifier lock --update for dependency selection"
            )
        if any(
            a in ("--config", "--template")
            or a.startswith(("--config=", "--template="))
            for a in rest
        ):
            raise ValueError(
                "Use the tracked native configuration files with a locked workspace"
            )
        env = prepare(root, companion)
        os.execve(
            os.environ["BUF_PURIFIER_ORIGINAL"],
            [os.environ["BUF_PURIFIER_ORIGINAL"], *rest],
            env,
        )
    parser = argparse.ArgumentParser(description="Lock native Buf modules into Nix")
    parser.add_argument(
        "action", choices=["lock", "prefetch", "exec", "bundle", "publish"]
    )
    parser.add_argument("--project", type=Path)
    parser.add_argument("--lock", type=Path)
    parser.add_argument("--update", action="store_true")
    parser.add_argument("--input", action="append", default=[])
    parser.add_argument("--tag")
    opts, remaining = parser.parse_known_args(args)
    root, companion = locate(opts.project, opts.lock)
    if opts.action == "lock":
        if remaining:
            parser.error("Unexpected arguments: " + " ".join(remaining))
        capture(root, companion, opts.update, opts.input)
    elif opts.action in ("prefetch", "exec"):
        env = prepare(root, companion)
        if opts.action == "exec":
            if remaining and remaining[0] == "--":
                remaining = remaining[1:]
            if not remaining:
                parser.error("exec requires a command")
            env.update(BUF_PURIFIER_PROJECT=str(root), BUF_PURIFIER_LOCK=str(companion))
            os.execvpe(remaining[0], remaining, env)
    else:
        load(root, companion)
        expression = (
            "import "
            + json.dumps(
                os.environ["BUF_PURIFIER_SDK"] + "/lib/buf-purifier/nix/release.nix"
            )
            + " {root="
            + json.dumps(str(root))
            + ";lockFile="
            + json.dumps(str(companion))
            + ";}"
        )
        result = run(
            [
                "nix",
                "build",
                "--impure",
                "--expr",
                expression,
                "--no-link",
                "--print-out-paths",
            ]
        )
        artifact = Path(result.strip()) / "buf-source.tar.gz"
        if opts.action == "bundle":
            print(artifact)
        else:
            if not opts.tag:
                parser.error("publish requires --tag")
            subprocess.run(
                [
                    os.environ.get("BUF_PURIFIER_GH", "gh"),
                    "release",
                    "upload",
                    opts.tag,
                    str(artifact),
                    "--clobber",
                ],
                cwd=root,
                check=True,
            )


def main():
    try:
        main_impl()
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as error:
        print("buf-purifier: " + str(error), file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
