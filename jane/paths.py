"""Workspace home and default path resolution for Jane CLI."""

from __future__ import annotations

import os
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent.parent


def _is_jane_workspace(path: Path) -> bool:
    """Return True if path looks like a Jane workspace directory."""
    return (path / "data" / "raw").is_dir() or (path / "data" / "jane.db").is_file()


def resolve_jane_home(
    explicit_home: Path | str | None = None,
    *,
    cwd: Path | None = None,
    package_root: Path | None = None,
) -> Path:
    """Resolve Jane's base workspace directory using deterministic precedence.

    Precedence:
    1. explicit_home (--home CLI flag)
    2. JANE_HOME environment variable (if set and non-empty)
    3. Current working directory if it contains data/raw/ or data/jane.db
    4. Package repository root if it contains data/raw/ (supports editable installs)
    5. Current working directory fallback
    """
    if explicit_home is not None and str(explicit_home).strip():
        return Path(explicit_home).expanduser().resolve()

    env_home = os.environ.get("JANE_HOME", "").strip()
    if env_home:
        return Path(env_home).expanduser().resolve()

    cwd_path = (cwd if cwd is not None else Path.cwd()).resolve()
    if _is_jane_workspace(cwd_path):
        return cwd_path

    pkg_root = (package_root if package_root is not None else PACKAGE_ROOT).resolve()
    if (pkg_root / "data" / "raw").is_dir():
        return pkg_root

    return cwd_path


def default_db_path(home: Path) -> Path:
    return home / "data" / "jane.db"


def default_raw_dir(home: Path) -> Path:
    return home / "data" / "raw"


def default_exports_dir(home: Path) -> Path:
    return home / "exports"


def default_anki_dir(home: Path) -> Path:
    return home / "anki"
