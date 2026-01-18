#!/usr/bin/env python3
"""
Reset the database to a clean state.
WARNING: This will delete all existing data!
"""

import sys
from pathlib import Path
import shutil

# Add scripts directory to path
scripts_dir = Path(__file__).parent
sys.path.insert(0, str(scripts_dir))

from database import engine, init_db
from models import Base
from config_loader import get_database_path

def reset_database():
    """Drop all tables and recreate them."""
    print("=" * 70)
    print("Resetting Database")
    print("=" * 70)
    
    db_path = get_database_path()
    
    # Backup existing database if it exists
    if db_path.exists():
        backup_path = db_path.parent / f"{db_path.stem}_backup_before_reset.db"
        shutil.copy(db_path, backup_path)
        print(f"✓ Backed up existing database to: {backup_path}")
    
    # Drop all tables
    print("\nDropping all tables...")
    Base.metadata.drop_all(bind=engine)
    print("  ✓ Dropped all tables")
    
    # Create all tables
    print("\nCreating all tables...")
    Base.metadata.create_all(bind=engine)
    print("  ✓ Created all tables")
    
    print("\n" + "=" * 70)
    print("Database reset complete!")
    print("=" * 70)

if __name__ == "__main__":
    response = input("\n⚠️  WARNING: This will delete ALL data in the database!\n   Are you sure you want to continue? (yes/no): ")
    if response.lower() != 'yes':
        print("Aborted.")
        sys.exit(0)
    
    reset_database()
