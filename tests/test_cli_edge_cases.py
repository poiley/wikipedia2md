import pytest
import click
from unittest.mock import Mock, patch
from bs4 import BeautifulSoup
from wikipedia.exceptions import HTTPTimeoutError, PageError, DisambiguationError
from wikipedia2md.cli import make_markdown_from_page, fetch_wiki_page, WikiPageNotFoundError, Colors

def test_image_handling_edge_cases():
    """Test various edge cases in image handling"""
    # Create a mock page
    mock_page = Mock()
    mock_page.title = "Test Page"
    mock_page.categories = []
    
    # Test relative URL handling
    html = '''
    <div>
        <img src="/path/to/image.jpg" alt="Test Image">
        <img src="//example.com/image.jpg" alt="">
        <p>Text with <img src="/another/image.jpg"> inline</p>
    </div>
    '''
    mock_page.html = lambda: html
    
    result = make_markdown_from_page(mock_page)
    assert "![Test Image](https://en.wikipedia.org/path/to/image.jpg)" in result
    assert "![Image](https://example.com/image.jpg)" in result
    assert "![Image](https://en.wikipedia.org/another/image.jpg)" in result

def test_paragraph_text_processing():
    """Test complex paragraph text processing scenarios"""
    mock_page = Mock()
    mock_page.title = "Test Page"
    mock_page.categories = []
    
    # Test whitespace handling and mixed content
    html = '''
    <div>
        <p>Text with <a href="/wiki/Link">link</a> and <img src="/img.jpg"> and more text.</p>
        <p>Multiple     spaces   and
            newlines</p>
    </div>
    '''
    mock_page.html = lambda: html
    
    result = make_markdown_from_page(mock_page)
    assert "Text with [link](https://en.wikipedia.org/wiki/Link) and ![Image](https://en.wikipedia.org/img.jpg) and more text." in result
    assert "Multiple spaces and newlines" in result

def test_list_handling_with_references():
    """Test list handling with reference numbers and mixed content"""
    mock_page = Mock()
    mock_page.title = "Test Page"
    mock_page.categories = []
    
    html = '''
    <div>
        <ul>
            <li>Item 1<sup>[1]</sup></li>
            <li>Item 2 with <a href="/wiki/Link">link</a><sup>[2]</sup></li>
        </ul>
    </div>
    '''
    mock_page.html = lambda: html
    
    result = make_markdown_from_page(mock_page)
    assert "- Item 1" in result
    assert "- Item 2 with [link](https://en.wikipedia.org/wiki/Link)" in result
    assert "[1]" not in result
    assert "[2]" not in result

def test_invalid_url_handling():
    """Test handling of invalid Wikipedia URLs"""
    with pytest.raises(click.ClickException, match="Invalid Wikipedia URL"):
        fetch_wiki_page("https://en.wikipedia.org/invalid-path")

def test_language_handling():
    """Test handling of different language codes"""
    with patch('wikipedia.search') as mock_search:
        mock_search.return_value = ["Test Page"]
        with pytest.raises(ValueError, match="Invalid language code"):
            fetch_wiki_page("test query", lang="invalid")

def test_navigation_and_toc_skipping():
    """Test skipping of navigation and table of contents elements"""
    mock_page = Mock()
    mock_page.title = "Test Page"
    mock_page.categories = []
    
    html = '''
    <div>
        <div role="navigation">Skip this</div>
        <div class="toc">Skip this too</div>
        <div class="navigation-box">And this</div>
        <p>Keep this content</p>
    </div>
    '''
    mock_page.html = lambda: html
    
    result = make_markdown_from_page(mock_page)
    assert "Skip this" not in result
    assert "Skip this too" not in result
    assert "And this" not in result
    assert "Keep this content" in result

def test_complex_infobox_processing():
    """Test processing of complex infobox with various data types"""
    mock_page = Mock()
    mock_page.title = "Test Page"
    mock_page.categories = []
    
    html = '''
    <table class="infobox">
        <tr><th class="infobox-label">Mixed</th><td class="infobox-data">
            Text with <a href="/wiki/Link">link</a> and <img src="/img.jpg">
        </td></tr>
        <tr><td class="infobox-image" colspan="2"><img src="/image.jpg"></td></tr>
        <tr><th class="infobox-above">Title</th></tr>
    </table>
    '''
    mock_page.html = lambda: html
    
    result = make_markdown_from_page(mock_page)
    assert "| Attribute | Value |" in result
    assert "| Mixed | Text with, link, and, ![Image](/img.jpg) |" in result
    assert "![Image](/image.jpg)" in result

def test_http_timeout_handling():
    """Test handling of HTTP timeout errors"""
    with patch('wikipedia.page') as mock_page:
        mock_page.side_effect = HTTPTimeoutError("Connection timed out")
        with pytest.raises(click.ClickException, match="Connection timed out"):
            fetch_wiki_page("test query")

def test_disambiguation_handling():
    """Test handling of disambiguation pages"""
    with patch('wikipedia.page') as mock_page, \
         patch('wikipedia.search') as mock_search, \
         patch('click.prompt') as mock_prompt:
        
        mock_page.side_effect = [
            DisambiguationError("Page", ["Option 1", "Option 2"]),  # First call fails
            Mock(title="Selected Page", url="http://example.com")   # Second call succeeds
        ]
        mock_search.return_value = ["Option 1", "Option 2"]
        mock_prompt.return_value = "1"
        
        result = fetch_wiki_page("ambiguous query")
        assert result.title == "Selected Page"

def test_no_selection_handling():
    """Test handling when no selection is made for disambiguation"""
    with patch('wikipedia.page') as mock_page, \
         patch('wikipedia.search') as mock_search, \
         patch('click.prompt') as mock_prompt:
        
        mock_page.side_effect = DisambiguationError("Page", ["Option 1", "Option 2"])
        mock_search.return_value = ["Option 1", "Option 2"]
        mock_prompt.return_value = ""
        
        with pytest.raises(WikiPageNotFoundError, match="No valid choice provided"):
            fetch_wiki_page("ambiguous query")

def test_section_skipping():
    """Test skipping of forbidden sections"""
    mock_page = Mock()
    mock_page.title = "Test Page"
    mock_page.categories = []
    
    html = '''
    <div>
        <h2>Introduction</h2>
        <p>Keep this content</p>
        <h2>See Also</h2>
        <p>Skip this content</p>
        <h3>Subsection</h3>
        <p>Skip this too</p>
        <h2>Conclusion</h2>
        <p>Keep this content too</p>
    </div>
    '''
    mock_page.html = lambda: html
    
    result = make_markdown_from_page(mock_page)
    assert "## Introduction" in result
    assert "Keep this content" in result
    assert "Skip this content" not in result
    assert "Skip this too" not in result
    assert "## Conclusion" in result
    assert "Keep this content too" in result

def test_infobox_data_processing():
    """Test complex infobox data processing with various edge cases"""
    mock_page = Mock()
    mock_page.title = "Test Page"
    mock_page.categories = []
    
    html = '''
    <table class="infobox">
        <tr><th class="infobox-label">Complex</th><td class="infobox-data">
            <a href="/wiki/Link1">Link1</a>, <a href="/wiki/Link2">Link2</a>
            <img src="/img1.jpg" alt="Alt1">
            <img src="/img2.jpg" alt="Alt2">
            Text in between
        </td></tr>
        <tr><th class="infobox-label">Empty</th><td class="infobox-data"></td></tr>
        <tr><th class="infobox-label">Whitespace</th><td class="infobox-data">  </td></tr>
    </table>
    '''
    mock_page.html = lambda: html
    
    result = make_markdown_from_page(mock_page)
    assert "| Complex | Link1, Link2, ![Alt1](/img1.jpg), ![Alt2](/img2.jpg), Text in between |" in result

def test_text_processing_edge_cases():
    """Test text processing with various whitespace and formatting cases"""
    mock_page = Mock()
    mock_page.title = "Test Page"
    mock_page.categories = []
    
    html = '''
    <div>
        <p>Text with
            multiple
            newlines and    spaces</p>
        <p>Text with <sup>[1]</sup> reference and <a href="/wiki/Link">link</a>
            and more text</p>
        <p>Text with <img src="/img.jpg" alt="Alt"> image</p>
    </div>
    '''
    mock_page.html = lambda: html
    
    result = make_markdown_from_page(mock_page)
    assert "Text with multiple newlines and spaces" in result
    assert "Text with reference and [link](https://en.wikipedia.org/wiki/Link) and more text" in result
    assert "Text with ![Alt](https://en.wikipedia.org/img.jpg) image" in result

def test_list_processing_edge_cases():
    """Test list processing with various types of content"""
    mock_page = Mock()
    mock_page.title = "Test Page"
    mock_page.categories = []
    
    html = '''
    <div>
        <ul>
            <li>Simple item</li>
            <li>Item with <a href="/wiki/Link">link</a></li>
            <li>Item with <img src="/img.jpg" alt="Alt"></li>
            <li>Item with <sup>[1]</sup> reference</li>
            <li>   Item with whitespace   </li>
        </ul>
    </div>
    '''
    mock_page.html = lambda: html
    
    result = make_markdown_from_page(mock_page)
    assert "- Simple item" in result
    assert "- Item with [link](https://en.wikipedia.org/wiki/Link)" in result
    assert "![Alt](https://en.wikipedia.org/img.jpg)" in result
    assert "- Item with" in result
    assert "- Item with reference" in result
    assert "- Item with whitespace" in result

def test_heading_processing_edge_cases():
    """Test heading processing with various content types"""
    mock_page = Mock()
    mock_page.title = "Test Page"
    mock_page.categories = []
    
    html = '''
    <div>
        <h1>Top level heading</h1>
        <h2>Second level with <a href="/wiki/Link">link</a></h2>
        <h3>Third level with <img src="/img.jpg" alt="Alt"></h3>
        <h4>Fourth level with <sup>[1]</sup></h4>
        <h5>Fifth level heading</h5>
        <h6>Sixth level heading</h6>
    </div>
    '''
    mock_page.html = lambda: html
    
    result = make_markdown_from_page(mock_page)
    assert "# Top level heading" in result
    assert "## Second level with [link](https://en.wikipedia.org/wiki/Link)" in result
    assert "![Alt](https://en.wikipedia.org/img.jpg)" in result
    assert "### Third level with" in result
    assert "#### Fourth level with" in result
    assert "##### Fifth level heading" in result
    assert "###### Sixth level heading" in result

def test_obsidian_frontmatter():
    """Test Obsidian frontmatter generation with categories"""
    mock_page = Mock()
    mock_page.title = "Test Page"
    mock_page.categories = [
        "Category:Test Category",
        "Category:Help:Skip This",
        "Category:Articles Skip This",
        "Category:Valid Category"
    ]
    mock_page.html = lambda: "<div></div>"
    
    result = make_markdown_from_page(mock_page, obsidian=True)
    assert "title: \"Test Page\"" in result
    assert "wikipedia_url: \"https://en.wikipedia.org/wiki/Test_Page\"" in result
    assert "  - \"test-category\"" in result
    assert "  - \"valid-category\"" in result
    assert "Help:Skip This" not in result
    assert "Articles Skip This" not in result

def test_error_handling_edge_cases():
    """Test various error handling scenarios"""
    with patch('wikipedia.page') as mock_page, \
         patch('wikipedia.search') as mock_search, \
         patch('click.prompt') as mock_prompt:
        
        # Test out of range choice
        mock_page.side_effect = DisambiguationError("Page", ["Option 1", "Option 2"])
        mock_search.return_value = ["Option 1", "Option 2"]
        mock_prompt.return_value = "3"
        
        with pytest.raises(WikiPageNotFoundError, match="Choice out of range"):
            fetch_wiki_page("ambiguous query")
        
        # Test no results found
        mock_search.return_value = []
        with pytest.raises(WikiPageNotFoundError, match="No matches found"):
            fetch_wiki_page("nonexistent query")

def test_logging_setup():
    """Test logging setup with different levels"""
    from wikipedia2md.cli import setup_logging, ColoredFormatter
    import logging
    
    # Reset logging configuration
    for handler in logging.getLogger().handlers[:]:
        logging.getLogger().removeHandler(handler)
    
    # Test debug level
    setup_logging(logging.DEBUG)
    logger = logging.getLogger()
    assert logger.level == logging.DEBUG
    
    # Test info level
    setup_logging(logging.INFO)
    assert logger.level == logging.INFO
    
    # Verify handler formatting
    handlers = [h for h in logger.handlers if isinstance(h, logging.StreamHandler)]
    assert len(handlers) > 0
    handler = handlers[0]
    assert isinstance(handler.formatter, ColoredFormatter)
    assert handler.formatter._fmt == "%(message)s"

def test_page_error_handling():
    """Test handling of PageError"""
    with patch('wikipedia.page') as mock_page:
        mock_page.side_effect = PageError("Test Page")
        with patch('wikipedia.search') as mock_search:
            mock_search.return_value = []
            with pytest.raises(WikiPageNotFoundError, match="No matches found"):
                fetch_wiki_page("nonexistent page")

def test_complex_dom_walking():
    """Test walking through complex DOM structures"""
    mock_page = Mock()
    mock_page.title = "Test Page"
    mock_page.categories = []
    
    html = '''
    <div>
        <div role="navigation">Skip this</div>
        <div class="toc">Skip this too</div>
        <h2>Section 1</h2>
        <p>Content 1</p>
        <div class="navigation-box">Skip this as well</div>
        <h2>References</h2>
        <p>Skip all of this</p>
        <h3>Subsection</h3>
        <p>Skip this too</p>
        <h2>Section 2</h2>
        <p>Content 2</p>
    </div>
    '''
    mock_page.html = lambda: html
    
    result = make_markdown_from_page(mock_page)
    assert "Skip this" not in result
    assert "Skip this too" not in result
    assert "Skip this as well" not in result
    assert "## Section 1" in result
    assert "Content 1" in result
    assert "References" not in result
    assert "Skip all of this" not in result
    assert "Subsection" not in result
    assert "## Section 2" in result
    assert "Content 2" in result 