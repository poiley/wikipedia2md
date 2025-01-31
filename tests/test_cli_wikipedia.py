import pytest
from click.testing import CliRunner
from wikipedia2md.cli import main, fetch_wiki_page, WikiPageNotFoundError, make_markdown_from_page
from unittest.mock import patch, Mock
import wikipedia
from wikipedia.exceptions import HTTPTimeoutError
import click

@pytest.fixture
def runner():
    """Create a Click test runner that preserves color output"""
    return CliRunner(mix_stderr=False, env={"FORCE_COLOR": "1"})

def test_fetch_wiki_page_with_url():
    """Test fetching a page using a Wikipedia URL"""
    with patch('wikipedia2md.cli.wikipedia') as mock_wiki:
        mock_page = Mock()
        mock_page.title = "Test Page"
        mock_page.url = "https://en.wikipedia.org/wiki/Test_Page"
        mock_wiki.page.return_value = mock_page
        
        # Test with different URL formats
        urls = [
            "http://wikipedia.org/wiki/Test_Page",
            "https://wikipedia.org/wiki/Test_Page",
            "http://www.wikipedia.org/wiki/Test_Page",
            "https://www.wikipedia.org/wiki/Test_Page",
            "http://en.wikipedia.org/wiki/Test_Page",
            "https://en.wikipedia.org/wiki/Test_Page"
        ]
        
        for url in urls:
            result = fetch_wiki_page(url)
            assert result == mock_page

def test_fetch_wiki_page_disambiguation():
    """Test handling of disambiguation pages"""
    with patch('wikipedia2md.cli.wikipedia') as mock_wiki:
        mock_page = Mock()
        mock_page.title = "Test Page"
        mock_page.url = "https://en.wikipedia.org/wiki/Test_Page"
        
        def mock_is_disambiguation():
            raise wikipedia.exceptions.DisambiguationError(mock_page.title, ["Option 1", "Option 2"])
        
        mock_page.is_disambiguation_page = mock_is_disambiguation
        mock_wiki.page.return_value = mock_page
        
        with patch('click.prompt', return_value="1"):
            result = fetch_wiki_page("Test Page")
            assert result == mock_page

def test_fetch_wiki_page_network_error():
    """Test handling of network errors during page fetching"""
    with patch('wikipedia2md.cli.wikipedia') as mock_wiki:
        mock_wiki.page.side_effect = HTTPTimeoutError("Connection timed out")
        mock_wiki.search.return_value = []  # No search results
        
        with pytest.raises(click.ClickException) as exc_info:
            fetch_wiki_page("Test Page")
        assert "Connection timed out" in str(exc_info.value)

def test_fetch_wiki_page_not_found():
    """Test handling of pages that don't exist"""
    with patch('wikipedia2md.cli.wikipedia') as mock_wiki:
        mock_wiki.page.side_effect = wikipedia.PageError("Page not found")
        mock_wiki.search.return_value = []  # No search results
        
        with pytest.raises(WikiPageNotFoundError) as exc_info:
            fetch_wiki_page("Nonexistent Page")
        assert "No matches found for 'Nonexistent Page'" in str(exc_info.value)

def test_make_markdown_from_page_empty_content(runner):
    """Test handling of pages with empty content sections"""
    with patch('wikipedia2md.cli.wikipedia') as mock_wiki:
        mock_page = Mock()
        mock_page.title = "Test Page"
        mock_page.url = "https://en.wikipedia.org/wiki/Test_Page"
        
        # Create HTML with empty sections
        html = """
        <div class="mw-parser-output">
            <h2>Empty Section</h2>
            <p></p>
            <h2>Another Empty Section</h2>
            <ul></ul>
        </div>
        """
        mock_page.html.return_value = html
        mock_wiki.page.return_value = mock_page
        
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["Test Page"])
            assert result.exit_code == 0
            content = open("Test Page.md").read()
            # Headers are still included even if content is empty
            assert "## Empty Section" in content
            assert "## Another Empty Section" in content
            # But there should be no additional content
            assert len(content.split('\n')) <= 5  # Title, blank line, and two section headers with blank lines

def test_make_markdown_from_page_forbidden_sections(runner):
    """Test handling of forbidden sections"""
    with patch('wikipedia2md.cli.wikipedia') as mock_wiki:
        mock_page = Mock()
        mock_page.title = "Test Page"
        mock_page.url = "https://en.wikipedia.org/wiki/Test_Page"
        
        html = """
        <div>
            <h2>Main Content</h2>
            <p>Some content</p>
            <h2>See Also</h2>
            <p>Should be skipped</p>
            <h2>References</h2>
            <p>Should be skipped</p>
        </div>
        """
        mock_page.html.return_value = html
        mock_wiki.page.return_value = mock_page
        
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["Test Page"])
            assert result.exit_code == 0
            content = open("Test Page.md").read()
            assert "Main Content" in content
            assert "Some content" in content
            assert "See Also" not in content
            assert "References" not in content
            assert "Should be skipped" not in content

def test_fetch_wiki_page_error_handling():
    """Test comprehensive error handling scenarios"""
    with patch('wikipedia2md.cli.wikipedia') as mock_wiki, \
         patch('wikipedia2md.cli.click.prompt') as mock_prompt:
        mock_wiki.DisambiguationError = wikipedia.exceptions.DisambiguationError
        mock_wiki.PageError = wikipedia.exceptions.PageError
        mock_wiki.HTTPTimeoutError = wikipedia.exceptions.HTTPTimeoutError
        
        # Test disambiguation error with user selecting first option
        mock_wiki.page.side_effect = [
            wikipedia.exceptions.DisambiguationError("Python", ["Python (programming)", "Python (snake)"]),
            Mock(title="Python (programming)", url="http://en.wikipedia.org/wiki/Python_(programming)")
        ]
        mock_wiki.search.return_value = ["Python (programming)", "Python (snake)"]
        mock_prompt.return_value = "1"
        
        page = fetch_wiki_page("Python")
        assert page.title == "Python (programming)"
        
        # Test disambiguation error with user canceling
        mock_wiki.page.side_effect = wikipedia.exceptions.DisambiguationError(
            "Python", ["Python (programming)", "Python (snake)"]
        )
        mock_prompt.return_value = ""
        
        with pytest.raises(WikiPageNotFoundError):
            fetch_wiki_page("Python")
        
        # Test page not found
        mock_wiki.page.side_effect = wikipedia.exceptions.PageError("NonexistentPage")
        mock_wiki.search.return_value = []
        
        with pytest.raises(WikiPageNotFoundError):
            fetch_wiki_page("NonexistentPage")
        
        # Test network error
        mock_wiki.page.side_effect = wikipedia.exceptions.HTTPTimeoutError("Timeout")
        
        with pytest.raises(Exception) as exc_info:
            fetch_wiki_page("AnyPage")
        assert "Timeout" in str(exc_info.value)

def test_fetch_wiki_page_disambiguation(monkeypatch):
    """Test handling of disambiguation pages"""
    mock_page = Mock()
    mock_page.title = "Test Page"
    mock_page.url = "https://en.wikipedia.org/wiki/Test_Page"
    
    def mock_page_func(*args, **kwargs):
        return mock_page
    
    def mock_is_disambiguation():
        raise wikipedia.exceptions.DisambiguationError(mock_page.title, ["Option 1", "Option 2"])
    
    mock_page.is_disambiguation_page = mock_is_disambiguation
    monkeypatch.setattr('wikipedia.page', mock_page_func)
    monkeypatch.setattr('click.prompt', lambda *args, **kwargs: "1")
    
    result = fetch_wiki_page("Test Page")
    assert result == mock_page

def test_fetch_wiki_page_network_error(monkeypatch):
    """Test handling of network errors during page fetching"""
    def mock_page(*args, **kwargs):
        raise wikipedia.exceptions.HTTPTimeoutError("Connection timed out")
    
    monkeypatch.setattr('wikipedia.page', mock_page)
    monkeypatch.setattr('wikipedia.search', lambda *args, **kwargs: [])  # No search results
    
    with pytest.raises(click.ClickException) as exc_info:
        fetch_wiki_page("Test Page")
    assert "Connection timed out" in str(exc_info.value)

def test_fetch_wiki_page_not_found(monkeypatch):
    """Test handling of pages that don't exist"""
    def mock_page(*args, **kwargs):
        raise wikipedia.exceptions.PageError("Page not found")
    
    monkeypatch.setattr('wikipedia.page', mock_page)
    monkeypatch.setattr('wikipedia.search', lambda *args, **kwargs: [])  # No search results
    
    with pytest.raises(WikiPageNotFoundError) as exc_info:
        fetch_wiki_page("Nonexistent Page")
    assert "No matches found for 'Nonexistent Page'" in str(exc_info.value)

def test_make_markdown_from_page_empty_content(monkeypatch):
    """Test handling of pages with empty content sections"""
    mock_page = Mock()
    mock_page.title = "Test Page"
    mock_page.url = "https://en.wikipedia.org/wiki/Test_Page"
    
    # Create HTML with empty sections
    html = """
    <div class="mw-parser-output">
        <h2>Empty Section</h2>
        <p></p>
        <h2>Another Empty Section</h2>
        <ul></ul>
    </div>
    """
    mock_page.html = lambda: html
    
    result = make_markdown_from_page(mock_page)
    # Headers are still included even if content is empty
    assert "## Empty Section" in result
    assert "## Another Empty Section" in result
    # But there should be no additional content
    assert len(result.split('\n')) <= 5  # Title, blank line, and two section headers with blank lines

def test_make_markdown_from_page_forbidden_sections(monkeypatch):
    """Test handling of forbidden sections"""
    html = """
    <div>
        <h2>Main Content</h2>
        <p>Some content</p>
        <h2>See Also</h2>
        <p>Should be skipped</p>
        <h2>References</h2>
        <p>Should be skipped</p>
    </div>
    """
    mock_page = Mock()
    mock_page.title = "Test Page"
    mock_page.url = "https://en.wikipedia.org/wiki/Test_Page"
    mock_page.html = lambda: html
    
    result = make_markdown_from_page(mock_page)
    assert "Main Content" in result
    assert "Some content" in result
    assert "See Also" not in result
    assert "References" not in result
    assert "Should be skipped" not in result

def test_fetch_wiki_page_invalid_language(monkeypatch):
    """Test fetching a page with an invalid language code"""
    with pytest.raises(ValueError) as exc_info:
        fetch_wiki_page("Test Page", lang="invalid")
    assert "Invalid language code: invalid" in str(exc_info.value)

def test_fetch_wiki_page_url_network_error(monkeypatch):
    """Test handling network errors when fetching by URL"""
    def mock_page(*args, **kwargs):
        raise wikipedia.exceptions.HTTPTimeoutError("Connection timed out")
    
    monkeypatch.setattr('wikipedia.page', mock_page)
    
    with pytest.raises(click.ClickException) as exc_info:
        fetch_wiki_page("https://en.wikipedia.org/wiki/Test_Page")
    assert "Connection timed out" in str(exc_info.value) 