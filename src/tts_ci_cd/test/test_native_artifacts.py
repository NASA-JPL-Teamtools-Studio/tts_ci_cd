from pathlib import Path

import pytest

from tts_ci_cd.native_artifacts import (
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

    with pytest.raises(NativeManifestError, match="immutable"):
        NativeArtifactManifest.load(manifest_path)
