"""
utils/file_manager.py
Manages creation of output directory structure and file writes.
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Dict, Optional

from rich.console import Console

from config import settings

console = Console()


class FileManager:
    """Handles all output file and directory management."""

    def __init__(self, project_name: str) -> None:
        self.project_name = project_name
        self.project_root = settings.output_dir / project_name
        self._init_structure()

    # ------------------------------------------------------------------
    # Directory setup
    # ------------------------------------------------------------------

    def clean_project(self) -> None:
        """Completely erase previous generated output for this project."""
        if self.project_root.exists():
            try:
                shutil.rmtree(self.project_root, ignore_errors=True)
                console.print(f"[yellow]  ✓ Cleaned old output:[/yellow] {self.project_root}")
            except Exception as exc:
                console.print(f"[red]  [WARN] Could not fully erase {self.project_root}: {exc}[/red]")
        self._init_structure()

    def _init_structure(self) -> None:
        """Create the clean output directory structure."""
        self.react_src_dir.mkdir(parents=True, exist_ok=True)

    @property
    def metadata_dir(self) -> Path:
        d = self.project_root / ".metadata"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @property
    def static_html_dir(self) -> Path:
        return self.project_root

    @property
    def react_app_dir(self) -> Path:
        return self.project_root

    @property
    def react_src_dir(self) -> Path:
        return self.project_root / "src"

    @property
    def react_public_dir(self) -> Path:
        return self.project_root / "public"

    @property
    def stories_dir(self) -> Path:
        return self.react_src_dir

    @property
    def shared_components_dir(self) -> Path:
        return self.react_src_dir / "components" / "shared"

    # ------------------------------------------------------------------
    # Story folder
    # ------------------------------------------------------------------

    def story_dir(self, story_id: str, story_name: str) -> Path:
        """Return (and create) the folder for a specific story."""
        safe_name = story_name.replace(" ", "_").replace("/", "_")
        folder = self.stories_dir / f"{story_id}_{safe_name}"
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    # ------------------------------------------------------------------
    # Write helpers
    # ------------------------------------------------------------------

    def write_text(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        console.print(f"[green]  ✓ Wrote:[/green] {path.relative_to(settings.output_dir)}")

    def copy_asset(self, src: Path, dest_name: Optional[str] = None) -> Path:
        """Copy a file into the public/assets directory."""
        dest = self.react_public_dir / "assets" / (dest_name or src.name)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        console.print(f"[green]  ✓ Asset:[/green] {dest.name}")
        return dest

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def summary(self) -> Dict[str, str]:
        """Return key paths for display."""
        return {
            "project_root": str(self.project_root),
            "metadata": str(self.metadata_dir),
            "static_html": str(self.static_html_dir),
            "react_app": str(self.react_app_dir),
        }

    def file_tree(self, max_depth: int = 5) -> str:
        """Return an ASCII file tree of the generated output."""
        lines: list[str] = []
        self._tree(self.project_root, "", lines, 0, max_depth)
        return "\n".join(lines)

    def _tree(
        self, path: Path, prefix: str, lines: list, depth: int, max_depth: int
    ) -> None:
        if depth > max_depth:
            return
        entries = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name))
        for i, entry in enumerate(entries):
            connector = "└── " if i == len(entries) - 1 else "├── "
            lines.append(f"{prefix}{connector}{entry.name}")
            if entry.is_dir():
                extension = "    " if i == len(entries) - 1 else "│   "
                self._tree(entry, prefix + extension, lines, depth + 1, max_depth)
