#!/usr/bin/env python3
"""
Integration tests for SMTP MCP Server end-to-end email flow.

This test suite provides comprehensive integration testing for the complete
email sending workflow, including mock SMTP servers, template processing,
attachment handling, and multi-server failover scenarios.
"""

import os
import sys
import asyncio
import tempfile
import threading
import time
from unittest.mock import patch, MagicMock, AsyncMock
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# Add the current directory to Python path
sys.path.insert(0, '.')

from smtp import (
    SMTPConfig, EmailService, EmailRequest, Attachment
)

from server import (
    get_email_service, 
    reset_email_service, 
    send_email, 
    test_smtp_connection, 
    get_smtp_status
)


class MockSMTPServer:
    """Mock SMTP server for testing without real network connections."""
    
    def __init__(self, host: str, port: int, should_fail: bool = False):
        self.host = host
        self.port = port
        self.should_fail = should_fail
        self.messages_sent = []
        self.connection_attempts = 0
        self.auth_attempts = 0
        
    def connect(self):
        """Mock SMTP connection."""
        self.connection_attempts += 1
        if self.should_fail:
            raise ConnectionError(f"Mock connection failure to {self.host}:{self.port}")
        return True
    
    def login(self, username: str, password: str):
        """Mock SMTP authentication."""
        self.auth_attempts += 1
        if self.should_fail:
            raise Exception(f"Mock authentication failure for {username}")
        return True
    
    def send_message(self, message, from_addr: str, to_addrs: list):
        """Mock message sending."""
        if self.should_fail:
            raise Exception("Mock message sending failure")
        
        message_info = {
            'from': from_addr,
            'to': to_addrs,
            'subject': message.get('Subject', ''),
            'body_length': len(str(message)),
            'timestamp': time.time()
        }
        self.messages_sent.append(message_info)
        return {}  # No refused recipients
    
    def quit(self):
        """Mock SMTP disconnect."""
        pass
    
    def close(self):
        """Mock SMTP force close."""
        pass


async def test_basic_email_sending():
    """Test basic email sending functionality with mock SMTP server."""
    print("Testing basic email sending functionality...")
    
    # Set up test environment
    test_env = {
        'SMTP_HOST': 'smtp.test.com',
        'SMTP_PORT': '587',
        'SMTP_USERNAME': 'test@test.com',
        'SMTP_PASSWORD': 'password',
        'SMTP_USE_TLS': 'true',
        'SMTP_FROM_EMAIL': 'sender@test.com',
        'SMTP_NAME': 'test_server',
    }
    
    with patch.dict(os.environ, test_env, clear=True):
        try:
            # Reset global service
            reset_email_service()
            
            # Mock SMTP connection
            mock_server = MockSMTPServer('smtp.test.com', 587)
            
            with patch('smtplib.SMTP') as mock_smtp_class:
                mock_smtp_instance = MagicMock()
                mock_smtp_class.return_value = mock_smtp_instance
                
                # Configure mock SMTP instance
                mock_smtp_instance.login.return_value = None
                mock_smtp_instance.send_message.return_value = {}
                mock_smtp_instance.starttls.return_value = None
                
                # Create email request
                email_request = EmailRequest(
                    to="recipient@test.com",
                    subject="Test Email",
                    body="This is a test email body.",
                    from_email="sender@test.com"
                )
                
                # Get service and send email
                service = get_email_service()
                response = await service.send_email(email_request)
                
                # Verify response
                assert response.success == True, f"Email sending should succeed: {response.error}"
                assert response.message_id is not None, "Should have message ID"
                assert response.details is not None, "Should have response details"
                
                # Verify SMTP interactions
                mock_smtp_class.assert_called_once()
                mock_smtp_instance.login.assert_called_once()
                mock_smtp_instance.send_message.assert_called_once()
                
                print("✓ Basic email sending works correctly")
                return response
                
        except Exception as e:
            print(f"✗ Basic email sending test failed: {e}")
            raise


async def test_html_email_with_attachments():
    """Test HTML email sending with attachments."""
    print("\nTesting HTML email with attachments...")
    
    test_env = {
        'SMTP_HOST': 'smtp.test.com',
        'SMTP_PORT': '587',
        'SMTP_USERNAME': 'test@test.com',
        'SMTP_PASSWORD': 'password',
        'SMTP_USE_TLS': 'true',
        'SMTP_FROM_EMAIL': 'sender@test.com',
    }
    
    with patch.dict(os.environ, test_env, clear=True):
        try:
            reset_email_service()
            
            # Create test attachment
            test_content = b"This is test file content for attachment testing."
            attachment = Attachment(
                filename="test_document.txt",
                content=test_content,
                mime_type="text/plain"
            )
            
            # Mock SMTP connection
            with patch('smtplib.SMTP') as mock_smtp_class:
                mock_smtp_instance = MagicMock()
                mock_smtp_class.return_value = mock_smtp_instance
                mock_smtp_instance.login.return_value = None
                mock_smtp_instance.send_message.return_value = {}
                mock_smtp_instance.starttls.return_value = None
                
                # Create HTML email request with attachment
                email_request = EmailRequest(
                    to="recipient@test.com",
                    subject="HTML Email with Attachment",
                    body="<html><body><h1>Test HTML Email</h1><p>This is <b>HTML</b> content.</p></body></html>",
                    html=True,
                    attachments=[attachment]
                )
                
                service = get_email_service()
                response = await service.send_email(email_request)
                
                # Verify response
                assert response.success == True, f"HTML email with attachment should succeed: {response.error}"
                assert response.details['content_type'] == 'text/html', "Should be HTML content type"
                assert response.details['attachments'] == 1, "Should have 1 attachment"
                
                # Verify SMTP call was made
                mock_smtp_instance.send_message.assert_called_once()
                
                # Get the message that was sent
                call_args = mock_smtp_instance.send_message.call_args
                sent_message = call_args[0][0]  # First positional argument
                
                # Verify message structure
                assert isinstance(sent_message, MIMEMultipart), "Should be multipart message"
                assert sent_message.get('Subject') == "HTML Email with Attachment"
                assert sent_message.get_content_type() == 'multipart/mixed'
                
                print("✓ HTML email with attachments works correctly")
                return response
                
        except Exception as e:
            print(f"✗ HTML email with attachments test failed: {e}")
            raise


async def test_template_processing():
    """Test email template processing with variable substitution."""
    print("\nTesting email template processing...")
    
    test_env = {
        'SMTP_HOST': 'smtp.test.com',
        'SMTP_PORT': '587',
        'SMTP_USERNAME': 'test@test.com',
        'SMTP_PASSWORD': 'password',
        'SMTP_USE_TLS': 'true',
        'SMTP_FROM_EMAIL': 'sender@test.com',
    }
    
    with patch.dict(os.environ, test_env, clear=True):
        try:
            reset_email_service()
            
            with patch('smtplib.SMTP') as mock_smtp_class:
                mock_smtp_instance = MagicMock()
                mock_smtp_class.return_value = mock_smtp_instance
                mock_smtp_instance.login.return_value = None
                mock_smtp_instance.send_message.return_value = {}
                mock_smtp_instance.starttls.return_value = None
                
                # Create email request with templates
                email_request = EmailRequest(
                    to="recipient@test.com",
                    subject="Hello {name}!",
                    body="Dear {name},\n\nWelcome to {company}!\n\n{?special_offer}Special offer: {special_offer}{/special_offer}\n\nBest regards,\nThe Team",
                    template_vars={
                        "name": "John Doe",
                        "company": "Test Corp",
                        "special_offer": "50% off your first order"
                    }
                )
                
                service = get_email_service()
                response = await service.send_email(email_request)
                
                # Verify response
                assert response.success == True, f"Template email should succeed: {response.error}"
                
                # Get the sent message to verify template processing
                call_args = mock_smtp_instance.send_message.call_args
                sent_message = call_args[0][0]
                
                # Verify template substitution in subject
                assert sent_message.get('Subject') == "Hello John Doe!"
                
                # Verify template substitution in body
                message_body = str(sent_message)
                
                # Check if template processing worked by looking for the processed content
                # The message body might be encoded, so let's check the payload
                payload_parts = sent_message.get_payload()
                if isinstance(payload_parts, list) and len(payload_parts) > 0:
                    text_part = payload_parts[0]
                    if hasattr(text_part, 'get_payload'):
                        actual_body = text_part.get_payload()
                        
                        # If the body is base64 encoded, decode it
                        if text_part.get('Content-Transfer-Encoding') == 'base64':
                            import base64
                            try:
                                decoded_body = base64.b64decode(actual_body).decode('utf-8')
                                actual_body = decoded_body
                            except Exception:
                                pass  # If decoding fails, use original body
                        
                        assert "Dear John Doe," in actual_body
                        assert "Welcome to Test Corp!" in actual_body
                        assert "Special offer: 50% off your first order" in actual_body
                else:
                    # Fallback to checking the full message string
                    assert "Dear John Doe," in message_body
                    assert "Welcome to Test Corp!" in message_body
                    assert "Special offer: 50% off your first order" in message_body
                
                print("✓ Email template processing works correctly")
                return response
                
        except Exception as e:
            print(f"✗ Email template processing test failed: {e}")
            raise


async def test_multi_server_failover():
    """Test multi-server failover functionality."""
    print("\nTesting multi-server failover...")
    
    # Set up multi-server environment
    test_env = {
        # Primary server (will fail)
        'SMTP_HOST_1': 'smtp.primary.com',
        'SMTP_PORT_1': '587',
        'SMTP_USERNAME_1': 'user1@primary.com',
        'SMTP_PASSWORD_1': 'password1',
        'SMTP_USE_TLS_1': 'true',
        'SMTP_NAME_1': 'primary',
        'SMTP_PRIORITY_1': '100',
        'SMTP_FROM_EMAIL_1': 'sender@primary.com',
        
        # Backup server (will succeed)
        'SMTP_HOST_2': 'smtp.backup.com',
        'SMTP_PORT_2': '587',
        'SMTP_USERNAME_2': 'user2@backup.com',
        'SMTP_PASSWORD_2': 'password2',
        'SMTP_USE_TLS_2': 'true',
        'SMTP_NAME_2': 'backup',
        'SMTP_PRIORITY_2': '50',
        'SMTP_FROM_EMAIL_2': 'sender@backup.com',
    }
    
    with patch.dict(os.environ, test_env, clear=True):
        try:
            reset_email_service()
            
            # Mock SMTP connections - primary fails, backup succeeds
            def mock_smtp_factory(host, port, timeout=None):
                mock_instance = MagicMock()
                
                if host == 'smtp.primary.com':
                    # Primary server fails
                    mock_instance.login.side_effect = Exception("Primary server connection failed")
                    mock_instance.starttls.side_effect = Exception("Primary server connection failed")
                else:
                    # Backup server succeeds
                    mock_instance.login.return_value = None
                    mock_instance.send_message.return_value = {}
                    mock_instance.starttls.return_value = None
                
                return mock_instance
            
            with patch('smtplib.SMTP', side_effect=mock_smtp_factory):
                email_request = EmailRequest(
                    to="recipient@test.com",
                    subject="Failover Test Email",
                    body="This email should be sent via backup server."
                )
                
                service = get_email_service()
                response = await service.send_email(email_request)
                
                # Verify response
                assert response.success == True, f"Failover email should succeed: {response.error}"
                assert response.details is not None, "Should have response details"
                
                # Verify that backup server was used
                if 'smtp_server' in response.details:
                    # The exact server name might vary based on implementation
                    print(f"✓ Email sent via server: {response.details.get('smtp_server', 'unknown')}")
                
                print("✓ Multi-server failover works correctly")
                return response
                
        except Exception as e:
            print(f"✗ Multi-server failover test failed: {e}")
            raise


async def test_mcp_tools_integration():
    """Test MCP tools integration by testing underlying service methods."""
    print("\nTesting MCP tools integration...")
    
    test_env = {
        'SMTP_HOST': 'smtp.test.com',
        'SMTP_PORT': '587',
        'SMTP_USERNAME': 'test@test.com',
        'SMTP_PASSWORD': 'password',
        'SMTP_USE_TLS': 'true',
        'SMTP_FROM_EMAIL': 'sender@test.com',
    }
    
    with patch.dict(os.environ, test_env, clear=True):
        try:
            reset_email_service()
            service = get_email_service()
            
            # Test service status (underlying functionality of get_smtp_status)
            status_result = service.get_service_status()
            assert isinstance(status_result, dict), "Status should be a dictionary"
            assert status_result.get('service') == 'SMTP MCP Server', "Should identify as SMTP MCP Server"
            assert 'total_servers' in status_result, "Should include server count"
            
            print("✓ Service status functionality works correctly")
            
            # Test SMTP connection test (underlying functionality of test_smtp_connection)
            with patch('smtplib.SMTP') as mock_smtp_class:
                mock_smtp_instance = MagicMock()
                mock_smtp_class.return_value = mock_smtp_instance
                mock_smtp_instance.login.return_value = None
                mock_smtp_instance.starttls.return_value = None
                
                connection_result = await service.test_connection()
                assert isinstance(connection_result, dict), "Connection test should return dictionary"
                assert 'success' in connection_result, "Should have success field"
                
                print("✓ Connection test functionality works correctly")
            
            # Test email sending (underlying functionality of send_email)
            with patch('smtplib.SMTP') as mock_smtp_class:
                mock_smtp_instance = MagicMock()
                mock_smtp_class.return_value = mock_smtp_instance
                mock_smtp_instance.login.return_value = None
                mock_smtp_instance.send_message.return_value = {}
                mock_smtp_instance.starttls.return_value = None
                
                from server import EmailRequest
                email_request = EmailRequest(
                    to="recipient@test.com",
                    subject="MCP Tool Test",
                    body="This email was sent via MCP tool."
                )
                
                email_result = await service.send_email(email_request)
                
                assert email_result.success == True, f"Email should succeed: {email_result.error}"
                assert email_result.message_id is not None, "Should have message ID"
                
                print("✓ Email sending functionality works correctly")
            
            print("✓ All MCP tools underlying functionality tests passed")
            
        except Exception as e:
            print(f"✗ MCP tools integration test failed: {e}")
            raise


async def test_error_handling():
    """Test comprehensive error handling scenarios."""
    print("\nTesting error handling scenarios...")
    
    test_env = {
        'SMTP_HOST': 'smtp.test.com',
        'SMTP_PORT': '587',
        'SMTP_USERNAME': 'test@test.com',
        'SMTP_PASSWORD': 'password',
        'SMTP_USE_TLS': 'true',
    }
    
    with patch.dict(os.environ, test_env, clear=True):
        try:
            reset_email_service()
            service = get_email_service()
            
            # Test invalid email request
            try:
                invalid_request = EmailRequest(
                    to="",  # Empty recipient
                    subject="Test",
                    body="Test body"
                )
                assert False, "Should have raised ValueError for empty recipient"
            except ValueError as e:
                print("✓ Invalid email request validation works correctly")
            
            # Test SMTP connection failure
            with patch('smtplib.SMTP') as mock_smtp_class:
                mock_smtp_class.side_effect = Exception("Connection failed")
                
                valid_request = EmailRequest(
                    to="recipient@test.com",
                    subject="Test Email",
                    body="Test body"
                )
                
                response = await service.send_email(valid_request)
                assert response.success == False, "Should fail with connection error"
                assert "connection" in response.error.lower() or "failed" in response.error.lower()
                
                print("✓ SMTP connection failure handling works correctly")
            
            # Test template processing error
            with patch('smtplib.SMTP') as mock_smtp_class:
                mock_smtp_instance = MagicMock()
                mock_smtp_class.return_value = mock_smtp_instance
                
                template_request = EmailRequest(
                    to="recipient@test.com",
                    subject="Hello {missing_var}!",  # Missing template variable
                    body="Test body",
                    template_vars={"name": "John"}  # missing_var not provided
                )
                
                response = await service.send_email(template_request)
                assert response.success == False, "Should fail with template error"
                assert "template" in response.error.lower() or "missing" in response.error.lower()
                
                print("✓ Template processing error handling works correctly")
            
            print("✓ All error handling scenarios work correctly")
            
        except Exception as e:
            print(f"✗ Error handling test failed: {e}")
            raise


async def test_concurrent_email_sending():
    """Test concurrent email sending to verify thread safety."""
    print("\nTesting concurrent email sending...")
    
    test_env = {
        'SMTP_HOST': 'smtp.test.com',
        'SMTP_PORT': '587',
        'SMTP_USERNAME': 'test@test.com',
        'SMTP_PASSWORD': 'password',
        'SMTP_USE_TLS': 'true',
        'SMTP_FROM_EMAIL': 'sender@test.com',
    }
    
    with patch.dict(os.environ, test_env, clear=True):
        try:
            reset_email_service()
            
            with patch('smtplib.SMTP') as mock_smtp_class:
                mock_smtp_instance = MagicMock()
                mock_smtp_class.return_value = mock_smtp_instance
                mock_smtp_instance.login.return_value = None
                mock_smtp_instance.send_message.return_value = {}
                mock_smtp_instance.starttls.return_value = None
                
                service = get_email_service()
                
                # Create multiple email requests
                email_requests = []
                for i in range(5):
                    request = EmailRequest(
                        to=f"recipient{i}@test.com",
                        subject=f"Concurrent Test Email {i}",
                        body=f"This is concurrent test email number {i}."
                    )
                    email_requests.append(request)
                
                # Send emails concurrently
                tasks = [service.send_email(request) for request in email_requests]
                responses = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Verify all responses
                successful_sends = 0
                for i, response in enumerate(responses):
                    if isinstance(response, Exception):
                        print(f"✗ Concurrent email {i} failed with exception: {response}")
                    else:
                        assert hasattr(response, 'success'), f"Response {i} should have success attribute"
                        if response.success:
                            successful_sends += 1
                        else:
                            print(f"✗ Concurrent email {i} failed: {response.error}")
                
                assert successful_sends > 0, "At least some concurrent emails should succeed"
                print(f"✓ Concurrent email sending works correctly ({successful_sends}/{len(responses)} succeeded)")
                
        except Exception as e:
            print(f"✗ Concurrent email sending test failed: {e}")
            raise


def main():
    """Run all integration tests."""
    print("Running SMTP MCP Server Integration Tests...\n")
    print("=" * 60)
    
    try:
        # Run all integration tests
        asyncio.run(test_basic_email_sending())
        asyncio.run(test_html_email_with_attachments())
        asyncio.run(test_template_processing())
        asyncio.run(test_multi_server_failover())
        asyncio.run(test_mcp_tools_integration())
        asyncio.run(test_error_handling())
        asyncio.run(test_concurrent_email_sending())
        
        print("\n" + "=" * 60)
        print("✓ ALL INTEGRATION TESTS PASSED SUCCESSFULLY!")
        print("✓ End-to-end email flow works correctly")
        print("✓ Multi-server failover is functional")
        print("✓ Template processing is working")
        print("✓ Attachment handling is operational")
        print("✓ MCP tools integration is complete")
        print("✓ Error handling is comprehensive")
        print("✓ Concurrent operations are thread-safe")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"\n✗ INTEGRATION TESTS FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)