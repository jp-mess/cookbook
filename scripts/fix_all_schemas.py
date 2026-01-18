#!/usr/bin/env python3
"""
Migration script to fix all tables with incorrect ID schema.
Tables were created with 'id INT' instead of 'INTEGER PRIMARY KEY',
which prevents SQLite from auto-incrementing IDs.

This script fixes:
- recipes
- ingredients (already fixed, but included for completeness)
- articles
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

def fix_table_schema(conn: sqlite3.Connection, table_name: str, columns: list, foreign_keys: list = None):
    """
    Fix a table's schema by recreating it with INTEGER PRIMARY KEY.
    
    Args:
        conn: Database connection
        table_name: Name of the table to fix
        columns: List of (name, type, nullable, default) tuples (excluding id)
        foreign_keys: List of (column, ref_table, ref_column) tuples
    """
    cursor = conn.cursor()
    
    print(f"\nFixing {table_name} table...")
    
    # Get all data from the table
    cursor.execute(f"SELECT * FROM {table_name} WHERE id IS NOT NULL")
    rows = cursor.fetchall()
    cursor.execute(f"PRAGMA table_info({table_name})")
    table_info = cursor.fetchall()
    
    # Get column names (excluding id)
    col_names = [col[1] for col in table_info if col[1] != 'id']
    
    print(f"  Found {len(rows)} rows to migrate")
    
    # Create new table with correct schema
    new_table_name = f"{table_name}_new"
    
    # Build CREATE TABLE statement
    create_sql = f"CREATE TABLE {new_table_name} (\n    id INTEGER PRIMARY KEY AUTOINCREMENT"
    
    for col_name, col_type, nullable, default in columns:
        nullable_str = "" if nullable else " NOT NULL"
        default_str = f" DEFAULT {default}" if default else ""
        create_sql += f",\n    {col_name} {col_type}{nullable_str}{default_str}"
    
    if foreign_keys:
        for fk_col, ref_table, ref_col in foreign_keys:
            create_sql += f",\n    FOREIGN KEY ({fk_col}) REFERENCES {ref_table}({ref_col})"
    
    create_sql += "\n)"
    
    cursor.execute(f"DROP TABLE IF EXISTS {new_table_name}")
    cursor.execute(create_sql)
    
    # Re-insert all data
    if rows:
        placeholders = ", ".join(["?"] * len(col_names))
        insert_sql = f"INSERT INTO {new_table_name} ({', '.join(col_names)}) VALUES ({placeholders})"
        
        id_map = {}
        for row in rows:
            old_id = row[0]
            data = row[1:]  # Skip id column
            cursor.execute(insert_sql, data)
            new_id = cursor.lastrowid
            id_map[old_id] = new_id
        
        print(f"  ✓ Migrated {len(id_map)} rows")
        return id_map
    else:
        print(f"  ✓ Table recreated (no data to migrate)")
        return {}
    
def migrate_recipe_ingredients(conn: sqlite3.Connection, id_map: dict):
    """Update recipe_ingredients table with new ingredient IDs."""
    cursor = conn.cursor()
    
    print("\nUpdating recipe_ingredients with new ingredient IDs...")
    cursor.execute("SELECT recipe_id, ingredient_id FROM recipe_ingredients")
    relationships = cursor.fetchall()
    
    updated = 0
    for recipe_id, old_ing_id in relationships:
        new_ing_id = id_map.get(old_ing_id)
        if new_ing_id and new_ing_id != old_ing_id:
            # Delete old relationship
            cursor.execute(
                "DELETE FROM recipe_ingredients WHERE recipe_id = ? AND ingredient_id = ?",
                (recipe_id, old_ing_id)
            )
            # Insert new relationship (if it doesn't already exist)
            cursor.execute(
                "INSERT OR IGNORE INTO recipe_ingredients (recipe_id, ingredient_id) VALUES (?, ?)",
                (recipe_id, new_ing_id)
            )
            updated += 1
    
    print(f"  ✓ Updated {updated} relationships")
    conn.commit()

def fix_recipes_table(conn: sqlite3.Connection):
    """Fix the recipes table schema."""
    columns = [
        ("name", "TEXT", False, None),
        ("instructions", "TEXT", True, None),
        ("notes", "TEXT", True, None),
    ]
    
    id_map = fix_table_schema(conn, "recipes", columns)
    
    # Replace old table
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS recipes")
    cursor.execute("ALTER TABLE recipes_new RENAME TO recipes")
    conn.commit()
    
    return id_map

def fix_articles_table(conn: sqlite3.Connection):
    """Fix the articles table schema."""
    columns = [
        ("notes", "TEXT", True, None),
    ]
    
    id_map = fix_table_schema(conn, "articles", columns)
    
    # Replace old table
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS articles")
    cursor.execute("ALTER TABLE articles_new RENAME TO articles")
    conn.commit()
    
    return id_map

def verify_table(conn: sqlite3.Connection, table_name: str) -> bool:
    """Verify that a table has the correct schema."""
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = cursor.fetchall()
    
    id_column = [col for col in columns if col[1] == 'id']
    if not id_column:
        print(f"  ✗ {table_name}: No id column found!")
        return False
    
    id_col = id_column[0]
    if id_col[2].upper() != 'INTEGER' or id_col[5] != 1:
        print(f"  ✗ {table_name}: Schema incorrect (type: {id_col[2]}, PK: {id_col[5]})")
        return False
    
    # Check for NULL IDs
    cursor.execute(f"SELECT COUNT(*) FROM {table_name} WHERE id IS NULL")
    null_count = cursor.fetchone()[0]
    if null_count > 0:
        print(f"  ✗ {table_name}: Found {null_count} rows with NULL IDs!")
        return False
    
    print(f"  ✓ {table_name}: Schema correct")
    return True

def main():
    """Main migration function."""
    db_path = get_database_path()
    
    if not db_path.exists():
        print(f"✗ Database not found: {db_path}")
        sys.exit(1)
    
    print("=" * 70)
    print("Database Schema Migration")
    print("=" * 70)
    print(f"\nDatabase: {db_path}")
    
    # Backup
    backup_path = backup_database(db_path)
    
    try:
        conn = sqlite3.connect(str(db_path))
        
        # Fix recipes table
        recipe_id_map = fix_recipes_table(conn)
        
        # Fix articles table
        article_id_map = fix_articles_table(conn)
        
        # Update recipe_tags if recipe IDs changed
        if recipe_id_map:
            cursor = conn.cursor()
            print("\nUpdating recipe_tags with new recipe IDs...")
            cursor.execute("SELECT recipe_id, tag_id FROM recipe_tags")
            relationships = cursor.fetchall()
            
            updated = 0
            for old_recipe_id, tag_id in relationships:
                new_recipe_id = recipe_id_map.get(old_recipe_id)
                if new_recipe_id and new_recipe_id != old_recipe_id:
                    cursor.execute(
                        "DELETE FROM recipe_tags WHERE recipe_id = ? AND tag_id = ?",
                        (old_recipe_id, tag_id)
                    )
                    cursor.execute(
                        "INSERT OR IGNORE INTO recipe_tags (recipe_id, tag_id) VALUES (?, ?)",
                        (new_recipe_id, tag_id)
                    )
                    updated += 1
            print(f"  ✓ Updated {updated} recipe-tag relationships")
        
        # Update article_tags if article IDs changed
        if article_id_map:
            cursor = conn.cursor()
            print("\nUpdating article_tags with new article IDs...")
            cursor.execute("SELECT article_id, tag_id FROM article_tags")
            relationships = cursor.fetchall()
            
            updated = 0
            for old_article_id, tag_id in relationships:
                new_article_id = article_id_map.get(old_article_id)
                if new_article_id and new_article_id != old_article_id:
                    cursor.execute(
                        "DELETE FROM article_tags WHERE article_id = ? AND tag_id = ?",
                        (old_article_id, tag_id)
                    )
                    cursor.execute(
                        "INSERT OR IGNORE INTO article_tags (article_id, tag_id) VALUES (?, ?)",
                        (new_article_id, tag_id)
                    )
                    updated += 1
            print(f"  ✓ Updated {updated} article-tag relationships")
        
        conn.commit()
        
        # Verify all tables
        print("\n" + "=" * 70)
        print("Verification:")
        print("=" * 70)
        all_ok = True
        all_ok &= verify_table(conn, "recipes")
        all_ok &= verify_table(conn, "ingredients")
        all_ok &= verify_table(conn, "articles")
        
        if not all_ok:
            print("\n✗ Some tables failed verification!")
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
