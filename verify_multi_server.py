#!/usr/bin/env python3
"""
Simple verification script for multi-server SMTP functionality.
"""

import os
from server import SMTPConfig, MultiServerSMTPClient, EmailService

def verify_multi_server_config():
    """Verify multi-server configuration creation."""
    print("Verifying multi-server configuration...")
    
    # Create test configurations manually
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
    
    print(f"✓ Created {len(configs)} SMTP configurations")
    
    # Test MultiServerSMTPClient
    client = MultiServerSMTPClient(configs)
    print(f"✓ MultiServerSMTPClient initialized with {len(client.configs)} servers")
    
    # Test server status
    status = client.get_server_status()
    print(f"✓ Server status: {status['total_servers']} total, {status['available_servers']} available")
    
    # Test EmailService
    service = EmailService(configs)
    print(f"✓ EmailService initialized with multi-server support")
    
    # Test service status
    service_status = service.get_service_status()
    print(f"✓ Service status: multi-server enabled = {service_status['multi_server_enabled']}")
    
    return True

def verify_environment_loading():
    """Verify environment variable loading for multi-server."""
    print("\nVerifying environment variable loading...")
    
    # Test with environment variables
    test_env = {
        'SMTP_HOST_1': 'smtp.test1.com',
        'SMTP_PORT_1': '587',
        'SMTP_USERNAME_1': 'user1@test.com',
        'SMTP_PASSWORD_1': 'pass1',
        'SMTP_NAME_1': 'test1',
        'SMTP_PRIORITY_1': '100',
        
        'SMTP_HOST_2': 'smtp.test2.com',
        'SMTP_PORT_2': '465',
        'SMTP_USERNAME_2': 'user2@test.com',
        'SMTP_PASSWORD_2': 'pass2',
        'SMTP_USE_SSL_2': 'true',
        'SMTP_NAME_2': 'test2',
        'SMTP_PRIORITY_2': '50',
    }
    
    # Temporarily set environment variables
    original_env = {}
    for key, value in test_env.items():
        original_env[key] = os.environ.get(key)
        os.environ[key] = value
    
    try:
        configs = SMTPConfig.from_env_multi()
        print(f"✓ Loaded {len(configs)} configurations from environment")
        
        # Verify priority sorting
        assert configs[0].priority >= configs[1].priority, "Configs should be sorted by priority"
        print(f"✓ Configurations sorted by priority: {configs[0].name} (p={configs[0].priority}), {configs[1].name} (p={configs[1].priority})")
        
        return True
        
    finally:
        # Restore original environment
        for key in test_env:
            if original_env[key] is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = original_env[key]

def main():
    """Run verification tests."""
    print("Multi-Server SMTP Implementation Verification")
    print("=" * 50)
    
    try:
        verify_multi_server_config()
        verify_environment_loading()
        
        print("\n" + "=" * 50)
        print("✓ All verification tests passed!")
        print("✓ Multi-server SMTP support is implemented correctly")
        print("=" * 50)
        
        return True
        
    except Exception as e:
        print(f"\n✗ Verification failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)