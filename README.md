# SMTP MCP Server

A Python-based MCP (Model Context Protocol) server that provides SMTP email functionality for AI assistants. This server enables AI systems to send emails through SMTP servers with comprehensive features including multi-server support, template processing, attachment handling, and dynamic reconfiguration.

## Features

### Core Email Functionality
- **SMTP Server Support**: Connect to any SMTP server with authentication
- **Multiple Content Types**: Send both plain text and HTML emails
- **Multi-Recipients**: Support for TO, CC, and BCC recipients
- **Email Attachments**: Send files with proper MIME encoding
- **Template Processing**: Variable substitution and conditional content in emails
- **Character Encoding**: Full UTF-8 support for international content

### Advanced Capabilities
- **Multi-Server Support**: Configure multiple SMTP servers with automatic failover
- **Dynamic Reconfiguration**: Update server configurations without restart
- **Connection Management**: Automatic retry with exponential backoff
- **Security**: Support for SSL/TLS and STARTTLS encryption
- **Comprehensive Logging**: Detailed logging with sensitive data sanitization
- **Thread Safety**: Safe concurrent email sending

### MCP Integration
- **FastMCP Framework**: Built on the FastMCP framework for optimal performance
- **Standard MCP Tools**: Expose email functionality through standardized MCP protocol
- **Tool Validation**: Comprehensive parameter validation and error handling
- **Protocol Compliance**: Full adherence to MCP protocol specifications

## Installation

### Prerequisites
- Python 3.12 or higher
- UV package manager (recommended) or pip
- Docker (optional, for containerized deployment)

### Using Docker (Recommended for Production)

The easiest way to run the SMTP MCP Server is using Docker:

```bash
# Clone the repository
git clone <repository-url>
cd py-mcp-server-smtp

# Copy environment configuration
cp .env.example .env
# Edit .env with your SMTP settings

# Build and run with Docker Compose (stdio transport)
docker-compose up --build

# Or run with HTTP transport
docker-compose --profile http up --build smtp-mcp-server-http
```

#### Docker Build Options

```bash
# Build the Docker image
docker build -t smtp-mcp-server .

# Run with stdio transport (default)
docker run -it --rm \
  --env-file .env \
  smtp-mcp-server

# Run with HTTP transport
docker run -it --rm \
  --env-file .env \
  -p 8000:8000 \
  smtp-mcp-server \
  python main.py --transport http --host 0.0.0.0 --port 8000
```

#### Docker Environment Variables

When using Docker, set your SMTP configuration in a `.env` file:

```bash
# Copy the example file
cp .env.example .env

# Edit with your settings
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_USE_TLS=true
SMTP_FROM_EMAIL=your-email@gmail.com
LOG_LEVEL=INFO
```

### Using UV (Recommended for Development)
```bash
# Clone the repository
git clone <repository-url>
cd py-mcp-server-smtp

# Install dependencies
uv sync

# Activate virtual environment
source .venv/bin/activate
```

### Using pip
```bash
# Clone the repository
git clone <repository-url>
cd py-mcp-server-smtp

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Configuration

The SMTP MCP Server is configured using environment variables. You can configure either a single SMTP server or multiple servers for failover support.

### Single Server Configuration

Set these environment variables for a single SMTP server:

```bash
# Required Configuration
export SMTP_HOST="smtp.gmail.com"
export SMTP_PORT="587"
export SMTP_USERNAME="your-email@gmail.com"
export SMTP_PASSWORD="your-app-password"

# Optional Configuration
export SMTP_USE_TLS="true"          # Use STARTTLS (default: true)
export SMTP_USE_SSL="false"         # Use SSL/TLS (default: false)
export SMTP_TIMEOUT="30"            # Connection timeout in seconds
export SMTP_MAX_RETRIES="3"         # Maximum retry attempts
export SMTP_FROM_EMAIL="your-email@gmail.com"  # Default sender
export SMTP_NAME="primary"          # Server identifier
export SMTP_PRIORITY="100"          # Server priority
```

### Multi-Server Configuration

For multiple SMTP servers with automatic failover, use numbered suffixes:

```bash
# Primary Server (highest priority)
export SMTP_HOST_1="smtp.gmail.com"
export SMTP_PORT_1="587"
export SMTP_USERNAME_1="primary@gmail.com"
export SMTP_PASSWORD_1="primary-password"
export SMTP_USE_TLS_1="true"
export SMTP_NAME_1="gmail_primary"
export SMTP_PRIORITY_1="100"

# Backup Server
export SMTP_HOST_2="smtp.outlook.com"
export SMTP_PORT_2="587"
export SMTP_USERNAME_2="backup@outlook.com"
export SMTP_PASSWORD_2="backup-password"
export SMTP_USE_TLS_2="true"
export SMTP_NAME_2="outlook_backup"
export SMTP_PRIORITY_2="50"

# Fallback Server
export SMTP_HOST_3="smtp.example.com"
export SMTP_PORT_3="465"
export SMTP_USERNAME_3="fallback@example.com"
export SMTP_PASSWORD_3="fallback-password"
export SMTP_USE_SSL_3="true"
export SMTP_NAME_3="example_fallback"
export SMTP_PRIORITY_3="10"
```

### Common SMTP Provider Settings

#### Gmail
```bash
export SMTP_HOST="smtp.gmail.com"
export SMTP_PORT="587"
export SMTP_USE_TLS="true"
# Use App Password, not regular password
```

#### Outlook/Hotmail
```bash
export SMTP_HOST="smtp-mail.outlook.com"
export SMTP_PORT="587"
export SMTP_USE_TLS="true"
```

#### Yahoo Mail
```bash
export SMTP_HOST="smtp.mail.yahoo.com"
export SMTP_PORT="587"
export SMTP_USE_TLS="true"
```

#### Custom SMTP Server
```bash
export SMTP_HOST="mail.yourdomain.com"
export SMTP_PORT="587"  # or 465 for SSL
export SMTP_USE_TLS="true"  # or SMTP_USE_SSL="true" for port 465
```

## Usage

### Starting the Server

The SMTP MCP Server supports both **stdio** and **HTTP** transports.

#### Stdio Transport (Default)

The default transport uses stdin/stdout for communication:

```bash
# Using UV
uv run python main.py

# Using Python directly
python main.py

# Or explicitly specify stdio transport
python main.py --transport stdio
```

#### HTTP Transport

To run the server with HTTP transport (useful for web-based clients):

```bash
# Start HTTP server on default port 8000
python main.py --transport http

# Specify custom host and port
python main.py --transport http --host 0.0.0.0 --port 8080

# Using UV
uv run python main.py --transport http --port 8000
```

The server will start and you'll see output like:
```
2024-01-01 12:00:00 - server - INFO - SMTP MCP Server - Starting Up
2024-01-01 12:00:00 - server - INFO - Transport: http
2024-01-01 12:00:00 - server - INFO - HTTP Server: 127.0.0.1:8000
2024-01-01 12:00:00 - server - INFO - Configuration validation successful:
2024-01-01 12:00:00 - server - INFO -   - Total SMTP servers: 1
2024-01-01 12:00:00 - server - INFO -   - Available servers: 1
2024-01-01 12:00:00 - server - INFO - Starting SMTP MCP Server with http transport...
2024-01-01 12:00:00 - server - INFO - HTTP server will be available at http://127.0.0.1:8000
```

### Command Line Options

```
usage: main.py [-h] [--transport {stdio,http}] [--host HOST] [--port PORT]

SMTP MCP Server

options:
  -h, --help            show this help message and exit
  --transport {stdio,http}
                        Transport type (default: stdio)
  --host HOST           Host to bind to for HTTP transport (default: 127.0.0.1)
  --port PORT           Port to bind to for HTTP transport (default: 8000)
```

### Connecting to the Server

#### HTTP Transport

When using HTTP transport, the server exposes an HTTP endpoint that MCP clients can connect to:

```
http://127.0.0.1:8000/mcp
```

You can test the connection with curl:
```bash
curl http://127.0.0.1:8000/mcp
```

#### Stdio Transport

MCP servers communicate via stdio transport. To connect to this server, you'll need an MCP client that can communicate via this protocol. The server is designed to be used with AI assistants and other MCP-compatible clients.

### For Development and Testing

You can test the server functionality using the provided test scripts:

```bash
# Test basic functionality
python test_integration.py

# Test multi-server features  
python test_multi_server.py

# Test dynamic reconfiguration
python test_dynamic_reconfiguration.py

# Test server startup
python test_server_startup.py
```

### MCP Client Configuration

#### For HTTP Transport

If you're using HTTP transport, configure your MCP client to connect to the HTTP endpoint:

```json
{
  "mcpServers": {
    "smtp-server": {
      "url": "http://127.0.0.1:8000/mcp",
      "env": {
        "SMTP_HOST": "smtp.gmail.com",
        "SMTP_PORT": "587",
        "SMTP_USERNAME": "your-email@gmail.com",
        "SMTP_PASSWORD": "your-app-password",
        "SMTP_USE_TLS": "true",
        "SMTP_FROM_EMAIL": "your-email@gmail.com"
      }
    }
  }
}
```

#### For Stdio Transport

If you're using stdio transport with an MCP client (like Claude Desktop), configure it to run the server as a subprocess:

```json
{
  "mcpServers": {
    "smtp-server": {
      "command": "python",
      "args": ["/path/to/your/project/main.py"],
      "env": {
        "SMTP_HOST": "smtp.gmail.com",
        "SMTP_PORT": "587",
        "SMTP_USERNAME": "your-email@gmail.com",
        "SMTP_PASSWORD": "your-app-password",
        "SMTP_USE_TLS": "true",
        "SMTP_FROM_EMAIL": "your-email@gmail.com"
      }
    }
  }
}
```

### MCP Tools

The server exposes the following MCP tools:

#### send_email
Send an email via SMTP.

**Parameters:**
- `to` (string, required): Recipient email address (comma-separated for multiple)
- `subject` (string, required): Email subject line
- `body` (string, required): Email body content
- `from_email` (string, optional): Sender email address
- `cc` (string, optional): Carbon copy recipients (comma-separated)
- `bcc` (string, optional): Blind carbon copy recipients (comma-separated)
- `html` (boolean, optional): Whether body content is HTML (default: false)
- `attachments` (array, optional): List of attachments (not yet fully implemented)
- `template_vars` (object, optional): Template variables for substitution

**Example:**
```json
{
  "to": "recipient@example.com",
  "subject": "Hello {name}!",
  "body": "Dear {name},\n\nWelcome to {company}!\n\nBest regards,\nThe Team",
  "html": false,
  "template_vars": {
    "name": "John Doe",
    "company": "Acme Corp"
  }
}
```

#### test_smtp_connection
Test SMTP connection without sending an email.

**Returns:** Connection test results for all configured servers.

#### get_smtp_status
Get SMTP service status and configuration information.

**Returns:** Detailed status including server configurations and availability.

#### switch_smtp_server
Switch to a specific SMTP server or get current server information.

**Parameters:**
- `server_name` (string, optional): Name of server to switch to

#### reload_smtp_configuration
Reload SMTP configuration from environment variables without restart.

**Returns:** Configuration reload results with change summary.

#### reconnect_smtp_servers
Reconnect to SMTP servers without changing configuration.

**Returns:** Reconnection results and server status.

### Email Templates

The server supports powerful template processing with variable substitution and conditional content.

#### Variable Substitution
Use `{variable_name}` syntax for simple variable substitution:

```
Subject: Welcome {name}!
Body: Hello {name}, welcome to {company}!
```

#### Conditional Content
Use `{?variable_name}content{/variable_name}` for conditional blocks:

```
Body: Hello {name}!

{?special_offer}
Special Offer: {special_offer}
Limited time only!
{/special_offer}

Best regards,
{company}
```

### Attachments

Create attachments using the Attachment class:

```python
from server import Attachment

# From file path
attachment = Attachment.from_file_path("/path/to/document.pdf")

# From bytes content
attachment = Attachment.from_bytes(
    filename="report.txt",
    content=b"Report content here",
    mime_type="text/plain"
)
```

## Deployment

### Docker Deployment

#### Production Deployment with Docker Compose

1. **Prepare Environment**:
```bash
# Clone and setup
git clone <repository-url>
cd py-mcp-server-smtp

# Configure environment
cp .env.example .env
# Edit .env with your production SMTP settings
```

2. **Deploy with Stdio Transport** (for MCP clients):
```bash
# Start the service
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the service
docker-compose down
```

3. **Deploy with HTTP Transport** (for web clients):
```bash
# Start HTTP service
docker-compose --profile http up -d smtp-mcp-server-http

# Access at http://localhost:8000/mcp
curl http://localhost:8000/mcp
```

#### Docker Security Best Practices

The provided Dockerfile follows security best practices:
- Runs as non-root user (`appuser`)
- Uses Python slim image to minimize attack surface
- Includes health checks for monitoring
- Sets resource limits in docker-compose.yml
- Excludes sensitive files via .dockerignore

#### Kubernetes Deployment

For Kubernetes deployment, create these manifests:

```yaml
# smtp-mcp-server-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: smtp-mcp-server
spec:
  replicas: 1
  selector:
    matchLabels:
      app: smtp-mcp-server
  template:
    metadata:
      labels:
        app: smtp-mcp-server
    spec:
      containers:
      - name: smtp-mcp-server
        image: smtp-mcp-server:latest
        ports:
        - containerPort: 8000
        env:
        - name: SMTP_HOST
          valueFrom:
            secretKeyRef:
              name: smtp-config
              key: host
        - name: SMTP_USERNAME
          valueFrom:
            secretKeyRef:
              name: smtp-config
              key: username
        - name: SMTP_PASSWORD
          valueFrom:
            secretKeyRef:
              name: smtp-config
              key: password
        args: ["python", "main.py", "--transport", "http", "--host", "0.0.0.0"]
        resources:
          limits:
            memory: "256Mi"
            cpu: "500m"
          requests:
            memory: "128Mi"
            cpu: "250m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 30
```

### Traditional Deployment

For traditional server deployment:

```bash
# Install system dependencies
sudo apt-get update
sudo apt-get install python3.12 python3.12-venv

# Create application user
sudo useradd -r -s /bin/false smtp-mcp-server

# Setup application
sudo mkdir -p /opt/smtp-mcp-server
sudo chown smtp-mcp-server:smtp-mcp-server /opt/smtp-mcp-server

# Deploy application
sudo -u smtp-mcp-server git clone <repo> /opt/smtp-mcp-server
cd /opt/smtp-mcp-server
sudo -u smtp-mcp-server python3.12 -m venv .venv
sudo -u smtp-mcp-server .venv/bin/pip install -r requirements.txt

# Create systemd service
sudo tee /etc/systemd/system/smtp-mcp-server.service << EOF
[Unit]
Description=SMTP MCP Server
After=network.target

[Service]
Type=simple
User=smtp-mcp-server
WorkingDirectory=/opt/smtp-mcp-server
Environment=PATH=/opt/smtp-mcp-server/.venv/bin
EnvironmentFile=/opt/smtp-mcp-server/.env
ExecStart=/opt/smtp-mcp-server/.venv/bin/python main.py --transport http --host 0.0.0.0
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Start service
sudo systemctl enable smtp-mcp-server
sudo systemctl start smtp-mcp-server
```

## Testing

The project includes comprehensive test suites:

### Running All Tests
```bash
# Run integration tests
python test_integration.py

# Run multi-server tests
python test_multi_server.py

# Run dynamic reconfiguration tests
python test_dynamic_reconfiguration.py

# Run minimal functionality tests
python test_minimal.py
```

### Test Categories

1. **Integration Tests** (`test_integration.py`): End-to-end email flow testing
2. **Multi-Server Tests** (`test_multi_server.py`): Multi-server and failover functionality
3. **Dynamic Reconfiguration Tests** (`test_dynamic_reconfiguration.py`): Configuration management
4. **Unit Tests**: Individual component testing

## Architecture

### Components

- **EmailService**: Main orchestration service coordinating all components
- **MultiServerSMTPClient**: Multi-server SMTP client with automatic failover
- **SMTPClient**: Individual SMTP server connection management
- **EmailMessageBuilder**: Email message construction and formatting
- **TemplateEngine**: Template processing and variable substitution
- **AttachmentHandler**: File attachment processing and encoding

### Multi-Server Architecture

The server supports multiple SMTP configurations with automatic failover:

1. **Priority-Based Selection**: Servers are tried in priority order (highest first)
2. **Automatic Failover**: Failed servers are automatically skipped
3. **Backoff Strategy**: Failed servers are temporarily excluded with exponential backoff
4. **Health Monitoring**: Continuous monitoring of server availability
5. **Dynamic Switching**: Manual server switching via MCP tools

### Security Features

- **Credential Protection**: Passwords are never logged or exposed
- **TLS/SSL Support**: Full encryption support for secure connections
- **Input Validation**: Comprehensive validation of all inputs
- **Error Sanitization**: Sensitive information is sanitized from error messages

## Troubleshooting

### Common Issues

#### Authentication Errors
```
SMTP authentication failed for user@gmail.com: (535, '5.7.8 Username and Password not accepted')
```

**Solutions:**
- For Gmail: Use App Passwords instead of regular passwords
- Enable 2-factor authentication and generate an app-specific password
- Check that the username and password are correct

#### Connection Timeouts
```
SMTP connection failed: [Errno 110] Connection timed out
```

**Solutions:**
- Check firewall settings
- Verify SMTP server hostname and port
- Try different ports (587 for STARTTLS, 465 for SSL)
- Check network connectivity

#### TLS/SSL Errors
```
SSL: CERTIFICATE_VERIFY_FAILED
```

**Solutions:**
- Ensure correct TLS/SSL configuration
- Use `SMTP_USE_TLS="true"` for port 587
- Use `SMTP_USE_SSL="true"` for port 465
- Check server certificate validity

### Debugging

Enable debug logging:
```bash
export LOG_LEVEL="DEBUG"
python main.py
```

This will provide detailed information about:
- SMTP connection attempts
- Authentication processes
- Message construction
- Server failover decisions
- Template processing steps

### Configuration Validation

Test your configuration:
```bash
# Test SMTP connection
python -c "
import asyncio
from server import get_email_service
async def test():
    service = get_email_service()
    result = await service.test_connection()
    print(result)
asyncio.run(test())
"
```

## Development

### Project Structure
```
py-mcp-server-smtp/
├── main.py                 # Application entry point
├── server.py              # Main MCP server implementation
├── test_integration.py    # Integration tests
├── test_multi_server.py   # Multi-server tests
├── test_dynamic_reconfiguration.py  # Configuration tests
├── pyproject.toml         # Project configuration
├── uv.lock               # Dependency lock file
└── README.md             # This file
```

### Adding New Features

1. **Email Features**: Extend the `EmailService` class
2. **SMTP Features**: Modify the `SMTPClient` or `MultiServerSMTPClient` classes
3. **MCP Tools**: Add new tools using the `@mcp.tool()` decorator
4. **Template Features**: Enhance the `TemplateEngine` class

### Testing Guidelines

- Write integration tests for end-to-end functionality
- Use mock SMTP servers to avoid external dependencies
- Test error conditions and edge cases
- Verify thread safety for concurrent operations
- Test multi-server failover scenarios

## License

[Add your license information here]

## Contributing

[Add contribution guidelines here]

## Support

For issues and questions:
1. Check the troubleshooting section above
2. Review the test files for usage examples
3. Enable debug logging for detailed diagnostics
4. [Add support contact information]