import pytest
from click.testing import CliRunner
from wikipedia2md.cli import main, ColoredFormatter
from unittest.mock import patch, Mock
import logging
import os
import click

@pytest.fixture
def runner():
    """Create a Click test runner that preserves color output"""
    return CliRunner(mix_stderr=False, env={"FORCE_COLOR": "1"})

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

def test_logging_setup_comprehensive(runner, caplog):
    """Test comprehensive logging setup and configuration"""
    caplog.set_level(logging.DEBUG)
    
    # Test verbose mode with debug level
    with runner.isolated_filesystem(), \
         patch('wikipedia2md.cli.wikipedia') as mock_wiki:
        mock_page = Mock()
        mock_page.html.return_value = "<div>content</div>"
        mock_page.title = "Test"
        mock_wiki.page.return_value = mock_page
        
        result = runner.invoke(main, ["Title", "--verbose", "--loglevel", "DEBUG"])
        assert result.exit_code == 0
        assert "Debug mode enabled" in result.stdout

    # Test different log levels
    log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    for level in log_levels:
        with runner.isolated_filesystem(), \
             patch('wikipedia2md.cli.wikipedia') as mock_wiki:
            mock_page = Mock()
            mock_page.html.return_value = "<div>content</div>"
            mock_page.title = "Test"
            mock_wiki.page.return_value = mock_page
            
            result = runner.invoke(main, ["Title", "--loglevel", level])
            assert result.exit_code == 0

def test_colored_formatter():
    """Test ColoredFormatter functionality"""
    formatter = ColoredFormatter()
    
    # Test initialization
    assert formatter.COLORS['DEBUG'] == '\033[36m'  # Cyan
    assert formatter.COLORS['INFO'] == '\033[32m'   # Green
    assert formatter.COLORS['ERROR'] == '\033[31m'  # Red
    
    # Test color detection
    os.environ['FORCE_COLOR'] = '1'
    assert formatter.should_use_colors() is True
    
    os.environ['FORCE_COLOR'] = '0'
    assert formatter.should_use_colors() is False
    
    # Test formatting with colors
    record = logging.LogRecord(
        name='test', level=logging.ERROR,
        pathname='test.py', lineno=1,
        msg='Test error message', args=(),
        exc_info=None
    )
    
    os.environ['FORCE_COLOR'] = '1'
    formatted = formatter.format(record)
    assert '\033[31m' in formatted  # Red color for error
    assert '\033[0m' in formatted   # Reset color

def test_colored_formatter_no_click_context(monkeypatch):
    """Test ColoredFormatter when no Click context is available"""
    formatter = ColoredFormatter()
    
    def mock_get_context():
        raise RuntimeError("No context found")
    
    monkeypatch.setattr('click.get_current_context', mock_get_context)
    monkeypatch.delenv('FORCE_COLOR', raising=False)
    assert not formatter.should_use_colors()

def test_colored_formatter_force_color(monkeypatch):
    """Test ColoredFormatter when FORCE_COLOR is set"""
    formatter = ColoredFormatter()
    monkeypatch.setenv('FORCE_COLOR', '1')
    assert formatter.should_use_colors()

def test_colored_formatter_error_message(monkeypatch):
    """Test ColoredFormatter with error messages"""
    formatter = ColoredFormatter()
    monkeypatch.setenv('FORCE_COLOR', '1')
    
    record = logging.LogRecord(
        name='test', level=logging.ERROR,
        pathname='test.py', lineno=1,
        msg='Test error message', args=(),
        exc_info=None
    )
    
    result = formatter.format(record)
    assert '\033[31m' in result  # Red color for error
    assert '\033[0m' in result   # Reset color

def test_logging_edge_cases(runner, caplog):
    """Test edge cases in logging"""
    caplog.set_level(logging.DEBUG)

    # Test debug logging with empty content
    with runner.isolated_filesystem(), \
         patch('wikipedia2md.cli.wikipedia') as mock_wiki:
        mock_page = Mock()
        mock_page.title = "Test Article"
        mock_page.html.return_value = "<div class='mw-parser-output'></div>"
        mock_wiki.page.return_value = mock_page

        result = runner.invoke(main, ["Test Article", "--verbose", "--loglevel", "DEBUG"])
        assert result.exit_code == 0
        assert "Debug mode enabled" in result.stdout
        assert "Skipping element <div>" in result.stdout

def test_logging_with_empty_debug_message(caplog):
    """Test logging with empty debug message"""
    caplog.set_level(logging.DEBUG)
    logger = logging.getLogger()
    formatter = ColoredFormatter()
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    # Test logging empty message
    logger.debug("")
    assert "DEBUG" in caplog.text

def test_image_logging(runner, caplog):
    """Test logging of image processing"""
    caplog.set_level(logging.DEBUG)
    
    # Set up logging handler
    logger = logging.getLogger()
    formatter = ColoredFormatter()
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    with runner.isolated_filesystem(), \
         patch('wikipedia2md.cli.wikipedia') as mock_wiki:
        mock_page = Mock()
        mock_page.title = "Test Article"
        # Add list items before the image
        mock_page.html.return_value = """
        <div class="mw-parser-output">
            <ul>
                <li>List item 1</li>
                <li>List item 2</li>
            </ul>
            <img alt="Test image" src="//test.com/image.jpg">
        </div>
        """
        mock_wiki.page.return_value = mock_page
        
        result = runner.invoke(main, ["Test Article", "--verbose", "--loglevel", "DEBUG"])
        assert result.exit_code == 0
        
        # Check both caplog and result output for the messages
        log_message = "Added image: ![Test image](https://test.com/image.jpg)"
        assert any(log_message in record.message for record in caplog.records) or log_message in result.stdout
        
        # Verify list items appear before image in output
        content = open("Test Article.md").read()
        list_pos = content.find("- List item")
        image_pos = content.find("![Test image]")
        assert list_pos < image_pos, "List items should appear before the image"

def test_logging_color_from_click_context():
    """Test that logging respects Click's context color setting"""
    # Ensure we start with a clean environment
    with patch.dict(os.environ, {'FORCE_COLOR': '0'}, clear=True):
        formatter = ColoredFormatter()
        
        # Test with explicit color setting in Click context
        ctx = click.Context(click.Command('test'))
        ctx.color = False
        with ctx:
            assert not formatter.should_use_colors()
        
        # Test with color enabled
        ctx.color = True
        with ctx:
            assert formatter.should_use_colors()
        
        # Test with no Click context
        with patch('click.get_current_context', side_effect=RuntimeError):
            assert not formatter.should_use_colors()