"""Declarative Docker builds for native TTS runtime artifacts."""

import json
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


class SourceSpec:
    def __init__(self, name: str, url: str, ref: str) -> None:
        if not url:
            raise NativeManifestError(f"source {name!r} has no URL")
        if not ref or ref in {"main", "master", "HEAD"}:
            raise NativeManifestError(
                f"source {name!r} must use an immutable ref"
            )
        self.name = name
        self.url = url
        self.ref = ref


class OutputSpec:
    def __init__(self, source: str, destination: str) -> None:
        if not source or not destination:
            raise NativeManifestError("each output needs from and to")
        self.source = source
        self.destination = Path(destination)


class PackageSpec:
    def __init__(self, project: str, staging: str) -> None:
        self.project = Path(project)
        self.staging = Path(staging)


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
        self.id = build_id
        self.source = source
        self.platform = platform
        self.dockerfile = Path(dockerfile)
        self.context = Path(context)
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

        sources = {
            name: SourceSpec(
                name,
                values.get("url", ""),
                values.get("ref", ""),
            )
            for name, values in raw.get("sources", {}).items()
        }
        builds = []
        for values in raw.get("builds", []):
            source_name = values.get("source", "")
            if source_name not in sources:
                raise NativeManifestError(
                    f"build {values.get('id')!r} references unknown source"
                )
            outputs = [
                OutputSpec(item.get("from", ""), item.get("to", ""))
                for item in values.get("outputs", [])
            ]
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
                    values.get("id", ""),
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
            command.extend(["--ssh", "default"])
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
