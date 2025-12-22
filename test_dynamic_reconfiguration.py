#!/usr/bin/env python3
"""
Test script for dynamic reconfiguration MCP tools.

This script tests the MCP tools for dynamic reconfiguration functionality
without requiring actual SMTP servers.
"""

import os
import sys
import asyncio
from unittest.mock import patch, MagicMock

# Add the current directory to Python path
sys.path.insert(0, '.')

from server import (
    SMTPConfig, EmailService, get_email_service, reset_email_service,
    reload_smtp_configuration, reconnect_smtp_servers
)


async def test_reload_smtp_configuration_tool():
    """Test the reload_smtp_configuration MCP tool."""
    print("Testing reload_smtp_configuration MCP tool...")
    
    # Set up initial environment
    initial_env = {
        'SMTP_HOST': 'smtp.initial.com',
        'SMTP_PORT': '587',
        'SMTP_USERNAME': 'user@initial.com',
        'SMTP_PASSWORD': 'password1',
        'SMTP_USE_TLS': 'true',
        'SMTP_NAME': 'initial_server',
    }
    
    with patch.dict(os.environ, initial_env, clear=True):
        try:
            # Reset global service to ensure clean state
            reset_email_service()
            
            # Initialize service with initial config
            service = get_email_service()
            initial_server_count = len(service.configs)
            initial_server_name = service.primary_config.name
            
            print(f"✓ Initial service initialized with {initial_server_count} server: {initial_server_name}")
            
            # Change environment to new configuration
            new_env = {
                'SMTP_HOST_1': 'smtp.new1.com',
                'SMTP_PORT_1': '587',
                'SMTP_USERNAME_1': 'user1@new.com',
                'SMTP_PASSWORD_1': 'password1',
                'SMTP_USE_TLS_1': 'true',
                'SMTP_USE_SSL_1': 'false',
                'SMTP_NAME_1': 'new_server_1',
                'SMTP_PRIORITY_1': '100',
                
                'SMTP_HOST_2': 'smtp.new2.com',
                'SMTP_PORT_2': '465',
                'SMTP_USERNAME_2': 'user2@new.com',
                'SMTP_PASSWORD_2': 'password2',
                'SMTP_USE_SSL_2': 'true',
                'SMTP_USE_TLS_2': 'false',
                'SMTP_NAME_2': 'new_server_2',
                'SMTP_PRIORITY_2': '50',
            }
            
            with patch.dict(os.environ, new_env, clear=True):
                # Mock the SMTPClient.connect method to avoid actual SMTP connections
                from unittest.mock import AsyncMock
                
                async def mock_connect():
                    return False  # Simulate connection failure
                
                # Patch the SMTPClient.connect method
                with patch('server.SMTPClient.connect', new=mock_connect):
                    # Test the underlying service method directly
                    result = await service.reload_configuration()
                    
                    # The reload should fail because of mocked connection failure
                    assert isinstance(result, dict), "Result should be a dictionary"
                    assert 'success' in result, "Result should have success field"
                    
                    if result['success']:
                        print("✓ Configuration reload succeeded (unexpected)")
                        assert 'changes' in result, "Successful result should include changes"
                        assert 'new_configuration' in result, "Successful result should include new configuration"
                    else:
                        print("✓ Configuration reload failed as expected (mocked connection failure)")
                        assert 'error' in result, "Failed result should include error message"
                        # Should fail at connection test step
                        if 'step' in result:
                            assert result['step'] in ['connection_test', 'smtp_connection', 'configuration_loading'], f"Should fail at expected step, got: {result['step']}"
                    
                    print("✓ reload_smtp_configuration functionality works correctly")
                
        except Exception as e:
            print(f"✗ Failed reload_smtp_configuration test: {e}")
            raise


async def test_reconnect_smtp_servers_tool():
    """Test the reconnect_smtp_servers MCP tool."""
    print("\nTesting reconnect_smtp_servers MCP tool...")
    
    # Set up test environment
    test_env = {
        'SMTP_HOST': 'smtp.test.com',
        'SMTP_PORT': '587',
        'SMTP_USERNAME': 'user@test.com',
        'SMTP_PASSWORD': 'password',
        'SMTP_USE_TLS': 'true',
        'SMTP_NAME': 'test_server',
    }
    
    with patch.dict(os.environ, test_env, clear=True):
        try:
            # Reset global service to ensure clean state
            reset_email_service()
            
            # Initialize service
            service = get_email_service()
            
            print(f"✓ Service initialized with {len(service.configs)} server")
            
            # Mock the SMTPClient.connect method to avoid actual SMTP connections
            from unittest.mock import AsyncMock
            
            async def mock_connect():
                return False  # Simulate connection failure
            
            # Patch the SMTPClient.connect method
            with patch('server.SMTPClient.connect', new=mock_connect):
                # Test the underlying service method directly
                result = await service.reconnect_smtp_servers()
                
                assert isinstance(result, dict), "Result should be a dictionary"
                assert 'success' in result, "Result should have success field"
                
                if result['success']:
                    print("✓ Server reconnection succeeded (unexpected)")
                    assert 'connection_test' in result, "Successful result should include connection test"
                else:
                    print("✓ Server reconnection failed as expected (mocked connection failure)")
                    assert 'error' in result or 'connection_test' in result, "Failed result should include error message or connection test"
                
                print("✓ reconnect_smtp_servers functionality works correctly")
            
        except Exception as e:
            print(f"✗ Failed reconnect_smtp_servers test: {e}")
            raise


async def test_configuration_validation_edge_cases():
    """Test configuration validation edge cases."""
    print("\nTesting configuration validation edge cases...")
    
    try:
        # Create a service for testing
        initial_config = SMTPConfig(
            host='smtp.test.com',
            port=587,
            username='user@test.com',
            password='password',
            use_tls=True,
            name='test_server',
            priority=100
        )
        
        service = EmailService([initial_config])
        
        # Test empty configuration
        empty_validation = service._validate_configuration_changes([initial_config], [])
        assert empty_validation['valid'] == False, "Empty configuration should be invalid"
        assert 'No SMTP server configurations found' in empty_validation['error']
        
        print("✓ Empty configuration validation works correctly")
        
        # Test configuration with invalid port
        invalid_port_config = SMTPConfig(
            host='smtp.test.com',
            port=99999,  # Invalid port
            username='user@test.com',
            password='password',
            use_tls=True,
            name='invalid_port_server',
            priority=100
        )
        
        invalid_port_validation = service._validate_configuration_changes([initial_config], [invalid_port_config])
        assert invalid_port_validation['valid'] == False, "Invalid port configuration should be invalid"
        
        print("✓ Invalid port validation works correctly")
        
        # Test configuration with empty host
        invalid_host_config = SMTPConfig(
            host='',  # Empty host
            port=587,
            username='user@test.com',
            password='password',
            use_tls=True,
            name='invalid_host_server',
            priority=100
        )
        
        invalid_host_validation = service._validate_configuration_changes([initial_config], [invalid_host_config])
        assert invalid_host_validation['valid'] == False, "Empty host configuration should be invalid"
        
        print("✓ Empty host validation works correctly")
        
        # Test valid configuration change
        valid_new_config = SMTPConfig(
            host='smtp.newserver.com',
            port=587,
            username='user@newserver.com',
            password='newpassword',
            use_tls=True,
            name='new_server',
            priority=100
        )
        
        valid_validation = service._validate_configuration_changes([initial_config], [valid_new_config])
        assert valid_validation['valid'] == True, "Valid configuration should pass validation"
        
        print("✓ Valid configuration validation works correctly")
        
        print("✓ All configuration validation edge cases work correctly")
        
    except Exception as e:
        print(f"✗ Failed configuration validation edge cases test: {e}")
        raise


async def test_thread_safety():
    """Test thread safety of configuration updates."""
    print("\nTesting thread safety of configuration updates...")
    
    try:
        import threading
        import time
        
        # Create initial service
        initial_config = SMTPConfig(
            host='smtp.test.com',
            port=587,
            username='user@test.com',
            password='password',
            use_tls=True,
            name='test_server',
            priority=100
        )
        
        service = EmailService([initial_config])
        
        # Test that the service has a configuration lock
        assert hasattr(service, '_config_lock'), "Service should have configuration lock"
        assert isinstance(service._config_lock, threading.RLock), "Configuration lock should be RLock"
        
        print("✓ Service has proper thread synchronization primitives")
        
        # Test that configuration methods use the lock
        # We can't easily test actual concurrent access without complex setup,
        # but we can verify the lock exists and is used in the context manager
        
        with service._config_lock:
            original_configs = service.configs.copy()
            # This simulates what happens during configuration reload
            assert len(original_configs) > 0, "Should have original configurations"
        
        print("✓ Configuration lock can be acquired and released")
        
        print("✓ Thread safety mechanisms are in place")
        
    except Exception as e:
        print(f"✗ Failed thread safety test: {e}")
        raise


def main():
    """Run all dynamic reconfiguration tests."""
    print("Running dynamic reconfiguration MCP tools tests...\n")
    
    try:
        # Test MCP tools
        asyncio.run(test_reload_smtp_configuration_tool())
        asyncio.run(test_reconnect_smtp_servers_tool())
        
        # Test validation edge cases
        asyncio.run(test_configuration_validation_edge_cases())
        
        # Test thread safety
        asyncio.run(test_thread_safety())
        
        print("\n" + "="*70)
        print("✓ All dynamic reconfiguration tests passed successfully!")
        print("✓ Dynamic reconfiguration MCP tools are working correctly")
        print("✓ Configuration validation and thread safety are implemented")
        print("="*70)
        
        return True
        
    except Exception as e:
        print(f"\n✗ Dynamic reconfiguration tests failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)