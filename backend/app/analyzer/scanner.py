from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Iterator


GITHUB_URL_PATTERN = re.compile(
    r"^https?://github\.com/[\w.-]+/[\w.-]+(?:\.git)?/?$"
)


class RepositoryScanner:
    """Clone and scan public GitHub repositories."""

    SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}

    def __init__(self, work_root: Path | None = None) -> None:
        self.work_root = work_root or Path(tempfile.gettempdir()) / "repo-cicd-auditor"
        self.work_root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def validate_github_url(url: str) -> str:
        url = url.strip().rstrip("/")
        if url.endswith(".git"):
            url = url[:-4]
        if not GITHUB_URL_PATTERN.match(url):
            raise ValueError(
                "Invalid GitHub repository URL. Expected format: https://github.com/owner/repo"
            )
        return url

    def clone(self, repo_url: str) -> Path:
        repo_url = self.validate_github_url(repo_url)
        repo_name = repo_url.rstrip("/").split("/")[-1]
        target = self.work_root / repo_name

        if target.exists():
            shutil.rmtree(target)

        result = subprocess.run(
            ["git", "clone", repo_url, str(target)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Failed to clone repository: {result.stderr.strip()}")

        return target

    def build_file_tree(self, repo_path: Path) -> dict:
        tree: dict = {"name": repo_path.name, "type": "directory", "children": []}

        def walk(directory: Path, node: dict) -> None:
            try:
                entries = sorted(directory.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
            except PermissionError:
                return

            for entry in entries:
                if entry.name in self.SKIP_DIRS:
                    continue
                if entry.is_dir():
                    child = {"name": entry.name, "type": "directory", "path": str(entry.relative_to(repo_path)), "children": []}
                    walk(entry, child)
                    node["children"].append(child)
                else:
                    node["children"].append({
                        "name": entry.name,
                        "type": "file",
                        "path": str(entry.relative_to(repo_path)),
                        "size": entry.stat().st_size,
                    })

        walk(repo_path, tree)
        return tree

    def iter_files(self, repo_path: Path) -> Iterator[Path]:
        for path in repo_path.rglob("*"):
            if not path.is_file():
                continue
            parts = set(path.relative_to(repo_path).parts)
            if parts & self.SKIP_DIRS:
                continue
            yield path

    def read_file_safe(self, path: Path, max_bytes: int = 512_000) -> str | None:
        try:
            if path.stat().st_size > max_bytes:
                return None
            return path.read_text(encoding="utf-8", errors="replace")
        except (OSError, UnicodeDecodeError):
            return None

    def cleanup(self, repo_path: Path) -> None:
        if repo_path.exists() and repo_path.is_relative_to(self.work_root):
            shutil.rmtree(repo_path, ignore_errors=True)
