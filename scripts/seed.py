#!/usr/bin/env python3
"""Convenience root wrapper for the backend seed script."""
import sys
from pathlib import Path

# Add backend directory to sys.path
root_dir = Path(__file__).resolve().parents[1]
backend_dir = root_dir / "backend"
sys.path.insert(0, str(backend_dir))

# Change working directory to backend so relative configs resolve correctly if needed
import os
os.chdir(str(backend_dir))

from scripts.seed import seed_database

if __name__ == "__main__":
    seed_database()

