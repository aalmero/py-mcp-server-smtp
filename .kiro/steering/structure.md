---
inclusion: always
---

# Project Structure & Architecture Guidelines

## Core Architecture Pattern
This is a **single-server MCP implementation** using FastMCP framework. Follow these patterns:
- **server.py**: Contains all MCP server logic, SMTP tools, and business logic
- **main.py**: Minimal entry point that imports and runs the server
- Keep the architecture simple and focused on SMTP functionality

## File Organization Rules

### Core Files
- **server.py**: MCP server implementation with SMTP tools (`send_email`, `validate_email`, etc.)
- **main.py**: Application entry point - should only import server and call `run()`
- **pyproject.toml**: Project configuration, dependencies, and metadata

### Test Files
- **test_*.py**: Test files for different scenarios (integration, startup, HTTP transport)
- **verify_*.py**: Verification scripts for specific functionality

### Configuration Files
- **.python-version**: Python 3.12+ requirement
- **uv.lock**: Dependency lock file (do not modify manually)
- **.gitignore**: Standard Python gitignore patterns

## Code Organization Conventions

### MCP Server Structure (server.py)
```python
# 1. Imports (standard library, third-party, fastmcp)
# 2. Configuration and constants
# 3. MCP server instance creation
# 4. Tool definitions (@mcp.tool decorators)
# 5. Server startup logic
```

### Tool Implementation Guidelines
- Use `@mcp.tool` decorator for all SMTP operations
- Include comprehensive docstrings with parameter descriptions
- Handle errors gracefully with informative messages
- Validate inputs before processing
- Return structured responses (success/error status)

### Dependency Management
- Use `uv add <package>` to add new dependencies
- All dependencies must be declared in `pyproject.toml`
- Pin FastMCP to `>=2.13.3` for compatibility
- Avoid adding unnecessary dependencies

## Development Workflow
1. **Setup**: `uv sync` to install dependencies
2. **Testing**: Run test files to verify functionality
3. **Development**: Modify `server.py` for new SMTP features
4. **Validation**: Use verification scripts to test changes