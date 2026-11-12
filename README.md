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

## Generated Java packages

Configure a native Java generator in `buf.gen.yaml`:

```yaml
version: v2
plugins:
  - protoc_builtin: java
    out: gen/java
```

Then select that output in the named builder:

```nix
pkgs.buf-purifier.buildBufProject {
  src = ./.;
  javaPackage = {
    groupId = "org.example";
    artifactId = "schemas";
    version = "1.0.0";
    sourceDirectory = "gen/java";
  };
}
```

This compiles the Java files emitted by native Buf into a JAR and exports
`projections.maven` and `projections.ivy`. Both views contain the generated
package and its transitive Protobuf Java runtime. Read their immutable,
identity-qualified versions from `projections.maven.catalog`; the package and
the source-built SDK runtime each receive their own Nix identity.

`packages.java-bindings` exposes the compiled package and its projections.
`packages.java-runtime` exposes the compiler-matched SDK runtime and its own
projections. The runtime is built from the same pinned Protobuf source as the
native generator, including its well-known types, schema resources and license.
Its source version, actual compiler version and Java runtime constants must
agree. The pinned JDK compiles Java 17 class files; checks execute the pinned JVM.
No Maven dependency resolution is needed to build these artifacts.

`sourceDirectory` must stay under `gen/` and match a native
`protoc_builtin: java` output. Configure Buf to emit required schema
dependencies; well-known types come from the SDK runtime. Identical generated
SDK types are reused only after checking their source bytes; inconsistent SDK
types and runtime class collisions fail. An empty selection preserves existing
outputs, including the schema resource views and optional Python package.

Native generation, source hashes, class hashes, JAR bytes and SDK provenance are
retained under each producer's `proof/`. Checks resolve both Maven and Ivy with
ordinary offline Gradle, round-trip generated messages across two real schema
revisions, and verify every generated class plus actual runtime class origins.
They reject missing runtime/local classes, a genuinely compiled schema
replacement, an actual older Protobuf runtime, inconsistent compiler SDKs,
incorrect output ownership and SDK class collisions. Fresh native captures and
direct producer/runtime/binding/projection/consumer rebuilds cover replay and
reproducibility.

## Credits

The purifier idea was inspired by nixcloud's
[cargo (libnix)](https://github.com/nixcloud/cargo).

### C++ bindings

`buildBufProject` accepts `cppPackage = { name = "proof"; version = "0.1.0"; };`.
It exposes `packages.cpp-bindings` and `projections.cpp`, with generated headers,
a shared library, pkg-config metadata and a CMake package (`proof::proof`).
The side producer runs the selected SDK's native `protoc` on the exported schema
closure, separately from the generators declared in `buf.gen.yaml`. The ordinary
Buf producer retains its build identity. Captured schemas matching SDK schemas
must have identical bytes; SDK message implementations come from the matching
Protobuf library. Captured project and dependency messages compile into the new
library. The package propagates its Protobuf SDK to Nix consumers.

Use `buildInputs = [ built.packages.cpp-bindings ];` with pkg-config, or
`find_package(proof 0.1.0 EXACT CONFIG REQUIRED)` and link `proof::proof` with
CMake. This is a C++ API, with its selected compiler/runtime ABI. It supplies no
C marshaling wrapper. `cpp-products.json` and `compile_commands.json` retain the
native generation, schema hashes, SDK versions and compiler commands.
