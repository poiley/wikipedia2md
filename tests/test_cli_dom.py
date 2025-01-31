import pytest
from bs4 import BeautifulSoup
from wikipedia2md.cli import walk_dom

def test_walk_dom_comprehensive():
    """Test comprehensive DOM traversal scenarios including edge cases and logging"""
    # Test deeply nested elements
    html = """
    <div>
        <h1>Title</h1>
        <div>
            <p>Text before</p>
            <div>
                <ul>
                    <li>Item 1</li>
                    <li>Item 2</li>
                </ul>
            </div>
            <p>Text after</p>
        </div>
        <h2>Section</h2>
        <img src="test.jpg" alt="Test">
    </div>
    """
    soup = BeautifulSoup(html, 'html.parser')
    elements = list(walk_dom(soup))
    assert len(elements) == 8  # h1, p, li, li, ul, p, h2, img
    assert [e.name for e in elements] == ['h1', 'p', 'li', 'li', 'ul', 'p', 'h2', 'img']

    # Test with non-element nodes (strings, comments)
    html = """
    <div>
        <!-- Comment -->
        Plain text
        <p>Paragraph</p>
        More text
        <h2>Header</h2>
    </div>
    """
    soup = BeautifulSoup(html, 'html.parser')
    elements = list(walk_dom(soup))
    assert len(elements) == 2  # p, h2
    assert [e.name for e in elements] == ['p', 'h2']

    # Test with invalid/empty elements
    html = """
    <div>
        <p></p>
        <invalid>Test</invalid>
        <h2/>
        <img>
    </div>
    """
    soup = BeautifulSoup(html, 'html.parser')
    elements = list(walk_dom(soup))
    assert len(elements) == 3  # p, h2, img
    assert [e.name for e in elements] == ['p', 'h2', 'img']

    # Test Wikidata edit images
    html = """
    <div>
        <img src="edit-ltr-progressive.png">
        <img src="normal.png">
    </div>
    """
    soup = BeautifulSoup(html, 'html.parser')
    elements = list(walk_dom(soup))
    assert len(elements) == 1  # Only the normal image
    assert elements[0]['src'] == 'normal.png'

def test_walk_dom_content_processing():
    """Test content processing in walk_dom"""
    # Test nested content
    soup = BeautifulSoup("""
    <div>
        <h2>Section 1</h2>
        <p>Text 1</p>
        <div>
            <h3>Subsection</h3>
            <p>Text 2</p>
            <ul>
                <li>Item 1</li>
            </ul>
        </div>
    </div>
    """, "html.parser")
    
    elements = list(walk_dom(soup))
    element_types = [elem.name for elem in elements]
    # The order of elements depends on the traversal implementation
    assert set(element_types) == {'h2', 'p', 'h3', 'p', 'ul', 'li'}
    assert element_types.index('h2') < element_types.index('h3')  # Section order is preserved
    
    # Test handling of irrelevant elements
    soup = BeautifulSoup("""
    <div>
        <style>css code</style>
        <script>js code</script>
        <p>Valid content</p>
        <div class="navigation">nav stuff</div>
    </div>
    """, "html.parser")
    
    elements = list(walk_dom(soup))
    assert len(elements) == 1
    assert elements[0].name == 'p'
    assert elements[0].get_text() == 'Valid content'

def test_walk_dom_invalid_elements():
    """Test walk_dom with invalid elements"""
    soup = BeautifulSoup('<div><span>Test</span>Invalid</div>', 'html.parser')
    elements = list(walk_dom(soup))
    assert len(elements) == 0  # No relevant elements found

def test_walk_dom_wikidata_edit_image():
    """Test walk_dom skips Wikidata edit images"""
    soup = BeautifulSoup(
        '<div><img src="edit-ltr-progressive.png"><img src="normal.png"></div>',
        'html.parser'
    )
    elements = list(walk_dom(soup))
    assert len(elements) == 1  # Only the normal image
    assert elements[0]['src'] == 'normal.png'

def test_walk_dom_edge_cases():
    """Test edge cases in DOM traversal"""
    # Test empty content
    soup = BeautifulSoup("<div class='mw-parser-output'></div>", 'html.parser')
    elements = list(walk_dom(soup))
    assert len(elements) == 0
    
    # Test malformed content
    soup = BeautifulSoup("""
    <div class='mw-parser-output'>
        <p>Text before <img> broken image
        <h2>Unclosed header
        <p>Unclosed paragraph
    </div>
    """, 'html.parser')
    
    elements = list(walk_dom(soup))
    assert len(elements) > 0  # Should still process valid elements
    assert any('Text before' in elem.get_text() for elem in elements) 