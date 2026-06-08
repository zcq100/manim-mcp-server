FROM docker.io/manimcommunity/manim:latest

USER root

# Install MCP dependencies
RUN pip install --no-cache-dir \
    -i https://pypi.org/simple/ \
    --trusted-host pypi.org \
    --trusted-host files.pythonhosted.org \
    "mcp>=1.0,<2.0" \
    "starlette>=0.38" \
    "uvicorn>=0.27"

# Create output directory
RUN mkdir -p /manim/output && chown manimuser:manimuser /manim/output

# Copy project source
COPY pyproject.toml /manim/
COPY src/ /manim/src/

# Use manimuser (non-root for safety)
USER manimuser

# Expose MCP HTTP port
EXPOSE 8000

# Run the MCP server
CMD ["python3", "-c", "import sys; sys.path.insert(0, '/manim/src'); from manim_mcp_server.server import main; main()"]
