# Project Structure

## Root Directory Layout
```
py-mcp-server-smtp/
├── .git/                 # Git repository metadata
├── .kiro/               # Kiro IDE configuration and steering rules
├── .venv/               # Virtual environment (UV managed)
├── .gitignore           # Git ignore patterns
├── .python-version      # Python version specification (3.12)
├── README.md            # Project documentation
├── main.py              # Main application entry point
├── server.py            # MCP server implementation (to be developed)
├── pyproject.toml       # Project configuration and dependencies
└── uv.lock              # Dependency lock file
```

## File Organization Conventions
- **main.py**: Primary entry point for the application
- **server.py**: Contains the MCP server implementation and SMTP functionality
- **pyproject.toml**: Central configuration for project metadata, dependencies, and build settings
- **.python-version**: Ensures consistent Python version (3.12) across environments

## Development Guidelines
- Keep MCP server logic in `server.py`
- Use `main.py` for application bootstrapping
- All dependencies should be declared in `pyproject.toml`
- Virtual environment is managed by UV in `.venv/`
- Follow Python 3.12+ syntax and features