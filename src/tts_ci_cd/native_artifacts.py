"""Declarative Docker builds for native TTS runtime artifacts."""

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List

try:
    import tomllib
except ImportError:  # pragma: no cover - exercised on Python 3.10 and older
    import tomli as tomllib


class NativeManifestError(ValueError):
    """Raised when a native artifact manifest is invalid."""


_BUILD_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_COMMIT_SHA = re.compile(r"^[0-9a-fA-F]{7,40}$")


def _relative_path(value: str, field: str) -> Path:
    if not isinstance(value, str):
        raise NativeManifestError(f"{field} must be a relative path")
    path = Path(value)
    if not value or path.is_absolute() or ".." in path.parts:
        raise NativeManifestError(f"{field} must be a relative path")
    return path


class SourceSpec:
    def __init__(self, name: str, url: str, ref: str, ref_type: str) -> None:
        if not isinstance(url, str) or not url:
            raise NativeManifestError(f"source {name!r} has no URL")
        if ref_type not in {"commit", "tag"}:
            raise NativeManifestError(
                f"source {name!r} ref_type must be 'commit' or 'tag'"
            )
        if not isinstance(ref, str) or not ref:
            raise NativeManifestError(f"source {name!r} has no ref")
        if ref_type == "commit" and not _COMMIT_SHA.fullmatch(ref):
            raise NativeManifestError(
                f"source {name!r} must use a hexadecimal commit SHA"
            )
        if ref_type == "tag" and ref in {"HEAD", "main", "master"}:
            raise NativeManifestError(
                f"source {name!r} tag must not be a branch name"
            )
        self.name = name
        self.url = url
        self.ref = ref
        self.ref_type = ref_type


class OutputSpec:
    def __init__(self, source: str, destination: str) -> None:
        if not source or not destination:
            raise NativeManifestError("each output needs from and to")
        self.source = source
        self.destination = _relative_path(destination, "output destination")


class PackageSpec:
    def __init__(self, project: str, staging: str) -> None:
        self.project = _relative_path(project, "package project")
        self.staging = _relative_path(staging, "package staging")


class BuildSpec:
    def __init__(
        self,
        build_id: str,
        source: str,
        platform: str,
        dockerfile: str,
        context: str,
        outputs: List[OutputSpec],
        package: PackageSpec,
        ssh: bool,
        build_args: Dict[str, str],
    ) -> None:
        if not _BUILD_ID.fullmatch(build_id):
            raise NativeManifestError(
                "each build needs an id containing only letters, numbers, "
                "periods, underscores, or hyphens"
            )
        if not platform:
            raise NativeManifestError(f"build {build_id!r} needs a platform")
        if not dockerfile or not context:
            raise NativeManifestError(
                f"build {build_id!r} needs a Dockerfile and build context"
            )
        self.id = build_id
        self.source = source
        self.platform = platform
        self.dockerfile = _relative_path(dockerfile, "dockerfile")
        self.context = _relative_path(context, "build context")
        self.outputs = outputs
        self.package = package
        self.ssh = ssh
        self.build_args = build_args


class NativeArtifactManifest:
    """Validated source and build matrix for native artifacts."""

    def __init__(
        self,
        path: Path,
        sources: Dict[str, SourceSpec],
        builds: List[BuildSpec],
    ) -> None:
        self.path = path
        self.sources = sources
        self.builds = builds

    @classmethod
    def load(cls, path: Path) -> "NativeArtifactManifest":
        with path.open("rb") as stream:
            raw = tomllib.load(stream)

        if raw.get("schema_version") != 1:
            raise NativeManifestError("schema_version must be 1")

        raw_sources = raw.get("sources", {})
        if not isinstance(raw_sources, dict) or not raw_sources:
            raise NativeManifestError("manifest must declare at least one source")
        sources = {
            name: SourceSpec(
                name,
                values.get("url", ""),
                values.get("ref", ""),
                values.get("ref_type", "commit"),
            )
            for name, values in raw.get("sources", {}).items()
        }
        raw_builds = raw.get("builds", [])
        if not isinstance(raw_builds, list):
            raise NativeManifestError("builds must be an array")
        builds = []
        build_ids = set()
        for values in raw_builds:
            source_name = values.get("source", "")
            if source_name not in sources:
                raise NativeManifestError(
                    f"build {values.get('id')!r} references unknown source"
                )
            build_id = values.get("id", "")
            if build_id in build_ids:
                raise NativeManifestError(f"duplicate build id {build_id!r}")
            build_ids.add(build_id)
            outputs = [
                OutputSpec(item.get("from", ""), item.get("to", ""))
                for item in values.get("outputs", [])
            ]
            if not outputs:
                raise NativeManifestError(
                    f"build {build_id!r} needs at least one output"
                )
            package_values = values.get("package", {})
            package = PackageSpec(
                package_values.get("project", ""),
                package_values.get("staging", ""),
            )
            if not package.project or not package.staging:
                raise NativeManifestError(
                    f"build {values.get('id')!r} needs a package project and staging path"
                )
            builds.append(
                BuildSpec(
                    build_id,
                    source_name,
                    values.get("platform", ""),
                    values.get("dockerfile", ""),
                    values.get("context", ""),
                    outputs,
                    package,
                    bool(values.get("ssh", False)),
                    {
                        str(key): str(value)
                        for key, value in values.get("build_args", {}).items()
                    },
                )
            )
        if not builds:
            raise NativeManifestError("manifest must declare at least one build")
        return cls(path, sources, builds)


class NativeArtifactBuilder:
    """Build and stage a manifest entry using Docker BuildKit."""

    def __init__(self, runner=subprocess.run) -> None:
        self.runner = runner

    def build(
        self,
        manifest: NativeArtifactManifest,
        spec: BuildSpec,
    ) -> Path:
        source = manifest.sources[spec.source]
        root = manifest.path.parent
        context = (root / spec.context).resolve()
        dockerfile = (root / spec.dockerfile).resolve()
        image = f"tts-native-{spec.id}".lower().replace("_", "-")

        command = [
            "docker",
            "buildx",
            "build",
            "--load",
            "--platform",
            spec.platform,
            "--file",
            str(dockerfile),
            "--tag",
            image,
            "--build-arg",
            f"SOURCE_URL={source.url}",
            "--build-arg",
            f"SOURCE_REF={source.ref}",
        ]
        for name, value in spec.build_args.items():
            command.extend(["--build-arg", f"{name}={value}"])
        if spec.ssh:
            ssh_socket = os.environ.get("SSH_AUTH_SOCK")
            command.extend(["--ssh", f"default={ssh_socket}" if ssh_socket else "default"])
            known_hosts = Path.home() / ".ssh/known_hosts"
            if known_hosts.is_file():
                command.extend(
                    [
                        "--secret",
                        f"id=ssh_known_hosts,src={known_hosts}",
                    ]
                )
        command.append(str(context))
        self.runner(command, check=True)

        package_project = (root / spec.package.project).resolve()
        staging = package_project / spec.package.staging
        if staging.exists():
            shutil.rmtree(staging)
        staging.mkdir(parents=True)

        container = self._create_container(image, spec.platform)
        try:
            for output in spec.outputs:
                destination = staging / output.destination
                destination.parent.mkdir(parents=True, exist_ok=True)
                self.runner(
                    [
                        "docker",
                        "cp",
                        f"{container}:{output.source}",
                        str(destination),
                    ],
                    check=True,
                )
        finally:
            self.runner(["docker", "rm", container], check=True)

        manifest_path = staging / "manifest.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "build_id": spec.id,
                    "source_url": source.url,
                    "source_ref": source.ref,
                    "source_ref_type": source.ref_type,
                    "platform": spec.platform,
                },
                indent=2,
            )
            + "\n"
        )
        return staging

    def _create_container(self, image: str, platform: str) -> str:
        result = self.runner(
            ["docker", "create", "--platform", platform, image],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
