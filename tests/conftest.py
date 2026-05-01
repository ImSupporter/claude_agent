import os
import pytest

# Set environment variables before importing config
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("DOC_API_BASE_URL", "http://localhost:8000")
os.environ.setdefault("DB_CONNECTION_STRING", "sqlite:///./test.db")
os.environ.setdefault("DOC_API_KEY", "test-doc-key")
