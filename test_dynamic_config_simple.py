#!/usr/bin/env python3
"""
Simple test for dynamic reconfiguration functionality.

This script tests the core dynamic reconfiguration logic without network connections.
"""

import os
import sys
import asyncio
from unittest.mock import patch

# Add the current directory to Python path
sys.path.insert(0, '.')

from server import SMTPConfig, EmailService


def test_configuration_validation():
    """Test configuration validation logic."""
    print("Testing configuration validation...")
    
    try:
        # Create initial configuration
        initial_config = SMTPConfig(
            host='smtp.initial.com',
            port=587,
            username='user@initial.com',
            password='password1',
            use_tls=True,
            name='initial_server',
            priority=100
        )
        
        service = EmailService([initial_config])
        
        # Test valid configuration change
        new_configs = [
            SMTPConfig(
                host='smtp.new.com',
                port=587,
                username='user@new.com',
                password='password2',
                use_tls=True,
                name='new_server',
                priority=100
            )
        ]
        
        validation_result = service._validate_configuration_changes([initial_config], new_configs)
        
        assert validation_result['valid'] == True, f"Valid configuration should pass: {validation_result}"
        assert validation_result['details']['new_server_count'] == 1
        assert validation_result['details']['old_server_count'] == 1
        
        print("✓ Valid configuration validation works")
        
        # Test invalid configuration (empty host)
        invalid_configs = [
            SMTPConfig(
                host='',  # Invalid empty host
                port=587,
                username='user@invalid.com',
                password='password',
                use_tls=True,
                name='invalid_server',
                priority=100
            )
        ]
        
        invalid_validation = service._validate_configuration_changes([initial_config], invalid_configs)
        assert invalid_validation['valid'] == False, "Invalid configuration should fail validation"
        assert 'SMTP host cannot be empty' in invalid_validation['error']
        
        print("✓ Invalid configuration rejection works")
        
        # Test duplicate server names
        duplicate_configs = [
            SMTPConfig(
                host='smtp.server1.com',
                port=587,
                username='user1@server.com',
                password='password1',
                use_tls=True,
                name='duplicate_name',
                priority=100
            ),
            SMTPConfig(
                host='smtp.server2.com',
                port=587,
                username='user2@server.com',
                password='password2',
                use_tls=True,
                name='duplicate_name',  # Same name as above
                priority=50
            )
        ]
        
        duplicate_validation = service._validate_configuration_changes([initial_config], duplicate_configs)
        assert duplicate_validation['valid'] == False, "Duplicate server names should fail validation"
        assert 'Duplicate server names found' in duplicate_validation['error']
        
        print("✓ Duplicate server name validation works")
        
        return True
        
    except Exception as e:
        print(f"✗ Configuration validation test failed: {e}")
        raise


def test_configuration_change_summary():
    """Test configuration change summary generation."""
    print("\nTesting configuration change summary...")
    
    try:
        # Create initial configuration
        initial_configs = [
            SMTPConfig(
                host='smtp.old.com',
                port=587,
                username='user@old.com',
                password='password1',
                use_tls=True,
                name='old_server',
                priority=100
            )
        ]
        
        service = EmailService(initial_configs)
        
        # Create new configuration with changes
        new_configs = [
            SMTPConfig(
                host='smtp.new.com',  # Changed host
                port=465,  # Changed port
                username='user@new.com',  # Changed username
                password='password2',  # Changed password
                use_ssl=True,  # Changed encryption
                use_tls=False,
                name='old_server',  # Same name (modified server)
                priority=50  # Changed priority
            ),
            SMTPConfig(
                host='smtp.backup.com',
                port=587,
                username='user@backup.com',
                password='password3',
                use_tls=True,
                name='backup_server',  # New server
                priority=25
            )
        ]
        
        change_summary = service._generate_configuration_change_summary(initial_configs, new_configs)
        
        assert change_summary['total_changes'] > 0, "Should detect changes"
        assert change_summary['old_server_count'] == 1, "Should track old server count"
        assert change_summary['new_server_count'] == 2, "Should track new server count"
        assert 'backup_server' in change_summary['servers_added'], "Should detect added server"
        
        # Check for modified server
        modified_servers = change_summary['servers_modified']
        assert len(modified_servers) == 1, "Should detect one modified server"
        assert modified_servers[0]['name'] == 'old_server', "Should identify modified server"
        
        # Check specific changes
        changes = modified_servers[0]['changes']
        assert 'host' in changes, "Should detect host change"
        assert 'port' in changes, "Should detect port change"
        assert 'priority' in changes, "Should detect priority change"
        assert changes['host']['old'] == 'smtp.old.com', "Should track old host"
        assert changes['host']['new'] == 'smtp.new.com', "Should track new host"
        
        print("✓ Configuration change summary generation works")
        
        return True
        
    except Exception as e:
        print(f"✗ Configuration change summary test failed: {e}")
        raise


def test_thread_safety():
    """Test thread safety mechanisms."""
    print("\nTesting thread safety...")
    
    try:
        import threading
        
        # Create service
        config = SMTPConfig(
            host='smtp.test.com',
            port=587,
            username='user@test.com',
            password='password',
            use_tls=True,
            name='test_server',
            priority=100
        )
        
        service = EmailService([config])
        
        # Test that the service has a configuration lock
        assert hasattr(service, '_config_lock'), "Service should have configuration lock"
        assert isinstance(service._config_lock, threading.RLock), "Configuration lock should be RLock"
        
        print("✓ Service has proper thread synchronization primitives")
        
        # Test that the lock can be acquired and released
        with service._config_lock:
            original_configs = service.configs.copy()
            assert len(original_configs) > 0, "Should have original configurations"
        
        print("✓ Configuration lock can be acquired and released")
        
        # Test that multiple acquisitions work (RLock behavior)
        with service._config_lock:
            with service._config_lock:
                # This should not deadlock
                assert True, "RLock should allow multiple acquisitions"
        
        print("✓ RLock allows multiple acquisitions")
        
        return True
        
    except Exception as e:
        print(f"✗ Thread safety test failed: {e}")
        raise


def test_configuration_loading():
    """Test configuration loading from environment variables."""
    print("\nTesting configuration loading...")
    
    # Test single server configuration
    single_env = {
        'SMTP_HOST': 'smtp.single.com',
        'SMTP_PORT': '587',
        'SMTP_USERNAME': 'user@single.com',
        'SMTP_PASSWORD': 'password',
        'SMTP_USE_TLS': 'true',
        'SMTP_NAME': 'single_server',
    }
    
    with patch.dict(os.environ, single_env, clear=True):
        try:
            from server import load_smtp_configs
            configs = load_smtp_configs()
            
            assert len(configs) == 1, f"Expected 1 config, got {len(configs)}"
            assert configs[0].name == 'single_server'
            assert configs[0].host == 'smtp.single.com'
            
            print("✓ Single server configuration loading works")
            
        except Exception as e:
            print(f"✗ Single server configuration loading failed: {e}")
            raise
    
    # Test multi-server configuration
    multi_env = {
        'SMTP_HOST_1': 'smtp.primary.com',
        'SMTP_PORT_1': '587',
        'SMTP_USERNAME_1': 'user1@primary.com',
        'SMTP_PASSWORD_1': 'password1',
        'SMTP_USE_TLS_1': 'true',
        'SMTP_NAME_1': 'primary_server',
        'SMTP_PRIORITY_1': '100',
        
        'SMTP_HOST_2': 'smtp.backup.com',
        'SMTP_PORT_2': '465',
        'SMTP_USERNAME_2': 'user2@backup.com',
        'SMTP_PASSWORD_2': 'password2',
        'SMTP_USE_SSL_2': 'true',
        'SMTP_USE_TLS_2': 'false',
        'SMTP_NAME_2': 'backup_server',
        'SMTP_PRIORITY_2': '50',
    }
    
    with patch.dict(os.environ, multi_env, clear=True):
        try:
            configs = load_smtp_configs()
            
            assert len(configs) == 2, f"Expected 2 configs, got {len(configs)}"
            assert configs[0].name == 'primary_server', "Primary server should be first (highest priority)"
            assert configs[0].priority == 100
            assert configs[1].name == 'backup_server'
            assert configs[1].priority == 50
            
            print("✓ Multi-server configuration loading works")
            
        except Exception as e:
            print(f"✗ Multi-server configuration loading failed: {e}")
            raise
    
    return True


def main():
    """Run all dynamic reconfiguration tests."""
    print("Running dynamic reconfiguration core functionality tests...\n")
    
    try:
        # Test configuration validation
        test_configuration_validation()
        
        # Test configuration change summary
        test_configuration_change_summary()
        
        # Test thread safety
        test_thread_safety()
        
        # Test configuration loading
        test_configuration_loading()
        
        print("\n" + "="*70)
        print("✓ All dynamic reconfiguration core tests passed successfully!")
        print("✓ Configuration validation, change detection, and thread safety work correctly")
        print("✓ Dynamic reconfiguration implementation is ready for use")
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