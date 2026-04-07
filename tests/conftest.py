import pytest
import os
import tempfile


@pytest.fixture
def temp_graph():
    """Create a temporary graph file for testing.
    
    Uses mkstemp() to avoid race condition between file creation and use.
    """
    fd, graph_path = tempfile.mkstemp(suffix=".graph")
    os.close(fd)
    os.remove(graph_path)
    yield graph_path
    if os.path.exists(graph_path):
        os.remove(graph_path)