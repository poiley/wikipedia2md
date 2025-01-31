import pytest
from wikipedia2md.cli import clean_text_value, ColoredFormatter
import logging
import os

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

def test_colored_formatter():
    """Test ColoredFormatter functionality"""
    formatter = ColoredFormatter()
    
    # Test color detection
    os.environ['FORCE_COLOR'] = '1'
    assert formatter.should_use_colors() is True
    
    # Test formatting with colors
    record = logging.LogRecord(
        name='test', level=logging.ERROR,
        pathname='test.py', lineno=1,
        msg='Test error message', args=(),
        exc_info=None
    )
    
    formatted = formatter.format(record)
    assert '\033[31m' in formatted  # Red color for error
    assert '\033[0m' in formatted   # Reset color 