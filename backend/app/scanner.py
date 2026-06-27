from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Iterator

_GITHUB_RE = re.compile(r"^https?://github\.com/[\w.\-]+/[\w.\-]+(?:\.git)?/?$")

_SKIP = frozenset({
    ".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build",
    ".next", ".nuxt", "target", ".gradle",
})


class Scanner:
    """Clone a public GitHub repo and provide safe file iteration."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or Path(tempfile.gettempdir()) / "cicd-auditor"
        self.root.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def clone(self, url: str) -> Path:
        url = self._validate(url)
        name = url.rstrip("/").split("/")[-1]
        dest = self.root / name

        if dest.exists():
            shutil.rmtree(dest)

        self._run_clone(url, dest)
        return dest

    def cleanup(self, path: Path) -> None:
        if path.exists() and path.is_relative_to(self.root):
            shutil.rmtree(path, ignore_errors=True)

    def file_tree(self, path: Path) -> dict:
        node: dict = {"name": path.name, "type": "dir", "children": []}
        self._walk(path, path, node)
        return node

    def iter_files(self, path: Path) -> Iterator[Path]:
        for p in path.rglob("*"):
            if p.is_file() and not (_SKIP & set(p.relative_to(path).parts)):
                yield p

    def read(self, path: Path, max_bytes: int = 524_288) -> str | None:
        try:
            if path.stat().st_size > max_bytes:
                return None
            return path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _validate(url: str) -> str:
        url = url.strip().rstrip("/")
        if url.endswith(".git"):
            url = url[:-4]
        if not _GITHUB_RE.match(url):
            raise ValueError(
                "Invalid URL. Expected: https://github.com/owner/repo"
            )
        return url

    def _run_clone(self, url: str, dest: Path) -> None:
        for args in (
            ["git", "clone", "--depth=1", url, str(dest)],
            ["git", "clone", "--depth=10", "--no-single-branch", url, str(dest)],
        ):
            try:
                subprocess.run(
                    args, capture_output=True, text=True, check=True, timeout=120
                )
                return
            except (subprocess.SubprocessError, subprocess.TimeoutExpired):
                if dest.exists():
                    shutil.rmtree(dest)
        raise RuntimeError(f"Failed to clone {url}")

    def _walk(self, base: Path, current: Path, node: dict) -> None:
        try:
            entries = sorted(current.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
        except OSError:
            return
        for entry in entries:
            if entry.name in _SKIP:
                continue
            if entry.is_dir():
                child: dict = {"name": entry.name, "type": "dir", "children": []}
                self._walk(base, entry, child)
                node["children"].append(child)
            else:
                node["children"].append({
                    "name": entry.name,
                    "type": "file",
                    "path": str(entry.relative_to(base)),
                    "size": entry.stat().st_size,
                })
