import pytest
from click.testing import CliRunner
from wikipedia2md.cli import main
from unittest.mock import patch, Mock
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

def test_basic_cli(runner, mock_wikipedia):
    """Test basic CLI functionality"""
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["Python (programming language)"])
        assert result.exit_code == 0
        assert "Python" in open("Python (programming language).md").read()

def test_cli_with_output_dir(runner, mock_wikipedia, tmp_path):
    """Test CLI with output directory option"""
    result = runner.invoke(main, [
        "Python (programming language)",
        "-o", str(tmp_path)
    ])
    assert result.exit_code == 0
    assert len(list(tmp_path.glob("*.md"))) == 1

def test_cli_with_obsidian_option(runner, mock_wikipedia):
    """Test CLI with Obsidian option"""
    with runner.isolated_filesystem():
        result = runner.invoke(main, [
            "Python (programming language)",
            "-O"
        ])
        assert result.exit_code == 0
        content = open("Python (programming language).md").read()
        assert "---" in content

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