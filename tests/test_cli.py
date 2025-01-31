import pytest
from click.testing import CliRunner
from wikipedia2md.cli import main
from unittest.mock import patch, Mock
import logging
import os
import wikipedia

@pytest.fixture
def runner():
    """Create a Click test runner that preserves color output"""
    return CliRunner(mix_stderr=False, env={"FORCE_COLOR": "1"})

@pytest.fixture
def mock_wikipedia():
    with patch('wikipedia2md.cli.wikipedia') as mock_wiki:
        mock_page = Mock()
        mock_page.html.return_value = """<div class="mw-parser-output"><p>Python is a programming language.</p></div>"""
        mock_page.title = "Python (programming language)"
        mock_wiki.page.return_value = mock_page
        mock_wiki.PageError = wikipedia.PageError
        mock_wiki.DisambiguationError = wikipedia.DisambiguationError
        yield mock_wiki

@pytest.fixture(autouse=True)
def setup_logging():
    """Reset logging before each test"""
    # Store existing handlers
    root = logging.getLogger()
    old_handlers = root.handlers[:]
    old_level = root.level
    old_env = os.environ.get('FORCE_COLOR')
    
    # Clear handlers but don't change level
    root.handlers = []
    
    # Force color output for tests
    os.environ['FORCE_COLOR'] = '1'
    
    # Let the test run
    yield
    
    # Restore original state
    root.handlers = old_handlers
    root.level = old_level
    if old_env is None:
        del os.environ['FORCE_COLOR']
    else:
        os.environ['FORCE_COLOR'] = old_env

def test_basic_cli_functionality(runner, mock_wikipedia):
    """Test basic CLI functionality"""
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["Python (programming language)"])
        assert result.exit_code == 0
        content = open("Python (programming language).md").read()
        assert "Python is a programming language" in content 