#!/usr/bin/env python3
"""
Test script for multi-server SMTP functionality.

This script tests the multi-server configuration loading and basic functionality
without requiring actual SMTP servers.
"""

import os
import sys
import asyncio
from unittest.mock import patch, MagicMock

# Add the current directory to Python path
sys.path.insert(0, '.')

from server import SMTPConfig, MultiServerSMTPClient, EmailService, load_smtp_configs


def test_smtp_config_multi_loading():
    """Test loading multiple SMTP configurations from environment variables."""
    print("Testing multi-server SMTP configuration loading...")
    
    # Set up test environment variables for multiple servers
    test_env = {
        # Server 1 (primary)
        'SMTP_HOST_1': 'smtp.gmail.com',
        'SMTP_PORT_1': '587',
        'SMTP_USERNAME_1': 'user1@gmail.com',
        'SMTP_PASSWORD_1': 'password1',
        'SMTP_USE_TLS_1': 'true',
        'SMTP_NAME_1': 'gmail_primary',
        'SMTP_PRIORITY_1': '100',
        
        # Server 2 (backup)
        'SMTP_HOST_2': 'smtp.outlook.com',
        'SMTP_PORT_2': '587',
        'SMTP_USERNAME_2': 'user2@outlook.com',
        'SMTP_PASSWORD_2': 'password2',
        'SMTP_USE_TLS_2': 'true',
        'SMTP_NAME_2': 'outlook_backup',
        'SMTP_PRIORITY_2': '50',
        
        # Server 3 (fallback)
        'SMTP_HOST_3': 'smtp.example.com',
        'SMTP_PORT_3': '465',
        'SMTP_USERNAME_3': 'user3@example.com',
        'SMTP_PASSWORD_3': 'password3',
        'SMTP_USE_SSL_3': 'true',
        'SMTP_NAME_3': 'example_fallback',
        'SMTP_PRIORITY_3': '10',
    }
    
    with patch.dict(os.environ, test_env, clear=True):
        try:
            configs = SMTPConfig.from_env_multi()
            
            print(f"✓ Successfully loaded {len(configs)} server configurations")
            
            # Verify configurations are sorted by priority (highest first)
            assert len(configs) == 3, f"Expected 3 configs, got {len(configs)}"
            assert configs[0].name == 'gmail_primary', f"Expected gmail_primary first, got {configs[0].name}"
            assert configs[0].priority == 100, f"Expected priority 100, got {configs[0].priority}"
            assert configs[1].name == 'outlook_backup', f"Expected outlook_backup second, got {configs[1].name}"
            assert configs[2].name == 'example_fallback', f"Expected example_fallback third, got {configs[2].name}"
            
            print("✓ Server configurations are correctly sorted by priority")
            
            # Verify individual server configurations
            gmail_config = configs[0]
            assert gmail_config.host == 'smtp.gmail.com'
            assert gmail_config.port == 587
            assert gmail_config.use_tls == True
            assert gmail_config.use_ssl == False
            
            outlook_config = configs[1]
            assert outlook_config.host == 'smtp.outlook.com'
            assert outlook_config.port == 587
            
            example_config = configs[2]
            assert example_config.host == 'smtp.example.com'
            assert example_config.port == 465
            assert example_config.use_ssl == True
            # Note: use_tls defaults to True, but use_ssl takes precedence
            
            print("✓ Individual server configurations are correct")
            
            return configs
            
        except Exception as e:
            print(f"✗ Failed to load multi-server configurations: {e}")
            raise


def test_multi_server_client_initialization():
    """Test MultiServerSMTPClient initialization and basic functionality."""
    print("\nTesting MultiServerSMTPClient initialization...")
    
    # Create test configurations
    configs = [
        SMTPConfig(
            host='smtp.gmail.com',
            port=587,
            username='user1@gmail.com',
            password='password1',
            use_tls=True,
            name='gmail_primary',
            priority=100
        ),
        SMTPConfig(
            host='smtp.outlook.com',
            port=587,
            username='user2@outlook.com',
            password='password2',
            use_tls=True,
            name='outlook_backup',
            priority=50
        )
    ]
    
    try:
        client = MultiServerSMTPClient(configs)
        
        print(f"✓ MultiServerSMTPClient initialized with {len(client.configs)} servers")
        
        # Test server status
        status = client.get_server_status()
        assert status['total_servers'] == 2
        assert status['available_servers'] == 2
        assert status['failed_servers'] == 0
        assert status['current_server'] is None
        
        print("✓ Server status reporting works correctly")
        
        # Test available servers
        available = client._get_available_servers()
        assert len(available) == 2
        assert available[0].name == 'gmail_primary'  # Higher priority first
        assert available[1].name == 'outlook_backup'
        
        print("✓ Available servers are correctly prioritized")
        
        return client
        
    except Exception as e:
        print(f"✗ Failed to initialize MultiServerSMTPClient: {e}")
        raise


def test_email_service_multi_server():
    """Test EmailService with multi-server support."""
    print("\nTesting EmailService with multi-server support...")
    
    # Create test configurations
    configs = [
        SMTPConfig(
            host='smtp.gmail.com',
            port=587,
            username='user1@gmail.com',
            password='password1',
            use_tls=True,
            name='gmail_primary',
            priority=100,
            from_email='sender@gmail.com'
        ),
        SMTPConfig(
            host='smtp.outlook.com',
            port=587,
            username='user2@outlook.com',
            password='password2',
            use_tls=True,
            name='outlook_backup',
            priority=50,
            from_email='sender@outlook.com'
        )
    ]
    
    try:
        service = EmailService(configs)
        
        print(f"✓ EmailService initialized with {len(service.configs)} servers")
        
        # Test service status
        status = service.get_service_status()
        assert status['service'] == 'SMTP MCP Server'
        assert status['multi_server_enabled'] == True
        assert status['total_servers'] == 2
        assert status['primary_server'] == 'gmail_primary'
        
        print("✓ EmailService status reporting works correctly")
        
        # Test primary config selection
        assert service.primary_config.name == 'gmail_primary'
        assert service.primary_config.priority == 100
        
        print("✓ Primary server configuration is correctly selected")
        
        return service
        
    except Exception as e:
        print(f"✗ Failed to initialize EmailService with multi-server support: {e}")
        raise


def test_fallback_to_single_server():
    """Test fallback to single server configuration when no numbered configs exist."""
    print("\nTesting fallback to single server configuration...")
    
    # Set up single server environment
    test_env = {
        'SMTP_HOST': 'smtp.example.com',
        'SMTP_PORT': '587',
        'SMTP_USERNAME': 'user@example.com',
        'SMTP_PASSWORD': 'password',
        'SMTP_USE_TLS': 'true',
        'SMTP_NAME': 'single_server',
    }
    
    with patch.dict(os.environ, test_env, clear=True):
        try:
            configs = SMTPConfig.from_env_multi()
            
            print(f"✓ Successfully loaded {len(configs)} server configuration (fallback)")
            
            assert len(configs) == 1, f"Expected 1 config, got {len(configs)}"
            assert configs[0].name == 'single_server'
            assert configs[0].host == 'smtp.example.com'
            
            print("✓ Single server fallback works correctly")
            
            return configs
            
        except Exception as e:
            print(f"✗ Failed single server fallback test: {e}")
            raise


async def test_server_failover_logic():
    """Test server failover logic (without actual SMTP connections)."""
    print("\nTesting server failover logic...")
    
    configs = [
        SMTPConfig(
            host='smtp.primary.com',
            port=587,
            username='user1@primary.com',
            password='password1',
            use_tls=True,
            name='primary',
            priority=100
        ),
        SMTPConfig(
            host='smtp.backup.com',
            port=587,
            username='user2@backup.com',
            password='password2',
            use_tls=True,
            name='backup',
            priority=50
        )
    ]
    
    try:
        client = MultiServerSMTPClient(configs)
        
        # Test server key generation
        key1 = client._get_server_key(configs[0])
        key2 = client._get_server_key(configs[1])
        
        assert key1 != key2, "Server keys should be unique"
        assert 'smtp.primary.com:587:user1@primary.com' == key1
        
        print("✓ Server key generation works correctly")
        
        # Test marking servers as failed
        client.failed_servers.add(key1)
        client.last_failure_time[key1] = 1000.0  # Old timestamp
        
        available = client._get_available_servers()
        assert len(available) == 2, "Old failures should be reset"
        
        print("✓ Failed server reset logic works correctly")
        
        # Test recent failure
        import time
        client.failed_servers.add(key1)
        client.last_failure_time[key1] = time.time()  # Recent timestamp
        
        available = client._get_available_servers()
        assert len(available) == 1, "Recent failures should be excluded"
        assert available[0].name == 'backup'
        
        print("✓ Recent failure exclusion works correctly")
        
        return client
        
    except Exception as e:
        print(f"✗ Failed server failover logic test: {e}")
        raise


async def test_dynamic_reconfiguration():
    """Test dynamic reconfiguration functionality."""
    print("\nTesting dynamic reconfiguration functionality...")
    
    # Initial configuration
    initial_configs = [
        SMTPConfig(
            host='smtp.initial.com',
            port=587,
            username='user@initial.com',
            password='password1',
            use_tls=True,
            name='initial_server',
            priority=100
        )
    ]
    
    try:
        service = EmailService(initial_configs)
        
        print("✓ EmailService initialized with initial configuration")
        
        # Test configuration validation
        new_configs = [
            SMTPConfig(
                host='smtp.new.com',
                port=587,
                username='user@new.com',
                password='password2',
                use_tls=True,
                name='new_server',
                priority=100
            ),
            SMTPConfig(
                host='smtp.backup.com',
                port=465,
                username='user@backup.com',
                password='password3',
                use_ssl=True,
                use_tls=False,  # Explicitly set to False when using SSL
                name='backup_server',
                priority=50
            )
        ]
        
        # Test configuration validation
        validation_result = service._validate_configuration_changes(initial_configs, new_configs)
        
        assert validation_result['valid'] == True, f"Configuration validation should pass: {validation_result}"
        assert validation_result['details']['new_server_count'] == 2
        assert validation_result['details']['old_server_count'] == 1
        
        print("✓ Configuration validation works correctly")
        
        # Test configuration change summary
        change_summary = service._generate_configuration_change_summary(initial_configs, new_configs)
        
        assert change_summary['total_changes'] > 0
        assert 'initial_server' in change_summary['servers_removed']
        assert 'new_server' in change_summary['servers_added']
        assert 'backup_server' in change_summary['servers_added']
        
        print("✓ Configuration change summary generation works correctly")
        
        # Test invalid configuration validation
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
        
        invalid_validation = service._validate_configuration_changes(initial_configs, invalid_configs)
        assert invalid_validation['valid'] == False, "Invalid configuration should fail validation"
        
        print("✓ Invalid configuration rejection works correctly")
        
        # Test duplicate server name validation
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
        
        duplicate_validation = service._validate_configuration_changes(initial_configs, duplicate_configs)
        assert duplicate_validation['valid'] == False, "Duplicate server names should fail validation"
        assert 'duplicate_name' in duplicate_validation['error']
        
        print("✓ Duplicate server name validation works correctly")
        
        return service
        
    except Exception as e:
        print(f"✗ Failed dynamic reconfiguration test: {e}")
        raise


def main():
    """Run all multi-server tests."""
    print("Running multi-server SMTP functionality tests...\n")
    
    try:
        # Test configuration loading
        configs = test_smtp_config_multi_loading()
        
        # Test multi-server client
        client = test_multi_server_client_initialization()
        
        # Test email service
        service = test_email_service_multi_server()
        
        # Test single server fallback
        single_configs = test_fallback_to_single_server()
        
        # Test failover logic
        asyncio.run(test_server_failover_logic())
        
        # Test dynamic reconfiguration
        asyncio.run(test_dynamic_reconfiguration())
        
        print("\n" + "="*60)
        print("✓ All multi-server SMTP tests passed successfully!")
        print("✓ Multi-server support implementation is working correctly")
        print("✓ Dynamic reconfiguration functionality is working correctly")
        print("="*60)
        
        return True
        
    except Exception as e:
        print(f"\n✗ Multi-server tests failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)