#!/usr/bin/env python3
"""
Simple test to check FastMCP HTTP functionality.
"""

import os
import asyncio

# Set test environment variables
os.environ['SMTP_HOST'] = 'smtp.test.com'
os.environ['SMTP_PORT'] = '587'
os.environ['SMTP_USERNAME'] = 'test@test.com'
os.environ['SMTP_PASSWORD'] = 'password'
os.environ['SMTP_USE_TLS'] = 'true'
os.environ['SMTP_FROM_EMAIL'] = 'test@test.com'

async def test_fastmcp_http():
    """Test FastMCP HTTP server directly."""
    try:
        from server import mcp
        print("✓ FastMCP server imported successfully")
        
        print("Available methods:")
        for method in ['run_http_async', 'run_stdio_async', 'http_app']:
            if hasattr(mcp, method):
                print(f"  ✓ {method}")
            else:
                print(f"  ✗ {method}")
        
        # Try to get the HTTP app
        try:
            app = mcp.http_app()
            print(f"✓ HTTP app created: {type(app)}")
        except Exception as e:
            print(f"✗ Failed to create HTTP app: {e}")
            return False
        
        # Try to run HTTP server for a short time
        print("Testing HTTP server startup...")
        try:
            # Use asyncio.wait_for to timeout the server after a few seconds
            await asyncio.wait_for(
                mcp.run_http_async(host="127.0.0.1", port=8002),
                timeout=2.0
            )
        except asyncio.TimeoutError:
            print("✓ HTTP server started successfully (timed out as expected)")
            return True
        except Exception as e:
            print(f"✗ HTTP server failed to start: {e}")
            return False
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    try:
        result = asyncio.run(test_fastmcp_http())
        print(f"Test result: {'PASSED' if result else 'FAILED'}")
    except Exception as e:
        print(f"Test failed with exception: {e}")
        import traceback
        traceback.print_exc()