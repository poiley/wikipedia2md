import pytest
from wikipedia2md.cli import fetch_wiki_page, make_markdown_from_page
from bs4 import BeautifulSoup
import os
from unittest.mock import Mock, patch

class MockWikiPage:
    def __init__(self, html_content, title="Test Page"):
        self._html = html_content
        self.title = title
        
    def html(self):
        return self._html

@pytest.fixture
def sample_wiki_html():
    return """
    <div class="mw-parser-output">
        <p>This is a test paragraph.</p>
        <h2>Test Section</h2>
        <p>Another paragraph with <a href="/wiki/Test">links</a>.</p>
        <table class="infobox">
            <tbody>
                <tr><th class="infobox-label">Title</th><td class="infobox-data">Value</td></tr>
                <tr><th class="infobox-label">Another</th><td class="infobox-data">Data</td></tr>
            </tbody>
        </table>
    </div>
    """

@pytest.fixture
def sample_page(sample_wiki_html):
    return MockWikiPage(
        html_content=sample_wiki_html,
        title="Test Article"
    )

@pytest.fixture
def mock_wikipedia():
    with patch('wikipedia2md.cli.wikipedia') as mock_wiki:
        mock_page = Mock()
        mock_page.html.return_value = """<div class="mw-parser-output"><p>Python is a programming language.</p></div>"""
        mock_page.title = "Python (programming language)"
        mock_wiki.page.return_value = mock_page
        yield mock_wiki

def test_fetch_wiki_page(mock_wikipedia):
    """Test fetching a known Wikipedia page"""
    page = fetch_wiki_page("Python (programming language)")
    assert page is not None
    mock_wikipedia.page.assert_called_once_with("Python (programming language)", auto_suggest=False)

def test_fetch_nonexistent_page(mock_wikipedia):
    """Test fetching a non-existent page"""
    mock_wikipedia.page.side_effect = Exception("Page does not exist")
    mock_wikipedia.search.return_value = []
    with pytest.raises(Exception):
        fetch_wiki_page("ThisPageDefinitelyDoesNotExist12345")

def test_make_markdown_basic(sample_page):
    """Test basic markdown conversion"""
    markdown = make_markdown_from_page(sample_page)
    assert "This is a test paragraph." in markdown
    assert "## Test Section" in markdown
    assert "[links]" in markdown
    assert "Test Article" in markdown  # Verify title is included

def test_make_markdown_with_infobox(sample_page):
    """Test markdown conversion with infobox"""
    markdown = make_markdown_from_page(sample_page)
    assert "| Title | Value |" in markdown
    assert "| Another | Data |" in markdown

@pytest.mark.parametrize("options", [
    {"obsidian": True},
    {"no_links": True},
    {"obsidian": True, "no_links": True}
])
def test_make_markdown_with_options(sample_page, options):
    """Test markdown conversion with different options"""
    markdown = make_markdown_from_page(sample_page, **options)
    if options.get("obsidian"):
        assert "---" in markdown  # Check for YAML frontmatter
        assert 'title: "Test Article"' in markdown  # Check title in frontmatter with quotes
    if options.get("no_links"):
        assert "[links]" not in markdown 