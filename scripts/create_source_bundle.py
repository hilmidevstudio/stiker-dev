"""Create a source-only StickerDrop ZIP without local secrets or build artifacts.

Run from the project root:
    python scripts/create_source_bundle.py

An optional --output path can be supplied. The output ZIP is created outside the
project tree by default, so it cannot accidentally include itself.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path, PurePosixPath
import zipfile


EXCLUDED_DIRECTORIES = {
    ".git", ".venv", "venv", "env", "node_modules", "build", "dist",
    ".dart_tool", ".gradle", "__pycache__", ".pytest_cache", ".mypy_cache",
    ".ruff_cache", ".idea", ".vscode-test", "downloads", "temp",
}
EXCLUDED_FILENAMES = {
    ".env", "local.properties", "key.properties", "credentials.json",
    "secrets.json",
}
EXCLUDED_SUFFIXES = {
    ".jks", ".keystore", ".p12", ".pfx", ".pem", ".db", ".sqlite",
    ".sqlite3", ".pyc", ".pyo",
}


def should_include(relative_path: Path | PurePosixPath) -> bool:
    """Return whether a project-relative file is safe/useful to bundle."""
    path = PurePosixPath(relative_path.as_posix())
    parts = path.parts
    name = path.name.lower()

    if any(part in EXCLUDED_DIRECTORIES for part in parts[:-1]):
        return False
    if name in EXCLUDED_FILENAMES:
        return False
    if name.endswith(".env") or (name.startswith(".env.") and name != ".env.example"):
        return False
    if PurePosixPath(name).suffix in EXCLUDED_SUFFIXES:
        return False
    return True


def create_source_bundle(root: Path, output: Path) -> tuple[int, int]:
    root = root.resolve()
    output = output.resolve()
    if not root.is_dir():
        raise ValueError(f"Project root does not exist: {root}")
    if output == root or root in output.parents:
        raise ValueError("Output ZIP must be outside the project root.")

    files = []
    for current, directory_names, file_names in os.walk(root):
        # Prune generated/secret directories before descending into them.
        directory_names[:] = sorted(
            name for name in directory_names if name not in EXCLUDED_DIRECTORIES
        )
        current_path = Path(current)
        for file_name in file_names:
            path = current_path / file_name
            if path.is_symlink():
                continue
            relative = path.relative_to(root)
            if should_include(relative) and path.resolve() != output:
                files.append((path, relative))

    files.sort(key=lambda item: item[1].as_posix().lower())
    output.parent.mkdir(parents=True, exist_ok=True)
    total_bytes = 0
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path, relative in files:
            archive.write(path, arcname=f"{root.name}/{relative.as_posix()}")
            total_bytes += path.stat().st_size
    return len(files), total_bytes


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a safe StickerDrop source ZIP.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    root = args.root.resolve()
    output = args.output or root.parent / f"{root.name}-source-bundle.zip"
    count, total_bytes = create_source_bundle(root, output)
    size_mb = output.stat().st_size / (1024 * 1024)
    print(f"Source files: {count}")
    print(f"Uncompressed source size: {total_bytes:,} bytes")
    print(f"ZIP size: {size_mb:.2f} MiB")
    print(f"Output: {output}")
    print("Excluded: .env files (except .env.example), .git, virtualenvs, build caches, local databases, and signing keys.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
