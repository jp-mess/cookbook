#!/usr/bin/env python3
"""
Reset/Wipe Database: Delete all data from all tables.
This will remove all recipes, articles, ingredients, tags, types, and subtags.
"""
import sys
from pathlib import Path

# Add scripts directory to path
scripts_dir = Path(__file__).parent / 'scripts'
if str(scripts_dir) not in sys.path:
    sys.path.insert(0, str(scripts_dir))

from database import SessionLocal, init_db
from models import (
    Recipe, Article, Ingredient, Tag, IngredientType, Subtag, RecipeIngredient,
    recipe_tags, article_tags, recipe_secondary_ingredients, recipe_clashing_ingredients,
    recipe_want_to_try_ingredients
)
from sqlalchemy import delete


def reset_database():
    """Delete all data from all tables."""
    print("="*70)
    print("RESET DATABASE")
    print("="*70)
    print("\n⚠️  WARNING: This will delete ALL data from the database!")
    print("   - All recipes")
    print("   - All articles")
    print("   - All ingredients")
    print("   - All tags")
    print("   - All ingredient types")
    print("   - All subtags")
    print()
    
    response = input("Are you sure you want to continue? (yes/no): ").strip().lower()
    if response not in ['yes', 'y']:
        print("Reset cancelled.")
        return
    
    db = SessionLocal()
    try:
        print("\nResetting database...")
        
        # Delete in order to respect foreign key constraints
        # Start with junction tables and relationships
        print("  Deleting recipe-ingredient associations...")
        db.execute(delete(RecipeIngredient))
        
        print("  Deleting recipe-tag associations...")
        db.execute(recipe_tags.delete())
        
        print("  Deleting article-tag associations...")
        db.execute(article_tags.delete())
        
        print("  Deleting recipe-secondary-ingredient associations...")
        db.execute(recipe_secondary_ingredients.delete())
        
        print("  Deleting recipe-clashing-ingredient associations...")
        db.execute(recipe_clashing_ingredients.delete())
        
        print("  Deleting recipe-want-to-try-ingredient associations...")
        db.execute(recipe_want_to_try_ingredients.delete())
        
        print("  Deleting recipes...")
        db.execute(delete(Recipe))
        
        print("  Deleting articles...")
        db.execute(delete(Article))
        
        print("  Deleting ingredients...")
        db.execute(delete(Ingredient))
        
        print("  Deleting tags...")
        db.execute(delete(Tag))
        
        print("  Deleting ingredient types...")
        db.execute(delete(IngredientType))
        
        print("  Deleting subtags...")
        db.execute(delete(Subtag))
        
        db.commit()
        
        print("\n" + "="*70)
        print("✓ Database reset complete!")
        print("="*70)
        print("\nAll data has been deleted. The database schema remains intact.")
        print("You can now use bootload.py to repopulate with ingredients and tags.")
        print()
        
    except Exception as e:
        db.rollback()
        print(f"\n✗ Error during reset: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()


if __name__ == '__main__':
    reset_database()
