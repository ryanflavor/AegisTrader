"""Shared pytest fixtures for monitor-api tests."""

import sys
from pathlib import Path

# Add the app directory to Python path for imports
app_dir = Path(__file__).parent.parent
sys.path.insert(0, str(app_dir))
