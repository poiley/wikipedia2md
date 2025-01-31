import pytest
from bs4 import BeautifulSoup
from wikipedia2md.cli import walk_dom, infobox_to_markdown

def test_walk_dom():
    """Test DOM traversal with various element types"""
    html = """
    <div>
        <h1>Title</h1>
        <p>Text before</p>
        <ul>
            <li>Item 1</li>
            <li>Item 2</li>
        </ul>
        <p>Text after</p>
        <h2>Section</h2>
        <img src="test.jpg" alt="Test">
    </div>
    """
    soup = BeautifulSoup(html, 'html.parser')
    elements = list(walk_dom(soup))
    assert len(elements) == 8  # h1, p, li, li, ul, p, h2, img
    assert [e.name for e in elements] == ['h1', 'p', 'li', 'li', 'ul', 'p', 'h2', 'img']

def test_infobox_processing():
    """Test infobox processing with various content types"""
    html = """
    <table class="infobox">
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
            <th class="infobox-label">Mixed</th>
            <td class="infobox-data">
                Text before
                <a href="#">Link</a>
                Text after
            </td>
        </tr>
    </table>
    """
    soup = BeautifulSoup(html, 'html.parser')
    result = infobox_to_markdown(soup)
    
    assert "| Simple | Value |" in result
    assert "| List | Item 1, Item 2 |" in result
    assert "| Mixed | Text before, Link, Text after |" in result 