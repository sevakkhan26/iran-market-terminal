"""Point the SQLite layer at a throwaway directory before app modules import."""
import os
import tempfile

os.environ.setdefault("TERMINAL_DATA_DIR", tempfile.mkdtemp(prefix="terminal-test-"))
os.environ.setdefault("DEMO_MODE", "1")
