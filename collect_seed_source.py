"""Thu gom cac file can thiet de chay seed_data.py vao seed_source/."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CollectedFile:
    source: Path
    destination: Path


ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT = ROOT / "seed_source"
SEED_DATA = ROOT / "seed_data.py"
BACKEND_APP = ROOT / "backend" / "app"


def _module_path(module: str) -> Path | None:
    """Resolve mot module app.* thanh file trong backend/app."""
    if not module.startswith("app"):
        return None
    relative = Path(*module.split("."))
    candidate = ROOT / "backend" / f"{relative}.py"
    if candidate.is_file():
        return candidate
    package_init = ROOT / "backend" / relative / "__init__.py"
    return package_init if package_init.is_file() else None


def _imported_app_modules(path: Path) -> set[Path]:
    """Lay cac module app.* duoc import truc tiep, ke ca import trong ham."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[Path] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = (node.module,)
        else:
            continue
        for module in names:
            resolved = _module_path(module)
            if resolved is not None:
                modules.add(resolved)
    return modules


def _resolve_app_dependencies() -> set[Path]:
    """Theo import app.* tu seed_data.py de khong bo sot module cua pipeline."""
    pending = [SEED_DATA]
    visited: set[Path] = set()
    dependencies: set[Path] = set()

    while pending:
        current = pending.pop()
        if current in visited:
            continue
        visited.add(current)
        for dependency in _imported_app_modules(current):
            if dependency not in dependencies:
                dependencies.add(dependency)
                pending.append(dependency)
    return dependencies


def _collect_files() -> list[CollectedFile]:
    files: list[CollectedFile] = [
        CollectedFile(SEED_DATA, Path("seed_data.py")),
        CollectedFile(ROOT / "seed.bat", Path("seed.bat")),
        CollectedFile(ROOT / "backend" / "requirements.txt", Path("backend") / "requirements.txt"),
        CollectedFile(ROOT / "backend" / ".env.example", Path("backend") / ".env.example"),
    ]

    for source in sorted((ROOT / "data" / "seed").glob("*")):
        if source.is_file():
            files.append(CollectedFile(source, Path("data") / "seed" / source.name))

    for source in sorted(_resolve_app_dependencies() | set((BACKEND_APP / "indexing").glob("*_step.py"))):
        files.append(CollectedFile(source, source.relative_to(ROOT)))

    unique: dict[Path, CollectedFile] = {}
    for item in files:
        if item.source.is_file():
            unique[item.destination] = item
    return sorted(unique.values(), key=lambda item: item.destination.as_posix())


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect(output: Path, *, clean: bool, dry_run: bool) -> int:
    files = _collect_files()
    print(f"Nguon: {ROOT}")
    print(f"Dich:  {output}")
    print(f"So file: {len(files)}")

    if dry_run:
        for item in files:
            print(f"  {item.source.relative_to(ROOT)} -> {item.destination}")
        return len(files)

    if clean and output in (ROOT, ROOT.parent):
        raise ValueError("--clean chi duoc dung voi thu muc output rieng, khong phai repository.")

    if clean and output.exists():
        for child in output.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    output.mkdir(parents=True, exist_ok=True)

    manifest: list[dict[str, object]] = []
    for item in files:
        destination = output / item.destination
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item.source, destination)
        manifest.append(
            {
                "source": item.source.relative_to(ROOT).as_posix(),
                "path": item.destination.as_posix(),
                "bytes": destination.stat().st_size,
                "sha256": _sha256(destination),
            }
        )

    manifest_path = output / "MANIFEST.json"
    manifest_path.write_text(
        json.dumps({"generated_from": ROOT.name, "files": manifest}, ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    print(f"Da thu gom {len(files)} file vao {output}.")
    print(f"Manifest: {manifest_path}")
    return len(files)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Thu gom file lien quan den seed data vao seed_source."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Thu muc dich (mac dinh: seed_source).",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Xoa noi dung cu trong thu muc dich truoc khi thu gom.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Chi liet ke file, khong sao chep.",
    )
    args = parser.parse_args()
    collect(args.output.resolve(), clean=args.clean, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
