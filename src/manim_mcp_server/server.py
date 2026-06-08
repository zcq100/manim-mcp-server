"""MCP Manim Server entry point."""
import hmac
import os
import urllib.parse
from pathlib import Path

from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, FileResponse
from starlette.routing import Route

from mcp.server.fastmcp import FastMCP

from .tools import register_tools


# ---- FastMCP instance ----
mcp = FastMCP(
    name="manim-mcp-server",
    instructions="MCP server for rendering Manim math animations. "
                 "Supports rendering from code strings or script files.",
    host=os.environ.get("HOST", "0.0.0.0"),
    port=int(os.environ.get("PORT", "8000")),
    stateless_http=True,
)

register_tools(mcp)


# ---- Auth Middleware ----
class APIKeyMiddleware(BaseHTTPMiddleware):
    """Optional API key authentication.

    If the API_KEY environment variable is set, require a matching
    Authorization: Bearer <key> header on every request.
    The /health endpoint is exempt from authentication.
    """

    async def dispatch(self, request: Request, call_next):
        # Health check is always public (tolerate trailing slash)
        if request.url.path.rstrip("/") == "/health":
            return await call_next(request)

        api_key = os.environ.get("API_KEY", "")
        if api_key:
            auth = request.headers.get("Authorization", "")
            if not auth.startswith("Bearer "):
                return JSONResponse(
                    {"error": "Unauthorized", "detail": "Invalid or missing API key"},
                    status_code=401,
                )
            if not hmac.compare_digest(auth[7:], api_key):
                return JSONResponse(
                    {"error": "Unauthorized", "detail": "Invalid API key"},
                    status_code=401,
                )
        return await call_next(request)


# ---- Application Factory ----
def create_app() -> Starlette:
    """Build the full Starlette app with auth middleware and health check."""
    starlette_app = mcp.streamable_http_app()

    # Add health check endpoint before MCP routes
    async def health(request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok", "server": "manim-mcp-server"})

    health_route = Route("/health", health, methods=["GET"])
    starlette_app.routes.insert(0, health_route)

    # Add download endpoint
    async def download(request: Request):
        path_str = request.query_params.get("path", "")
        path_str = urllib.parse.unquote(path_str)
        file_path = Path(path_str)
        if not file_path.exists() or not file_path.is_file():
            return JSONResponse({"error": "File not found"}, status_code=404)
        if not file_path.suffix.lower() in (".mp4", ".webm", ".mov", ".gif"):
            return JSONResponse({"error": "Not a supported video format"}, status_code=400)
        return FileResponse(
            path=str(file_path),
            media_type=f"video/{file_path.suffix[1:]}",
            filename=file_path.name,
        )

    download_route = Route("/download", download, methods=["GET"])
    starlette_app.routes.insert(0, download_route)

    # Wrap with auth middleware
    starlette_app.add_middleware(APIKeyMiddleware)

    return starlette_app


# ---- Entry Point ----
def main() -> None:
    """Entry point for running the server."""
    import asyncio

    import uvicorn

    async def run() -> None:
        app = create_app()
        config = uvicorn.Config(
            app,
            host=mcp.settings.host,
            port=mcp.settings.port,
            log_level=mcp.settings.log_level.lower(),
        )
        server = uvicorn.Server(config)
        try:
            await server.serve()
        except Exception as exc:
            import sys
            print(f"Server failed to start: {exc}", file=sys.stderr)
            sys.exit(1)

    asyncio.run(run())


if __name__ == "__main__":
    main()
