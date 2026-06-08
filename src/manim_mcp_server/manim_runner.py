"""Async wrapper around the manim CLI."""
import asyncio
import os
import re
import uuid
from pathlib import Path
from dataclasses import dataclass, field


# Quality preset → (resolution_dir, native_fps)
QUALITY_MAP: dict[str, tuple[str, int]] = {
    "l": ("480p15", 15),
    "m": ("720p30", 30),
    "h": ("1080p60", 60),
    "k": ("2160p60", 60),
}

VALID_QUALITIES = set(QUALITY_MAP.keys())


@dataclass
class RenderResult:
    """Result of a manim render."""
    success: bool
    video_path: str | None = None
    scenes: list[str] = field(default_factory=list)
    stdout: str = ""
    stderr: str = ""
    error: str | None = None


class ManimRunner:
    """Run manim CLI asynchronously and return results."""

    def __init__(
        self,
        output_dir: str = "/manim/output",
        timeout: float = 300.0,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.timeout = timeout
        os.makedirs(self.output_dir, exist_ok=True)

    def _validate_quality(self, quality: str) -> None:
        """Raise ValueError for invalid quality presets."""
        if quality not in VALID_QUALITIES:
            raise ValueError(
                f"Invalid quality '{quality}'. Must be one of: {sorted(VALID_QUALITIES)}"
            )

    def _parse_video_path(
        self, stdout: str, script_stem: str, scene_name: str, quality: str
    ) -> str | None:
        """Extract video path from manim's stdout output."""
        # manim word-wraps long lines with spaces. Remove all newlines first,
        # then use regex to find the quoted path after the marker.
        collapsed = stdout.replace("\n", "")
        marker = "File ready at"
        if marker in collapsed:
            # Find the quoted path: '...'
            import re
            match = re.search(r"File ready at\s+'([^']+)'", collapsed)
            if match:
                # Remove word-wrap spaces from the path
                path = match.group(1)
                path = re.sub(r"\s+", "", path)
                if Path(path).exists():
                    return path
        # Fallback: construct expected path (--media_dir outputs to videos/, not media/videos/)
        qdir = QUALITY_MAP.get(quality, ("480p15", 15))[0]
        candidate = (
            self.output_dir
            / "videos" / script_stem / qdir / f"{scene_name}.mp4"
        )
        if candidate.exists():
            return str(candidate)
        return None

    async def render(
        self,
        script_path: str,
        quality: str = "l",
        fps: int | None = None,
        scene_name: str | None = None,
    ) -> RenderResult:
        """Render a manim script asynchronously.

        Args:
            script_path: Path to the .py file to render.
            quality: Render quality - 'l'/'m'/'h'/'k'.
            fps: Frame rate (auto-derived from quality if not given).
            scene_name: Specific scene class name to render (renders all if None).
        """
        self._validate_quality(quality)

        script = Path(script_path)
        if not script.exists():
            return RenderResult(
                success=False,
                error=f"Script not found: {script_path}",
            )

        _, native_fps = QUALITY_MAP[quality]
        actual_fps = fps if fps is not None else native_fps

        args = ["manim", f"-q{quality}", f"--fps={actual_fps}", "--media_dir", str(self.output_dir)]
        if quality != "k":
            args.append("--format=mp4")
        args.append(str(script))
        if scene_name:
            args.append(scene_name)

        proc = None
        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(),
                timeout=self.timeout,
            )
            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")
        except asyncio.TimeoutError:
            if proc is not None:
                proc.terminate()
                try:
                    await asyncio.wait_for(proc.wait(), timeout=10.0)
                except asyncio.TimeoutError:
                    proc.kill()
                    await proc.wait()
            return RenderResult(
                success=False,
                error=f"Render timed out after {self.timeout}s",
            )
        except FileNotFoundError:
            return RenderResult(
                success=False,
                error="manim executable not found on PATH",
            )

        video_path = None
        if proc.returncode == 0:
            resolved_scene = scene_name or script.stem
            video_path = self._parse_video_path(stdout, script.stem, resolved_scene, quality)

        if proc.returncode != 0:
            error_msg = stderr.splitlines()[-1] if stderr else "Unknown error"
        elif video_path is None:
            error_msg = f"Render completed but video file not found. stdout last line: {stdout.splitlines()[-1] if stdout else 'N/A'}"
        else:
            error_msg = None

        # Populate scenes list
        scenes: list[str] = []
        try:
            scenes = self.parse_scenes(script_path)
        except Exception:
            pass

        return RenderResult(
            success=proc.returncode == 0 and video_path is not None,
            video_path=video_path,
            scenes=scenes,
            stdout=stdout,
            stderr=stderr,
            error=error_msg,
        )

    def write_code_file(self, code: str, output_name: str | None = None) -> str:
        """Write a code string to a temp .py file, return the path."""
        name = output_name or f"scene_{uuid.uuid4().hex[:8]}"
        file_path = self.output_dir / f"{name}.py"
        file_path.write_text(code, encoding="utf-8")
        return str(file_path)

    @staticmethod
    def parse_scenes(script_path: str) -> list[str]:
        """Parse a manim script and return Scene class names.

        Uses a simple regex approach to avoid importing the script
        (which would require manim to be importable).
        """
        content = Path(script_path).read_text(encoding="utf-8")
        # Match single-line and multi-line: class Name(Scene) or class Name(Base1, Scene)
        pattern = r"class\s+(\w+)\s*\([\s\S]*?\bScene\b[\s\S]*?\)"
        scenes = re.findall(pattern, content)
        return scenes

    @staticmethod
    def get_video_info(video_path: str) -> dict:
        """Validate a video file exists and return metadata."""
        path = Path(video_path)
        if not path.exists():
            return {"success": False, "error": f"Video not found: {video_path}"}
        if not path.suffix.lower() in (".mp4", ".webm", ".mov", ".gif"):
            return {"success": False, "error": f"Not a supported video format: {video_path}"}
        return {
            "success": True,
            "video_path": str(path),
            "filename": path.name,
            "size": path.stat().st_size,
            "mime_type": f"video/{path.suffix[1:]}",
        }
