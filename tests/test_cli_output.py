import pytest
from click.testing import CliRunner
from wikipedia2md.cli import main
from unittest.mock import patch, Mock
import os

@pytest.fixture
def runner():
    """Create a Click test runner that preserves color output"""
    return CliRunner(mix_stderr=False, env={"FORCE_COLOR": "1"})

def test_cli_output_handling(runner, tmp_path):
    """Test CLI output handling"""
    with patch('wikipedia2md.cli.wikipedia') as mock_wiki:
        mock_page = Mock()
        mock_page.html.return_value = "<div>content</div>"
        mock_page.title = "Test"
        mock_wiki.page.return_value = mock_page

        # Test with existing output directory
        result = runner.invoke(main, ["Title", "--output-dir", str(tmp_path)])
        assert result.exit_code == 0
        assert (tmp_path / "Test.md").exists()

        # Test with nested output directory
        nested_dir = tmp_path / "nested" / "path"
        result = runner.invoke(main, ["Title", "--output-dir", str(nested_dir)])
        assert result.exit_code == 0
        assert (nested_dir / "Test.md").exists()

        # Test with read-only directory
        readonly_dir = tmp_path / "readonly"
        readonly_dir.mkdir()
        os.chmod(str(readonly_dir), 0o444)  # Make directory read-only
        result = runner.invoke(main, ["Title", "--output-dir", str(readonly_dir)])
        assert result.exit_code == 1
        assert "Permission denied" in result.stderr

def test_make_markdown_edge_cases(runner):
    """Test edge cases in markdown generation"""
    with patch('wikipedia2md.cli.wikipedia') as mock_wiki:
        mock_page = Mock()
        mock_page.title = "Test Article"
        mock_page.url = "https://en.wikipedia.org/wiki/Test_Article"

        # Test with malformed HTML
        mock_page.html.return_value = "<div class='mw-parser-output'><p>Unclosed paragraph"
        mock_wiki.page.return_value = mock_page
        
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["Test Article"])
            assert result.exit_code == 0
            content = open("Test Article.md").read()
            assert "Unclosed paragraph" in content

        # Test with empty sections and navigation elements
        mock_page.html.return_value = """
        <div class="mw-parser-output">
            <div role="navigation">Skip this</div>
            <h2>Empty Section</h2>
            <div class="toc">Skip this too</div>
            <h2>References</h2>
            <div>Skip this section</div>
        </div>
        """
        
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["Test Article"])
            assert result.exit_code == 0
            content = open("Test Article.md").read()
            assert "Skip this" not in content
            assert "## Empty Section" in content
            assert "References" not in content

def test_cli_option_combinations_comprehensive(runner, tmp_path):
    """Test comprehensive combinations of CLI options"""
    with patch('wikipedia2md.cli.wikipedia') as mock_wiki:
        mock_page = Mock()
        mock_page.html.return_value = "<div>content</div>"
        mock_page.title = "Test"
        mock_wiki.page.return_value = mock_page

        # Test all options together
        with runner.isolated_filesystem():
            result = runner.invoke(main, [
                "Title",
                "--verbose",
                "--loglevel", "DEBUG",
                "--no-links",
                "--obsidian",
                "--output-dir", "."
            ])
            assert result.exit_code == 0
            assert "Debug mode enabled" in result.stdout
            content = open("Test.md").read()
            
            # Split content at frontmatter
            parts = content.split("---", 2)
            assert len(parts) >= 3  # Should have at least 3 parts (empty, frontmatter, content)
            frontmatter = parts[1]
            main_content = parts[2]
            
            # URLs are allowed in frontmatter even with --no-links
            assert "wikipedia_url:" in frontmatter
            # But not in main content
            assert "http" not in main_content

        # Test with URL and other options
        with runner.isolated_filesystem():
            result = runner.invoke(main, [
                "--url", "https://en.wikipedia.org/wiki/Test",
                "--verbose",
                "--no-links",
                "--obsidian"
            ])
            assert result.exit_code == 0

        # Test with read-only directory
        readonly_dir = tmp_path / "readonly"
        readonly_dir.mkdir()
        os.chmod(str(readonly_dir), 0o444)  # Make directory read-only
        result = runner.invoke(main, ["Title", "--output-dir", str(readonly_dir)])
        assert result.exit_code == 1
        assert "Permission denied" in result.stderr 