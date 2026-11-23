"""Build and verify an allowlisted immutable release, without live configuration."""

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory


def files(root):
    result = {}
    for path in sorted(root.rglob("*")):
        name = path.relative_to(root).as_posix()
        if "__pycache__" in path.parts or path.suffix == ".pyc":
            raise ValueError("Executable bytecode caches are not allowed in a release")
        if name == "release.json":
            continue
        if path.is_symlink() or path.is_junction():
            target = path.resolve(strict=True)
            if not target.is_relative_to(root):
                raise ValueError("Release link leaves artifact")
            result[name] = {"link": os.readlink(path)}
        elif path.is_file():
            result[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def verify(release):
    release = Path(release).resolve(strict=True)
    manifest = json.loads((release / "release.json").read_text(encoding="utf-8"))
    if (
        manifest.get("format") != 1
        or manifest.get("catalogue_schema") != 1
        or manifest.get("files") != files(release)
    ):
        raise ValueError("Release incompatible or modified")
    return manifest


def install(source, output):
    source, output = Path(source).resolve(strict=True), Path(output).absolute()
    verify(source)
    if output.exists() or output.is_symlink() or not output.parent.is_dir():
        raise ValueError("Install destination must be a new release directory")
    if source.is_relative_to(output) or output.resolve().is_relative_to(source):
        raise ValueError("Release copies cannot contain each other")

    def copy_directory(before, after):
        after.mkdir()
        for path in before.iterdir():
            destination = after / path.name
            if path.is_symlink() or path.is_junction():
                destination.symlink_to(os.readlink(path), target_is_directory=path.is_dir())
            elif path.is_dir():
                copy_directory(path, destination)
            else:
                shutil.copyfile(path, destination)

    with TemporaryDirectory(prefix="copilot-install-", dir=output.parent) as temporary:
        stage = Path(temporary) / "release"
        copy_directory(source, stage)
        verify(stage)
        stage.rename(output)


def build(source, output, *, local=False):
    from deploy.linux_runtime import inventory

    source, output = Path(source).resolve(strict=True), Path(output).absolute()
    if output.exists() or output.is_symlink() or not output.parent.is_dir():
        raise ValueError("Release output must be a new directory under an existing parent")
    if source.is_relative_to(output):
        raise ValueError("Release output cannot contain source")
    # Validate preparation inputs before invoking build tools. The development
    # lock is preserved separately; it is not the Linux runtime install contract.
    inventory(source)
    pnpm = shutil.which("pnpm")
    if not pnpm:
        raise ValueError("Pinned pnpm is required")
    environment = dict(os.environ)
    if local:
        environment.update(
            COPILOT_ENV="local-rehearsal",
            COPILOT_PANEL_ORIGIN="http://localhost:4100",
            COPILOT_STORE_ORIGIN="http://localhost:4000",
            COPILOT_AGENT_ORIGIN="http://localhost:8000",
        )
    else:
        environment["COPILOT_ENV"] = "production"
        if not all(environment.get(k) for k in ("COPILOT_PANEL_ORIGIN", "COPILOT_STORE_ORIGIN")):
            raise ValueError("Production public origins required")

    def run(*arguments, cwd=source):
        subprocess.run(
            [pnpm, "--config.verifyDepsBeforeRun=false", *map(str, arguments)],
            cwd=cwd,
            env=environment,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )

    with TemporaryDirectory(prefix="copilot-release-", dir=output.parent) as temporary:
        stage = Path(temporary)
        run("--filter", "@shopping-copilot/bridge", "build")
        run("--filter", "@shopping-copilot/panel", "build")
        # pnpm deploy updates its workspace dependency-state metadata. Give it
        # an isolated manifest-only workspace so builds never alter checkout
        # dependency state or copy checkout configuration into the artifact.
        dependency_source = stage / "dependency-source"
        for name in (
            "package.json",
            "pnpm-lock.yaml",
            "pnpm-workspace.yaml",
            "bridge/package.json",
            "store/package.json",
            "panel/package.json",
        ):
            destination = dependency_source / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / name, destination)
        run(
            "--filter",
            "@shopping-copilot/store",
            "exec",
            "tsc",
            "-p",
            "tsconfig.release.json",
            "--outDir",
            stage / "release",
        )
        # Use pnpm's frozen deployment path only in the isolated staging workspace.
        # Legacy deploy re-resolves even dev-only platform dependencies with --prod.
        run(
            "--filter",
            "@shopping-copilot/store",
            "deploy",
            "--prod",
            "--config.injectWorkspacePackages=true",
            "--offline",
            stage / "dependencies",
            cwd=dependency_source,
        )
        release = stage / "release"
        shutil.move(stage / "dependencies/node_modules", release / "store/node_modules")
        # Legacy pnpm deploy leaves a workspace self-link back to the checkout;
        # the compiled Storefront uses relative imports and never needs that link.
        self_link = release / "store/node_modules/.pnpm/node_modules/@shopping-copilot/store"
        if self_link.is_symlink():
            self_link.unlink()
        for directory in ("bridge/dist", "store/public", "panel/dist"):
            shutil.copytree(source / directory, release / directory)
        for directory in ("agent", "deploy"):
            for path in (source / directory).rglob("*.py"):
                if "tests" in path.parts or "__pycache__" in path.parts:
                    continue
                destination = release / path.relative_to(source)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, destination)
        for name in (
            "storefront-definition.json",
            "pyproject.toml",
            "requirements.lock",
            "deploy/linux-runtime.json",
            "deploy/requirements-linux.lock",
            "pnpm-lock.yaml",
            "deploy/Caddyfile",
            "deploy/Caddyfile.public",
            "deploy/shopping-copilot.service",
            "deploy/shopping-copilot-agent.service",
            "deploy/shopping-copilot-store.service",
            "deploy/shopping-copilot-proxy.service",
            "deploy/shopping-copilot-metadata.service",
            "deploy/shopping-copilot-host.target",
            "agent/lifecycle/waiting.html",
        ):
            shutil.copyfile(source / name, release / name)
        (release / "package.json").write_text('{"type":"module"}\n', encoding="utf-8")
        revision = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=source, text=True
        ).strip()
        manifest = {
            "format": 1,
            "catalogue_schema": 1,
            "source_commit": revision,
            "source_dirty": bool(
                subprocess.check_output(
                    ["git", "status", "--porcelain"], cwd=source, text=True
                ).strip()
            ),
            "local_rehearsal": local,
            "public_origins": {
                "panel": environment["COPILOT_PANEL_ORIGIN"],
                "store": environment["COPILOT_STORE_ORIGIN"],
                "agent": environment.get(
                    "COPILOT_AGENT_ORIGIN", environment["COPILOT_PANEL_ORIGIN"]
                ),
            },
            "files": files(release),
        }
        (release / "release.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
        verify(release)
        # Exclusive final name: a failed build never becomes a selectable release.
        release.rename(output)
    return manifest
