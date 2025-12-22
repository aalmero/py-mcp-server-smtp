# Technology Stack

## Core Technologies
- **Python**: 3.12+ (specified in .python-version)
- **FastMCP**: 2.13.3+ - Framework for building MCP servers
- **UV**: Package manager and virtual environment tool

## Project Structure
- Built as a Python package with pyproject.toml configuration
- Uses UV for dependency management and virtual environment
- MCP server implementation for SMTP functionality

## Development Setup
```bash
# Install dependencies
uv sync

# Activate virtual environment
source .venv/bin/activate

# Run the main application
python main.py
```

## Key Dependencies
- `fastmcp>=2.13.3` - Core MCP server framework

## Build System
- Uses `pyproject.toml` for project configuration
- UV lock file (`uv.lock`) for reproducible builds
- Virtual environment managed in `.venv/`