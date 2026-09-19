"""
Root conftest.py — adds backend/ to sys.path so all test imports resolve correctly.
"""

import sys
import os

# Isolate all tests to cimet_test.db so production/dev cimet.db is never touched
os.environ["DATABASE_PATH"] = "cimet_test.db"

# Ensure the backend directory is on the path
sys.path.insert(0, os.path.dirname(__file__))
