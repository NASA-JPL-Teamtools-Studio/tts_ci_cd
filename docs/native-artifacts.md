# Native Artifact Builds in TTS

This document describes the common TTS workflow for building and publishing
compiled runtimes alongside Python packages. It is intended for a repository
that owns a C, C++, or other native program which must be built for a
specific operating system, architecture, compiler, or flight-software
runtime.

The design keeps three responsibilities separate:

```text
tts-build.toml
    Declares sources, build variants, extracted files, and package projects.

Dockerfile
    Defines the reproducible native build environment and build procedure.

tts-deploy-lib
    Orchestrates Docker, stages outputs, builds Python distributions, and
    publishes them. This CLI is used whether the deployed TTS-style library
    includes native artifacts or is pure Python.
```

A `Makefile` is optional. It can be called by the Dockerfile. The Dockerfile
itself is the primary native build contract with TTS core, while
`tts-build.toml` is the TTS artifact declaration and deployment contract.

## When to Use This Workflow

Use the native-artifact workflow when a repository needs to distribute:

- A standalone native executable alongside a Python wrapper.
- A runtime built for a target userspace, such as RHEL-compatible Linux.
- Several incompatible binaries for different FSW, compiler, or platform
  variants.
- A native resource tree that must remain adjacent to the executable.

Do not use this workflow merely because a Python package contains a small C
extension. A conventional Python extension should normally be built by the
package's PEP 517 build backend as part of its ordinary wheel.

## Repository Requirements

A Python-only repository needs its normal `pyproject.toml`, source tree, and
tests. A repository with a separately packaged native runtime adds:

```text
project/
  pyproject.toml
  tts-build.toml
  src/
  tests/
  native/
    Dockerfile.rhel
    runtime-package/
      pyproject.toml
```

The repository must provide:

1. A `tts-build.toml` manifest.
2. A repository-owned Dockerfile for each native build environment.
3. A Python package project that declares and includes the staged runtime
   files.
4. A pinned Git commit or explicitly declared Git tag for every source used
   in a release build.
5. Docker BuildKit, with `buildx`, available to the developer or CI runner.

The native source can live in another repository or in the same repository as
the Python wrapper. A Makefile is useful when it already exists, but adding
one solely to satisfy TTS is unnecessary.

## Manifest

The manifest is the release-facing description of the native artifacts:

```toml
schema_version = 1  # Manifest format understood by tts-deploy-lib.

[sources.simulator]  # Named source repository.
url = "git@github.jpl.nasa.gov:team/simulator.git"  # C/C++ source URL.
ref = "0123456789abcdef0123456789abcdef01234567"  # Source revision.
# Use ref_type = "tag" for a release tag such as v1.2.3.

[[builds]]  # One compiled native variant.
id = "rhel-fsw105"  # Unique identity for this build variant.
source = "simulator"  # Which source entry above this build uses.
platform = "linux/amd64"  # Docker Buildx target platform.
dockerfile = "native/Dockerfile.rhel"  # Toolchain and native build recipe.
context = "."  # Directory sent to Docker as the build context.
ssh = true  # Forward the developer's SSH agent to Docker BuildKit.
build_args = { BUILD_JOBS = "2" }  # Additional Docker ARG values.

[[builds.outputs]]  # A file or directory copied from the image.
from = "/opt/simulator/bin/simulator"  # Path inside the container.
to = "bin/simulator"  # Path inside the package staging directory.

[[builds.outputs]]  # A second output, such as runtime resources.
from = "/opt/simulator/share/xml"  # Path inside the container.
to = "share/xml"  # Path inside the package staging directory.

[builds.package]  # Python package containing the native files.
project = "native/runtime-package"  # Path to its pyproject.toml.
staging = "src/simulator_runtime"  # Directory where outputs are staged.
```

### Sources

Each source has a Git URL and a reference. By default, `ref` is a
hexadecimal commit SHA. A repository may explicitly use a release tag with
`ref_type = "tag"`:

```toml
[sources.simulator]
url = "git@github.jpl.nasa.gov:team/simulator.git"
ref = "v1.2.3"
ref_type = "tag"
```

Branch names, `HEAD`, and an untyped tag-like value are rejected. A commit is
the strongest reproducibility guarantee. Tags are accepted for projects whose
release process treats tags as immutable, but the resolved commit should be
recorded in package provenance because Git tags can technically be moved.

The source URL may point to a separate GHE repository or back to the current
repository when the compiled code is kept in the same repository.

### Builds

Each `[[builds]]` entry is an isolated native variant. The `id` must be
unique within the manifest. Use a separate build entry for materially
different binaries, such as:

```text
rhel-fsw105
rhel-fsw106
macos-arm64
linux-x86_64-debug
```

Each variant should have a distinct native package identity. Incompatible
binaries should not be placed into one package under the same name and
version.

### Outputs

Outputs map paths inside the built Docker image to paths inside the native
package's staging directory:

```toml
[[builds.outputs]]
from = "/opt/simulator/bin/simulator"
to = "bin/simulator"
```

Declare resource directories as well as executables when the runtime needs
configuration, dictionaries, schemas, or other files at execution time.

### Package

`package.project` points to a Python project relative to the manifest. The
`package.staging` directory is where `tts-deploy-lib` places extracted files
before building the native distribution.

The native package should have a distinct distribution name, for example:

```text
tts-eurc-py-ssim
tts-eurc-py-ssim-bin-rhel
```

The wrapper can depend on the native distribution through a Python extra.

## Dockerfile Contract

The Dockerfile is repository-owned. It should:

- Select the target base image and architecture.
- Install the compiler, linker, SDK, and runtime development libraries.
- Clone or access the source using `SOURCE_URL` and `SOURCE_REF`.
- Build the native program.
- Leave declared output files at stable paths in the image.

The common implementation passes these build arguments:

```text
SOURCE_URL
SOURCE_REF
```

Additional `build_args` from the manifest are passed through as Docker build
arguments. For example, `BUILD_JOBS` or `FSW_VERSION` may be used by the
Dockerfile.

A Makefile can remain the native project's internal build interface:

```dockerfile
RUN make -C /opt/simulator BUILD_JOBS="${BUILD_JOBS}"
```

However, `tts-deploy-lib` does not need to know whether the Dockerfile calls
Make, CMake, Meson, or a compiler directly.

## Local Development

Build and stage native outputs without publishing anything:

```bash
tts-deploy-lib \
  --build-only \
  --native-manifest tts-build.toml
```

`--build-only` requires `--native-manifest` and no deployment environment. It
builds each native variant with Docker and stages the declared files into
the native package project. It does not upload to Artifactory or PyPI.

For an SSH source, the developer needs an active SSH agent:

```bash
ssh-add -l
```

The local build uses the same Dockerfile and manifest as the release build.
This is useful for validating the C layer before running a full package
deployment.

## Release Deployment

Build the wrapper and native distributions, then publish them together:

```bash
tts-deploy-lib staging --native-manifest tts-build.toml
```

The deployment flow:

1. Checks repository hygiene.
2. Builds the wrapper distribution.
3. Builds each declared Docker native variant.
4. Extracts and stages each variant's outputs.
5. Builds each native Python distribution.
6. Uploads all distributions to the selected environment.

The native source reference and type, resolved source commit when
available, target platform, build ID, and output metadata should be recorded
with the resulting package provenance.

## Compiled Code in the Same Repository

There are three distinct cases:

### Python extension

Build the extension through the normal Python package backend. The extension
is part of the ordinary wheel and does not need a separate native manifest
unless it requires a special external runtime or build matrix.

### Standalone executable

Point the manifest source at the same repository and pin the release
commit or explicitly declare a release tag with `ref_type = "tag"`.
The Dockerfile checks out that source reference and builds the executable in
environment.

### Committed binaries

Avoid committing locally built binaries as source files. They make review,
reproducibility, platform support, and source-to-binary traceability harder.
Publish them as generated package artifacts with checksums and provenance.

## Security and Reproducibility

SSH credentials are forwarded to BuildKit only when `ssh = true`. They must
not be placed in Docker `ARG` or `ENV` values. For HTTPS authentication,
Docker BuildKit secrets should be used by the repository-owned Dockerfile.

Release builds should use:

- An immutable source commit, or an explicitly declared release tag whose
  resolved commit is recorded when available.
- A pinned or auditable base image.
- A declared target platform.
- A clean Git checkout.
- Separate package identities for incompatible binaries.
- Generated checksums and provenance metadata.

## Future Workspace Builds

The release path clones a pinned Git commit inside Docker. A future
development-only mode may build the current local workspace, including
uncommitted changes, without changing the release contract:

```toml
[sources.simulator]
mode = "workspace"
```

Workspace builds should be clearly identified as non-reproducible and should
not be accepted for a normal deployment without an explicit override. Until
that mode is implemented, local native iteration should use a temporary
commit or a local source-specific Docker development workflow.
