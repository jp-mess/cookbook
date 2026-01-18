#!/usr/bin/env python3
"""
Migration script to fix the ingredients table schema.
The table was created with 'id INT' instead of 'INTEGER PRIMARY KEY',
which prevents SQLite from auto-incrementing IDs.

This script:
1. Backs up the database
2. Reads all ingredient data
3. Recreates the table with correct schema
4. Re-inserts all data
5. Verifies the migration
"""

import sys
import sqlite3
import shutil
from pathlib import Path
from datetime import datetime

# Add scripts directory to path
scripts_dir = Path(__file__).parent
sys.path.insert(0, str(scripts_dir))

from config_loader import get_database_path

def backup_database(db_path: Path) -> Path:
    """Create a timestamped backup of the database."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = db_path.parent / f"recipes_backup_{timestamp}.db"
    shutil.copy(db_path, backup_path)
    print(f"✓ Created backup: {backup_path}")
    return backup_path

def get_all_ingredients(conn: sqlite3.Connection) -> list:
    """Read all ingredients from the database."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, name, alias, notes, type_id
        FROM ingredients
        WHERE id IS NOT NULL
        ORDER BY id
    """)
    ingredients = cursor.fetchall()
    print(f"✓ Found {len(ingredients)} ingredients to migrate")
    return ingredients

def get_ingredient_tags(conn: sqlite3.Connection, ingredient_id: int) -> list:
    """Get all tags for an ingredient."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT tag_id
        FROM ingredient_tags
        WHERE ingredient_id = ?
    """, (ingredient_id,))
    return [row[0] for row in cursor.fetchall()]

def recreate_ingredients_table(conn: sqlite3.Connection):
    """Recreate the ingredients table with correct schema."""
    cursor = conn.cursor()
    
    # Create new table with correct schema
    print("\nRecreating ingredients table with correct schema...")
    cursor.execute("DROP TABLE IF EXISTS ingredients_new")
    cursor.execute("""
        CREATE TABLE ingredients_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            alias TEXT,
            notes TEXT,
            type_id INTEGER,
            FOREIGN KEY (type_id) REFERENCES ingredient_types(id)
        )
    """)
    print("  ✓ Created new table with INTEGER PRIMARY KEY")
    
    # Get all ingredients with valid IDs
    ingredients = get_all_ingredients(conn)
    
    # Re-insert all ingredients
    print(f"\nRe-inserting {len(ingredients)} ingredients...")
    ingredient_id_map = {}  # Map old ID to new ID
    for old_id, name, alias, notes, type_id in ingredients:
        cursor.execute("""
            INSERT INTO ingredients_new (name, alias, notes, type_id)
            VALUES (?, ?, ?, ?)
        """, (name, alias, notes, type_id))
        new_id = cursor.lastrowid
        ingredient_id_map[old_id] = new_id
        if len(ingredient_id_map) % 10 == 0:
            print(f"  Migrated {len(ingredient_id_map)} ingredients...")
    
    print(f"  ✓ Re-inserted {len(ingredient_id_map)} ingredients")
    
    # Migrate ingredient_tags relationships
    print("\nMigrating ingredient_tags relationships...")
    cursor.execute("SELECT ingredient_id, tag_id FROM ingredient_tags")
    tag_relationships = cursor.fetchall()
    
    # Create new ingredient_tags table
    cursor.execute("DROP TABLE IF EXISTS ingredient_tags_new")
    cursor.execute("""
        CREATE TABLE ingredient_tags_new (
            ingredient_id INTEGER NOT NULL,
            tag_id INTEGER NOT NULL,
            PRIMARY KEY (ingredient_id, tag_id),
            FOREIGN KEY (ingredient_id) REFERENCES ingredients_new(id),
            FOREIGN KEY (tag_id) REFERENCES tags(id)
        )
    """)
    
    migrated_tags = 0
    for old_ing_id, tag_id in tag_relationships:
        new_ing_id = ingredient_id_map.get(old_ing_id)
        if new_ing_id:
            cursor.execute("""
                INSERT INTO ingredient_tags_new (ingredient_id, tag_id)
                VALUES (?, ?)
            """, (new_ing_id, tag_id))
            migrated_tags += 1
    
    print(f"  ✓ Migrated {migrated_tags} tag relationships")
    
    # Migrate recipe_ingredients relationships
    cursor.execute("SELECT recipe_id, ingredient_id FROM recipe_ingredients")
    recipe_relationships = cursor.fetchall()
    
    print("\nMigrating recipe_ingredients relationships...")
    cursor.execute("DROP TABLE IF EXISTS recipe_ingredients_new")
    cursor.execute("""
        CREATE TABLE recipe_ingredients_new (
            recipe_id INTEGER NOT NULL,
            ingredient_id INTEGER NOT NULL,
            PRIMARY KEY (recipe_id, ingredient_id),
            FOREIGN KEY (recipe_id) REFERENCES recipes(id),
            FOREIGN KEY (ingredient_id) REFERENCES ingredients_new(id)
        )
    """)
    
    migrated_recipes = 0
    for recipe_id, old_ing_id in recipe_relationships:
        new_ing_id = ingredient_id_map.get(old_ing_id)
        if new_ing_id:
            cursor.execute("""
                INSERT INTO recipe_ingredients_new (recipe_id, ingredient_id)
                VALUES (?, ?)
            """, (recipe_id, new_ing_id))
            migrated_recipes += 1
    
    print(f"  ✓ Migrated {migrated_recipes} recipe relationships")
    
    # Drop old tables and rename new ones
    print("\nReplacing old tables with new ones...")
    cursor.execute("DROP TABLE IF EXISTS recipe_ingredients")
    cursor.execute("DROP TABLE IF EXISTS ingredient_tags")
    cursor.execute("DROP TABLE IF EXISTS ingredients")
    
    cursor.execute("ALTER TABLE ingredients_new RENAME TO ingredients")
    cursor.execute("ALTER TABLE ingredient_tags_new RENAME TO ingredient_tags")
    cursor.execute("ALTER TABLE recipe_ingredients_new RENAME TO recipe_ingredients")
    
    print("  ✓ Tables replaced successfully")
    
    conn.commit()
    print("\n✓ Migration complete!")

def verify_migration(conn: sqlite3.Connection):
    """Verify that the migration was successful."""
    cursor = conn.cursor()
    
    # Check table schema
    cursor.execute("PRAGMA table_info(ingredients)")
    columns = cursor.fetchall()
    id_column = [col for col in columns if col[1] == 'id'][0]
    
    print("\nVerification:")
    print(f"  ID column type: {id_column[2]}")
    print(f"  ID is PRIMARY KEY: {id_column[5] == 1}")
    
    if id_column[2].upper() != 'INTEGER' or id_column[5] != 1:
        print("  ✗ WARNING: Schema may still be incorrect!")
        return False
    
    # Check ingredient count
    cursor.execute("SELECT COUNT(*) FROM ingredients")
    count = cursor.fetchone()[0]
    print(f"  Ingredient count: {count}")
    
    # Check for NULL IDs
    cursor.execute("SELECT COUNT(*) FROM ingredients WHERE id IS NULL")
    null_count = cursor.fetchone()[0]
    if null_count > 0:
        print(f"  ✗ WARNING: Found {null_count} ingredients with NULL IDs!")
        return False
    
    # Test ID generation
    cursor.execute("INSERT INTO ingredients (name) VALUES ('_test_migration')")
    test_id = cursor.lastrowid
    cursor.execute("DELETE FROM ingredients WHERE name = '_test_migration'")
    
    if test_id is None:
        print("  ✗ WARNING: ID generation test failed!")
        return False
    
    print(f"  ✓ ID generation test passed (generated ID: {test_id})")
    print("\n✓ Migration verified successfully!")
    return True

def main():
    """Main migration function."""
    db_path = get_database_path()
    
    if not db_path.exists():
        print(f"✗ Database not found: {db_path}")
        sys.exit(1)
    
    print("=" * 70)
    print("Ingredients Table Schema Migration")
    print("=" * 70)
    print(f"\nDatabase: {db_path}")
    
    # Backup
    backup_path = backup_database(db_path)
    
    try:
        conn = sqlite3.connect(str(db_path))
        
        # Perform migration
        recreate_ingredients_table(conn)
        
        # Verify
        if not verify_migration(conn):
            print("\n✗ Migration verification failed!")
            print(f"  Restore from backup: {backup_path}")
            sys.exit(1)
        
        conn.close()
        
        print("\n" + "=" * 70)
        print("Migration completed successfully!")
        print(f"Backup saved at: {backup_path}")
        print("=" * 70)
        
    except Exception as e:
        print(f"\n✗ Migration failed: {e}")
        print(f"  Restore from backup: {backup_path}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
