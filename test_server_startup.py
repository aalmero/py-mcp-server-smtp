#!/usr/bin/env python3
"""
Test script to verify SMTP MCP server startup and configuration.
"""

import os
import sys

# Set test environment variables
os.environ['SMTP_HOST'] = 'smtp.test.com'
os.environ['SMTP_PORT'] = '587'
os.environ['SMTP_USERNAME'] = 'test@test.com'
os.environ['SMTP_PASSWORD'] = 'password'
os.environ['SMTP_USE_TLS'] = 'true'
os.environ['SMTP_FROM_EMAIL'] = 'test@test.com'

def test_server_startup():
    """Test that the server can be imported and initialized."""
    try:
        print("Testing SMTP MCP Server startup...")
        
        # Test server imports
        from server import mcp, get_email_service
        print('✓ Server imports successfully')
        
        # Test configuration validation
        service = get_email_service()
        status = service.get_service_status()
        print(f'✓ Configuration validation: {status.get("status", "unknown")}')
        print(f'✓ Total servers: {status.get("total_servers", 0)}')
        
        # Test that FastMCP server is properly initialized
        print(f'✓ FastMCP server name: {mcp.name}')
        
        # Test that tools are registered
        tools = mcp.list_tools()
        print(f'✓ Registered tools: {len(tools)} tools')
        for tool in tools:
            print(f'  - {tool.name}')
        
        print('✓ Server is ready to run')
        return True
        
    except Exception as e:
        print(f'✗ Server initialization failed: {e}')
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_server_startup()
    sys.exit(0 if success else 1)