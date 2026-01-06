"""
SMTP MCP Server Implementation

This module provides SMTP email functionality through the MCP (Model Context Protocol) framework.
"""

import os
import logging
import re
import smtplib
import ssl
import time
import uuid
import mimetypes
import base64
import threading
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from email.utils import formataddr, formatdate
from fastmcp import FastMCP

from smtp import (EmailService, SMTPConfig, EmailRequest, EmailResponse, load_smtp_config, load_smtp_configs)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Attachment size limits (in bytes)
MAX_ATTACHMENT_SIZE = 25 * 1024 * 1024  # 25MB default limit
MAX_TOTAL_ATTACHMENTS_SIZE = 50 * 1024 * 1024  # 50MB total limit


# Email validation regex pattern
EMAIL_REGEX = re.compile(
    r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
)


def validate_email_address(email: str) -> bool:
    """
    Validate email address format using regex.
    
    Args:
        email: Email address to validate
        
    Returns:
        bool: True if email format is valid, False otherwise
    """
    if not email or not isinstance(email, str):
        return False
    
    email = email.strip()
    if not email:
        return False
    
    return bool(EMAIL_REGEX.match(email))


def validate_email_list(email_list: str) -> List[str]:
    """
    Validate and parse a comma-separated list of email addresses.
    
    Args:
        email_list: Comma-separated string of email addresses
        
    Returns:
        List[str]: List of valid email addresses
        
    Raises:
        ValueError: If any email address is invalid
    """
    if not email_list or not isinstance(email_list, str):
        return []
    
    emails = [email.strip() for email in email_list.split(',') if email.strip()]
    invalid_emails = []
    
    for email in emails:
        if not validate_email_address(email):
            invalid_emails.append(email)
    
    if invalid_emails:
        raise ValueError(f"Invalid email addresses: {', '.join(invalid_emails)}")
    
    return emails


# Initialize FastMCP server
mcp = FastMCP("smtp-server")

# Global email service instance (will be initialized when server starts)
email_service: Optional[EmailService] = None
email_service_lock = threading.RLock()


def get_email_service() -> EmailService:
    """
    Get or create email service instance with multi-server support.
    
    Returns:
        EmailService: Configured email service instance
        
    Raises:
        RuntimeError: If SMTP configuration is not available
    """
    global email_service
    
    with email_service_lock:
        if email_service is None:
            try:
                configs = load_smtp_configs()
                email_service = EmailService(configs)
                logger.info("Multi-server email service initialized successfully")
            except Exception as e:
                error_msg = f"Failed to initialize email service: {e}"
                logger.error(error_msg)
                raise RuntimeError(error_msg) from e
        
        return email_service


def reset_email_service() -> None:
    """
    Reset the global email service instance.
    
    This function is used internally by the dynamic reconfiguration system
    to force reinitialization of the email service with new configuration.
    """
    global email_service
    
    with email_service_lock:
        if email_service:
            try:
                # Attempt to disconnect cleanly
                import asyncio
                try:
                    loop = asyncio.get_running_loop()
                    # If we're in an async context, schedule the disconnect
                    asyncio.create_task(email_service.smtp_client.disconnect())
                except RuntimeError:
                    # No running event loop, we can run the disconnect directly
                    try:
                        asyncio.run(email_service.smtp_client.disconnect())
                    except Exception as e:
                        logger.warning(f"Error during SMTP disconnect: {e}")
            except Exception as e:
                logger.warning(f"Error during email service cleanup: {e}")
            finally:
                email_service = None
                logger.debug("Global email service instance reset")


@mcp.tool()
async def send_email(
    to: str,
    subject: str,
    body: str,
    from_email: str = None,
    cc: str = None,
    bcc: str = None,
    html: bool = False,
    attachments: list = None,
    template_vars: dict = None
) -> dict:
    """
    Send an email via SMTP.
    
    Args:
        to: Recipient email address (comma-separated for multiple)
        subject: Email subject line
        body: Email body content
        from_email: Sender email address (optional, uses config default)
        cc: Carbon copy recipients (optional, comma-separated)
        bcc: Blind carbon copy recipients (optional, comma-separated)
        html: Whether body content is HTML (default: False)
        attachments: List of attachments (optional) - not yet implemented
        template_vars: Template variables for substitution (optional)
    
    Returns:
        dict: Response containing success status and details
    """
    try:
        logger.info(f"MCP send_email tool called for recipients: {to}")
        
        # Get email service instance
        service = get_email_service()
        
        # Convert attachments from list of dicts to Attachment objects if provided
        attachment_objects = None
        if attachments:
            try:
                attachment_objects = []
                for att_dict in attachments:
                    if isinstance(att_dict, dict):
                        # Convert dict to Attachment object
                        # This is a simplified implementation - full attachment support
                        # would require handling file uploads through MCP protocol
                        attachment = Attachment(
                            filename=att_dict.get('filename', 'attachment'),
                            content=att_dict.get('content', b''),
                            mime_type=att_dict.get('mime_type', 'application/octet-stream'),
                            content_id=att_dict.get('content_id')
                        )
                        attachment_objects.append(attachment)
                    else:
                        logger.warning(f"Invalid attachment format: {type(att_dict)}")
            except Exception as e:
                logger.error(f"Failed to process attachments: {e}")
                return {
                    "success": False,
                    "error": f"Invalid attachment format: {e}"
                }
        
        # Create email request
        try:
            email_request = EmailRequest(
                to=to,
                subject=subject,
                body=body,
                from_email=from_email,
                cc=cc,
                bcc=bcc,
                html=html,
                attachments=attachment_objects,
                template_vars=template_vars
            )
        except Exception as e:
            logger.error(f"Failed to create email request: {e}")
            return {
                "success": False,
                "error": f"Invalid email request: {e}"
            }
        
        # Send email through service
        response = await service.send_email(email_request)
        
        # Convert EmailResponse to dict for MCP protocol
        result = {
            "success": response.success,
        }
        
        if response.success:
            result["message_id"] = response.message_id
            if response.details:
                result["details"] = response.details
        else:
            result["error"] = response.error
            if response.details:
                result["details"] = response.details
        
        return result
        
    except Exception as e:
        error_msg = f"MCP send_email tool failed: {e}"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg
        }


@mcp.tool()
async def test_smtp_connection() -> dict:
    """
    Test SMTP connection without sending an email.
    
    Returns:
        dict: Connection test result
    """
    try:
        logger.info("MCP test_smtp_connection tool called")
        
        # Get email service instance
        service = get_email_service()
        
        # Test connection
        result = await service.test_connection()
        
        return result
        
    except Exception as e:
        error_msg = f"SMTP connection test failed: {e}"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg
        }


@mcp.tool()
async def get_smtp_status() -> dict:
    """
    Get SMTP service status and configuration information.
    
    Returns:
        dict: Service status and configuration including multi-server details
    """
    try:
        logger.info("MCP get_smtp_status tool called")
        
        # Get email service instance
        service = get_email_service()
        
        # Get service status
        status = service.get_service_status()
        
        return status
        
    except Exception as e:
        error_msg = f"Failed to get SMTP status: {e}"
        logger.error(error_msg)
        return {
            "service": "SMTP MCP Server",
            "status": "error",
            "error": error_msg
        }


@mcp.tool()
async def switch_smtp_server(server_name: str = None) -> dict:
    """
    Switch to a specific SMTP server or get current server information.
    
    Args:
        server_name: Name of the server to switch to (optional)
    
    Returns:
        dict: Server switch result or current server information
    """
    try:
        logger.info(f"MCP switch_smtp_server tool called with server: {server_name}")
        
        # Get email service instance
        service = get_email_service()
        
        if server_name:
            # Find the requested server configuration
            target_config = None
            for config in service.configs:
                if config.name == server_name:
                    target_config = config
                    break
            
            if not target_config:
                available_servers = [config.name for config in service.configs]
                return {
                    "success": False,
                    "error": f"Server '{server_name}' not found",
                    "available_servers": available_servers
                }
            
            # Disconnect current connection to force reconnection to specific server
            await service.smtp_client.disconnect()
            
            # Temporarily modify the server list to prioritize the requested server
            original_configs = service.configs.copy()
            service.configs = [target_config] + [c for c in original_configs if c.name != server_name]
            service.smtp_client.configs = service.configs
            
            try:
                # Test connection to the specific server
                await service.smtp_client.connect()
                current_server = service.smtp_client.get_current_server()
                
                return {
                    "success": True,
                    "message": f"Successfully switched to server: {server_name}",
                    "current_server": current_server.name if current_server else None,
                    "server_details": {
                        "name": current_server.name,
                        "host": f"{current_server.host}:{current_server.port}",
                        "priority": current_server.priority
                    } if current_server else None
                }
                
            except Exception as e:
                # Restore original configuration on failure
                service.configs = original_configs
                service.smtp_client.configs = original_configs
                
                return {
                    "success": False,
                    "error": f"Failed to switch to server '{server_name}': {e}",
                    "current_server": service.smtp_client.get_current_server().name if service.smtp_client.get_current_server() else None
                }
        else:
            # Just return current server information
            current_server = service.smtp_client.get_current_server()
            server_status = service.smtp_client.get_server_status()
            
            return {
                "success": True,
                "current_server": current_server.name if current_server else None,
                "server_details": {
                    "name": current_server.name,
                    "host": f"{current_server.host}:{current_server.port}",
                    "priority": current_server.priority
                } if current_server else None,
                "server_status": server_status
            }
        
    except Exception as e:
        error_msg = f"Failed to switch SMTP server: {e}"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg
        }


@mcp.tool()
async def reload_smtp_configuration() -> dict:
    """
    Reload SMTP configuration from environment variables and reconnect without restart.
    
    This tool provides dynamic reconfiguration support by reloading SMTP server
    configurations from environment variables and reconnecting to servers with
    the new configuration. Includes validation and rollback on failure.
    
    Returns:
        dict: Configuration reload result with change details
    """
    try:
        logger.info("MCP reload_smtp_configuration tool called")
        
        # Get email service instance
        service = get_email_service()
        
        # Perform configuration reload
        result = await service.reload_configuration()
        
        return result
        
    except Exception as e:
        error_msg = f"SMTP configuration reload failed: {e}"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg
        }


@mcp.tool()
async def reconnect_smtp_servers() -> dict:
    """
    Reconnect to SMTP servers without changing configuration.
    
    Forces a reconnection to all SMTP servers using the current configuration.
    Useful for recovering from network issues or server restarts without
    requiring a full configuration reload.
    
    Returns:
        dict: Reconnection result with server status
    """
    try:
        logger.info("MCP reconnect_smtp_servers tool called")
        
        # Get email service instance
        service = get_email_service()
        
        # Perform server reconnection
        result = await service.reconnect_smtp_servers()
        
        return result
        
    except Exception as e:
        error_msg = f"SMTP server reconnection failed: {e}"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg
        }


# FastMCP server instance is initialized and ready to be imported by main.py
# The server will be started by main.py using the FastMCP framework