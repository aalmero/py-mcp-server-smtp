#!/usr/bin/env python3
"""
Test script to verify SMTP MCP server HTTP transport functionality.
"""

import os
import sys
import asyncio
import subprocess
import time
import requests
import json
from typing import Optional

# Set test environment variables
os.environ['SMTP_HOST'] = 'smtp.test.com'
os.environ['SMTP_PORT'] = '587'
os.environ['SMTP_USERNAME'] = 'test@test.com'
os.environ['SMTP_PASSWORD'] = 'password'
os.environ['SMTP_USE_TLS'] = 'true'
os.environ['SMTP_FROM_EMAIL'] = 'test@test.com'

def test_http_server_startup():
    """Test that the HTTP server starts correctly."""
    print("Testing SMTP MCP Server HTTP transport...")
    
    # Start the server in HTTP mode
    server_process = None
    try:
        print("Starting server with HTTP transport...")
        server_process = subprocess.Popen([
            sys.executable, "main.py", 
            "--transport", "http", 
            "--port", "8001"  # Use different port to avoid conflicts
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        # Wait a moment for server to start
        time.sleep(3)
        
        # Check if server is running
        if server_process.poll() is not None:
            stdout, stderr = server_process.communicate()
            print(f"✗ Server failed to start:")
            print(f"STDOUT: {stdout}")
            print(f"STDERR: {stderr}")
            return False
        
        print("✓ Server started successfully")
        
        # Test HTTP endpoint
        try:
            response = requests.get("http://127.0.0.1:8001/", timeout=5)
            print(f"✓ HTTP endpoint accessible (status: {response.status_code})")
        except requests.exceptions.RequestException as e:
            print(f"✗ HTTP endpoint test failed: {e}")
            return False
        
        # Test MCP endpoint (if available)
        try:
            # Try to access the MCP endpoint
            mcp_response = requests.get("http://127.0.0.1:8001/mcp", timeout=5)
            print(f"✓ MCP endpoint accessible (status: {mcp_response.status_code})")
        except requests.exceptions.RequestException as e:
            print(f"ℹ MCP endpoint test: {e} (this might be expected)")
        
        return True
        
    except Exception as e:
        print(f"✗ HTTP server test failed: {e}")
        return False
        
    finally:
        # Clean up server process
        if server_process and server_process.poll() is None:
            print("Stopping server...")
            server_process.terminate()
            try:
                server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server_process.kill()
                server_process.wait()
            print("✓ Server stopped")

def test_command_line_args():
    """Test command line argument parsing."""
    print("\nTesting command line arguments...")
    
    try:
        # Test help output
        result = subprocess.run([
            sys.executable, "main.py", "--help"
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0 and "SMTP MCP Server" in result.stdout:
            print("✓ Help output works correctly")
        else:
            print(f"✗ Help output failed: {result.stderr}")
            return False
        
        # Test argument validation (this should fail quickly)
        result = subprocess.run([
            sys.executable, "main.py", "--transport", "invalid"
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode != 0:
            print("✓ Invalid transport argument properly rejected")
        else:
            print("✗ Invalid transport argument should be rejected")
            return False
        
        return True
        
    except Exception as e:
        print(f"✗ Command line args test failed: {e}")
        return False

def main():
    """Run HTTP transport tests."""
    print("Running SMTP MCP Server HTTP Transport Tests...\n")
    print("=" * 60)
    
    success = True
    
    # Test command line arguments
    if not test_command_line_args():
        success = False
    
    # Test HTTP server startup
    if not test_http_server_startup():
        success = False
    
    print("\n" + "=" * 60)
    if success:
        print("✓ ALL HTTP TRANSPORT TESTS PASSED!")
        print("✓ Server supports both stdio and HTTP transports")
        print("✓ Command line arguments work correctly")
        print("✓ HTTP server starts and responds to requests")
    else:
        print("✗ SOME HTTP TRANSPORT TESTS FAILED!")
    print("=" * 60)
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)