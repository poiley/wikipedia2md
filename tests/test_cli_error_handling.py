import pytest
from click.testing import CliRunner
from wikipedia2md.cli import main, fetch_wiki_page, WikiPageNotFoundError
from unittest.mock import patch, Mock
import wikipedia
from wikipedia.exceptions import HTTPTimeoutError
import click

@pytest.fixture
def runner():
    """Create a Click test runner that preserves color output"""
    return CliRunner(mix_stderr=False, env={"FORCE_COLOR": "1"})

def test_cli_invalid_article(runner):
    """Test CLI with invalid article name"""
    with patch('wikipedia2md.cli.wikipedia') as mock_wiki:
        mock_wiki.page.side_effect = wikipedia.PageError("Page does not exist")
        mock_wiki.search.return_value = []
        result = runner.invoke(main, ["NonexistentArticle123"])
        assert result.exit_code == 1
        assert "Error: No matches found for 'NonexistentArticle123'" in result.stderr

def test_cli_disambiguation(runner):
    """Test handling of disambiguation pages"""
    with patch('wikipedia2md.cli.wikipedia') as mock_wiki:
        mock_page = Mock()
        mock_page.title = "Python (programming)"
        mock_page.html.return_value = "<div>content</div>"
        mock_wiki.page.side_effect = [
            wikipedia.DisambiguationError("Python", ["Python (programming)", "Python (snake)"]),
            mock_page
        ]
        mock_wiki.search.return_value = ["Python (programming)", "Python (snake)"]
        
        result = runner.invoke(main, ["Python"], input="1\n")
        assert result.exit_code == 0
        assert "Multiple matches found" in result.output

def test_cli_url_handling(runner):
    """Test URL handling in CLI"""
    # Test with invalid URL (missing /wiki/ path)
    result = runner.invoke(main, ["--url", "https://wikipedia.org/Test"])
    assert result.exit_code == 1
    assert "Invalid Wikipedia URL" in result.stderr

    # Test with valid URL
    with patch('wikipedia2md.cli.wikipedia') as mock_wiki:
        mock_page = Mock()
        mock_page.title = "Test"
        mock_page.url = "https://wikipedia.org/wiki/Test"
        mock_page.html.return_value = "<div>Test content</div>"
        mock_wiki.page.return_value = mock_page
        
        result = runner.invoke(main, ["--url", "https://wikipedia.org/wiki/Test"])
        assert result.exit_code == 0

def test_cli_invalid_options(runner):
    """Test CLI with invalid option combinations"""
    # Test missing required arguments
    result = runner.invoke(main)
    assert result.exit_code == 1
    assert "Error: Either TITLE or --url must be provided" in result.stderr

    # Test conflicting arguments
    result = runner.invoke(main, ["Title", "--url", "http://example.com"])
    assert result.exit_code == 1
    assert "Error: Cannot specify both TITLE and --url" in result.stderr

    # Test invalid log level
    result = runner.invoke(main, ["Title", "--loglevel", "INVALID"])
    assert result.exit_code == 1
    assert "Error: Invalid log level: INVALID" in result.stderr

def test_fetch_wiki_page_errors():
    """Test error handling in fetch_wiki_page function"""
    with patch('wikipedia2md.cli.wikipedia') as mock_wiki:
        mock_wiki.DisambiguationError = wikipedia.DisambiguationError
        mock_wiki.PageError = wikipedia.PageError
        mock_wiki.HTTPTimeoutError = HTTPTimeoutError

        # Test page not found
        mock_wiki.page.side_effect = wikipedia.PageError("NonexistentPage")
        mock_wiki.search.return_value = []
        with pytest.raises(WikiPageNotFoundError):
            fetch_wiki_page("NonexistentPage")

        # Test network error
        mock_wiki.page.side_effect = HTTPTimeoutError("Connection timed out")
        with pytest.raises(click.ClickException) as exc_info:
            fetch_wiki_page("Test Page")
        assert "Connection timed out" in str(exc_info.value)

def test_fetch_wiki_page_invalid_language():
    """Test fetching a page with an invalid language code"""
    with pytest.raises(ValueError) as exc_info:
        fetch_wiki_page("Test Page", lang="invalid")
    assert "Invalid language code: invalid" in str(exc_info.value)

def test_fetch_wiki_page_url_network_error():
    """Test handling network errors when fetching by URL"""
    with patch('wikipedia2md.cli.wikipedia') as mock_wiki:
        mock_wiki.page.side_effect = HTTPTimeoutError("Connection timed out")
        with pytest.raises(click.ClickException) as exc_info:
            fetch_wiki_page("https://en.wikipedia.org/wiki/Test_Page")
        assert "Connection timed out" in str(exc_info.value)

def test_error_handling_comprehensive(runner):
    """Test comprehensive error handling scenarios"""
    # Test CLI errors
    result = runner.invoke(main)
    assert result.exit_code == 1
    assert "Error: Either TITLE or --url must be provided" in result.stderr

    result = runner.invoke(main, ["Title", "--url", "http://example.com"])
    assert result.exit_code == 1
    assert "Error: Cannot specify both TITLE and --url" in result.stderr

    result = runner.invoke(main, ["Title", "--loglevel", "INVALID"])
    assert result.exit_code == 1
    assert "Error: Invalid log level: INVALID" in result.stderr

def test_error_handling_wikipedia_errors(runner):
    """Test handling of Wikipedia API errors"""
    with patch('wikipedia2md.cli.wikipedia') as mock_wiki:
        mock_wiki.DisambiguationError = wikipedia.DisambiguationError
        mock_wiki.PageError = wikipedia.PageError
        
        # Test page not found
        mock_wiki.page.side_effect = wikipedia.PageError("Page does not exist")
        mock_wiki.search.return_value = []
        result = runner.invoke(main, ["NonexistentArticle123"])
        assert result.exit_code == 1
        assert "Error: No matches found for 'NonexistentArticle123'" in result.stderr
        
        # Test disambiguation page
        mock_wiki.page.side_effect = wikipedia.DisambiguationError(
            "Python", ["Python (programming)", "Python (snake)"]
        )
        mock_wiki.search.return_value = ["Python (programming)", "Python (snake)"]
        result = runner.invoke(main, ["Python"], input="")  # User cancels selection
        assert result.exit_code == 1
        assert "Error: No valid choice provided" in result.stderr

def test_error_handling_invalid_url(runner):
    """Test handling of invalid URLs"""
    result = runner.invoke(main, ["--url", "https://wikipedia.org/Test"])  # Missing /wiki/
    assert result.exit_code == 1
    assert "Invalid Wikipedia URL" in result.stderr

    result = runner.invoke(main, ["--url", "https://example.com/wiki/Test"])  # Wrong domain
    assert result.exit_code == 1
    assert "Error: Page id" in result.stderr

def test_error_handling_file_operations(runner, tmp_path):
    """Test handling of file operation errors"""
    with patch('wikipedia2md.cli.wikipedia') as mock_wiki:
        mock_page = Mock()
        mock_page.html.return_value = "<div>content</div>"
        mock_page.title = "Test"
        mock_wiki.page.return_value = mock_page
        
        # Test with read-only directory
        readonly_dir = tmp_path / "readonly"
        readonly_dir.mkdir()
        import os
        os.chmod(str(readonly_dir), 0o444)  # Make directory read-only
        
        result = runner.invoke(main, ["Title", "--output-dir", str(readonly_dir)])
        assert result.exit_code == 1
        assert "Permission denied" in result.stderr 