import pytest
from bs4 import BeautifulSoup
from wikipedia2md.cli import (
    clean_text_value,
    infobox_to_markdown,
    Colors,
    ACCEPTED_URL_PREFIXES,
)
from urllib.parse import urljoin

def test_text_cleaning():
    """Test text cleaning functions"""
    # Test reference removal
    assert clean_text_value("Some text[1]") == "Some text"
    assert clean_text_value("Multiple refs[1][2][3]") == "Multiple refs"
    
    # Test whitespace handling
    assert clean_text_value("  Extra  spaces  ") == "Extra spaces"
    assert clean_text_value("New\nlines\nremoved") == "New lines removed"
    
    # Test combined cases
    assert clean_text_value("  Text with [refs][1] and  spaces  ") == "Text with  and spaces"

def test_url_handling():
    """Test URL handling functionality"""
    # Test accepted URL prefixes
    assert 'https://wikipedia.org' in ACCEPTED_URL_PREFIXES
    assert 'http://www.wikipedia.org' in ACCEPTED_URL_PREFIXES
    
    # Test URL joining
    base = "https://en.wikipedia.org"
    assert urljoin(base, "/wiki/test") == "https://en.wikipedia.org/wiki/test"
    assert urljoin(base, "//upload.wikimedia.org/test.jpg") == "https://upload.wikimedia.org/test.jpg"

def test_colors_class():
    """Test the Colors class attributes"""
    assert Colors.CYAN == '\033[96m'
    assert Colors.GREEN == '\033[92m'
    assert Colors.YELLOW == '\033[93m'
    assert Colors.RED == '\033[91m'
    assert Colors.WHITE == '\033[97m'
    assert Colors.RESET == '\033[0m'

def test_process_data_content():
    """Test processing of data content in infoboxes"""
    def create_test_infobox(data):
        """Helper to create a test infobox with the given data"""
        return BeautifulSoup(f"""
        <table class="infobox">
            <tbody>
                <tr>
                    <th class="infobox-label">Test</th>
                    <td class="infobox-data">{data}</td>
                </tr>
            </tbody>
        </table>
        """, "html.parser")
    
    # Test plain text
    infobox = create_test_infobox("Simple text")
    result = infobox_to_markdown(infobox)
    assert "| Test | Simple text |" in result
    
    # Test links
    infobox = create_test_infobox('<a href="/wiki/test">Link text</a>')
    result = infobox_to_markdown(infobox)
    assert "| Test | Link text |" in result
    
    # Test lists
    list_html = """
    <ul>
        <li>Item 1</li>
        <li>Item 2</li>
    </ul>
    """
    infobox = create_test_infobox(list_html)
    result = infobox_to_markdown(infobox)
    assert "| Test | Item 1, Item 2 |" in result
    
    # Test mixed content
    mixed_html = """
    Text before
    <a href="/wiki/test">Link</a>
    <br>
    Text after
    """
    infobox = create_test_infobox(mixed_html)
    result = infobox_to_markdown(infobox)
    assert "| Test | Text before, Link, Text after |" in result

def test_process_data_content_complex():
    """Test process_data_content with complex nested content"""
    html = """
    <td class="infobox-data">
        <div>Text before</div>
        <a href="#">Link</a>
        <div>More text</div>
        <br/>
        <div>Text after</div>
    </td>
    """
    soup = BeautifulSoup(html, 'html.parser')
    infobox = soup.find('td')
    
    # Create a mock infobox with the test data
    mock_infobox = BeautifulSoup('<table class="infobox"></table>', 'html.parser')
    row = mock_infobox.new_tag('tr')
    row.append(soup.new_tag('th', attrs={'class': 'infobox-label'}))
    row.th.string = 'Test'
    row.append(infobox)
    mock_infobox.table.append(row)
    
    result = infobox_to_markdown(mock_infobox)
    assert "| Test | Text before, Link, More text, Text after |" in result

def test_process_data_content_empty():
    """Test process_data_content with empty or invalid content"""
    html = """
    <td class="infobox-data">
        <style></style>
        <sup></sup>
        <span></span>
    </td>
    """
    soup = BeautifulSoup(html, 'html.parser')
    infobox = soup.find('td')
    
    # Create a mock infobox with the test data
    mock_infobox = BeautifulSoup('<table class="infobox"></table>', 'html.parser')
    row = mock_infobox.new_tag('tr')
    row.append(soup.new_tag('th', attrs={'class': 'infobox-label'}))
    row.th.string = 'Test'
    row.append(infobox)
    mock_infobox.table.append(row)
    
    result = infobox_to_markdown(mock_infobox)
    assert "| Test |" not in result  # Empty content should be skipped

def test_process_data_content_mixed_lists():
    """Test process_data_content with mixed list types"""
    html = """
    <td class="infobox-data">
        <ul>
            <li>Item 1</li>
            <li>Item 2</li>
        </ul>
        <div class="hlist">
            <ul>
                <li>Item 3</li>
                <li>Item 4</li>
            </ul>
        </div>
    </td>
    """
    soup = BeautifulSoup(html, 'html.parser')
    infobox = soup.find('td')
    
    # Create a mock infobox with the test data
    mock_infobox = BeautifulSoup('<table class="infobox"></table>', 'html.parser')
    row = mock_infobox.new_tag('tr')
    row.append(soup.new_tag('th', attrs={'class': 'infobox-label'}))
    row.th.string = 'Test'
    row.append(infobox)
    mock_infobox.table.append(row)
    
    result = infobox_to_markdown(mock_infobox)
    assert "| Test | Item 1, Item 2, Item 3, Item 4 |" in result

def test_infobox_processing_comprehensive():
    """Test comprehensive infobox processing including edge cases"""
    # Test infobox with images
    html = """
    <table class="infobox">
        <tr>
            <td class="infobox-image">
                <img src="//test1.jpg" alt="Test 1">
            </td>
        </tr>
        <tr>
            <th class="infobox-label">Image2</th>
            <td class="infobox-data">
                <img src="//test2.jpg" alt="Test 2">
            </td>
        </tr>
    </table>
    """
    soup = BeautifulSoup(html, 'html.parser')
    result = infobox_to_markdown(soup)
    assert "![Test 1](https://test1.jpg)" in result
    assert "| Image2 | ![Test 2](https://test2.jpg) |" in result

    # Test with only commas and whitespace
    def create_test_infobox(data):
        return BeautifulSoup(f"""
        <table class="infobox">
            <tr>
                <th class="infobox-label">Test</th>
                <td class="infobox-data">{data}</td>
            </tr>
        </table>
        """, "html.parser")

    infobox = create_test_infobox(",,,,")
    result = infobox_to_markdown(infobox)
    assert "| Test |" not in result  # Empty content should be skipped

def test_infobox_edge_cases():
    """Test edge cases in infobox processing"""
    # Test with malformed infobox
    html = """
    <table class="infobox">
        <tr><td class="infobox-data">No label cell</td></tr>
        <tr><th class="infobox-label">Label</th></tr>
        <tr>
            <th class="infobox-label">Special</th>
            <td class="infobox-data">
                <style>Skip this</style>
                <script>Skip this too</script>
                Keep this
            </td>
        </tr>
    </table>
    """
    soup = BeautifulSoup(html, 'html.parser')
    result = infobox_to_markdown(soup)
    assert "| Special | Skip this tooKeep this |" in result
    assert "<style>" not in result
    assert "<script>" not in result 