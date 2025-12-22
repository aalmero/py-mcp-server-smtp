"""
Main entry point for the SMTP MCP Server.

This module provides the main entry point for starting the SMTP MCP server,
supporting both stdio and HTTP transports, including server startup logic, 
graceful shutdown handling, and startup configuration validation.
"""

import asyncio
import logging
import signal
import sys
import os
import argparse
from typing import Optional

# Import the FastMCP server instance from server.py
from server import mcp, logger


def setup_logging() -> None:
    """
    Configure logging for the application.
    
    Sets up logging level based on environment variables and configures
    appropriate formatters for console output.
    """
    # Get log level from environment variable (default: INFO)
    log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
    
    # Map string levels to logging constants
    level_map = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL
    }
    
    level = level_map.get(log_level, logging.INFO)
    
    # Configure root logger
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    logger.info(f"Logging configured at {log_level} level")


def validate_startup_configuration() -> bool:
    """
    Validate SMTP configuration on startup.
    
    Performs basic validation of SMTP configuration parameters
    to ensure the server can start successfully.
    
    Returns:
        bool: True if configuration is valid, False otherwise
        
    Raises:
        SystemExit: If critical configuration errors are found
    """
    try:
        logger.info("Validating startup configuration...")
        
        # Basic validation - just check that required environment variables exist
        # Avoid any async operations or service initialization
        required_vars = ['SMTP_HOST', 'SMTP_PORT', 'SMTP_USERNAME', 'SMTP_PASSWORD']
        missing_vars = []
        
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        # Check for numbered configurations as well
        server_index = 1
        has_numbered_config = False
        while True:
            suffix = f"_{server_index}"
            host_var = f"SMTP_HOST{suffix}"
            if os.getenv(host_var):
                has_numbered_config = True
                # Check required vars for this numbered config
                numbered_required = [f'SMTP_HOST{suffix}', f'SMTP_PORT{suffix}', 
                                   f'SMTP_USERNAME{suffix}', f'SMTP_PASSWORD{suffix}']
                for var in numbered_required:
                    if not os.getenv(var):
                        missing_vars.append(var)
                server_index += 1
            else:
                break
        
        if missing_vars and not has_numbered_config:
            logger.error(f"Missing required SMTP configuration environment variables: {', '.join(missing_vars)}")
            logger.error("Please set the following environment variables:")
            for var in required_vars:
                logger.error(f"  - {var}")
            return False
        
        if has_numbered_config:
            logger.info(f"Configuration validation successful:")
            logger.info(f"  - Found {server_index - 1} numbered SMTP server configurations")
        else:
            logger.info(f"Configuration validation successful:")
            logger.info(f"  - Found single SMTP server configuration")
        
        return True
        
    except Exception as e:
        logger.error(f"Startup configuration validation failed: {e}")
        return False


class GracefulShutdownHandler:
    """
    Handler for graceful shutdown of the SMTP MCP server.
    
    Manages cleanup of resources and connections when the server
    receives shutdown signals.
    """
    
    def __init__(self):
        self.shutdown_event = asyncio.Event()
        self.shutdown_requested = False
    
    def setup_signal_handlers(self) -> None:
        """
        Set up signal handlers for graceful shutdown.
        
        Registers handlers for SIGINT (Ctrl+C) and SIGTERM signals
        to initiate graceful shutdown process.
        """
        def signal_handler(signum, frame):
            signal_name = signal.Signals(signum).name
            logger.info(f"Received {signal_name} signal, initiating graceful shutdown...")
            self.shutdown_requested = True
            
            # Set the shutdown event in the event loop
            try:
                loop = asyncio.get_running_loop()
                loop.call_soon_threadsafe(self.shutdown_event.set)
            except RuntimeError:
                # No running event loop, set the event directly
                asyncio.run(self._set_shutdown_event())
        
        # Register signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        logger.debug("Signal handlers registered for graceful shutdown")
    
    async def _set_shutdown_event(self) -> None:
        """Set the shutdown event asynchronously."""
        self.shutdown_event.set()
    
    async def wait_for_shutdown(self) -> None:
        """
        Wait for shutdown signal.
        
        This coroutine blocks until a shutdown signal is received.
        """
        await self.shutdown_event.wait()
    
    async def cleanup(self) -> None:
        """
        Perform cleanup operations during shutdown.
        
        Disconnects from SMTP servers and cleans up resources.
        """
        try:
            logger.info("Performing cleanup operations...")
            
            # Get email service and disconnect SMTP clients
            try:
                # Import here to avoid circular imports and startup issues
                from server import get_email_service
                service = get_email_service()
                await service.smtp_client.disconnect()
                logger.info("SMTP connections closed successfully")
            except Exception as e:
                logger.warning(f"Error during SMTP cleanup: {e}")
            
            logger.info("Cleanup completed successfully")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


async def run_server(transport: str = "stdio", host: str = "127.0.0.1", port: int = 8000) -> None:
    """
    Run the SMTP MCP server with graceful shutdown support.
    
    This is the main server loop that starts the FastMCP server
    and handles graceful shutdown when signals are received.
    
    Args:
        transport: Transport type ("stdio" or "http")
        host: Host to bind to for HTTP transport
        port: Port to bind to for HTTP transport
    """
    shutdown_handler = GracefulShutdownHandler()
    shutdown_handler.setup_signal_handlers()
    
    try:
        logger.info(f"Starting SMTP MCP Server with {transport} transport...")
        
        if transport == "http":
            logger.info(f"HTTP server will be available at http://{host}:{port}/mcp")
            # Start the FastMCP server with HTTP transport using the built-in method
            await mcp.run_http_async(host=host, port=port)
            
        else:
            # Start the FastMCP server with stdio transport
            logger.info("Server running with stdio transport (stdin/stdout)")
            await mcp.run_stdio_async()
        
    except Exception as e:
        logger.error(f"Server error: {e}")
        raise
    finally:
        # Perform cleanup
        await shutdown_handler.cleanup()
        logger.info("SMTP MCP Server stopped")


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="SMTP MCP Server")
    parser.add_argument(
        "--transport", 
        choices=["stdio", "http"], 
        default="stdio",
        help="Transport type (default: stdio)"
    )
    parser.add_argument(
        "--host", 
        default="127.0.0.1",
        help="Host to bind to for HTTP transport (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port", 
        type=int, 
        default=8000,
        help="Port to bind to for HTTP transport (default: 8000)"
    )
    return parser.parse_args()


def main() -> None:
    """
    Main entry point for the SMTP MCP Server.
    
    Performs startup configuration validation, sets up logging,
    and starts the server with graceful shutdown handling.
    
    Requirements:
    - 1.1: SMTP server connection management
    - 5.5: Startup configuration validation
    """
    try:
        # Parse command line arguments first (this handles --help)
        args = parse_arguments()
        
        # Set up logging after argument parsing
        setup_logging()
        
        logger.info("=" * 60)
        logger.info("SMTP MCP Server - Starting Up")
        logger.info(f"Transport: {args.transport}")
        if args.transport == "http":
            logger.info(f"HTTP Server: {args.host}:{args.port}")
        logger.info("=" * 60)
        
        # Validate startup configuration
        if not validate_startup_configuration():
            logger.error("Startup configuration validation failed - exiting")
            sys.exit(1)
        
        # Run the server
        try:
            asyncio.run(run_server(args.transport, args.host, args.port))
        except KeyboardInterrupt:
            logger.info("Server interrupted by user")
        except Exception as e:
            logger.error(f"Server failed: {e}")
            sys.exit(1)
        
    except SystemExit:
        # Handle --help and other argparse exits gracefully
        raise
    except Exception as e:
        print(f"Fatal error during startup: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()