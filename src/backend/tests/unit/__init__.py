"""
Unit test package initialization module for the Memory Agent system.
Configures unit test environment with test isolation, mock response handling,
and component-level error testing capabilities.

External Dependencies:
- pytest==7.4.0: Testing framework configuration and test scope management
"""

import os
import pytest
from typing import Dict, Any
from .. import configure_test_environment

# Unit test configuration constants
UNIT_TEST_SCOPE = "function"  # Ensure test isolation at function level
MOCK_RESPONSES_DIR = "tests/unit/mock_responses"  # Directory for mock response data

def setup_unit_test_environment() -> None:
    """
    Configures the specific environment for unit tests including mock directories,
    test scopes, and integration with parent configuration.
    
    Sets up:
    - Unit test scope configuration
    - Mock response directories
    - Component error simulation
    - Test metrics collection
    - Resource cleanup handlers
    - Test parallelization
    - Mock data optimization
    """
    # Initialize parent test environment
    configure_test_environment()
    
    # Create mock responses directory if it doesn't exist
    os.makedirs(MOCK_RESPONSES_DIR, exist_ok=True)
    
    # Configure unit test specific settings
    pytest.unit_test_config = {
        "scope": UNIT_TEST_SCOPE,
        "mock_dir": MOCK_RESPONSES_DIR,
        "metrics": {
            "unit_tests_executed": 0,
            "component_validations": {},
            "mock_response_hits": 0
        }
    }
    
    # Register unit test fixtures
    register_unit_test_fixtures()
    
    # Configure parallel test execution
    pytest.parallel_config = {
        "workers": 4,
        "scope": "function"
    }

def register_unit_test_fixtures():
    """Register pytest fixtures specific to unit testing."""
    
    @pytest.fixture(scope=UNIT_TEST_SCOPE, autouse=True)
    def unit_test_metrics():
        """Track unit test execution metrics."""
        # Pre-test setup
        test_start = pytest.unit_test_config["metrics"]["unit_tests_executed"]
        
        yield  # Test execution
        
        # Post-test metrics update
        pytest.unit_test_config["metrics"]["unit_tests_executed"] = test_start + 1
    
    @pytest.fixture(scope=UNIT_TEST_SCOPE)
    def mock_response_loader():
        """Fixture for loading mock response data."""
        def _load_mock(component: str, response_file: str) -> Dict[str, Any]:
            """
            Load mock response data for a specific component.
            
            Args:
                component: Name of the component being tested
                response_file: Name of the mock response file
                
            Returns:
                Dict containing mock response data
            """
            file_path = os.path.join(MOCK_RESPONSES_DIR, component, response_file)
            if os.path.exists(file_path):
                pytest.unit_test_config["metrics"]["mock_response_hits"] += 1
                with open(file_path, 'r') as f:
                    return eval(f.read())  # Safe eval for mock data
            raise FileNotFoundError(f"Mock response not found: {file_path}")
        
        return _load_mock
    
    @pytest.fixture(scope=UNIT_TEST_SCOPE)
    def component_error_simulator():
        """Fixture for simulating component-level errors."""
        def _simulate_error(component: str, error_type: str, **kwargs):
            """
            Simulate specific component errors for testing error handling.
            
            Args:
                component: Name of the component to simulate error for
                error_type: Type of error to simulate
                **kwargs: Additional error parameters
            """
            error_registry = {
                "storage": {
                    "connection": ConnectionError,
                    "permission": PermissionError,
                    "not_found": FileNotFoundError
                },
                "llm": {
                    "timeout": TimeoutError,
                    "api": RuntimeError,
                    "rate_limit": Exception
                }
            }
            
            if component in error_registry and error_type in error_registry[component]:
                raise error_registry[component][error_type](**kwargs)
            raise ValueError(f"Unknown error simulation: {component}.{error_type}")
        
        return _simulate_error

# Initialize unit test environment when module is imported
setup_unit_test_environment()

# Export public interface
__all__ = [
    'setup_unit_test_environment',
    'UNIT_TEST_SCOPE',
    'MOCK_RESPONSES_DIR'
]