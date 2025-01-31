import pytest
import os
import sys
from pathlib import Path
import tempfile
import logging
from unittest.mock import Mock

# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.parent

# Add src directory to Python path
sys.path.insert(0, str(PROJECT_ROOT / "src"))

# Common fixtures can be added here
@pytest.fixture
def test_output_dir():
    """Create a temporary directory for test outputs"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir

@pytest.fixture
def setup_logging():
    """Set up logging for tests"""
    logging.basicConfig(level=logging.DEBUG)
    yield
    logging.getLogger().handlers = []

@pytest.fixture
def mock_wikipedia(monkeypatch):
    """Mock the wikipedia module"""
    mock_page = Mock()
    mock_page.title = "Test Page"
    mock_page.url = "https://en.wikipedia.org/wiki/Test_Page"
    mock_page.html = lambda: "<div>Test content</div>"
    
    monkeypatch.setattr('wikipedia.page', lambda *args, **kwargs: mock_page)
    return mock_page

@pytest.fixture
def no_cover():
    """Disable coverage for a test"""
    pytest.skip("Test not covered") 