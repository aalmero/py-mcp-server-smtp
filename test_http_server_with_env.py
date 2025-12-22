#!/usr/bin/env python3
"""
Test HTTP server with environment variables set.
"""

import os
import subprocess
import time
import requests
import signal
import sys

# Set test environment variables
os.environ['SMTP_HOST'] = 'smtp.test.com'
os.environ['SMTP_PORT'] = '587'
os.environ['SMTP_USERNAME'] = 'test@test.com'
os.environ['SMTP_PASSWORD'] = 'password'
os.environ['SMTP_USE_TLS'] = 'true'
os.environ['SMTP_FROM_EMAIL'] = 'test@test.com'

def test_http_server():
    """Test the HTTP server startup and basic functionality."""
    print("Starting HTTP server test...")
    
    # Start the server process
    server_process = None
    try:
        print("Starting SMTP MCP server with HTTP transport...")
        server_process = subprocess.Popen(
            ['.venv/bin/python', 'main.py', '--transport', 'http', '--port', '8001'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Wait a bit for server to start
        print("Waiting for server to start...")
        time.sleep(3)
        
        # Check if server is running
        if server_process.poll() is not None:
            stdout, stderr = server_process.communicate()
            print(f"Server failed to start!")
            print(f"STDOUT: {stdout}")
            print(f"STDERR: {stderr}")
            return False
        
        # Test if server is accessible
        try:
            print("Testing server accessibility at http://127.0.0.1:8001/mcp")
            response = requests.get("http://127.0.0.1:8001/mcp", timeout=5)
            print(f"Server response status: {response.status_code}")
            print("✓ HTTP server is accessible!")
            return True
        except requests.exceptions.RequestException as e:
            print(f"✗ Server not accessible: {e}")
            return False
            
    except Exception as e:
        print(f"✗ Test failed: {e}")
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
            print("Server stopped.")

if __name__ == "__main__":
    success = test_http_server()
    print(f"Test result: {'PASSED' if success else 'FAILED'}")
    sys.exit(0 if success else 1)