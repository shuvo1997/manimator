from __future__ import annotations

import glob
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

from .code_extractor import ensure_scene_class
from .code_validator import ValidationResult, validate_code


def _find_manimgl() -> str:
    """
    Return the path to the manimgl executable.
    Checks PATH first, then common pip user-install locations.
    """
    found = shutil.which("manimgl")
    if found:
        return found
    # pip install --user puts scripts here on macOS/Linux
    user_bin = Path(sys.executable).parent / "manimgl"
    if user_bin.exists():
        return str(user_bin)
    # Python user base (e.g. ~/Library/Python/3.9/bin on macOS)
    import site
    for base in site.getusersitepackages().split(os.pathsep) if isinstance(
        site.getusersitepackages(), str
    ) else []:
        candidate = Path(base).parent.parent / "bin" / "manimgl"
        if candidate.exists():
            return str(candidate)
    # Hardcoded macOS fallback
    fallback = Path.home() / "Library" / "Python" / f"{sys.version_info.major}.{sys.version_info.minor}" / "bin" / "manimgl"
    if fallback.exists():
        return str(fallback)
    return "manimgl"  # let it fail with a clear FileNotFoundError

QUALITY_FLAGS: dict[str, list[str]] = {
    "low": ["-l"],        # 480p
    "medium": ["-w"],     # 720p
    "high": ["--hd"],     # 1080p
    "ultra": ["--uhd"],   # 4K
}

OUTPUT_PATH_RE = re.compile(r"File ready at (.+\.mp4)", re.IGNORECASE)
# rich may wrap long paths across multiple lines — this catches the next line(s)
OUTPUT_PATH_MULTILINE_RE = re.compile(r"File ready at\s*\n\s*(.+)", re.IGNORECASE)
FRAME_PROGRESS_RE = re.compile(r"(\d+)/(\d+)")


class ValidationError(Exception):
    def __init__(self, violations: list[str]) -> None:
        self.violations = violations
        super().__init__("\n".join(violations))


class RenderPipeline:
    def __init__(self, renders_dir: Path | None = None) -> None:
        if renders_dir is None:
            renders_dir = Path.home() / ".manimator" / "renders"
        renders_dir.mkdir(parents=True, exist_ok=True)
        self._renders_dir = renders_dir

    def prepare_scene_file(self, code: str) -> tuple[Path, Path]:
        """
        Validate + write code to a temp directory.
        Returns (scene_file_path, temp_dir_path).
        Raises ValidationError on safety violations.
        """
        # Always ensure the manimlib import is present — some models omit it
        if "from manimlib" not in code and "import manimlib" not in code:
            code = "from manimlib import *\n\n" + code

        result: ValidationResult = validate_code(code)
        if not result.is_safe:
            raise ValidationError(result.violations)

        code = ensure_scene_class(code)

        temp_dir = Path(tempfile.mkdtemp(dir=self._renders_dir))
        scene_file = temp_dir / "scene.py"
        scene_file.write_text(code, encoding="utf-8")
        return scene_file, temp_dir

    def build_command(self, scene_file: Path, quality: str) -> list[str]:
        flags = QUALITY_FLAGS.get(quality, QUALITY_FLAGS["medium"])
        # --write_file renders to disk instead of opening an interactive window
        return [_find_manimgl(), "--write_file"] + flags + [str(scene_file), "GeneratedScene"]

    def parse_output_path(self, stdout: str, stderr: str, temp_dir: Path) -> Path:
        # Strip ANSI escape codes (rich/manimgl colorizes output)
        ansi_escape = re.compile(r"\x1b\[[0-9;]*m")
        combined = ansi_escape.sub("", stdout + "\n" + stderr)

        # Strategy 1: single-line "File ready at /path/to/file.mp4"
        match = OUTPUT_PATH_RE.search(combined)
        if match:
            p = Path(match.group(1).strip())
            if p.exists():
                return p

        # Strategy 2: rich wraps long paths across lines — join them
        # e.g. "File ready at\n   /Users/.../ma\n   nimator/videos/Scene.mp4"
        for m in OUTPUT_PATH_MULTILINE_RE.finditer(combined):
            # Collect this line and the next few continuation lines
            start = m.start()
            # Find everything from "File ready at" to the next blank line or new log entry
            block = combined[start:]
            lines = block.splitlines()
            # First line after "File ready at" is the start of the path
            path_parts = []
            for line in lines[1:6]:  # look at up to 5 continuation lines
                stripped = line.strip()
                if not stripped or re.match(r"\[\d{2}:\d{2}:\d{2}\]", stripped):
                    break
                path_parts.append(stripped)
            if path_parts:
                candidate = "".join(path_parts)
                p = Path(candidate)
                if p.exists() and p.suffix == ".mp4":
                    return p

        # Strategy 3: glob under temp_dir subtree
        pattern = str(temp_dir / "**" / "*.mp4")
        files = glob.glob(pattern, recursive=True)
        if files:
            return Path(max(files, key=os.path.getmtime))

        # Strategy 4: manimgl writes to <cwd>/videos/ by default
        cwd_videos = Path.cwd() / "videos"
        if cwd_videos.exists():
            files = glob.glob(str(cwd_videos / "**" / "*.mp4"), recursive=True)
            if files:
                return Path(max(files, key=os.path.getmtime))

        raise FileNotFoundError(
            f"No output MP4 found after render.\n"
            f"stdout: {stdout[-500:]}\n"
            f"stderr: {stderr[-500:]}"
        )

    def cleanup(self, temp_dir: Path, keep_video: bool = True) -> None:
        if not temp_dir.exists():
            return
        if keep_video:
            for f in temp_dir.rglob("*"):
                if f.is_file() and f.suffix != ".mp4":
                    try:
                        f.unlink()
                    except OSError:
                        pass
        else:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
