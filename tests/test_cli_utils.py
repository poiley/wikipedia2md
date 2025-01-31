import pytest
import io
from wikipedia2md.cli import get_package_data

def test_package_data_loading_fallback(monkeypatch):
    """Test fallback path for package data loading when importlib.resources fails"""
    def mock_open_text(*args, **kwargs):
        raise Exception("Resource not found")
    
    def mock_open(*args, **kwargs):
        return io.StringIO("test data")
    
    monkeypatch.setattr('importlib.resources.open_text', mock_open_text)
    monkeypatch.setattr('builtins.open', mock_open)
    
    result = get_package_data("test.txt")
    assert result == "test data"

def test_get_package_data_both_paths_fail(monkeypatch):
    """Test when both package data loading methods fail"""
    def mock_open_text(*args, **kwargs):
        raise Exception("Resource not found")
    
    def mock_open(*args, **kwargs):
        raise FileNotFoundError("File not found")
    
    monkeypatch.setattr('importlib.resources.open_text', mock_open_text)
    monkeypatch.setattr('builtins.open', mock_open)
    
    with pytest.raises(FileNotFoundError):
        get_package_data("nonexistent.txt") 