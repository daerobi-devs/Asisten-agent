import pytest
from lxion.memory.workspace import workspace

def test_workspace_file_operations():
    test_filename = "test_note.txt"
    content = "Hello LXION autonomous agent!"

    # Test write
    res = workspace.write_file(test_filename, content)
    assert "Successfully written" in res

    # Test read
    read_back = workspace.read_file(test_filename)
    assert read_back == content

    # Test list
    files = workspace.list_files()
    assert any(f["path"] == test_filename for f in files)

    # Test delete
    del_res = workspace.delete_file(test_filename)
    assert "Deleted" in del_res