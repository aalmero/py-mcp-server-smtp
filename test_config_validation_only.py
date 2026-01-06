#!/usr/bin/env python3
"""
Test only the configuration validation logic without any network operations.
"""

import sys
sys.path.insert(0, '.')

#from server import SMTPConfig, EmailService
from smtp import SMTPConfig, EmailService


def test_basic_functionality():
    """Test basic dynamic reconfiguration functionality."""
    print("Testing basic dynamic reconfiguration functionality...")
    
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
        
        # Create service (this should not trigger network operations)
        service = EmailService([initial_config])
        
        print("✓ EmailService created successfully")
        
        # Test that service has the required methods for dynamic reconfiguration
        assert hasattr(service, 'reload_configuration'), "Service should have reload_configuration method"
        assert hasattr(service, 'reconnect_smtp_servers'), "Service should have reconnect_smtp_servers method"
        assert hasattr(service, '_validate_configuration_changes'), "Service should have _validate_configuration_changes method"
        assert hasattr(service, '_generate_configuration_change_summary'), "Service should have _generate_configuration_change_summary method"
        assert hasattr(service, '_config_lock'), "Service should have _config_lock for thread safety"
        
        print("✓ Service has all required dynamic reconfiguration methods")
        
        # Test configuration validation with valid configuration
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
        
        assert isinstance(validation_result, dict), "Validation result should be a dictionary"
        assert 'valid' in validation_result, "Validation result should have 'valid' field"
        assert validation_result['valid'] == True, f"Valid configuration should pass validation: {validation_result}"
        
        print("✓ Configuration validation works for valid configurations")
        
        # Test configuration validation with invalid configuration
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
        
        try:
            # This should raise an exception during SMTPConfig creation due to validation
            service._validate_configuration_changes([initial_config], invalid_configs)
            print("✗ Expected validation to fail for invalid configuration")
            return False
        except ValueError as e:
            print("✓ Invalid configuration properly rejected during creation")
        
        # Test change summary generation
        change_summary = service._generate_configuration_change_summary([initial_config], new_configs)
        
        assert isinstance(change_summary, dict), "Change summary should be a dictionary"
        assert 'total_changes' in change_summary, "Change summary should have total_changes"
        assert change_summary['total_changes'] > 0, "Should detect changes"
        assert 'servers_removed' in change_summary, "Should track removed servers"
        assert 'servers_added' in change_summary, "Should track added servers"
        
        print("✓ Configuration change summary generation works")
        
        # Test thread safety primitives
        import threading
        assert isinstance(service._config_lock, threading.RLock), "Should have RLock for thread safety"
        
        with service._config_lock:
            # This should not deadlock
            with service._config_lock:
                assert True, "RLock should allow multiple acquisitions"
        
        print("✓ Thread safety mechanisms are in place")
        
        return True
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run the basic functionality test."""
    print("Testing dynamic reconfiguration core functionality (no network)...\n")
    
    success = test_basic_functionality()
    
    if success:
        print("\n" + "="*60)
        print("✓ Dynamic reconfiguration core functionality test passed!")
        print("✓ All required methods and mechanisms are implemented")
        print("✓ Configuration validation and change detection work")
        print("✓ Thread safety primitives are in place")
        print("="*60)
    else:
        print("\n✗ Dynamic reconfiguration test failed!")
    
    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)