# manim-mcp-server

MCP Server for rendering Manim math animations via HTTP Streamable transport.

## Quick Start

### Build

```bash
podman build --network host -t manim-mcp-server .
```

### Run

```bash
# Without authentication
podman run -d --rm --network host \
  -v "$(pwd)/output:/manim/output" \
  manim-mcp-server

# With API key authentication
podman run -d --rm --network host \
  -e API_KEY=your-secret-key \
  -v "$(pwd)/output:/manim/output" \
  manim-mcp-server
```

Server listens on `http://localhost:8000`.

### Endpoints

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/health` | GET | No | Health check |
| `/mcp` | POST | Optional | MCP Streamable HTTP |
| `/download?path=...` | GET | Optional | Download rendered video |

## Tools

### `render_code`

Render Manim animation from Python code string.

- `code` (required) — Manim Python code
- `output_name` — Script file base name
- `quality` — `l`/`m`/`h`/`k` (480p/720p/1080p/4K), default `l`
- `fps` — Frame rate

### `render_script`

Render an existing Manim script file.

- `script_path` (required) — Path to .py file in container
- `quality` — Render quality, default `l`
- `fps` — Frame rate

### `list_scenes`

List Scene class names in a Manim script.

- `script_path` or `code` — Provide one

### `render_scene`

Render a specific scene from a Manim script.

- `scene_name` (required) — Scene class to render
- `script_path` or `code` — Provide one
- `quality` — Render quality, default `l`
- `fps` — Frame rate

### `get_video`

Get download URL for a rendered video file.

- `video_path` (required) — Path returned by render_* tools

## MCP Integration

### Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "manim": {
      "type": "http",
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

With API key:

```json
{
  "mcpServers": {
    "manim": {
      "type": "http",
      "url": "http://localhost:8000/mcp",
      "headers": {
        "Authorization": "Bearer your-secret-key"
      }
    }
  }
}
```

### Claude Code (CLI)

Add to `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "manim": {
      "type": "http",
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

Or with API key:

```json
{
  "mcpServers": {
    "manim": {
      "type": "http",
      "url": "http://localhost:8000/mcp",
      "headers": {
        "Authorization": "Bearer your-secret-key"
      }
    }
  }
}
```

### Using Pre-built Image

```bash
# Pull and run the pre-built image from GHCR
podman run -d --rm --network host \
  -v "$(pwd)/output:/manim/output" \
  ghcr.io/zcq100/manim-mcp-server:latest
```

### Example: Render an animation

Once integrated, the agent can:

1. **List scenes** in a script:
   ```
   Call list_scenes with script_path=/manim/scripts/example.py
   → ["MyScene", "AnotherScene"]
   ```

2. **Render from code**:
   ```
   Call render_code with code="from manim import *\nclass Circle(Scene):\n    def construct(self):\n        self.add(Circle())\n        self.wait()"
   → video_path="/manim/output/videos/.../Circle.mp4"
   ```

3. **Download the video**:
   ```
   Call get_video with video_path="/manim/output/videos/.../Circle.mp4"
   → download_url="http://localhost:8000/download?path=..."
   → GET download_url → .mp4 file
   ```

## Development

### Interactive dev container

```bash
podman run -it --user 0 --rm --network host \
  --name manim-mcp-dev \
  -v "$(pwd):/manim" \
  -v "/path/to/scripts:/manim/scripts:ro" \
  manimcommunity/manim /bin/bash

# In container:
pip install mcp starlette uvicorn
cd /manim
python3 -c "import sys; sys.path.insert(0, 'src'); from manim_mcp_server.server import main; main()"
```

### Build & test cycle

```bash
podman build --network host -t manim-mcp-server .
podman run -d --rm --network host \
  -v "$(pwd)/output:/manim/output" \
  manim-mcp-server
# Test with curl or MCP client
```

## Project Structure

```
manim-mcp-server/
├── Dockerfile
├── pyproject.toml
├── README.md
├── src/manim_mcp_server/
│   ├── __init__.py
│   ├── server.py          # FastMCP + Starlette + Auth
│   ├── tools.py           # MCP tool implementations
│   └── manim_runner.py    # Manim CLI async wrapper
└── output/                # Rendered videos (gitignored)
```
