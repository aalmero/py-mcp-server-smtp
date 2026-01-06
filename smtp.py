"""
SMTP Server Implementation

This module provides SMTP email functionality.
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


@dataclass
class Attachment:
    """Email attachment data model."""
    
    filename: str
    content: bytes
    mime_type: str
    content_id: Optional[str] = None
    
    def __post_init__(self):
        """Validate attachment data after initialization."""
        if not self.filename or not isinstance(self.filename, str):
            raise ValueError("Attachment filename must be a non-empty string")
        
        if not isinstance(self.content, bytes):
            raise ValueError("Attachment content must be bytes")
        
        if not self.mime_type or not isinstance(self.mime_type, str):
            raise ValueError("Attachment MIME type must be a non-empty string")
        
        # Basic MIME type validation
        if '/' not in self.mime_type:
            raise ValueError(f"Invalid MIME type format: {self.mime_type}")
        
        # Validate attachment size
        if len(self.content) > MAX_ATTACHMENT_SIZE:
            size_mb = len(self.content) / (1024 * 1024)
            limit_mb = MAX_ATTACHMENT_SIZE / (1024 * 1024)
            raise ValueError(
                f"Attachment '{self.filename}' size ({size_mb:.1f}MB) exceeds maximum allowed size ({limit_mb}MB)"
            )
        
        # Validate filename for security (basic check)
        if '..' in self.filename or '/' in self.filename or '\\' in self.filename:
            raise ValueError(f"Invalid filename: {self.filename}. Filenames cannot contain path separators or '..'")
    
    @classmethod
    def from_file_path(cls, file_path: str, content_id: Optional[str] = None) -> 'Attachment':
        """
        Create an attachment from a file path.
        
        Args:
            file_path: Path to the file to attach
            content_id: Optional content ID for inline attachments
            
        Returns:
            Attachment: Created attachment object
            
        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file is too large or invalid
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Attachment file not found: {file_path}")
        
        # Get filename from path
        filename = os.path.basename(file_path)
        
        # Read file content
        with open(file_path, 'rb') as f:
            content = f.read()
        
        # Detect MIME type
        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            mime_type = 'application/octet-stream'  # Default binary type
        
        return cls(
            filename=filename,
            content=content,
            mime_type=mime_type,
            content_id=content_id
        )
    
    @classmethod
    def from_bytes(
        cls,
        filename: str,
        content: bytes,
        mime_type: Optional[str] = None,
        content_id: Optional[str] = None
    ) -> 'Attachment':
        """
        Create an attachment from bytes content.
        
        Args:
            filename: Name of the attachment file
            content: File content as bytes
            mime_type: MIME type (auto-detected if not provided)
            content_id: Optional content ID for inline attachments
            
        Returns:
            Attachment: Created attachment object
        """
        # Auto-detect MIME type if not provided
        if not mime_type:
            mime_type, _ = mimetypes.guess_type(filename)
            if not mime_type:
                mime_type = 'application/octet-stream'
        
        return cls(
            filename=filename,
            content=content,
            mime_type=mime_type,
            content_id=content_id
        )
    
    def get_size_mb(self) -> float:
        """Get attachment size in megabytes."""
        return len(self.content) / (1024 * 1024)
    
    def is_inline(self) -> bool:
        """Check if attachment is inline (has content_id)."""
        return self.content_id is not None


@dataclass
class EmailRequest:
    """Email request data model with validation."""
    
    to: str
    subject: str
    body: str
    from_email: Optional[str] = None
    cc: Optional[str] = None
    bcc: Optional[str] = None
    html: bool = False
    attachments: Optional[List[Attachment]] = None
    template_vars: Optional[Dict[str, str]] = None
    
    def __post_init__(self):
        """Validate email request data after initialization."""
        # Validate required fields
        if not self.to or not isinstance(self.to, str):
            raise ValueError("Email 'to' field must be a non-empty string")
        
        if not self.subject or not isinstance(self.subject, str):
            raise ValueError("Email 'subject' field must be a non-empty string")
        
        if not isinstance(self.body, str):
            raise ValueError("Email 'body' field must be a string")
        
        # Validate email addresses
        self.to_emails = validate_email_list(self.to)
        if not self.to_emails:
            raise ValueError("At least one valid recipient email address is required")
        
        if self.from_email:
            if not validate_email_address(self.from_email):
                raise ValueError(f"Invalid from_email address: {self.from_email}")
        
        if self.cc:
            self.cc_emails = validate_email_list(self.cc)
        else:
            self.cc_emails = []
        
        if self.bcc:
            self.bcc_emails = validate_email_list(self.bcc)
        else:
            self.bcc_emails = []
        
        # Validate attachments
        if self.attachments:
            if not isinstance(self.attachments, list):
                raise ValueError("Attachments must be a list")
            
            total_attachment_size = 0
            for i, attachment in enumerate(self.attachments):
                if not isinstance(attachment, Attachment):
                    raise ValueError(f"Attachment {i} must be an Attachment instance")
                total_attachment_size += len(attachment.content)
            
            # Check total attachment size limit
            if total_attachment_size > MAX_TOTAL_ATTACHMENTS_SIZE:
                total_mb = total_attachment_size / (1024 * 1024)
                limit_mb = MAX_TOTAL_ATTACHMENTS_SIZE / (1024 * 1024)
                raise ValueError(
                    f"Total attachments size ({total_mb:.1f}MB) exceeds maximum allowed size ({limit_mb}MB)"
                )
        
        # Validate template variables
        if self.template_vars:
            if not isinstance(self.template_vars, dict):
                raise ValueError("Template variables must be a dictionary")
            
            for key, value in self.template_vars.items():
                if not isinstance(key, str):
                    raise ValueError(f"Template variable key must be string, got: {type(key)}")
                if not isinstance(value, str):
                    raise ValueError(f"Template variable value must be string, got: {type(value)}")


@dataclass
class EmailResponse:
    """Email response data model."""
    
    success: bool
    message_id: Optional[str] = None
    error: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Validate email response data after initialization."""
        if not isinstance(self.success, bool):
            raise ValueError("Success field must be a boolean")
        
        if self.success:
            # For successful responses, message_id should be provided
            if not self.message_id:
                raise ValueError("Message ID is required for successful email responses")
        else:
            # For failed responses, error message should be provided
            if not self.error:
                raise ValueError("Error message is required for failed email responses")
        
        if self.details and not isinstance(self.details, dict):
            raise ValueError("Details field must be a dictionary")


@dataclass
class SMTPConfig:
    """Configuration for SMTP server connection and authentication."""
    
    host: str
    port: int
    username: str
    password: str
    use_tls: bool = True
    use_ssl: bool = False
    timeout: int = 30
    max_retries: int = 3
    from_email: Optional[str] = None
    name: Optional[str] = None  # Server identifier for multi-server support
    priority: int = 0  # Server priority (higher = preferred)
    
    @classmethod
    def from_env(cls) -> 'SMTPConfig':
        """
        Load SMTP configuration from environment variables.
        
        Required environment variables:
        - SMTP_HOST: SMTP server hostname
        - SMTP_PORT: SMTP server port
        - SMTP_USERNAME: SMTP authentication username
        - SMTP_PASSWORD: SMTP authentication password
        
        Optional environment variables:
        - SMTP_USE_TLS: Use STARTTLS (default: true)
        - SMTP_USE_SSL: Use SSL/TLS (default: false)
        - SMTP_TIMEOUT: Connection timeout in seconds (default: 30)
        - SMTP_MAX_RETRIES: Maximum retry attempts (default: 3)
        - SMTP_FROM_EMAIL: Default from email address
        - SMTP_NAME: Server identifier (default: "primary")
        - SMTP_PRIORITY: Server priority (default: 0)
        
        Returns:
            SMTPConfig: Configured SMTP settings
            
        Raises:
            ValueError: If required configuration is missing or invalid
        """
        # Check for required environment variables
        required_vars = ['SMTP_HOST', 'SMTP_PORT', 'SMTP_USERNAME', 'SMTP_PASSWORD']
        missing_vars = []
        
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        if missing_vars:
            raise ValueError(
                f"Missing required SMTP configuration environment variables: {', '.join(missing_vars)}. "
                f"Please set the following environment variables: {', '.join(required_vars)}"
            )
        
        # Parse port as integer
        try:
            port = int(os.getenv('SMTP_PORT'))
        except (ValueError, TypeError):
            raise ValueError(
                f"Invalid SMTP_PORT value: '{os.getenv('SMTP_PORT')}'. "
                "SMTP_PORT must be a valid integer (e.g., 587, 465, 25)"
            )
        
        # Parse optional boolean values
        use_tls = os.getenv('SMTP_USE_TLS', 'true').lower() in ('true', '1', 'yes', 'on')
        use_ssl = os.getenv('SMTP_USE_SSL', 'false').lower() in ('true', '1', 'yes', 'on')
        
        # Parse optional integer values
        try:
            timeout = int(os.getenv('SMTP_TIMEOUT', '30'))
        except (ValueError, TypeError):
            raise ValueError(
                f"Invalid SMTP_TIMEOUT value: '{os.getenv('SMTP_TIMEOUT')}'. "
                "SMTP_TIMEOUT must be a valid integer representing seconds"
            )
        
        try:
            max_retries = int(os.getenv('SMTP_MAX_RETRIES', '3'))
        except (ValueError, TypeError):
            raise ValueError(
                f"Invalid SMTP_MAX_RETRIES value: '{os.getenv('SMTP_MAX_RETRIES')}'. "
                "SMTP_MAX_RETRIES must be a valid integer"
            )
        
        try:
            priority = int(os.getenv('SMTP_PRIORITY', '0'))
        except (ValueError, TypeError):
            raise ValueError(
                f"Invalid SMTP_PRIORITY value: '{os.getenv('SMTP_PRIORITY')}'. "
                "SMTP_PRIORITY must be a valid integer"
            )
        
        return cls(
            host=os.getenv('SMTP_HOST'),
            port=port,
            username=os.getenv('SMTP_USERNAME'),
            password=os.getenv('SMTP_PASSWORD'),
            use_tls=use_tls,
            use_ssl=use_ssl,
            timeout=timeout,
            max_retries=max_retries,
            from_email=os.getenv('SMTP_FROM_EMAIL'),
            name=os.getenv('SMTP_NAME', 'primary'),
            priority=priority
        )
    
    @classmethod
    def from_env_multi(cls) -> List['SMTPConfig']:
        """
        Load multiple SMTP configurations from environment variables.
        
        Supports multiple server configurations using numbered suffixes:
        - SMTP_HOST_1, SMTP_HOST_2, etc.
        - SMTP_PORT_1, SMTP_PORT_2, etc.
        - And so on for all configuration parameters
        
        Falls back to single server configuration if no numbered configs found.
        
        Returns:
            List[SMTPConfig]: List of configured SMTP servers
            
        Raises:
            ValueError: If configuration is missing or invalid
        """
        configs = []
        
        # First try to load numbered configurations
        server_index = 1
        while True:
            suffix = f"_{server_index}"
            
            # Check if this server configuration exists
            host_var = f"SMTP_HOST{suffix}"
            if not os.getenv(host_var):
                break
            
            # Load configuration for this server
            try:
                config = cls._load_config_with_suffix(suffix, server_index)
                configs.append(config)
                logger.debug(f"Loaded SMTP server config {server_index}: {config.name}")
                server_index += 1
            except ValueError as e:
                logger.error(f"Failed to load SMTP server config {server_index}: {e}")
                break
        
        # If no numbered configs found, try to load single server config
        if not configs:
            try:
                config = cls.from_env()
                configs.append(config)
                logger.debug("Loaded single SMTP server configuration")
            except ValueError as e:
                logger.error(f"Failed to load SMTP configuration: {e}")
                raise
        
        # Sort by priority (highest first)
        configs.sort(key=lambda c: c.priority, reverse=True)
        
        logger.info(f"Loaded {len(configs)} SMTP server configurations")
        return configs
    
    @classmethod
    def _load_config_with_suffix(cls, suffix: str, server_index: int) -> 'SMTPConfig':
        """
        Load SMTP configuration with environment variable suffix.
        
        Args:
            suffix: Environment variable suffix (e.g., "_1", "_2")
            server_index: Server index for naming
            
        Returns:
            SMTPConfig: Configured SMTP settings
            
        Raises:
            ValueError: If required configuration is missing or invalid
        """
        # Check for required environment variables with suffix
        required_vars = [f'SMTP_HOST{suffix}', f'SMTP_PORT{suffix}', 
                        f'SMTP_USERNAME{suffix}', f'SMTP_PASSWORD{suffix}']
        missing_vars = []
        
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        if missing_vars:
            raise ValueError(
                f"Missing required SMTP configuration environment variables: {', '.join(missing_vars)}"
            )
        
        # Parse port as integer
        try:
            port = int(os.getenv(f'SMTP_PORT{suffix}'))
        except (ValueError, TypeError):
            raise ValueError(
                f"Invalid SMTP_PORT{suffix} value: '{os.getenv(f'SMTP_PORT{suffix}')}'. "
                "Must be a valid integer (e.g., 587, 465, 25)"
            )
        
        # Parse optional boolean values
        use_tls = os.getenv(f'SMTP_USE_TLS{suffix}', 'true').lower() in ('true', '1', 'yes', 'on')
        use_ssl = os.getenv(f'SMTP_USE_SSL{suffix}', 'false').lower() in ('true', '1', 'yes', 'on')
        
        # Parse optional integer values
        try:
            timeout = int(os.getenv(f'SMTP_TIMEOUT{suffix}', '30'))
        except (ValueError, TypeError):
            raise ValueError(
                f"Invalid SMTP_TIMEOUT{suffix} value. Must be a valid integer representing seconds"
            )
        
        try:
            max_retries = int(os.getenv(f'SMTP_MAX_RETRIES{suffix}', '3'))
        except (ValueError, TypeError):
            raise ValueError(
                f"Invalid SMTP_MAX_RETRIES{suffix} value. Must be a valid integer"
            )
        
        try:
            priority = int(os.getenv(f'SMTP_PRIORITY{suffix}', str(100 - server_index)))
        except (ValueError, TypeError):
            raise ValueError(
                f"Invalid SMTP_PRIORITY{suffix} value. Must be a valid integer"
            )
        
        return cls(
            host=os.getenv(f'SMTP_HOST{suffix}'),
            port=port,
            username=os.getenv(f'SMTP_USERNAME{suffix}'),
            password=os.getenv(f'SMTP_PASSWORD{suffix}'),
            use_tls=use_tls,
            use_ssl=use_ssl,
            timeout=timeout,
            max_retries=max_retries,
            from_email=os.getenv(f'SMTP_FROM_EMAIL{suffix}'),
            name=os.getenv(f'SMTP_NAME{suffix}', f'server_{server_index}'),
            priority=priority
        )
    
    def validate(self) -> None:
        """
        Validate SMTP configuration parameters.
        
        Raises:
            ValueError: If configuration parameters are invalid
        """
        # Validate host
        if not self.host or not self.host.strip():
            raise ValueError("SMTP host cannot be empty")
        
        # Validate port range
        if not (1 <= self.port <= 65535):
            raise ValueError(f"SMTP port must be between 1 and 65535, got: {self.port}")
        
        # Validate username and password
        if not self.username or not self.username.strip():
            raise ValueError("SMTP username cannot be empty")
        
        if not self.password:
            raise ValueError("SMTP password cannot be empty")
        
        # Validate timeout
        if self.timeout <= 0:
            raise ValueError(f"SMTP timeout must be positive, got: {self.timeout}")
        
        # Validate max_retries
        if self.max_retries < 0:
            raise ValueError(f"SMTP max_retries must be non-negative, got: {self.max_retries}")
        
        # Validate TLS/SSL configuration
        if self.use_tls and self.use_ssl:
            raise ValueError("Cannot use both TLS and SSL simultaneously. Choose either STARTTLS (use_tls=True) or SSL/TLS (use_ssl=True)")
        
        # Validate common port configurations
        if self.use_ssl and self.port not in [465, 993, 995]:
            logger.warning(f"SSL is enabled but port {self.port} is not a common SSL port (465, 993, 995)")
        
        if self.use_tls and self.port not in [587, 25]:
            logger.warning(f"STARTTLS is enabled but port {self.port} is not a common STARTTLS port (587, 25)")
        
        logger.info(f"SMTP configuration validated successfully for {self.host}:{self.port}")


class AttachmentHandler:
    """
    Utility class for handling email attachments.
    
    Provides methods for encoding attachments, detecting MIME types,
    and validating attachment constraints.
    """
    
    @staticmethod
    def encode_attachment_base64(content: bytes) -> str:
        """
        Encode attachment content using base64 encoding.
        
        Args:
            content: Raw attachment content as bytes
            
        Returns:
            str: Base64 encoded content
            
        Raises:
            ValueError: If encoding fails
        """
        try:
            return base64.b64encode(content).decode('ascii')
        except Exception as e:
            raise ValueError(f"Failed to base64 encode attachment content: {e}") from e
    
    @staticmethod
    def detect_mime_type(filename: str, content: bytes = None) -> str:
        """
        Detect MIME type for a file based on filename and optionally content.
        
        Args:
            filename: Name of the file
            content: Optional file content for content-based detection
            
        Returns:
            str: Detected MIME type
        """
        # First try to detect based on filename extension
        mime_type, _ = mimetypes.guess_type(filename)
        
        if mime_type:
            return mime_type
        
        # If filename-based detection fails, try content-based detection
        if content:
            # Basic content-based detection for common types
            if content.startswith(b'\x89PNG\r\n\x1a\n'):
                return 'image/png'
            elif content.startswith(b'\xff\xd8\xff'):
                return 'image/jpeg'
            elif content.startswith(b'GIF8'):
                return 'image/gif'
            elif content.startswith(b'%PDF'):
                return 'application/pdf'
            elif content.startswith(b'PK\x03\x04'):
                # ZIP-based formats
                if filename.lower().endswith(('.docx', '.xlsx', '.pptx')):
                    if filename.lower().endswith('.docx'):
                        return 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                    elif filename.lower().endswith('.xlsx'):
                        return 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                    elif filename.lower().endswith('.pptx'):
                        return 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
                return 'application/zip'
        
        # Default to binary if we can't detect
        return 'application/octet-stream'
    
    @staticmethod
    def validate_filename(filename: str) -> bool:
        """
        Validate attachment filename for security and compatibility.
        
        Args:
            filename: Filename to validate
            
        Returns:
            bool: True if filename is valid, False otherwise
        """
        if not filename or not isinstance(filename, str):
            return False
        
        # Check for path traversal attempts
        if '..' in filename or '/' in filename or '\\' in filename:
            return False
        
        # Check for reserved characters (Windows)
        reserved_chars = '<>:"|?*'
        if any(char in filename for char in reserved_chars):
            return False
        
        # Check for reserved names (Windows)
        reserved_names = {
            'CON', 'PRN', 'AUX', 'NUL',
            'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
            'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
        }
        name_without_ext = filename.split('.')[0].upper()
        if name_without_ext in reserved_names:
            return False
        
        # Check length (most filesystems support up to 255 characters)
        if len(filename) > 255:
            return False
        
        return True
    
    @staticmethod
    def get_content_disposition_header(filename: str, inline: bool = False) -> str:
        """
        Generate Content-Disposition header value for attachment.
        
        Args:
            filename: Name of the attachment file
            inline: Whether attachment should be inline (default: False)
            
        Returns:
            str: Content-Disposition header value
        """
        disposition = 'inline' if inline else 'attachment'
        
        # Encode filename if it contains non-ASCII characters
        try:
            filename.encode('ascii')
            # ASCII filename - use simple format
            return f'{disposition}; filename="{filename}"'
        except UnicodeEncodeError:
            # Non-ASCII filename - use RFC 2231 encoding
            import urllib.parse
            encoded_filename = urllib.parse.quote(filename.encode('utf-8'))
            return f'{disposition}; filename*=UTF-8\'\'{encoded_filename}'


class TemplateEngine:
    """
    Template engine for email content processing with variable substitution.
    
    Supports simple string substitution using format strings, conditional content,
    template syntax validation, missing variable detection, and HTML formatting preservation.
    """
    
    def __init__(self):
        """Initialize template engine."""
        logger.debug("Template engine initialized")
    
    def process_template(self, template: str, variables: Dict[str, str]) -> str:
        """
        Process template with variable substitution.
        
        Supports both simple variable substitution using {variable_name} syntax
        and basic conditional content using {?variable_name}content{/variable_name} syntax.
        
        Args:
            template: Template string with variables and conditional blocks
            variables: Dictionary of variable names and values for substitution
            
        Returns:
            str: Processed template with variables substituted
            
        Raises:
            ValueError: If template syntax is invalid or variables are missing
        """
        if not isinstance(template, str):
            raise ValueError("Template must be a string")
        
        if not isinstance(variables, dict):
            raise ValueError("Variables must be a dictionary")
        
        try:
            logger.debug(f"Processing template with {len(variables)} variables")
            
            # First validate template syntax
            self.validate_template(template)
            
            # Process conditional content first
            processed_template = self._process_conditional_content(template, variables)
            
            # Then process simple variable substitution
            result = self._process_variable_substitution(processed_template, variables)
            
            logger.debug("Template processing completed successfully")
            return result
            
        except Exception as e:
            error_msg = f"Template processing failed: {e}"
            logger.error(error_msg)
            raise ValueError(error_msg) from e
    
    def validate_template(self, template: str) -> bool:
        """
        Validate template syntax before processing.
        
        Checks for:
        - Balanced braces for variables and conditionals
        - Valid conditional block syntax
        - No nested conditionals (not supported)
        
        Args:
            template: Template string to validate
            
        Returns:
            bool: True if template syntax is valid
            
        Raises:
            ValueError: If template syntax is invalid
        """
        if not isinstance(template, str):
            raise ValueError("Template must be a string")
        
        try:
            logger.debug("Validating template syntax")
            
            # Check for balanced braces
            self._validate_balanced_braces(template)
            
            # Check conditional block syntax
            self._validate_conditional_blocks(template)
            
            # Check for valid variable names
            self._validate_variable_names(template)
            
            logger.debug("Template syntax validation passed")
            return True
            
        except Exception as e:
            error_msg = f"Template syntax validation failed: {e}"
            logger.error(error_msg)
            raise ValueError(error_msg) from e
    
    def get_template_variables(self, template: str) -> List[str]:
        """
        Extract all variable names from a template.
        
        Args:
            template: Template string to analyze
            
        Returns:
            List[str]: List of unique variable names found in template
        """
        import re
        
        # Find simple variables {variable_name}
        simple_vars = re.findall(r'\{([a-zA-Z_][a-zA-Z0-9_]*)\}', template)
        
        # Find conditional variables {?variable_name}...{/variable_name}
        conditional_vars = re.findall(r'\{\?([a-zA-Z_][a-zA-Z0-9_]*)\}', template)
        
        # Combine and deduplicate
        all_vars = list(set(simple_vars + conditional_vars))
        
        logger.debug(f"Found {len(all_vars)} unique variables in template: {all_vars}")
        return all_vars
    
    def _process_variable_substitution(self, template: str, variables: Dict[str, str]) -> str:
        """
        Process simple variable substitution using {variable_name} syntax.
        
        Args:
            template: Template string with variables
            variables: Dictionary of variable values
            
        Returns:
            str: Template with variables substituted
            
        Raises:
            ValueError: If required variables are missing
        """
        import re
        
        # Find all simple variable references
        variable_pattern = re.compile(r'\{([a-zA-Z_][a-zA-Z0-9_]*)\}')
        found_vars = variable_pattern.findall(template)
        
        # Check for missing variables
        missing_vars = []
        for var_name in found_vars:
            if var_name not in variables:
                missing_vars.append(var_name)
        
        if missing_vars:
            raise ValueError(f"Missing template variables: {', '.join(missing_vars)}")
        
        # Substitute variables
        def replace_var(match):
            var_name = match.group(1)
            return str(variables[var_name])
        
        result = variable_pattern.sub(replace_var, template)
        logger.debug(f"Substituted {len(found_vars)} variables")
        return result
    
    def _process_conditional_content(self, template: str, variables: Dict[str, str]) -> str:
        """
        Process conditional content blocks using {?variable_name}content{/variable_name} syntax.
        
        Content is included if the variable exists and has a non-empty value.
        
        Args:
            template: Template string with conditional blocks
            variables: Dictionary of variable values
            
        Returns:
            str: Template with conditional blocks processed
        """
        import re
        
        # Pattern for conditional blocks: {?var_name}content{/var_name}
        conditional_pattern = re.compile(
            r'\{\?([a-zA-Z_][a-zA-Z0-9_]*)\}(.*?)\{/\1\}',
            re.DOTALL
        )
        
        def replace_conditional(match):
            var_name = match.group(1)
            content = match.group(2)
            
            # Include content if variable exists and has non-empty value
            if var_name in variables and variables[var_name]:
                return content
            else:
                return ''
        
        result = conditional_pattern.sub(replace_conditional, template)
        
        # Count processed conditionals
        conditionals_found = len(conditional_pattern.findall(template))
        if conditionals_found > 0:
            logger.debug(f"Processed {conditionals_found} conditional blocks")
        
        return result
    
    def _validate_balanced_braces(self, template: str) -> None:
        """
        Validate that braces are balanced in the template.
        
        Args:
            template: Template string to validate
            
        Raises:
            ValueError: If braces are not balanced
        """
        open_count = template.count('{')
        close_count = template.count('}')
        
        if open_count != close_count:
            raise ValueError(f"Unbalanced braces in template: {open_count} opening, {close_count} closing")
    
    def _validate_conditional_blocks(self, template: str) -> None:
        """
        Validate conditional block syntax.
        
        Args:
            template: Template string to validate
            
        Raises:
            ValueError: If conditional blocks are malformed
        """
        import re
        
        # Find all conditional opening tags
        opening_pattern = re.compile(r'\{\?([a-zA-Z_][a-zA-Z0-9_]*)\}')
        opening_matches = opening_pattern.findall(template)
        
        # Find all conditional closing tags
        closing_pattern = re.compile(r'\{/([a-zA-Z_][a-zA-Z0-9_]*)\}')
        closing_matches = closing_pattern.findall(template)
        
        # Check that every opening has a matching closing
        for var_name in opening_matches:
            if var_name not in closing_matches:
                raise ValueError(f"Conditional block for '{var_name}' is not closed")
        
        for var_name in closing_matches:
            if var_name not in opening_matches:
                raise ValueError(f"Closing tag for '{var_name}' has no matching opening tag")
        
        # Check for nested conditionals (not supported)
        full_pattern = re.compile(
            r'\{\?([a-zA-Z_][a-zA-Z0-9_]*)\}(.*?)\{/\1\}',
            re.DOTALL
        )
        
        for match in full_pattern.finditer(template):
            content = match.group(2)
            if '{?' in content:
                raise ValueError("Nested conditional blocks are not supported")
    
    def _validate_variable_names(self, template: str) -> None:
        """
        Validate that all variable names follow valid naming conventions.
        
        Args:
            template: Template string to validate
            
        Raises:
            ValueError: If variable names are invalid
        """
        import re
        
        # Find all variable references (both simple and conditional)
        all_vars = re.findall(r'\{[\?/]?([a-zA-Z_][a-zA-Z0-9_]*)\}', template)
        
        for var_name in all_vars:
            # Check that variable name starts with letter or underscore
            if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', var_name):
                raise ValueError(f"Invalid variable name: '{var_name}'. Variable names must start with a letter or underscore and contain only letters, numbers, and underscores.")
    
    def preserve_html_formatting(self, html_content: str, processed_content: str) -> str:
        """
        Ensure HTML template formatting and structure is preserved after processing.
        
        This method performs basic validation to ensure that HTML structure
        is maintained after template processing.
        
        Args:
            html_content: Original HTML template content
            processed_content: Processed content after variable substitution
            
        Returns:
            str: Processed content (validated for HTML preservation)
            
        Raises:
            ValueError: If HTML structure was corrupted during processing
        """
        try:
            # Basic HTML structure validation
            if '<html' in html_content.lower() or '<!doctype' in html_content.lower():
                # Full HTML document - check for basic structure preservation
                if '<html' in html_content.lower() and '<html' not in processed_content.lower():
                    raise ValueError("HTML document structure was corrupted during template processing")
            
            # Check for balanced HTML tags (basic validation)
            self._validate_html_tag_balance(processed_content)
            
            logger.debug("HTML formatting preservation validated")
            return processed_content
            
        except Exception as e:
            error_msg = f"HTML formatting preservation failed: {e}"
            logger.error(error_msg)
            raise ValueError(error_msg) from e
    
    def _validate_html_tag_balance(self, html_content: str) -> None:
        """
        Perform basic validation of HTML tag balance.
        
        Args:
            html_content: HTML content to validate
            
        Raises:
            ValueError: If HTML tags appear to be unbalanced
        """
        import re
        
        # Find all HTML tags
        tag_pattern = re.compile(r'<(/?)([a-zA-Z][a-zA-Z0-9]*)[^>]*>')
        tags = tag_pattern.findall(html_content)
        
        # Track opening and closing tags
        tag_stack = []
        
        for is_closing, tag_name in tags:
            tag_name = tag_name.lower()
            
            # Skip self-closing tags
            if tag_name in ['br', 'hr', 'img', 'input', 'meta', 'link', 'area', 'base', 'col', 'embed', 'source', 'track', 'wbr']:
                continue
            
            if is_closing:
                # Closing tag
                if not tag_stack:
                    raise ValueError(f"Closing tag </{tag_name}> has no matching opening tag")
                
                last_opened = tag_stack.pop()
                if last_opened != tag_name:
                    raise ValueError(f"Mismatched HTML tags: opened <{last_opened}> but closed </{tag_name}>")
            else:
                # Opening tag
                tag_stack.append(tag_name)
        
        # Check for unclosed tags
        if tag_stack:
            raise ValueError(f"Unclosed HTML tags: {', '.join(tag_stack)}")


class EmailMessageBuilder:
    """
    Builder class for creating properly formatted email messages.
    
    Handles plain text and HTML email formatting, character encoding (UTF-8),
    multiple recipients (TO, CC, BCC), and email header construction.
    """
    
    def __init__(self, config: SMTPConfig):
        """
        Initialize email message builder with SMTP configuration.
        
        Args:
            config: SMTP configuration for default settings
        """
        self.config = config
        self.template_engine = TemplateEngine()
        logger.debug("Email message builder initialized")
    
    def build_plain_text_message(
        self,
        email_request: EmailRequest,
        processed_subject: str,
        processed_body: str
    ) -> MIMEMultipart:
        """
        Create a plain text email message (text/plain).
        
        Args:
            email_request: Email request with recipient and content details
            processed_subject: Subject line (potentially with template variables substituted)
            processed_body: Email body content (potentially with template variables substituted)
            
        Returns:
            MIMEMultipart: Formatted plain text email message
            
        Raises:
            ValueError: If message construction fails
        """
        try:
            logger.debug("Building plain text email message")
            
            # Create multipart message for potential attachments
            message = MIMEMultipart()
            
            # Set basic headers
            self._set_message_headers(message, email_request, processed_subject)
            
            # Create plain text part with UTF-8 encoding
            text_part = MIMEText(processed_body, 'plain', 'utf-8')
            message.attach(text_part)
            
            logger.debug("Plain text email message built successfully")
            return message
            
        except Exception as e:
            error_msg = f"Failed to build plain text email message: {e}"
            logger.error(error_msg)
            raise ValueError(error_msg) from e
    
    def build_html_message(
        self,
        email_request: EmailRequest,
        processed_subject: str,
        processed_body: str
    ) -> MIMEMultipart:
        """
        Create an HTML email message (text/html) with proper encoding.
        
        Args:
            email_request: Email request with recipient and content details
            processed_subject: Subject line (potentially with template variables substituted)
            processed_body: HTML email body content (potentially with template variables substituted)
            
        Returns:
            MIMEMultipart: Formatted HTML email message
            
        Raises:
            ValueError: If message construction fails
        """
        try:
            logger.debug("Building HTML email message")
            
            # Create multipart message for potential attachments
            message = MIMEMultipart()
            
            # Set basic headers
            self._set_message_headers(message, email_request, processed_subject)
            
            # Create HTML part with UTF-8 encoding
            html_part = MIMEText(processed_body, 'html', 'utf-8')
            message.attach(html_part)
            
            logger.debug("HTML email message built successfully")
            return message
            
        except Exception as e:
            error_msg = f"Failed to build HTML email message: {e}"
            logger.error(error_msg)
            raise ValueError(error_msg) from e
    
    def _set_message_headers(
        self,
        message: MIMEMultipart,
        email_request: EmailRequest,
        processed_subject: str
    ) -> None:
        """
        Set email headers including recipients, subject, and metadata.
        
        Args:
            message: MIME message to set headers on
            email_request: Email request with recipient details
            processed_subject: Processed subject line
            
        Raises:
            ValueError: If header construction fails
        """
        try:
            # Set From header
            from_email = email_request.from_email or self.config.from_email
            if not from_email:
                raise ValueError("No from_email specified in request or configuration")
            
            message['From'] = formataddr(('', from_email))
            
            # Set To header (comma-separated list)
            if email_request.to_emails:
                to_addresses = ', '.join(email_request.to_emails)
                message['To'] = to_addresses
            
            # Set CC header if specified
            if email_request.cc_emails:
                cc_addresses = ', '.join(email_request.cc_emails)
                message['Cc'] = cc_addresses
            
            # Store BCC addresses separately (not included in headers for privacy)
            if email_request.bcc_emails:
                message._bcc_addresses = email_request.bcc_emails
            
            # Set Subject header with UTF-8 encoding
            message['Subject'] = processed_subject
            
            # Set Date header
            message['Date'] = formatdate(localtime=True)
            
            # Set Message-ID header
            message_id = f"<{uuid.uuid4()}@{self.config.host}>"
            message['Message-ID'] = message_id
            
            # Set additional headers for better deliverability
            message['MIME-Version'] = '1.0'
            message['X-Mailer'] = 'SMTP MCP Server'
            
            logger.debug(f"Email headers set successfully. Message-ID: {message_id}")
            
        except Exception as e:
            error_msg = f"Failed to set email headers: {e}"
            logger.error(error_msg)
            raise ValueError(error_msg) from e
    
    def add_recipients_to_message(
        self,
        message: MIMEMultipart,
        to_emails: List[str],
        cc_emails: List[str] = None,
        bcc_emails: List[str] = None
    ) -> None:
        """
        Add multiple recipients (TO, CC, BCC) to email message.
        
        Args:
            message: MIME message to add recipients to
            to_emails: List of TO recipient email addresses
            cc_emails: List of CC recipient email addresses (optional)
            bcc_emails: List of BCC recipient email addresses (optional)
            
        Raises:
            ValueError: If recipient addition fails
        """
        try:
            # Validate that we have at least one recipient
            if not to_emails:
                raise ValueError("At least one TO recipient is required")
            
            # Set TO recipients
            message['To'] = ', '.join(to_emails)
            logger.debug(f"Added {len(to_emails)} TO recipients")
            
            # Set CC recipients if provided
            if cc_emails:
                message['Cc'] = ', '.join(cc_emails)
                logger.debug(f"Added {len(cc_emails)} CC recipients")
            
            # Store BCC recipients separately (not in headers for privacy)
            if bcc_emails:
                message._bcc_addresses = bcc_emails
                logger.debug(f"Added {len(bcc_emails)} BCC recipients")
            
            total_recipients = len(to_emails) + len(cc_emails or []) + len(bcc_emails or [])
            logger.debug(f"Total recipients added to message: {total_recipients}")
            
        except Exception as e:
            error_msg = f"Failed to add recipients to message: {e}"
            logger.error(error_msg)
            raise ValueError(error_msg) from e
    
    def build_message(self, email_request: EmailRequest) -> MIMEMultipart:
        """
        Build a complete email message based on the email request.
        
        This is the main entry point for message building that handles both
        plain text and HTML messages with proper formatting and encoding.
        Includes template processing if template variables are provided.
        
        Args:
            email_request: Complete email request with all details
            
        Returns:
            MIMEMultipart: Fully formatted email message ready for sending
            
        Raises:
            ValueError: If message building fails
        """
        try:
            logger.info(f"Building email message for {len(email_request.to_emails)} recipients")
            
            # Process templates if template variables are provided
            processed_subject = email_request.subject
            processed_body = email_request.body
            
            if email_request.template_vars:
                logger.debug(f"Processing templates with {len(email_request.template_vars)} variables")
                
                # Process subject template
                processed_subject = self.template_engine.process_template(
                    email_request.subject, 
                    email_request.template_vars
                )
                
                # Process body template
                processed_body = self.template_engine.process_template(
                    email_request.body, 
                    email_request.template_vars
                )
                
                # If HTML content, ensure formatting is preserved
                if email_request.html:
                    processed_body = self.template_engine.preserve_html_formatting(
                        email_request.body, 
                        processed_body
                    )
                
                logger.debug("Template processing completed successfully")
            
            # Build message based on content type
            if email_request.html:
                message = self.build_html_message(email_request, processed_subject, processed_body)
                logger.debug("Built HTML email message")
            else:
                message = self.build_plain_text_message(email_request, processed_subject, processed_body)
                logger.debug("Built plain text email message")
            
            # Add attachments if present
            if email_request.attachments:
                self.add_attachments_to_message(message, email_request.attachments)
                logger.info(f"Added {len(email_request.attachments)} attachments to message")
            
            logger.info("Email message built successfully")
            return message
            
        except Exception as e:
            error_msg = f"Failed to build email message: {e}"
            logger.error(error_msg)
            raise ValueError(error_msg) from e
    
    def add_attachments_to_message(self, message: MIMEMultipart, attachments: List[Attachment]) -> None:
        """
        Add multiple attachments to an email message.
        
        Handles base64 encoding, MIME type detection, Content-Disposition headers,
        and supports both regular and inline attachments.
        
        Args:
            message: MIME message to add attachments to
            attachments: List of attachments to add
            
        Raises:
            ValueError: If attachment processing fails
        """
        try:
            logger.debug(f"Adding {len(attachments)} attachments to message")
            
            for i, attachment in enumerate(attachments):
                try:
                    self.add_single_attachment(message, attachment)
                    logger.debug(f"Added attachment {i+1}/{len(attachments)}: {attachment.filename}")
                except Exception as e:
                    error_msg = f"Failed to add attachment '{attachment.filename}': {e}"
                    logger.error(error_msg)
                    raise ValueError(error_msg) from e
            
            logger.debug("All attachments added successfully")
            
        except Exception as e:
            error_msg = f"Failed to add attachments to message: {e}"
            logger.error(error_msg)
            raise ValueError(error_msg) from e
    
    def add_single_attachment(self, message: MIMEMultipart, attachment: Attachment) -> None:
        """
        Add a single attachment to an email message with proper encoding and headers.
        
        Args:
            message: MIME message to add attachment to
            attachment: Attachment to add
            
        Raises:
            ValueError: If attachment processing fails
        """
        try:
            logger.debug(f"Processing attachment: {attachment.filename} ({attachment.mime_type})")
            
            # Validate filename
            if not AttachmentHandler.validate_filename(attachment.filename):
                raise ValueError(f"Invalid attachment filename: {attachment.filename}")
            
            # Create MIME part for attachment
            main_type, sub_type = attachment.mime_type.split('/', 1)
            part = MIMEBase(main_type, sub_type)
            part.set_payload(attachment.content)
            
            # Encode attachment content using base64
            encoders.encode_base64(part)
            
            # Set Content-Disposition header with filename
            if attachment.is_inline() and attachment.content_id:
                # Inline attachment (e.g., embedded images)
                part.add_header(
                    'Content-Disposition',
                    AttachmentHandler.get_content_disposition_header(attachment.filename, inline=True)
                )
                part.add_header('Content-ID', f'<{attachment.content_id}>')
                logger.debug(f"Added inline attachment with Content-ID: {attachment.content_id}")
            else:
                # Regular attachment
                part.add_header(
                    'Content-Disposition',
                    AttachmentHandler.get_content_disposition_header(attachment.filename, inline=False)
                )
                logger.debug(f"Added regular attachment: {attachment.filename}")
            
            # Set Content-Type header (MIMEBase sets this, but ensure it's correct)
            part.set_type(attachment.mime_type)
            
            # Add Content-Transfer-Encoding header (base64 is already set by encoders.encode_base64)
            
            # Add the part to the message
            message.attach(part)
            
            logger.debug(f"Successfully processed attachment: {attachment.filename} ({attachment.get_size_mb():.2f}MB)")
            
        except Exception as e:
            error_msg = f"Failed to process attachment '{attachment.filename}': {e}"
            logger.error(error_msg)
            raise ValueError(error_msg) from e
    
    def validate_attachments(self, attachments: List[Attachment]) -> None:
        """
        Validate a list of attachments for size limits and other constraints.
        
        Args:
            attachments: List of attachments to validate
            
        Raises:
            ValueError: If validation fails
        """
        if not attachments:
            return
        
        try:
            total_size = 0
            filenames = set()
            
            for i, attachment in enumerate(attachments):
                # Check for duplicate filenames
                if attachment.filename in filenames:
                    raise ValueError(f"Duplicate attachment filename: {attachment.filename}")
                filenames.add(attachment.filename)
                
                # Add to total size
                total_size += len(attachment.content)
                
                logger.debug(f"Validated attachment {i+1}: {attachment.filename} ({attachment.get_size_mb():.2f}MB)")
            
            # Check total size limit
            if total_size > MAX_TOTAL_ATTACHMENTS_SIZE:
                total_mb = total_size / (1024 * 1024)
                limit_mb = MAX_TOTAL_ATTACHMENTS_SIZE / (1024 * 1024)
                raise ValueError(
                    f"Total attachments size ({total_mb:.1f}MB) exceeds maximum allowed size ({limit_mb}MB)"
                )
            
            logger.debug(f"All {len(attachments)} attachments validated successfully. Total size: {total_size / (1024 * 1024):.2f}MB")
            
        except Exception as e:
            error_msg = f"Attachment validation failed: {e}"
            logger.error(error_msg)
            raise ValueError(error_msg) from e

def load_smtp_config() -> SMTPConfig:
    """
    Load and validate SMTP configuration from environment variables.
    
    Returns:
        SMTPConfig: Validated SMTP configuration
        
    Raises:
        ValueError: If configuration is missing or invalid
    """
    try:
        config = SMTPConfig.from_env()
        config.validate()
        return config
    except ValueError as e:
        logger.error(f"SMTP configuration error: {e}")
        raise


def load_smtp_configs() -> List[SMTPConfig]:
    """
    Load and validate multiple SMTP configurations from environment variables.
    
    Returns:
        List[SMTPConfig]: List of validated SMTP configurations
        
    Raises:
        ValueError: If configuration is missing or invalid
    """
    try:
        configs = SMTPConfig.from_env_multi()
        
        # Validate all configurations
        for config in configs:
            config.validate()
        
        logger.info(f"Loaded and validated {len(configs)} SMTP server configurations")
        return configs
        
    except ValueError as e:
        logger.error(f"SMTP configuration error: {e}")
        raise


class MultiServerSMTPClient:
    """
    Multi-server SMTP client with automatic failover and server selection.
    
    Manages multiple SMTP server configurations and provides automatic failover
    when servers become unavailable. Servers are tried in priority order.
    """
    
    def __init__(self, configs: List[SMTPConfig]):
        """
        Initialize multi-server SMTP client with server configurations.
        
        Args:
            configs: List of SMTP server configurations (sorted by priority)
        """
        if not configs:
            raise ValueError("At least one SMTP server configuration is required")
        
        self.configs = configs
        self.current_client: Optional[SMTPClient] = None
        self.current_config: Optional[SMTPConfig] = None
        self.failed_servers: set = set()  # Track temporarily failed servers
        self.last_failure_time: Dict[str, float] = {}  # Track failure times for backoff
        self.failure_backoff_time = 300  # 5 minutes backoff for failed servers
        
        logger.info(f"Multi-server SMTP client initialized with {len(configs)} servers")
        for i, config in enumerate(configs):
            logger.debug(f"Server {i+1}: {config.name} ({config.host}:{config.port}) priority={config.priority}")
    
    async def connect(self) -> bool:
        """
        Connect to an available SMTP server using priority order and failover.
        
        Tries servers in priority order, skipping recently failed servers.
        If all servers fail, retries with exponential backoff.
        
        Returns:
            bool: True if connection successful, False otherwise
            
        Raises:
            ConnectionError: If no servers are available after all attempts
        """
        # Clean up any existing connection
        await self.disconnect()
        
        # Get available servers (excluding recently failed ones)
        available_servers = self._get_available_servers()
        
        if not available_servers:
            # All servers recently failed, wait and try again
            logger.warning("All SMTP servers recently failed, attempting retry with backoff")
            self._reset_failed_servers_if_needed()
            available_servers = self._get_available_servers()
        
        if not available_servers:
            raise ConnectionError("No SMTP servers available for connection")
        
        # Try each available server in priority order
        last_exception = None
        
        for config in available_servers:
            try:
                logger.info(f"Attempting connection to SMTP server: {config.name} ({config.host}:{config.port})")
                
                client = SMTPClient(config)
                success = await client.connect()
                
                if success:
                    self.current_client = client
                    self.current_config = config
                    
                    # Remove from failed servers if it was there
                    server_key = self._get_server_key(config)
                    self.failed_servers.discard(server_key)
                    self.last_failure_time.pop(server_key, None)
                    
                    logger.info(f"Successfully connected to SMTP server: {config.name}")
                    return True
                else:
                    await client.disconnect()
                    
            except Exception as e:
                last_exception = e
                server_key = self._get_server_key(config)
                
                logger.warning(f"Failed to connect to SMTP server {config.name}: {e}")
                
                # Mark server as failed
                self.failed_servers.add(server_key)
                self.last_failure_time[server_key] = time.time()
                
                # Clean up failed client
                if 'client' in locals():
                    try:
                        await client.disconnect()
                    except Exception:
                        pass
        
        # All servers failed
        error_msg = f"Failed to connect to any SMTP server. Last error: {last_exception}"
        logger.error(error_msg)
        raise ConnectionError(error_msg) from last_exception
    
    async def disconnect(self) -> None:
        """
        Disconnect from current SMTP server and clean up resources.
        """
        if self.current_client:
            try:
                await self.current_client.disconnect()
            except Exception as e:
                logger.warning(f"Error during SMTP disconnect: {e}")
            finally:
                self.current_client = None
                self.current_config = None
    
    async def send_message(self, message: MIMEMultipart) -> str:
        """
        Send email message with automatic failover to backup servers.
        
        If the current server fails during sending, automatically tries
        backup servers in priority order.
        
        Args:
            message: Prepared MIME message to send
            
        Returns:
            str: Message ID from successful send
            
        Raises:
            ConnectionError: If no servers are available
            ValueError: If message sending fails on all servers
        """
        if not self.current_client or not self.current_config:
            # No current connection, try to connect
            await self.connect()
        
        # Try to send with current server
        try:
            message_id = await self.current_client.send_message(message)
            logger.debug(f"Message sent successfully via {self.current_config.name}")
            return message_id
            
        except Exception as e:
            logger.warning(f"Failed to send message via {self.current_config.name}: {e}")
            
            # Mark current server as failed
            server_key = self._get_server_key(self.current_config)
            self.failed_servers.add(server_key)
            self.last_failure_time[server_key] = time.time()
            
            # Disconnect from failed server
            await self.disconnect()
            
            # Try failover to backup servers
            return await self._send_with_failover(message)
    
    async def _send_with_failover(self, message: MIMEMultipart) -> str:
        """
        Attempt to send message using failover servers.
        
        Args:
            message: MIME message to send
            
        Returns:
            str: Message ID from successful send
            
        Raises:
            ConnectionError: If no backup servers are available
            ValueError: If sending fails on all backup servers
        """
        logger.info("Attempting message send with failover servers")
        
        # Get available backup servers
        available_servers = self._get_available_servers()
        
        if not available_servers:
            raise ConnectionError("No backup SMTP servers available for failover")
        
        last_exception = None
        
        for config in available_servers:
            try:
                logger.info(f"Trying failover server: {config.name} ({config.host}:{config.port})")
                
                # Create new client for this server
                client = SMTPClient(config)
                
                # Connect and send
                await client.connect()
                message_id = await client.send_message(message)
                
                # Success - update current client
                self.current_client = client
                self.current_config = config
                
                # Remove from failed servers
                server_key = self._get_server_key(config)
                self.failed_servers.discard(server_key)
                self.last_failure_time.pop(server_key, None)
                
                logger.info(f"Message sent successfully via failover server: {config.name}")
                return message_id
                
            except Exception as e:
                last_exception = e
                server_key = self._get_server_key(config)
                
                logger.warning(f"Failover server {config.name} failed: {e}")
                
                # Mark server as failed
                self.failed_servers.add(server_key)
                self.last_failure_time[server_key] = time.time()
                
                # Clean up failed client
                if 'client' in locals():
                    try:
                        await client.disconnect()
                    except Exception:
                        pass
        
        # All failover attempts failed
        error_msg = f"All SMTP servers failed during message sending. Last error: {last_exception}"
        logger.error(error_msg)
        raise ValueError(error_msg) from last_exception
    
    def _get_available_servers(self) -> List[SMTPConfig]:
        """
        Get list of available servers (excluding recently failed ones).
        
        Returns:
            List[SMTPConfig]: Available servers sorted by priority
        """
        current_time = time.time()
        available = []
        
        for config in self.configs:
            server_key = self._get_server_key(config)
            
            # Check if server recently failed
            if server_key in self.failed_servers:
                failure_time = self.last_failure_time.get(server_key, 0)
                if current_time - failure_time < self.failure_backoff_time:
                    # Still in backoff period
                    continue
                else:
                    # Backoff period expired, remove from failed list
                    self.failed_servers.discard(server_key)
                    self.last_failure_time.pop(server_key, None)
            
            available.append(config)
        
        return available
    
    def _reset_failed_servers_if_needed(self) -> None:
        """
        Reset failed servers list if all servers have been failed for too long.
        """
        current_time = time.time()
        
        # If all servers failed more than 2x backoff time ago, reset the list
        old_failures = []
        for server_key, failure_time in self.last_failure_time.items():
            if current_time - failure_time > (self.failure_backoff_time * 2):
                old_failures.append(server_key)
        
        if len(old_failures) == len(self.configs):
            logger.info("Resetting all failed servers due to extended downtime")
            self.failed_servers.clear()
            self.last_failure_time.clear()
    
    def _get_server_key(self, config: SMTPConfig) -> str:
        """
        Generate unique key for server configuration.
        
        Args:
            config: SMTP configuration
            
        Returns:
            str: Unique server key
        """
        return f"{config.host}:{config.port}:{config.username}"
    
    def is_connected(self) -> bool:
        """
        Check if currently connected to an SMTP server.
        
        Returns:
            bool: True if connected, False otherwise
        """
        return (self.current_client is not None and 
                self.current_config is not None and 
                self.current_client.is_connected())
    
    def get_current_server(self) -> Optional[SMTPConfig]:
        """
        Get currently connected server configuration.
        
        Returns:
            Optional[SMTPConfig]: Current server config or None if not connected
        """
        return self.current_config
    
    def get_server_status(self) -> Dict[str, Any]:
        """
        Get status of all configured servers.
        
        Returns:
            Dict[str, Any]: Server status information
        """
        current_time = time.time()
        servers = []
        
        for config in self.configs:
            server_key = self._get_server_key(config)
            is_current = (self.current_config and 
                         self._get_server_key(self.current_config) == server_key)
            is_failed = server_key in self.failed_servers
            failure_time = self.last_failure_time.get(server_key)
            
            server_info = {
                "name": config.name,
                "host": config.host,
                "port": config.port,
                "priority": config.priority,
                "is_current": is_current,
                "is_failed": is_failed,
                "is_available": not is_failed or (
                    failure_time and current_time - failure_time >= self.failure_backoff_time
                )
            }
            
            if failure_time:
                server_info["last_failure"] = failure_time
                server_info["backoff_remaining"] = max(0, 
                    self.failure_backoff_time - (current_time - failure_time))
            
            servers.append(server_info)
        
        return {
            "total_servers": len(self.configs),
            "available_servers": len(self._get_available_servers()),
            "failed_servers": len(self.failed_servers),
            "current_server": self.current_config.name if self.current_config else None,
            "servers": servers
        }
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()


class SMTPClient:
    """
    SMTP client for handling email connections and sending messages.
    
    Supports SSL/TLS (port 465) and STARTTLS (port 587) encryption methods,
    authentication, and connection retry logic with exponential backoff.
    """
    
    def __init__(self, config: SMTPConfig):
        """
        Initialize SMTP client with configuration.
        
        Args:
            config: SMTP configuration settings
        """
        self.config = config
        self.connection: Optional[smtplib.SMTP] = None
        self._is_connected = False
        self._is_authenticated = False
        
        logger.info(f"SMTP client initialized for {config.host}:{config.port}")
    
    async def connect(self) -> bool:
        """
        Establish SMTP connection with authentication and encryption.
        
        Supports both SSL/TLS (direct secure connection) and STARTTLS
        (upgrade to secure connection after initial plain connection).
        
        Returns:
            bool: True if connection and authentication successful, False otherwise
            
        Raises:
            ConnectionError: If connection fails after all retry attempts
            ValueError: If authentication fails
        """
        if self._is_connected and self._is_authenticated:
            logger.debug("SMTP client already connected and authenticated")
            return True
        
        # Disconnect any existing connection
        await self.disconnect()
        
        retry_count = 0
        last_exception = None
        
        while retry_count <= self.config.max_retries:
            try:
                logger.info(f"Attempting SMTP connection to {self.config.host}:{self.config.port} (attempt {retry_count + 1}/{self.config.max_retries + 1})")
                
                # Create SMTP connection based on encryption method
                if self.config.use_ssl:
                    # Direct SSL/TLS connection (typically port 465)
                    logger.debug("Establishing SSL/TLS connection")
                    context = ssl.create_default_context()
                    self.connection = smtplib.SMTP_SSL(
                        host=self.config.host,
                        port=self.config.port,
                        timeout=self.config.timeout,
                        context=context
                    )
                else:
                    # Plain connection, potentially upgraded with STARTTLS
                    logger.debug("Establishing plain SMTP connection")
                    self.connection = smtplib.SMTP(
                        host=self.config.host,
                        port=self.config.port,
                        timeout=self.config.timeout
                    )
                    
                    # Upgrade to TLS if requested (typically port 587)
                    if self.config.use_tls:
                        logger.debug("Upgrading connection with STARTTLS")
                        context = ssl.create_default_context()
                        self.connection.starttls(context=context)
                
                # Enable debug output if logging level is DEBUG
                if logger.isEnabledFor(logging.DEBUG):
                    self.connection.set_debuglevel(1)
                
                self._is_connected = True
                logger.info(f"SMTP connection established to {self.config.host}:{self.config.port}")
                
                # Authenticate with the server
                try:
                    logger.debug(f"Authenticating as {self.config.username}")
                    self.connection.login(self.config.username, self.config.password)
                    self._is_authenticated = True
                    logger.info(f"SMTP authentication successful for {self.config.username}")
                    return True
                    
                except smtplib.SMTPAuthenticationError as auth_error:
                    error_msg = f"SMTP authentication failed for {self.config.username}: {auth_error}"
                    logger.error(error_msg)
                    await self.disconnect()
                    raise ValueError(error_msg) from auth_error
                
                except smtplib.SMTPException as smtp_error:
                    error_msg = f"SMTP authentication error: {smtp_error}"
                    logger.error(error_msg)
                    await self.disconnect()
                    raise ValueError(error_msg) from smtp_error
                
            except (smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected, OSError, ssl.SSLError) as e:
                last_exception = e
                error_msg = f"SMTP connection failed (attempt {retry_count + 1}): {e}"
                logger.warning(error_msg)
                
                # Clean up failed connection
                await self.disconnect()
                
                # If this was the last retry, don't wait
                if retry_count >= self.config.max_retries:
                    break
                
                # Exponential backoff: wait 2^retry_count seconds (1, 2, 4, 8, ...)
                wait_time = 2 ** retry_count
                logger.info(f"Retrying SMTP connection in {wait_time} seconds...")
                time.sleep(wait_time)
                retry_count += 1
            
            except Exception as e:
                # Unexpected error - don't retry
                error_msg = f"Unexpected SMTP connection error: {e}"
                logger.error(error_msg)
                await self.disconnect()
                raise ConnectionError(error_msg) from e
        
        # All retry attempts failed
        error_msg = f"SMTP connection failed after {self.config.max_retries + 1} attempts. Last error: {last_exception}"
        logger.error(error_msg)
        raise ConnectionError(error_msg) from last_exception
    
    async def disconnect(self) -> None:
        """
        Close SMTP connection and clean up resources.
        """
        if self.connection:
            try:
                logger.debug("Closing SMTP connection")
                self.connection.quit()
            except Exception as e:
                logger.warning(f"Error during SMTP disconnect: {e}")
                try:
                    self.connection.close()
                except Exception:
                    pass  # Ignore errors during forced close
            finally:
                self.connection = None
                self._is_connected = False
                self._is_authenticated = False
                logger.info("SMTP connection closed")
    
    async def send_message(self, message: MIMEMultipart) -> str:
        """
        Send an email message through the SMTP connection.
        
        Args:
            message: Prepared MIME message to send
            
        Returns:
            str: Message ID from the SMTP server
            
        Raises:
            ConnectionError: If not connected to SMTP server
            ValueError: If message sending fails
        """
        if not self._is_connected or not self._is_authenticated:
            raise ConnectionError("SMTP client is not connected or authenticated. Call connect() first.")
        
        if not self.connection:
            raise ConnectionError("SMTP connection is not available")
        
        try:
            # Extract recipients from message headers
            to_addresses = []
            
            # Get TO recipients
            if message.get('To'):
                to_addresses.extend([addr.strip() for addr in message.get('To').split(',')])
            
            # Get CC recipients
            if message.get('Cc'):
                to_addresses.extend([addr.strip() for addr in message.get('Cc').split(',')])
            
            # Get BCC recipients (not included in message headers but needed for sending)
            bcc_addresses = []
            if hasattr(message, '_bcc_addresses'):
                bcc_addresses = message._bcc_addresses
                to_addresses.extend(bcc_addresses)
            
            if not to_addresses:
                raise ValueError("No recipients specified in message")
            
            from_address = message.get('From')
            if not from_address:
                raise ValueError("No sender address specified in message")
            
            logger.debug(f"Sending email from {from_address} to {len(to_addresses)} recipients")
            
            # Send the message
            refused_recipients = self.connection.send_message(message, from_addr=from_address, to_addrs=to_addresses)
            
            if refused_recipients:
                refused_list = list(refused_recipients.keys())
                logger.warning(f"Some recipients were refused: {refused_list}")
                raise ValueError(f"SMTP server refused recipients: {refused_list}")
            
            # Generate a message ID (SMTP servers typically don't return one)
            message_id = message.get('Message-ID')
            if not message_id:
                import uuid
                message_id = f"<{uuid.uuid4()}@{self.config.host}>"
            
            logger.info(f"Email sent successfully to {len(to_addresses)} recipients. Message ID: {message_id}")
            return message_id
            
        except smtplib.SMTPRecipientsRefused as e:
            error_msg = f"All recipients were refused by SMTP server: {e.recipients}"
            logger.error(error_msg)
            raise ValueError(error_msg) from e
        
        except smtplib.SMTPSenderRefused as e:
            error_msg = f"Sender address was refused by SMTP server: {e.sender} - {e.smtp_error}"
            logger.error(error_msg)
            raise ValueError(error_msg) from e
        
        except smtplib.SMTPDataError as e:
            error_msg = f"SMTP server rejected message data: {e.smtp_error}"
            logger.error(error_msg)
            raise ValueError(error_msg) from e
        
        except smtplib.SMTPException as e:
            error_msg = f"SMTP error during message sending: {e}"
            logger.error(error_msg)
            raise ValueError(error_msg) from e
        
        except Exception as e:
            error_msg = f"Unexpected error during message sending: {e}"
            logger.error(error_msg)
            raise ValueError(error_msg) from e
    
    def is_connected(self) -> bool:
        """
        Check if SMTP client is connected and authenticated.
        
        Returns:
            bool: True if connected and authenticated, False otherwise
        """
        return self._is_connected and self._is_authenticated
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()


class EmailService:
    """
    Email service orchestration class that coordinates all email components.
    
    This service provides the main business logic for email operations,
    coordinating multi-server SMTP client, template engine, message builder, and attachment handler
    to provide a complete email sending workflow with comprehensive error handling and failover support.
    """
    
    def __init__(self, configs: List[SMTPConfig]):
        """
        Initialize email service with SMTP configurations.
        
        Args:
            configs: List of SMTP configurations for multi-server support
        """
        if not configs:
            raise ValueError("At least one SMTP configuration is required")
        
        self.configs = configs
        self.primary_config = configs[0]  # Highest priority config for defaults
        self.smtp_client = MultiServerSMTPClient(configs)
        self.message_builder = EmailMessageBuilder(self.primary_config)
        self.template_engine = TemplateEngine()
        
        # Thread lock for configuration updates
        self._config_lock = threading.RLock()
        
        logger.info(f"Email service initialized with {len(configs)} SMTP servers")
        for config in configs:
            logger.debug(f"SMTP server: {config.name} ({config.host}:{config.port}) priority={config.priority}")
    
    async def send_email(self, email_request: EmailRequest) -> EmailResponse:
        """
        Process and send email with full workflow orchestration and multi-server failover.
        
        This method coordinates all email components to:
        1. Validate the email request
        2. Process templates if provided
        3. Build the email message
        4. Connect to SMTP server (with failover)
        5. Send the email (with failover)
        6. Handle errors and logging
        
        Args:
            email_request: Complete email request with all details
            
        Returns:
            EmailResponse: Response with success status, message ID, or error details
            
        Raises:
            ValueError: If email request validation fails
        """
        start_time = time.time()
        
        try:
            logger.info(f"Starting email send workflow for {len(email_request.to_emails)} recipients")
            
            # Step 1: Validate email request
            validation_result = self.validate_email_request(email_request)
            if not validation_result.is_valid:
                error_msg = f"Email request validation failed: {validation_result.error_message}"
                logger.error(error_msg)
                return EmailResponse(
                    success=False,
                    error=error_msg,
                    details={"validation_errors": validation_result.errors}
                )
            
            logger.debug("Email request validation passed")
            
            # Step 2: Build email message (includes template processing)
            try:
                message = self.message_builder.build_message(email_request)
                logger.debug("Email message built successfully")
            except Exception as e:
                error_msg = f"Failed to build email message: {e}"
                logger.error(error_msg)
                return EmailResponse(
                    success=False,
                    error=error_msg,
                    details={"step": "message_building", "original_error": str(e)}
                )
            
            # Step 3: Connect to SMTP server and send email (with multi-server failover)
            try:
                async with self.smtp_client:
                    message_id = await self.smtp_client.send_message(message)
                    
                    # Calculate send duration
                    duration = time.time() - start_time
                    
                    # Get current server info for logging
                    current_server = self.smtp_client.get_current_server()
                    
                    # Log successful operation
                    self._log_success_operation(email_request, message_id, duration, current_server)
                    
                    logger.info(f"Email sent successfully via {current_server.name if current_server else 'unknown'} in {duration:.2f}s. Message ID: {message_id}")
                    
                    return EmailResponse(
                        success=True,
                        message_id=message_id,
                        details={
                            "recipients": len(email_request.to_emails) + len(email_request.cc_emails) + len(email_request.bcc_emails),
                            "attachments": len(email_request.attachments) if email_request.attachments else 0,
                            "duration_seconds": round(duration, 2),
                            "content_type": "text/html" if email_request.html else "text/plain",
                            "smtp_server": current_server.name if current_server else "unknown",
                            "server_host": f"{current_server.host}:{current_server.port}" if current_server else "unknown"
                        }
                    )
                    
            except ConnectionError as e:
                error_msg = f"SMTP connection failed on all servers: {e}"
                logger.error(error_msg)
                self._log_smtp_error(email_request, error_msg, "connection_error")
                
                return EmailResponse(
                    success=False,
                    error=error_msg,
                    details={
                        "error_type": "connection_error",
                        "step": "smtp_connection",
                        "server_status": self.smtp_client.get_server_status()
                    }
                )
                
            except ValueError as e:
                error_msg = f"Email sending failed on all servers: {e}"
                logger.error(error_msg)
                self._log_smtp_error(email_request, error_msg, "send_error")
                
                return EmailResponse(
                    success=False,
                    error=error_msg,
                    details={
                        "error_type": "send_error",
                        "step": "message_sending",
                        "original_error": str(e),
                        "server_status": self.smtp_client.get_server_status()
                    }
                )
                
            except Exception as e:
                error_msg = f"Unexpected error during email sending: {e}"
                logger.error(error_msg)
                self._log_smtp_error(email_request, error_msg, "unexpected_error")
                
                return EmailResponse(
                    success=False,
                    error=error_msg,
                    details={
                        "error_type": "unexpected_error",
                        "step": "email_sending",
                        "original_error": str(e),
                        "server_status": self.smtp_client.get_server_status()
                    }
                )
        
        except Exception as e:
            # Catch-all for any unexpected errors in the workflow
            error_msg = f"Email service workflow failed: {e}"
            logger.error(error_msg)
            
            return EmailResponse(
                success=False,
                error=error_msg,
                details={
                    "error_type": "workflow_error",
                    "step": "email_service_workflow",
                    "original_error": str(e)
                }
            )
    
    def validate_email_request(self, email_request: EmailRequest) -> 'ValidationResult':
        """
        Validate email request with comprehensive checks.
        
        Performs validation beyond the basic EmailRequest validation,
        including business logic validation and configuration checks.
        
        Args:
            email_request: Email request to validate
            
        Returns:
            ValidationResult: Validation result with details
        """
        try:
            logger.debug("Validating email request")
            
            errors = []
            
            # Basic validation is already done in EmailRequest.__post_init__
            # Here we add business logic validation
            
            # Check if from_email is available (either in request or primary config)
            if not email_request.from_email and not self.primary_config.from_email:
                errors.append("No from_email specified in request or configuration")
            
            # Validate template variables if templates are used
            if email_request.template_vars:
                try:
                    # Check if templates are valid by getting required variables
                    subject_vars = self.template_engine.get_template_variables(email_request.subject)
                    body_vars = self.template_engine.get_template_variables(email_request.body)
                    
                    all_template_vars = set(subject_vars + body_vars)
                    provided_vars = set(email_request.template_vars.keys())
                    
                    missing_vars = all_template_vars - provided_vars
                    if missing_vars:
                        errors.append(f"Missing template variables: {', '.join(missing_vars)}")
                    
                except Exception as e:
                    errors.append(f"Template validation failed: {e}")
            
            # Validate attachments if present
            if email_request.attachments:
                try:
                    self.message_builder.validate_attachments(email_request.attachments)
                except Exception as e:
                    errors.append(f"Attachment validation failed: {e}")
            
            # Check total recipient count (reasonable limit)
            total_recipients = (
                len(email_request.to_emails) + 
                len(email_request.cc_emails) + 
                len(email_request.bcc_emails)
            )
            
            if total_recipients > 100:  # Reasonable limit to prevent abuse
                errors.append(f"Too many recipients ({total_recipients}). Maximum allowed: 100")
            
            if total_recipients == 0:
                errors.append("No recipients specified")
            
            # Validate content length (reasonable limits)
            if len(email_request.subject) > 998:  # RFC 5322 limit
                errors.append(f"Subject line too long ({len(email_request.subject)} characters). Maximum: 998")
            
            if len(email_request.body) > 10 * 1024 * 1024:  # 10MB limit
                errors.append(f"Email body too large ({len(email_request.body)} bytes). Maximum: 10MB")
            
            is_valid = len(errors) == 0
            
            if is_valid:
                logger.debug("Email request validation passed")
            else:
                logger.warning(f"Email request validation failed with {len(errors)} errors")
            
            return ValidationResult(
                is_valid=is_valid,
                errors=errors,
                error_message="; ".join(errors) if errors else None
            )
            
        except Exception as e:
            error_msg = f"Email request validation error: {e}"
            logger.error(error_msg)
            return ValidationResult(
                is_valid=False,
                errors=[error_msg],
                error_message=error_msg
            )
    
    def _log_success_operation(self, email_request: EmailRequest, message_id: str, duration: float, server_config: Optional[SMTPConfig] = None) -> None:
        """
        Log successful email operation with relevant details including server info.
        
        Args:
            email_request: Original email request
            message_id: Generated message ID
            duration: Time taken to send email
            server_config: SMTP server configuration used for sending
        """
        try:
            # Sanitize sensitive information
            sanitized_details = {
                "message_id": message_id,
                "recipients_count": len(email_request.to_emails) + len(email_request.cc_emails) + len(email_request.bcc_emails),
                "to_count": len(email_request.to_emails),
                "cc_count": len(email_request.cc_emails),
                "bcc_count": len(email_request.bcc_emails),
                "has_attachments": bool(email_request.attachments),
                "attachment_count": len(email_request.attachments) if email_request.attachments else 0,
                "content_type": "text/html" if email_request.html else "text/plain",
                "has_templates": bool(email_request.template_vars),
                "template_vars_count": len(email_request.template_vars) if email_request.template_vars else 0,
                "duration_seconds": round(duration, 2),
                "from_email": self._sanitize_email(email_request.from_email or self.primary_config.from_email),
                "subject_length": len(email_request.subject),
                "body_length": len(email_request.body)
            }
            
            # Add server information
            if server_config:
                sanitized_details.update({
                    "smtp_server": server_config.name,
                    "smtp_host": f"{server_config.host}:{server_config.port}",
                    "smtp_priority": server_config.priority
                })
            else:
                sanitized_details.update({
                    "smtp_server": "unknown",
                    "smtp_host": "unknown",
                    "smtp_priority": 0
                })
            
            logger.info(f"Email sent successfully: {sanitized_details}")
            
        except Exception as e:
            logger.warning(f"Failed to log success operation details: {e}")
    
    def _log_smtp_error(self, email_request: EmailRequest, error_message: str, error_type: str) -> None:
        """
        Log SMTP error with detailed information for troubleshooting including multi-server status.
        
        Args:
            email_request: Original email request
            error_message: Error message to log
            error_type: Type of error (connection_error, send_error, etc.)
        """
        try:
            # Sanitize sensitive information
            sanitized_details = {
                "error_type": error_type,
                "error_message": error_message,
                "recipients_count": len(email_request.to_emails) + len(email_request.cc_emails) + len(email_request.bcc_emails),
                "from_email": self._sanitize_email(email_request.from_email or self.primary_config.from_email),
                "has_attachments": bool(email_request.attachments),
                "content_type": "text/html" if email_request.html else "text/plain",
                "total_servers": len(self.configs),
                "server_status": self.smtp_client.get_server_status()
            }
            
            logger.error(f"SMTP error occurred: {sanitized_details}")
            
        except Exception as e:
            logger.warning(f"Failed to log SMTP error details: {e}")
    
    def _sanitize_email(self, email: str) -> str:
        """
        Sanitize email address for logging (hide sensitive parts).
        
        Args:
            email: Email address to sanitize
            
        Returns:
            str: Sanitized email address
        """
        if not email:
            return "None"
        
        try:
            if '@' in email:
                local, domain = email.split('@', 1)
                # Show first 2 characters of local part, hide the rest
                if len(local) > 2:
                    sanitized_local = local[:2] + '*' * (len(local) - 2)
                else:
                    sanitized_local = '*' * len(local)
                return f"{sanitized_local}@{domain}"
            else:
                # Not a valid email format, just mask most of it
                if len(email) > 4:
                    return email[:2] + '*' * (len(email) - 4) + email[-2:]
                else:
                    return '*' * len(email)
        except Exception:
            return "***sanitization_error***"
    
    async def test_connection(self) -> dict:
        """
        Test SMTP connection to all configured servers.
        
        Returns:
            dict: Connection test result for all servers
        """
        try:
            logger.info("Testing SMTP connections to all servers")
            
            results = []
            overall_success = False
            
            # Test each server individually
            for config in self.configs:
                try:
                    client = SMTPClient(config)
                    success = await client.connect()
                    
                    if success:
                        await client.disconnect()
                        overall_success = True
                        
                        results.append({
                            "server": config.name,
                            "host": f"{config.host}:{config.port}",
                            "priority": config.priority,
                            "success": True,
                            "message": "Connection successful"
                        })
                    else:
                        results.append({
                            "server": config.name,
                            "host": f"{config.host}:{config.port}",
                            "priority": config.priority,
                            "success": False,
                            "error": "Connection failed"
                        })
                        
                except Exception as e:
                    results.append({
                        "server": config.name,
                        "host": f"{config.host}:{config.port}",
                        "priority": config.priority,
                        "success": False,
                        "error": str(e)
                    })
            
            # Test multi-server client
            multi_server_success = False
            try:
                async with self.smtp_client:
                    multi_server_success = True
                    current_server = self.smtp_client.get_current_server()
                    
                logger.info("Multi-server SMTP connection test successful")
            except Exception as e:
                logger.warning(f"Multi-server SMTP connection test failed: {e}")
            
            return {
                "success": overall_success,
                "multi_server_success": multi_server_success,
                "total_servers": len(self.configs),
                "successful_servers": sum(1 for r in results if r["success"]),
                "server_results": results,
                "server_status": self.smtp_client.get_server_status()
            }
                
        except Exception as e:
            error_msg = f"SMTP connection test failed: {e}"
            logger.error(error_msg)
            return {
                "success": False,
                "multi_server_success": False,
                "error": error_msg,
                "total_servers": len(self.configs)
            }
    
    def get_service_status(self) -> dict:
        """
        Get current service status and configuration for all servers.
        
        Returns:
            dict: Service status information including multi-server details
        """
        try:
            server_configs = []
            for config in self.configs:
                server_configs.append({
                    "name": config.name,
                    "host": f"{config.host}:{config.port}",
                    "priority": config.priority,
                    "username": self._sanitize_email(config.username),
                    "encryption": "SSL" if config.use_ssl else ("TLS" if config.use_tls else "None"),
                    "timeout": config.timeout,
                    "max_retries": config.max_retries,
                    "from_email": self._sanitize_email(config.from_email)
                })
            
            return {
                "service": "SMTP MCP Server",
                "status": "ready",
                "multi_server_enabled": len(self.configs) > 1,
                "total_servers": len(self.configs),
                "primary_server": self.primary_config.name,
                "current_server": self.smtp_client.get_current_server().name if self.smtp_client.get_current_server() else None,
                "server_configurations": server_configs,
                "server_status": self.smtp_client.get_server_status(),
                "max_attachment_size_mb": MAX_ATTACHMENT_SIZE / (1024 * 1024),
                "max_total_attachments_size_mb": MAX_TOTAL_ATTACHMENTS_SIZE / (1024 * 1024)
            }
        except Exception as e:
            logger.error(f"Failed to get service status: {e}")
            return {
                "service": "SMTP MCP Server",
                "status": "error",
                "error": str(e)
            }
    
    async def reload_configuration(self) -> dict:
        """
        Reload SMTP configuration from environment variables and reconnect without restart.
        
        This method provides dynamic reconfiguration support by:
        1. Loading new configuration from environment variables
        2. Validating the new configuration
        3. Safely updating the service configuration with thread safety
        4. Reconnecting to SMTP servers with the new configuration
        5. Rolling back on failure
        
        Returns:
            dict: Configuration reload result with details
        """
        with self._config_lock:
            try:
                logger.info("Starting dynamic configuration reload")
                
                # Store original configuration for rollback
                original_configs = self.configs.copy()
                original_primary_config = self.primary_config
                original_smtp_client = self.smtp_client
                original_message_builder = self.message_builder
                
                # Step 1: Load new configuration from environment variables
                try:
                    new_configs = load_smtp_configs()
                    logger.info(f"Loaded {len(new_configs)} new SMTP configurations")
                except Exception as e:
                    error_msg = f"Failed to load new configuration: {e}"
                    logger.error(error_msg)
                    return {
                        "success": False,
                        "error": error_msg,
                        "step": "configuration_loading"
                    }
                
                # Step 2: Validate new configuration
                validation_result = self._validate_configuration_changes(original_configs, new_configs)
                if not validation_result["valid"]:
                    logger.error(f"Configuration validation failed: {validation_result['error']}")
                    return {
                        "success": False,
                        "error": validation_result["error"],
                        "step": "configuration_validation",
                        "details": validation_result.get("details", {})
                    }
                
                logger.debug("New configuration validation passed")
                
                # Step 3: Disconnect from current SMTP servers
                try:
                    await self.smtp_client.disconnect()
                    logger.debug("Disconnected from current SMTP servers")
                except Exception as e:
                    logger.warning(f"Error during disconnect: {e}")
                
                # Step 4: Update configuration safely
                try:
                    self.configs = new_configs
                    self.primary_config = new_configs[0]
                    self.smtp_client = MultiServerSMTPClient(new_configs)
                    self.message_builder = EmailMessageBuilder(self.primary_config)
                    
                    logger.info("Configuration updated successfully")
                except Exception as e:
                    error_msg = f"Failed to update configuration: {e}"
                    logger.error(error_msg)
                    
                    # Rollback to original configuration
                    self.configs = original_configs
                    self.primary_config = original_primary_config
                    self.smtp_client = original_smtp_client
                    self.message_builder = original_message_builder
                    
                    return {
                        "success": False,
                        "error": error_msg,
                        "step": "configuration_update",
                        "rollback_performed": True
                    }
                
                # Step 5: Test connection with new configuration
                try:
                    connection_test = await self.test_connection()
                    
                    if not connection_test["success"]:
                        error_msg = "New configuration failed connection test"
                        logger.error(f"{error_msg}: {connection_test}")
                        
                        # Rollback to original configuration
                        await self.smtp_client.disconnect()
                        self.configs = original_configs
                        self.primary_config = original_primary_config
                        self.smtp_client = original_smtp_client
                        self.message_builder = original_message_builder
                        
                        return {
                            "success": False,
                            "error": error_msg,
                            "step": "connection_test",
                            "rollback_performed": True,
                            "connection_test_details": connection_test
                        }
                    
                    logger.info("New configuration connection test passed")
                    
                except Exception as e:
                    error_msg = f"Connection test failed: {e}"
                    logger.error(error_msg)
                    
                    # Rollback to original configuration
                    await self.smtp_client.disconnect()
                    self.configs = original_configs
                    self.primary_config = original_primary_config
                    self.smtp_client = original_smtp_client
                    self.message_builder = original_message_builder
                    
                    return {
                        "success": False,
                        "error": error_msg,
                        "step": "connection_test",
                        "rollback_performed": True
                    }
                
                # Step 6: Generate configuration change summary
                change_summary = self._generate_configuration_change_summary(original_configs, new_configs)
                
                logger.info("Dynamic configuration reload completed successfully")
                
                return {
                    "success": True,
                    "message": "Configuration reloaded successfully",
                    "changes": change_summary,
                    "new_configuration": {
                        "total_servers": len(new_configs),
                        "primary_server": self.primary_config.name,
                        "servers": [
                            {
                                "name": config.name,
                                "host": f"{config.host}:{config.port}",
                                "priority": config.priority
                            }
                            for config in new_configs
                        ]
                    },
                    "connection_test": connection_test
                }
                
            except Exception as e:
                error_msg = f"Unexpected error during configuration reload: {e}"
                logger.error(error_msg)
                
                # Attempt rollback if we have original configuration
                if 'original_configs' in locals():
                    try:
                        await self.smtp_client.disconnect()
                        self.configs = original_configs
                        self.primary_config = original_primary_config
                        self.smtp_client = original_smtp_client
                        self.message_builder = original_message_builder
                        logger.info("Rollback completed after unexpected error")
                    except Exception as rollback_error:
                        logger.error(f"Rollback failed: {rollback_error}")
                
                return {
                    "success": False,
                    "error": error_msg,
                    "step": "unexpected_error",
                    "rollback_attempted": 'original_configs' in locals()
                }
    
    def _validate_configuration_changes(self, old_configs: List[SMTPConfig], new_configs: List[SMTPConfig]) -> dict:
        """
        Validate configuration changes before applying them.
        
        Args:
            old_configs: Current SMTP configurations
            new_configs: New SMTP configurations to validate
            
        Returns:
            dict: Validation result with details
        """
        try:
            logger.debug("Validating configuration changes")
            
            errors = []
            warnings = []
            
            # Basic validation - ensure we have at least one server
            if not new_configs:
                errors.append("No SMTP server configurations found")
                return {
                    "valid": False,
                    "error": "No SMTP server configurations found",
                    "details": {"errors": errors}
                }
            
            # Validate each new configuration
            for i, config in enumerate(new_configs):
                try:
                    config.validate()
                except Exception as e:
                    errors.append(f"Server {i+1} ({config.name}): {e}")
            
            # Check for duplicate server names
            server_names = [config.name for config in new_configs]
            duplicate_names = set([name for name in server_names if server_names.count(name) > 1])
            if duplicate_names:
                errors.append(f"Duplicate server names found: {', '.join(duplicate_names)}")
            
            # Check for duplicate server configurations (same host:port:username)
            server_keys = set()
            for config in new_configs:
                key = f"{config.host}:{config.port}:{config.username}"
                if key in server_keys:
                    errors.append(f"Duplicate server configuration: {config.host}:{config.port} with username {config.username}")
                server_keys.add(key)
            
            # Compare with old configuration and generate warnings for significant changes
            if old_configs:
                old_server_names = set(config.name for config in old_configs)
                new_server_names = set(config.name for config in new_configs)
                
                removed_servers = old_server_names - new_server_names
                added_servers = new_server_names - old_server_names
                
                if removed_servers:
                    warnings.append(f"Servers removed: {', '.join(removed_servers)}")
                
                if added_servers:
                    warnings.append(f"Servers added: {', '.join(added_servers)}")
                
                # Check for changes in existing servers
                for old_config in old_configs:
                    for new_config in new_configs:
                        if old_config.name == new_config.name:
                            changes = []
                            if old_config.host != new_config.host:
                                changes.append(f"host: {old_config.host} -> {new_config.host}")
                            if old_config.port != new_config.port:
                                changes.append(f"port: {old_config.port} -> {new_config.port}")
                            if old_config.username != new_config.username:
                                changes.append(f"username: {old_config.username} -> {new_config.username}")
                            if old_config.priority != new_config.priority:
                                changes.append(f"priority: {old_config.priority} -> {new_config.priority}")
                            
                            if changes:
                                warnings.append(f"Server '{old_config.name}' changed: {', '.join(changes)}")
                            break
            
            is_valid = len(errors) == 0
            
            result = {
                "valid": is_valid,
                "details": {
                    "errors": errors,
                    "warnings": warnings,
                    "old_server_count": len(old_configs) if old_configs else 0,
                    "new_server_count": len(new_configs)
                }
            }
            
            if not is_valid:
                result["error"] = f"Configuration validation failed: {'; '.join(errors)}"
            
            if warnings:
                logger.info(f"Configuration change warnings: {'; '.join(warnings)}")
            
            logger.debug(f"Configuration validation completed: valid={is_valid}, errors={len(errors)}, warnings={len(warnings)}")
            
            return result
            
        except Exception as e:
            error_msg = f"Configuration validation error: {e}"
            logger.error(error_msg)
            return {
                "valid": False,
                "error": error_msg,
                "details": {"validation_exception": str(e)}
            }
    
    def _generate_configuration_change_summary(self, old_configs: List[SMTPConfig], new_configs: List[SMTPConfig]) -> dict:
        """
        Generate a summary of configuration changes.
        
        Args:
            old_configs: Previous SMTP configurations
            new_configs: New SMTP configurations
            
        Returns:
            dict: Summary of changes
        """
        try:
            old_server_names = set(config.name for config in old_configs) if old_configs else set()
            new_server_names = set(config.name for config in new_configs)
            
            removed_servers = list(old_server_names - new_server_names)
            added_servers = list(new_server_names - old_server_names)
            
            modified_servers = []
            unchanged_servers = []
            
            # Check for modifications in existing servers
            for old_config in old_configs or []:
                for new_config in new_configs:
                    if old_config.name == new_config.name:
                        changes = {}
                        if old_config.host != new_config.host:
                            changes["host"] = {"old": old_config.host, "new": new_config.host}
                        if old_config.port != new_config.port:
                            changes["port"] = {"old": old_config.port, "new": new_config.port}
                        if old_config.username != new_config.username:
                            changes["username"] = {"old": old_config.username, "new": new_config.username}
                        if old_config.priority != new_config.priority:
                            changes["priority"] = {"old": old_config.priority, "new": new_config.priority}
                        if old_config.use_tls != new_config.use_tls:
                            changes["use_tls"] = {"old": old_config.use_tls, "new": new_config.use_tls}
                        if old_config.use_ssl != new_config.use_ssl:
                            changes["use_ssl"] = {"old": old_config.use_ssl, "new": new_config.use_ssl}
                        if old_config.timeout != new_config.timeout:
                            changes["timeout"] = {"old": old_config.timeout, "new": new_config.timeout}
                        if old_config.max_retries != new_config.max_retries:
                            changes["max_retries"] = {"old": old_config.max_retries, "new": new_config.max_retries}
                        
                        if changes:
                            modified_servers.append({
                                "name": old_config.name,
                                "changes": changes
                            })
                        else:
                            unchanged_servers.append(old_config.name)
                        break
            
            return {
                "total_changes": len(removed_servers) + len(added_servers) + len(modified_servers),
                "servers_removed": removed_servers,
                "servers_added": added_servers,
                "servers_modified": modified_servers,
                "servers_unchanged": unchanged_servers,
                "old_server_count": len(old_configs) if old_configs else 0,
                "new_server_count": len(new_configs),
                "primary_server_changed": (
                    old_configs[0].name != new_configs[0].name 
                    if old_configs and new_configs else False
                )
            }
            
        except Exception as e:
            logger.warning(f"Failed to generate configuration change summary: {e}")
            return {
                "total_changes": 0,
                "error": f"Failed to generate summary: {e}"
            }
    
    async def reconnect_smtp_servers(self) -> dict:
        """
        Reconnect to SMTP servers without changing configuration.
        
        This method forces a reconnection to all SMTP servers using the current
        configuration. Useful for recovering from network issues or server restarts.
        
        Returns:
            dict: Reconnection result with details
        """
        with self._config_lock:
            try:
                logger.info("Starting SMTP server reconnection")
                
                # Disconnect from current servers
                try:
                    await self.smtp_client.disconnect()
                    logger.debug("Disconnected from current SMTP servers")
                except Exception as e:
                    logger.warning(f"Error during disconnect: {e}")
                
                # Reset failed servers list to allow retry
                self.smtp_client.failed_servers.clear()
                self.smtp_client.last_failure_time.clear()
                logger.debug("Reset failed servers list")
                
                # Test connection to verify servers are accessible
                connection_test = await self.test_connection()
                
                if connection_test["success"]:
                    logger.info("SMTP server reconnection completed successfully")
                    return {
                        "success": True,
                        "message": "Successfully reconnected to SMTP servers",
                        "connection_test": connection_test
                    }
                else:
                    logger.warning("SMTP server reconnection completed with some failures")
                    return {
                        "success": False,
                        "error": "Some servers failed to reconnect",
                        "connection_test": connection_test
                    }
                
            except Exception as e:
                error_msg = f"SMTP server reconnection failed: {e}"
                logger.error(error_msg)
                return {
                    "success": False,
                    "error": error_msg
                }


@dataclass
class ValidationResult:
    """Result of email request validation."""
    
    is_valid: bool
    errors: List[str]
    error_message: Optional[str] = None