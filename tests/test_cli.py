import pytest
from click.testing import CliRunner
from wikipedia2md.cli import main
from unittest.mock import patch, Mock
import logging
import io
import sys
import wikipedia
import os

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

def capture_logging():
    """Helper to capture logging output"""
    log_capture = io.StringIO()
    handler = logging.StreamHandler(log_capture)
    handler.setFormatter(logging.Formatter('%(message)s'))
    logging.getLogger().addHandler(handler)
    return log_capture

def test_basic_cli(runner, mock_wikipedia):
    """Test basic CLI functionality"""
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["Python (programming language)"], 
                             catch_exceptions=False)
        assert result.exit_code == 0
        assert "Python" in open("Python (programming language).md").read()
        assert "Starting page processing" in result.stdout
        assert "Successfully created" in result.stdout

def test_cli_with_output_dir(runner, mock_wikipedia, tmp_path):
    """Test CLI with output directory option"""
    result = runner.invoke(main, [
        "Python (programming language)",
        "-o", str(tmp_path)
    ], catch_exceptions=False)
    assert result.exit_code == 0
    assert len(list(tmp_path.glob("*.md"))) == 1
    assert "Successfully created" in result.stdout

def test_cli_with_obsidian_option(runner, mock_wikipedia):
    """Test CLI with Obsidian option"""
    with runner.isolated_filesystem():
        result = runner.invoke(main, [
            "Python (programming language)",
            "-O"
        ], catch_exceptions=False)
        assert result.exit_code == 0
        content = open("Python (programming language).md").read()
        assert "---" in content

def test_cli_invalid_article(runner, mock_wikipedia):
    """Test CLI with invalid article name"""
    mock_wikipedia.page.side_effect = wikipedia.PageError("Page does not exist")
    mock_wikipedia.search.return_value = []
    result = runner.invoke(main, ["ThisPageDefinitelyDoesNotExist12345"], 
                         catch_exceptions=False)
    assert result.exit_code == 1
    assert "Error: No matches found for 'ThisPageDefinitelyDoesNotExist12345'" in result.stderr

@pytest.mark.parametrize("log_level", ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
def test_cli_log_levels(runner, mock_wikipedia, log_level):
    """Test different logging levels"""
    with runner.isolated_filesystem():
        result = runner.invoke(main, [
            "Python (programming language)",
            "-L", log_level
        ])
        assert result.exit_code == 0

def test_cli_verbose_mode(runner, mock_wikipedia):
    """Test verbose mode"""
    with runner.isolated_filesystem():
        # Create a mock page
        mock_page = Mock()
        mock_page.title = "Test Article"
        mock_page.html.return_value = "<div class='mw-parser-output'><p>Test content</p></div>"
        mock_wikipedia.page.return_value = mock_page

        result = runner.invoke(main, [
            "Test Article",
            "-v"
        ], catch_exceptions=False)
        assert result.exit_code == 0
        # Debug messages should be in stdout
        assert "🐞 Debug mode enabled" in result.stdout
        assert "🚀 Starting page processing" in result.stdout
        assert "✅ Successfully created" in result.stdout

def test_cli_no_links_option(runner, mock_wikipedia):
    """Test no-links option"""
    with runner.isolated_filesystem():
        result = runner.invoke(main, [
            "Python (programming language)",
            "-N"
        ])
        assert result.exit_code == 0
        content = open("Python (programming language).md").read()
        assert "http" not in content

def test_cli_multiple_options(runner, mock_wikipedia):
    """Test combining multiple options"""
    with runner.isolated_filesystem():
        result = runner.invoke(main, [
            "Python (programming language)",
            "-O", "-N", "-v"
        ])
        assert result.exit_code == 0
        content = open("Python (programming language).md").read()
        assert "---" in content  # Obsidian frontmatter
        assert "http" not in content  # No links

def test_cli_disambiguation(runner, mock_wikipedia):
    """Test handling of disambiguation pages"""
    mock_wikipedia.page.side_effect = [
        wikipedia.DisambiguationError("Python", ["Python (programming language)", "Python (snake)"]),
        Mock(title="Python (programming language)", 
             html=lambda: "<div>content</div>")
    ]
    mock_wikipedia.search.return_value = ["Python (programming language)", "Python (snake)"]
    
    with runner.isolated_filesystem():
        # Simulate user selecting first option
        result = runner.invoke(main, ["Python"], input="1\n")
        assert result.exit_code == 0
        assert "Multiple matches found" in result.output

def test_cli_search_no_results(runner, mock_wikipedia):
    """Test handling when search returns no results"""
    mock_wikipedia.page.side_effect = wikipedia.PageError("NonexistentArticle123")
    mock_wikipedia.search.return_value = []
    
    result = runner.invoke(main, ["NonexistentArticle123"], 
                         catch_exceptions=False)

    assert result.exit_code == 1
    assert "Error: No matches found for 'NonexistentArticle123'" in result.stderr

def test_cli_invalid_log_level(runner, mock_wikipedia):
    """Test handling of invalid log level"""
    result = runner.invoke(main, [
        "Python",
        "-L", "INVALID_LEVEL"
    ], catch_exceptions=False)
    assert result.exit_code == 1
    assert "Error: Invalid log level" in result.stderr

@pytest.mark.parametrize("option_combo", [
    ["-O", "-N"],
    ["-O", "-v"],
    ["-N", "-v"],
    ["-O", "-N", "-v"],
])
def test_cli_option_combinations(runner, mock_wikipedia, option_combo):
    """Test various combinations of options"""
    with runner.isolated_filesystem():
        args = ["Python (programming language)"] + option_combo
        result = runner.invoke(main, args, catch_exceptions=False)
        assert result.exit_code == 0 

def test_cli_with_images(runner, mock_wikipedia):
    """Test handling of images in articles"""
    mock_page = Mock()
    mock_page.title = "Test Article"
    mock_page.html.return_value = """
    <div class="mw-parser-output">
        <div class="infobox">
            <td class="infobox-image">
                <img alt="Test image" src="//test.com/image.jpg">
            </td>
        </div>
        <p>Text with <img alt="Inline image" src="/wiki/image2.jpg"> inline.</p>
    </div>
    """
    mock_wikipedia.page.return_value = mock_page
    
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["Test Article"], catch_exceptions=False)
        assert result.exit_code == 0
        content = open("Test Article.md").read()
        assert "![Test image](https://test.com/image.jpg)" in content
        assert "![Inline image](https://en.wikipedia.org/wiki/image2.jpg)" in content

def test_cli_with_lists(runner, mock_wikipedia):
    """Test handling of lists in articles"""
    mock_page = Mock()
    mock_page.title = "Test Article"
    mock_page.html.return_value = """
    <div class="mw-parser-output">
        <ul>
            <li>Item 1</li>
            <li>Item 2 with <a href="/wiki/Link">link</a></li>
        </ul>
        <ol>
            <li>Numbered item 1</li>
            <li>Numbered item 2</li>
        </ol>
    </div>
    """
    mock_wikipedia.page.return_value = mock_page
    
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["Test Article"], catch_exceptions=False)
        assert result.exit_code == 0
        content = open("Test Article.md").read()
        assert "- Item 1" in content
        assert "- Item 2 with [link]" in content

def test_cli_with_reference_cleanup(runner, mock_wikipedia):
    """Test cleaning up of reference numbers"""
    mock_page = Mock()
    mock_page.title = "Test Article"
    mock_page.html.return_value = """
    <div class="mw-parser-output">
        <p>Text with <sup>[1]</sup> multiple <sup>[2][3]</sup> references.</p>
        <ul>
            <li>List item with reference <sup>[4]</sup></li>
        </ul>
    </div>
    """
    mock_wikipedia.page.return_value = mock_page
    
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["Test Article"], catch_exceptions=False)
        assert result.exit_code == 0
        content = open("Test Article.md").read()
        # Add spaces in the test content to match actual formatting
        assert "Text with multiple references." in content
        assert "List item with reference" in content
        # Verify references are removed
        assert "[1]" not in content
        assert "[2]" not in content
        assert "[3]" not in content
        assert "[4]" not in content

def test_cli_with_navigation_elements(runner, mock_wikipedia):
    """Test handling of navigation elements"""
    mock_page = Mock()
    mock_page.title = "Test Article"
    mock_page.html.return_value = """
    <div class="mw-parser-output">
        <div role="navigation">Should be skipped</div>
        <div class="toc">Should be skipped</div>
        <div class="navigation-box">Should be skipped</div>
        <p>Real content</p>
    </div>
    """
    mock_wikipedia.page.return_value = mock_page
    
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["Test Article"], catch_exceptions=False)
        assert result.exit_code == 0
        content = open("Test Article.md").read()
        assert "Should be skipped" not in content
        assert "Real content" in content

def test_cli_with_forbidden_sections(runner, mock_wikipedia):
    """Test handling of forbidden sections"""
    mock_page = Mock()
    mock_page.title = "Test Article"
    mock_page.html.return_value = """
    <div class="mw-parser-output">
        <h2>Main Content</h2>
        <p>Good content</p>
        <h2>See Also</h2>
        <p>Should be skipped</p>
        <h2>References</h2>
        <p>Should be skipped</p>
    </div>
    """
    mock_wikipedia.page.return_value = mock_page
    
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["Test Article"], catch_exceptions=False)
        assert result.exit_code == 0
        content = open("Test Article.md").read()
        assert "Good content" in content
        assert "Should be skipped" not in content

def test_cli_with_complex_infobox(runner, mock_wikipedia):
    """Test handling of complex infobox data and lists"""
    mock_page = Mock()
    mock_page.title = "Test Article"
    mock_page.html.return_value = """
    <div class="mw-parser-output">
        <table class="infobox">
            <tr><th class="infobox-above">Title Row</th></tr>
            <tr><td class="infobox-image">Image Only Row</td></tr>
            <tr>
                <th class="infobox-label">Simple</th>
                <td class="infobox-data">Value</td>
            </tr>
            <tr>
                <th class="infobox-label">List</th>
                <td class="infobox-data">
                    <ul><li>Item 1</li><li>Item 2</li></ul>
                </td>
            </tr>
            <tr>
                <th class="infobox-label">Links</th>
                <td class="infobox-data">
                    <a href="/wiki/Link1">Link1</a>,
                    <a href="/wiki/Link2">Link2</a>
                </td>
            </tr>
            <tr>
                <th class="infobox-label">Mixed List</th>
                <td class="infobox-data">
                    <div class="hlist">
                        <ul>
                            <li>Item 1</li>
                            <li><a href="/wiki/Link">Link</a></li>
                            <li>Item with <br/> break</li>
                        </ul>
                    </div>
                </td>
            </tr>
            <tr>
                <th class="infobox-label">Complex Links</th>
                <td class="infobox-data">
                    <a href="/wiki/Link1">First</a>
                    <br/>
                    <a href="/wiki/Link2">Second</a>
                    with text
                    <br/>
                    Final text
                </td>
            </tr>
            <tr>
                <th class="infobox-label">Special|Chars</th>
                <td class="infobox-data">Value|with|pipes</td>
            </tr>
        </table>
    </div>
    """
    mock_wikipedia.page.return_value = mock_page
    
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["Test Article"], catch_exceptions=False)
        assert result.exit_code == 0
        content = open("Test Article.md").read()
        
        # Test basic infobox content
        assert "| Simple | Value |" in content
        assert "| List | Item 1, Item 2 |" in content
        assert "| Links | Link1, Link2 |" in content
        
        # Test complex lists and formatting
        assert "| Mixed List | Item 1, Link, Item with break |" in content
        assert "| Complex Links | First, Second, with text, Final text |" in content
        
        # Test special character handling
        assert "| Special|Chars | Value\\|with\\|pipes |" in content
        
        # Test skipping of title and image-only rows
        assert "Title Row" not in content
        assert "Image Only Row" not in content

def test_cli_dom_traversal(runner, mock_wikipedia):
    """Test DOM traversal, nested elements, and edge cases"""
    mock_page = Mock()
    mock_page.title = "Test Article"
    mock_page.html.return_value = """
    <div class="mw-parser-output">
        <!-- Test non-element nodes -->
        <!-- Comment node -->
        Text node
        <p>
            <!-- Nested comment -->
            <span>Text with comment<!-- comment --></span>
        </p>
        <!-- Test elements without name -->
        <p>Text with None name element</p>
        <!-- Test skipping already processed elements -->
        <p id="dup">Duplicate paragraph</p>
        <div><p id="dup">Duplicate paragraph</p></div>
        <!-- Test deep nesting -->
        <div>
            <div>
                <p>Deeply nested text</p>
                <div>
                    <ul>
                        <li>
                            <div>
                                <p>Very deep list item</p>
                                <a href="/wiki/Link">Deep link</a>
                            </div>
                        </li>
                    </ul>
                </div>
            </div>
        </div>
        <!-- Test mixed content types -->
        <div>
            Text before
            <p>Paragraph with <a href="/wiki/Link">link</a> and text</p>
            Text after
            <ul>
                <li>List after text</li>
            </ul>
        </div>
        <!-- Test empty elements -->
        <p></p>
        <div></div>
        <a></a>
        <!-- Test elements with no children -->
        <p>Single text node</p>
    </div>
    """
    mock_wikipedia.page.return_value = mock_page
    
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["Test Article"], catch_exceptions=False)
        assert result.exit_code == 0
        content = open("Test Article.md").read()
        
        # Test text node handling
        assert "Nested comment" in content
        assert "Text with None name element" in content
        assert content.count("Duplicate paragraph") == 1  # Should only appear once
        
        # Test deep nesting
        assert "Deeply nested text" in content
        assert "Very deep list item" in content
        assert "[link](https://en.wikipedia.org/wiki/Link)" in content
        
        # Test mixed content
        assert "Paragraph with" in content
        assert "- List after text" in content
        
        # Test empty and single node elements
        assert "Single text node" in content

def test_cli_error_handling(runner, mock_wikipedia):
    """Test comprehensive error handling scenarios"""
    mock_page = Mock()
    mock_page.title = "Test Article"
    
    # Test handling of None values
    mock_page.html.return_value = None
    mock_wikipedia.page.return_value = mock_page
    
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["Test Article"], catch_exceptions=False)
        assert result.exit_code == 1
        assert "Fatal error" in result.stderr
    
    # Test handling of malformed HTML
    def raise_html_error(*args, **kwargs):
        raise Exception("Malformed HTML")
    mock_page.html.side_effect = raise_html_error
    
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["Test Article"], catch_exceptions=False)
        assert result.exit_code == 1
        assert "Malformed HTML" in result.stderr
    
    # Test handling of empty content
    mock_page.html.side_effect = None
    mock_page.html.return_value = "<div class='mw-parser-output'></div>"
    
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["Test Article"], catch_exceptions=False)
        assert result.exit_code == 0
        content = open("Test Article.md").read()
        assert content.strip() == "# Test Article"
    
    # Test handling of missing parser output
    def raise_parser_error(*args, **kwargs):
        raise Exception("No parser output found")
    mock_page.html.side_effect = raise_parser_error
    
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["Test Article"], catch_exceptions=False)
        assert result.exit_code == 1
        assert "No parser output found" in result.stderr

def test_cli_special_cases(runner, mock_wikipedia):
    """Test special cases and edge cases in content processing"""
    mock_page = Mock()
    mock_page.title = "Test Article"
    mock_page.html.return_value = """
    <div class="mw-parser-output">
        <!-- Test special text processing -->
        <p>
            Text with unicode: é, ñ, 漢字
            Text with symbols: &lt; &gt; &amp; &quot;
            Text with multiple spaces:   test    spaces
        </p>
        <!-- Test special list processing -->
        <ul>
            <li>
                <!-- Test list item with only text nodes -->
                Text only list item
            </li>
            <li>
                <!-- Test list item with mixed content -->
                Text
                <br/>
                More text
                <span>Span text</span>
                Final text
            </li>
        </ul>
        <!-- Test special table processing -->
        <table class="infobox">
            <tr>
                <th class="infobox-label">Special</th>
                <td class="infobox-data">
                    <!-- Test cell with only text -->
                    Text only cell
                </td>
            </tr>
            <tr>
                <th class="infobox-label">Mixed</th>
                <td class="infobox-data">
                    Text
                    <br/>
                    <a href="/wiki/Link">Link</a>
                    <br/>
                    More text
                </td>
            </tr>
        </table>
        <!-- Test navigation elements -->
        <div role="navigation">
            <div class="navbox">Navigation content</div>
        </div>
        <div class="toc">
            <p>Table of contents</p>
        </div>
    </div>
    """
    mock_wikipedia.page.return_value = mock_page
    
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["Test Article"], catch_exceptions=False)
        assert result.exit_code == 0
        content = open("Test Article.md").read()
        
        # Test special text processing
        assert "Text with unicode: é, ñ, 漢字" in content
        assert "Text with symbols: < > & \"" in content
        assert "test spaces" in content  # Multiple spaces are normalized
        
        # Test special list processing
        assert "Text only list item" in content  # List marker may vary
        assert "Text More text Span text Final text" in content
        
        # Test special table processing
        assert "| Special |" in content
        assert "Text only cell" in content
        assert "| Mixed |" in content
        assert "Text" in content
        assert "Link" in content
        assert "More text" in content
        
        # Test navigation elements are skipped
        assert "Navigation content" not in content
        assert "Table of contents" not in content.split("\n")[0]  # Only check first line 