from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from app.core.render_pipeline import RenderPipeline, ValidationError

FRAME_RE = re.compile(r"(\d+)/(\d+)")


class RenderWorker(QThread):
    progress = pyqtSignal(int, int)          # (current_frame, total_frames)
    render_complete = pyqtSignal(str)        # absolute path to output MP4
    error_occurred = pyqtSignal(str, str)    # (user_display_msg, raw_stderr)

    def __init__(
        self,
        code: str,
        quality: str,
        timeout: int,
        pipeline: RenderPipeline | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._code = code
        self._quality = quality
        self._timeout = timeout
        self._pipeline = pipeline or RenderPipeline()

    def run(self) -> None:
        # 1. Validate + write scene file
        try:
            scene_file, temp_dir = self._pipeline.prepare_scene_file(self._code)
        except ValidationError as exc:
            violations = "\n• ".join(exc.violations)
            msg = f"Code safety check failed:\n• {violations}"
            self.error_occurred.emit(msg, msg)
            return
        except Exception as exc:
            msg = f"Failed to prepare scene: {exc}"
            self.error_occurred.emit(msg, msg)
            return

        # 2. Build subprocess command
        cmd = self._pipeline.build_command(scene_file, self._quality)

        # 3. Run manimgl
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # merge so we capture everything
                text=True,
                cwd=str(temp_dir),
                preexec_fn=_posix_resource_limits if sys.platform != "win32" else None,
            )
        except FileNotFoundError:
            msg = "manimgl not found.\nInstall it with: pip install manimgl\nThen restart the app."
            self.error_occurred.emit(msg, msg)
            return
        except Exception as exc:
            msg = f"Failed to launch manimgl: {exc}"
            self.error_occurred.emit(msg, msg)
            return

        # 4. Stream output, parse progress
        output_lines: list[str] = []
        assert proc.stdout is not None
        for line in proc.stdout:
            output_lines.append(line)
            match = FRAME_RE.search(line)
            if match:
                current = int(match.group(1))
                total = int(match.group(2))
                if total > 0:
                    self.progress.emit(current, total)

        try:
            proc.wait(timeout=self._timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            msg = (
                f"Render timed out after {self._timeout}s.\n"
                "Try a simpler animation or increase the timeout in Settings."
            )
            self.error_occurred.emit(msg, msg)
            return

        full_output = "".join(output_lines)
        if proc.returncode != 0:
            tail = full_output[-2000:]
            user_msg = f"manimgl exited with code {proc.returncode}.\n\n{tail}"
            self.error_occurred.emit(user_msg, full_output)
            return

        # 5. Find output path
        try:
            video_path = self._pipeline.parse_output_path(full_output, "", temp_dir)
        except FileNotFoundError as exc:
            msg = str(exc)
            self.error_occurred.emit(msg, full_output)
            return

        self.render_complete.emit(str(video_path))


def _posix_resource_limits() -> None:
    try:
        import resource
        # Max CPU time: 120 seconds
        resource.setrlimit(resource.RLIMIT_CPU, (120, 120))
        # Max address space: 3 GB
        resource.setrlimit(resource.RLIMIT_AS, (3 * 1024 ** 3, 3 * 1024 ** 3))
    except Exception:
        pass
