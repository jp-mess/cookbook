#!/usr/bin/env python3
"""
Bootload script: Initialize database with ingredients and tags from basics/ folder.
- Ingredients from basics/ingredients/*.txt (filename = ingredient type)
- Tags from basics/tags/*.txt (filename = subtag name)
- No recipes or articles are created.
"""
import sys
from pathlib import Path

# Add scripts directory to path
scripts_dir = Path(__file__).parent / 'scripts'
if str(scripts_dir) not in sys.path:
    sys.path.insert(0, str(scripts_dir))

from database import SessionLocal, init_db, engine
from db_operations import (
    add_ingredient_type, get_or_create_ingredient_type,
    add_ingredient,
    add_subtag, get_subtag,
    add_tag
)
from models import Recipe, Article, Ingredient, Tag, IngredientType, Subtag
from sqlalchemy import delete


def load_ingredients_from_file(file_path: Path) -> list[str]:
    """Load ingredient names from a text file, skipping empty lines and comments."""
    ingredients = []
    if file_path.exists():
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    ingredients.append(line)
    return ingredients


def load_tags_from_file(file_path: Path) -> list[str]:
    """Load tag names from a text file, skipping empty lines and comments."""
    tags = []
    if file_path.exists():
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    tags.append(line)
    return tags


def reset_database(db):
    """Delete all existing data (recipes, articles, ingredients, tags, types, subtags)."""
    print("Resetting database...")
    
    # Delete in order to respect foreign key constraints
    db.execute(delete(Recipe))
    db.execute(delete(Article))
    db.execute(delete(Ingredient))
    db.execute(delete(Tag))
    db.execute(delete(IngredientType))
    db.execute(delete(Subtag))
    
    db.commit()
    print("  ✓ Database reset complete")


def bootload_ingredients(db, ingredients_dir: Path):
    """Load all ingredients from basics/ingredients/ folder."""
    print("\n" + "="*70)
    print("Loading Ingredients")
    print("="*70)
    
    ingredient_files = sorted(ingredients_dir.glob('*.txt'))
    
    if not ingredient_files:
        print("  ✗ No ingredient files found")
        return
    
    total_ingredients = 0
    total_types = 0
    
    for file_path in ingredient_files:
        # Filename without .txt extension is the ingredient type
        type_name = file_path.stem
        
        # Get or create ingredient type
        ingredient_type = get_or_create_ingredient_type(db, type_name)
        if ingredient_type.id is None:
            total_types += 1
        
        # Load ingredients from file
        ingredient_names = load_ingredients_from_file(file_path)
        
        if not ingredient_names:
            print(f"\n  {type_name}: (empty file)")
            continue
        
        print(f"\n  {type_name}:")
        added_count = 0
        skipped_count = 0
        
        for ing_name in ingredient_names:
            try:
                # Check if ingredient already exists
                from db_operations import get_ingredient
                existing = get_ingredient(db, name=ing_name)
                if existing:
                    print(f"    - {ing_name} (already exists, skipped)")
                    skipped_count += 1
                    continue
                
                # Add ingredient with type
                ingredient = add_ingredient(
                    db,
                    name=ing_name,
                    type_name=type_name
                )
                print(f"    ✓ {ing_name}")
                added_count += 1
                total_ingredients += 1
            except ValueError as e:
                print(f"    ✗ {ing_name}: {e}")
            except Exception as e:
                print(f"    ✗ {ing_name}: Unexpected error - {e}")
        
        print(f"    ({added_count} added, {skipped_count} skipped)")
    
    print(f"\n  Total: {total_ingredients} ingredients added across {len(ingredient_files)} types")


def bootload_tags(db, tags_dir: Path):
    """Load all tags from basics/tags/ folder."""
    print("\n" + "="*70)
    print("Loading Tags")
    print("="*70)
    
    tag_files = sorted(tags_dir.glob('*.txt'))
    
    if not tag_files:
        print("  ✗ No tag files found")
        return
    
    total_tags = 0
    total_subtags = 0
    
    for file_path in tag_files:
        # Filename without .txt extension is the subtag name
        subtag_name = file_path.stem
        
        # Get or create subtag
        subtag = get_subtag(db, name=subtag_name)
        if not subtag:
            try:
                subtag = add_subtag(db, subtag_name)
                total_subtags += 1
            except ValueError:
                # Subtag already exists (shouldn't happen after reset, but handle gracefully)
                subtag = get_subtag(db, name=subtag_name)
        
        # Load tags from file
        tag_names = load_tags_from_file(file_path)
        
        if not tag_names:
            print(f"\n  {subtag_name}: (empty file)")
            continue
        
        print(f"\n  {subtag_name}:")
        added_count = 0
        skipped_count = 0
        
        for tag_name in tag_names:
            try:
                # Check if tag already exists
                from db_operations import get_tag
                existing = get_tag(db, name=tag_name)
                if existing:
                    print(f"    - {tag_name} (already exists, skipped)")
                    skipped_count += 1
                    continue
                
                # Add tag with subtag
                tag = add_tag(
                    db,
                    name=tag_name,
                    subtag_name=subtag_name
                )
                print(f"    ✓ {tag_name}")
                added_count += 1
                total_tags += 1
            except ValueError as e:
                print(f"    ✗ {tag_name}: {e}")
            except Exception as e:
                print(f"    ✗ {tag_name}: Unexpected error - {e}")
        
        print(f"    ({added_count} added, {skipped_count} skipped)")
    
    print(f"\n  Total: {total_tags} tags added across {len(tag_files)} subtags")


def main():
    """Main bootload function."""
    print("="*70)
    print("BOOTLOAD: Initializing Database")
    print("="*70)
    
    # Get paths
    project_root = Path(__file__).parent
    ingredients_dir = project_root / 'basics' / 'ingredients'
    tags_dir = project_root / 'basics' / 'tags'
    
    # Check directories exist
    if not ingredients_dir.exists():
        print(f"✗ Error: {ingredients_dir} does not exist")
        sys.exit(1)
    
    if not tags_dir.exists():
        print(f"✗ Error: {tags_dir} does not exist")
        sys.exit(1)
    
    # Initialize database
    print("\nInitializing database schema...")
    init_db()
    print("  ✓ Database schema initialized")
    
    # Connect to database
    db = SessionLocal()
    try:
        # Reset database (remove all existing data)
        reset_database(db)
        
        # Load ingredients
        bootload_ingredients(db, ingredients_dir)
        
        # Load tags
        bootload_tags(db, tags_dir)
        
        print("\n" + "="*70)
        print("BOOTLOAD COMPLETE")
        print("="*70)
        print("\nDatabase initialized with:")
        print("  - Ingredients (from basics/ingredients/)")
        print("  - Tags (from basics/tags/)")
        print("  - No recipes or articles")
        print()
        
    except Exception as e:
        db.rollback()
        print(f"\n✗ Error during bootload: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()


if __name__ == '__main__':
    main()
