import sys
from pathlib import Path

# Adds the project root to Python's path so "app" is findable when running tests
sys.path.insert(0, str(Path(__file__).parent))