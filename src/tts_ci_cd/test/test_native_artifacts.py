from pathlib import Path

import pytest

from tts_ci_cd.native_artifacts import (
    NativeArtifactBuilder,
    NativeArtifactManifest,
    NativeManifestError,
)


def test_manifest_loads_source_and_build_matrix(tmp_path: Path):
    manifest_path = tmp_path / "tts-build.toml"
    manifest_path.write_text(
        """
schema_version = 1

[sources.ssim]
url = "ssh://git@github.jpl.nasa.gov/example/ssim.git"
ref = "0123456789abcdef"

[[builds]]
id = "rhel-fsw105"
source = "ssim"
platform = "linux/amd64"
dockerfile = "native/Dockerfile.rhel"
context = "."
ssh = true
build_args = { BUILD_JOBS = "2" }

[[builds.outputs]]
from = "/opt/ssim/build/ssim"
to = "build/ssim"

[builds.package]
project = "native/rhel-package"
staging = "src/eurc_py_ssim_bin_rhel/runtime"
"""
    )

    manifest = NativeArtifactManifest.load(manifest_path)

    assert manifest.sources["ssim"].ref == "0123456789abcdef"
    assert manifest.builds[0].package.project == Path("native/rhel-package")
    assert manifest.builds[0].outputs[0].destination == Path("build/ssim")


def test_manifest_rejects_build_without_immutable_source_ref(tmp_path: Path):
    manifest_path = tmp_path / "tts-build.toml"
    manifest_path.write_text(
        """
schema_version = 1
[sources.ssim]
url = "https://github.example/ssim.git"
ref = "main"
"""
    )

    with pytest.raises(NativeManifestError, match="commit SHA"):
        NativeArtifactManifest.load(manifest_path)


def test_manifest_accepts_an_explicit_tag_ref(tmp_path: Path):
    manifest_path = tmp_path / "tts-build.toml"
    manifest_path.write_text(
        """
schema_version = 1

[sources.ssim]
url = "https://github.example/ssim.git"
ref = "v1.2.3"
ref_type = "tag"

[[builds]]
id = "linux"
source = "ssim"
platform = "linux/amd64"
dockerfile = "Dockerfile"
context = "."

[[builds.outputs]]
from = "/opt/ssim/bin/ssim"
to = "bin/ssim"

[builds.package]
project = "package"
staging = "runtime"
"""
    )

    manifest = NativeArtifactManifest.load(manifest_path)

    assert manifest.sources["ssim"].ref_type == "tag"


def test_manifest_rejects_incomplete_build(tmp_path: Path):
    manifest_path = tmp_path / "tts-build.toml"
    manifest_path.write_text(
        """
schema_version = 1

[sources.ssim]
url = "https://github.example/ssim.git"
ref = "0123456789abcdef"

[[builds]]
id = "rhel"
source = "ssim"
platform = "linux/amd64"
dockerfile = "native/Dockerfile"
context = "."

[builds.package]
project = "native/package"
staging = "runtime"
"""
    )

    with pytest.raises(NativeManifestError, match="at least one output"):
        NativeArtifactManifest.load(manifest_path)


def test_manifest_rejects_paths_outside_repository(tmp_path: Path):
    manifest_path = tmp_path / "tts-build.toml"
    manifest_path.write_text(
        """
schema_version = 1

[sources.ssim]
url = "https://github.example/ssim.git"
ref = "0123456789abcdef"

[[builds]]
id = "rhel"
source = "ssim"
platform = "linux/amd64"
dockerfile = "../Dockerfile"
context = "."

[[builds.outputs]]
from = "/opt/ssim"
to = "runtime"

[builds.package]
project = "native/package"
staging = "runtime"
"""
    )

    with pytest.raises(NativeManifestError, match="relative"):
        NativeArtifactManifest.load(manifest_path)


def test_builder_uses_buildkit_ssh_and_stages_each_output(tmp_path: Path):
    manifest_path = tmp_path / "tts-build.toml"
    manifest_path.write_text(
        """
schema_version = 1

[sources.ssim]
url = "git@github.example:ssim.git"
ref = "0123456789abcdef"

[[builds]]
id = "rhel"
source = "ssim"
platform = "linux/amd64"
dockerfile = "Dockerfile"
context = "."
ssh = true

[[builds.outputs]]
from = "/opt/ssim/bin/ssim"
to = "bin/ssim"

[builds.package]
project = "package"
staging = "runtime"
"""
    )
    (tmp_path / "Dockerfile").write_text("FROM scratch\n")
    manifest = NativeArtifactManifest.load(manifest_path)
    calls = []

    class Result:
        stdout = "container-id\n"

    def runner(command, **kwargs):
        calls.append(command)
        if command[:2] == ["docker", "create"]:
            return Result()
        if command[:2] == ["docker", "cp"]:
            destination = Path(command[-1])
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text("binary")
        return Result()

    staging = NativeArtifactBuilder(runner).build(manifest, manifest.builds[0])

    assert (staging / "bin/ssim").read_text() == "binary"
    assert "--ssh" in calls[0]
    assert (staging / "manifest.json").exists()
