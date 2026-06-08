"""MCP tool implementations for Manim rendering."""
from .manim_runner import ManimRunner

# Singleton runner
_runner = ManimRunner()


def _resolve_script(code: str | None, script_path: str | None) -> tuple[str | None, dict | None]:
    """Resolve code or script_path into a file path.

    Returns (path, None) on success, or (None, error_dict) on failure.
    """
    if code and script_path:
        return None, {
            "success": False,
            "error": "Provide either code or script_path, not both",
        }
    if code:
        return _runner.write_code_file(code), None
    if script_path:
        return script_path, None
    return None, {
        "success": False,
        "error": "Provide either script_path or code",
    }


def _make_response(result, script_path: str, extra: dict | None = None) -> dict:
    """Build a standardized response dict from a RenderResult."""
    resp = {
        "success": result.success,
        "video_path": result.video_path,
        "scenes": result.scenes,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "error": result.error,
        "script_path": script_path,
    }
    if extra:
        resp.update(extra)
    return resp


def register_tools(mcp) -> None:
    """Register all manim tools on a FastMCP instance."""

    @mcp.tool()
    async def render_code(
        code: str,
        output_name: str | None = None,
        quality: str = "l",
        fps: int = 15,
    ) -> dict:
        """Render Manim animation from Python code string.

        Args:
            code: Manim Python code as a string. Must contain at least one Scene subclass.
            output_name: Base name for the generated script file (without .py extension).
                         If not given, a random name is generated.
            quality: Render quality - 'l' (480p), 'm' (720p), 'h' (1080p), 'k' (4K).
            fps: Frame rate for the video.
        """
        script_path = _runner.write_code_file(code, output_name)
        scenes = _runner.parse_scenes(script_path)
        result = await _runner.render(script_path, quality=quality, fps=fps)
        return _make_response(result, script_path)

    @mcp.tool()
    async def render_script(
        script_path: str,
        quality: str = "l",
        fps: int = 15,
    ) -> dict:
        """Render an existing Manim script file (all scenes).

        Args:
            script_path: Path to the .py file inside the container (relative to /manim/).
            quality: Render quality - 'l' (480p), 'm' (720p), 'h' (1080p), 'k' (4K).
            fps: Frame rate for the video.
        """
        try:
            scenes = _runner.parse_scenes(script_path)
        except FileNotFoundError:
            return {"success": False, "error": f"File not found: {script_path}"}
        result = await _runner.render(script_path, quality=quality, fps=fps)
        return _make_response(result, script_path)

    @mcp.tool()
    async def list_scenes(
        script_path: str | None = None,
        code: str | None = None,
    ) -> dict:
        """List all Scene class names in a Manim script.

        Provide either script_path OR code, not both.

        Args:
            script_path: Path to a .py file inside the container.
            code: Manim Python code as a string.
        """
        resolved_path, error = _resolve_script(code, script_path)
        if error:
            return error
        try:
            scenes = _runner.parse_scenes(resolved_path)
            return {"success": True, "scenes": scenes, "count": len(scenes), "script_path": resolved_path}
        except FileNotFoundError:
            return {"success": False, "error": f"File not found: {resolved_path}"}

    @mcp.tool()
    async def render_scene(
        scene_name: str,
        script_path: str | None = None,
        code: str | None = None,
        quality: str = "l",
        fps: int = 15,
    ) -> dict:
        """Render a specific scene from a Manim script.

        Provide either script_path OR code, not both.

        Args:
            scene_name: The Scene class name to render.
            script_path: Path to a .py file inside the container.
            code: Manim Python code as a string.
            quality: Render quality - 'l' (480p), 'm' (720p), 'h' (1080p), 'k' (4K).
            fps: Frame rate for the video.
        """
        resolved_path, error = _resolve_script(code, script_path)
        if error:
            return error
        result = await _runner.render(
            resolved_path, quality=quality, fps=fps, scene_name=scene_name,
        )
        return _make_response(result, resolved_path, extra={"scene_name": scene_name})

    @mcp.tool()
    async def get_video(video_path: str) -> dict:
        """Get video file info and download URL for a rendered video.

        Use this after render_code/render_script/render_scene to get a
        downloadable link for the generated video file.

        Args:
            video_path: The video path returned by render_code/render_script/render_scene.
        """
        import urllib.parse
        info = _runner.get_video_info(video_path)
        if info["success"]:
            encoded = urllib.parse.quote(video_path, safe="")
            info["download_url"] = f"http://localhost:8000/download?path={encoded}"
        return info
