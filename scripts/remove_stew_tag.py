"""
Script to remove the 'stew' tag from all ingredients.
"""
import sys
from pathlib import Path

# Add scripts directory to path
scripts_dir = Path(__file__).parent
sys.path.insert(0, str(scripts_dir))

from database import SessionLocal
from db_operations import get_tag, list_ingredients, remove_tags_from_ingredient

def remove_stew_from_all_ingredients():
    """Remove 'stew' tag from all ingredients that have it."""
    db = SessionLocal()
    try:
        stew_tag = get_tag(db, name='stew')
        if not stew_tag:
            print('No stew tag found in database')
            return
        
        print(f'Found stew tag (ID: {stew_tag.id})')
        all_ingredients = list_ingredients(db)
        ingredients_with_stew = []
        
        for ing in all_ingredients:
            if ing and stew_tag in ing.tags:
                ingredients_with_stew.append(ing)
        
        if not ingredients_with_stew:
            print('No ingredients found with stew tag')
            return
        
        print(f'\nFound {len(ingredients_with_stew)} ingredient(s) with stew tag:')
        for ing in ingredients_with_stew:
            print(f'  [{ing.id:3d}] {ing.name}')
        
        print(f'\nRemoving stew tag from {len(ingredients_with_stew)} ingredient(s)...')
        for ing in ingredients_with_stew:
            remove_tags_from_ingredient(db, ingredient_id=ing.id, tag_names=['stew'])
            print(f'  ✓ Removed from [{ing.id:3d}] {ing.name}')
        
        print(f'\n✓ Successfully removed stew tag from {len(ingredients_with_stew)} ingredient(s)')
        
    except Exception as e:
        print(f'\n✗ Error: {e}', file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    remove_stew_from_all_ingredients()
