"""
Migration script to convert string subtags to Subtag entities.

This script:
1. Creates the subtags table
2. Extracts unique subtag strings from tags
3. Creates Subtag entities for each unique subtag
4. Updates tags to reference Subtag entities by foreign key
5. Drops the old subtag string column
"""
import sys
from pathlib import Path

# Add scripts directory to path
scripts_dir = Path(__file__).parent
sys.path.insert(0, str(scripts_dir))

from sqlalchemy import text
from database import SessionLocal, engine
from models import Base, Tag, Subtag

def migrate():
    """Migrate subtags from strings to Subtag entities."""
    db = SessionLocal()
    try:
        print("Starting subtag migration...")
        
        # Step 1: Create subtags table
        print("Step 1: Creating subtags table...")
        Base.metadata.create_all(engine, tables=[Subtag.__table__])
        print("  ✓ Subtags table created")
        
        # Step 2: Check if old subtag column exists
        print("\nStep 2: Checking for old subtag column...")
        inspector = db.execute(text("PRAGMA table_info(tags)")).fetchall()
        column_names = [col[1] for col in inspector]
        
        if 'subtag' not in column_names:
            print("  ℹ No old 'subtag' column found. Migration may have already been run.")
            print("  ℹ If subtag_id column exists, migration is complete.")
            if 'subtag_id' in column_names:
                print("  ✓ Migration already complete!")
                return
            else:
                print("  ✗ Neither subtag nor subtag_id column found. Something is wrong.")
                sys.exit(1)
        
        # Step 3: Extract unique subtags
        print("\nStep 3: Extracting unique subtags from tags...")
        result = db.execute(text("SELECT DISTINCT subtag FROM tags WHERE subtag IS NOT NULL AND subtag != ''"))
        unique_subtags = [row[0] for row in result.fetchall()]
        print(f"  Found {len(unique_subtags)} unique subtag(s): {', '.join(unique_subtags)}")
        
        # Step 4: Create Subtag entities
        print("\nStep 4: Creating Subtag entities...")
        subtag_map = {}  # Map from old string to new Subtag object
        for subtag_str in unique_subtags:
            if subtag_str:
                normalized = subtag_str.strip().lower()
                # Check if subtag already exists (in case migration was partially run)
                existing = db.query(Subtag).filter(Subtag.name == normalized).first()
                if existing:
                    subtag_map[subtag_str] = existing
                    print(f"  ℹ Subtag '{normalized}' already exists (ID: {existing.id})")
                else:
                    subtag = Subtag(name=normalized)
                    db.add(subtag)
                    db.flush()  # Flush to get ID
                    subtag_map[subtag_str] = subtag
                    print(f"  ✓ Created subtag: {normalized} (ID: {subtag.id})")
        
        db.commit()
        print(f"  ✓ Created {len(subtag_map)} subtag(s)")
        
        # Step 5: Add subtag_id column if it doesn't exist
        print("\nStep 5: Adding subtag_id column to tags table...")
        if 'subtag_id' not in column_names:
            db.execute(text("ALTER TABLE tags ADD COLUMN subtag_id INTEGER REFERENCES subtags(id)"))
            db.commit()
            print("  ✓ Added subtag_id column")
        else:
            print("  ℹ subtag_id column already exists")
        
        # Step 6: Update tags to reference Subtag entities
        print("\nStep 6: Updating tags to reference Subtag entities...")
        all_tags = db.query(Tag).all()
        updated_count = 0
        for tag in all_tags:
            if tag.subtag:  # This will still be the old string column
                old_subtag_str = tag.subtag
                if old_subtag_str in subtag_map:
                    subtag_obj = subtag_map[old_subtag_str]
                    # Update using raw SQL since SQLAlchemy might not see the new column yet
                    db.execute(
                        text("UPDATE tags SET subtag_id = :subtag_id WHERE id = :tag_id"),
                        {"subtag_id": subtag_obj.id, "tag_id": tag.id}
                    )
                    updated_count += 1
        
        db.commit()
        print(f"  ✓ Updated {updated_count} tag(s)")
        
        # Step 7: Drop old subtag column (SQLite doesn't support DROP COLUMN directly, so we'll recreate the table)
        print("\nStep 7: Removing old subtag column...")
        print("  ⚠ SQLite doesn't support DROP COLUMN, so we'll recreate the table")
        print("  This is safe because we've already migrated the data")
        
        # Create new table structure
        db.execute(text("""
            CREATE TABLE tags_new (
                id INTEGER PRIMARY KEY,
                name VARCHAR(100) NOT NULL UNIQUE,
                subtag_id INTEGER REFERENCES subtags(id)
            )
        """))
        
        # Copy data (without old subtag column)
        db.execute(text("""
            INSERT INTO tags_new (id, name, subtag_id)
            SELECT id, name, subtag_id FROM tags
        """))
        
        # Drop old table
        db.execute(text("DROP TABLE tags"))
        
        # Rename new table
        db.execute(text("ALTER TABLE tags_new RENAME TO tags"))
        
        # Recreate indexes and foreign keys
        db.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_tags_name ON tags(name)"))
        
        db.commit()
        print("  ✓ Removed old subtag column")
        
        print("\n" + "="*70)
        print("Migration complete!")
        print("="*70)
        print(f"  Created {len(subtag_map)} subtag(s)")
        print(f"  Updated {updated_count} tag(s)")
        print("\nYou can now use subtag management commands:")
        print("  python cli.py subtag add <name>")
        print("  python cli.py subtag list")
        print("  python cli.py subtag remove --id <id>")
        
    except Exception as e:
        db.rollback()
        print(f"\n✗ Migration failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    migrate()
