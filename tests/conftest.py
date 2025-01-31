import pytest
import os
import sys
from pathlib import Path

# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.parent

# Add src directory to Python path
sys.path.insert(0, str(PROJECT_ROOT / "src"))

# Common fixtures can be added here
@pytest.fixture
def test_output_dir(tmp_path):
    """Provide a temporary directory for test outputs"""
    output_dir = tmp_path / "test_output"
    output_dir.mkdir()
    return output_dir 