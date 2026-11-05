# buf-purifier

Locked, Nix-resolved Protobuf modules for Buf.

## Quickstart

```sh
nix shell 'github:nix-purifiers/buf-purifier'
buf-purifier lock
buf build
buf lint
buf generate
```

Buf's native resolver writes `buf.lock`. Nix supplies its digest-checked modules
through a private cache whose module sources are readonly. Your workspace remains
mutable, and source edits do not require relocking.

Commit `buf.lock` and `buf-purifier.lock.json`. After changing dependency selection:

```sh
buf-purifier lock --update
```

The wrapper warns and uses ordinary, impure Buf when there is no purifier lock.
Invalid or stale locks fail. Install the integration through your normal Nix
configuration if you want it available beyond the temporary shell.

## Development

```sh
buf format -w
buf-purifier exec -- your-editor
buf-purifier prefetch
```

Buf's language server uses the same locked modules. Dependency cache misses fail
before registry fetching; ordinary root commands retain their network access.
Private writable lock files and tool caches use `XDG_CACHE_HOME`.
The working tree's `.buf-purifier` retains the prepared SDK profile.

The initial integration supports v2 workspaces, public BSR modules with b5 digests, and
`protoc_builtin` generators supplied by the Nix Protobuf compiler. Remote and
external plugins need additional Nix tool providers. Generated output stays in
your normal working-tree directories.

`--input path` tracks extra selection files. Use `--project` and `--lock` for an
external companion; wrappers accept `BUF_PURIFIER_PROJECT` and
`BUF_PURIFIER_LOCK`. Prepared sessions retain their dependency and SDK closures
for garbage collection.

## Publication

```sh
buf-purifier bundle
buf-purifier publish --tag v0.1.0
```

The reproducible source archive contains native Buf configuration and schemas.
Ordinary Buf can consume it. Publication uploads the exact realized archive to
an existing GitHub release.

## Building with Nix

The overlay provides a named builder:

```nix
pkgs.buf-purifier.buildBufProject {
  src = ./.;
}
```

It exposes evaluation-known `packages`, `tests`, `release` and `fetches`. The
project output includes the native descriptor image and generated sources.

## Resource projections

`buildBufProject` exports the workspace and its imported schemas through native
`buf export` into `schemas/`. Both the result and `packages.project` expose
`projections.resources`, `projections.web`, and `projections.java-resources`.
Use `.directory` as a protoc import root, `.documentRoot` for static serving,
and `.classPath` for a Java resource JAR. Native import paths are preserved;
source/configuration files outside the schema export are excluded.

Pass `schemaEntrypoints = [ "proof/v1/proof.proto" ];` to record explicit
Protobuf entrypoints in the catalog. Buf resolves the locked schema dependencies;
the shared resource adapter itself does not infer an import closure. Built-in
Protobuf well-known types still come from the selected compiler/runtime SDK.
The check compiles the exported workspace plus imported protovalidate/Envoy
schemas with ordinary protoc and round-trips generated Python messages using
the same pinned SDK. Generated sources remain native outputs; no installable
language package or runtime-independent binding publication is claimed.

## Generated Python packages

Pass `pythonPackage = { name = "proof-schemas"; version = "1.0.0"; };`
to `buildBufProject` to generate Python bindings for the exported schema tree,
including imported non-well-known schemas. This creates a real wheel with
namespace packages and an exact dependency on the selected SDK's Protobuf
Python runtime. The `projections.python` repository contains the projected wheel
with its immutable Nix version plus the native runtime wheel. Compiler, schema
closure, wheel builder and runtime derivations all participate in its identity.

`packages.python-bindings` is the ordinary Nix Python package; use
`projections.python` with native pip, or its catalog for a downstream purifier.
For example, `python -m pip install --no-index --find-links /nix/store/...-python-projection proof-schemas`
installs the generated package and its supplied runtime without downloads.
The existing resource/Java schema views and native Buf outputs remain available.

The check builds imported protovalidate/Envoy schemas, makes the wheel, and
installs it with ordinary pip despite an available competing Protobuf99 wheel.
It verifies the exact runtime version, installed module/extension origins and
pip's selected wheel URLs/digests, then round-trips a generated message. This
covers the selected pinned Python/compiler/runtime SDK; it does not promise
other Python ABIs, Java bindings, remote generator plugins or arbitrary schema
namespaces that overlap other installed packages.

## Credits

The purifier idea was inspired by nixcloud's
[cargo (libnix)](https://github.com/nixcloud/cargo).
