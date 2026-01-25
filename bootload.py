#!/usr/bin/env python3
"""
Bootload script: Initialize database with ingredients, tags, and recipes from basics/ folder.
- Ingredients from basics/ingredients/*.txt (filename = ingredient type)
- Tags from basics/tags/*.txt (filename = subtag name)
- Recipes from basics/recipes/*.json (JSON recipe files)
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
    add_tag,
    add_recipe, get_recipe
)
from models import Recipe, Article, Ingredient, Tag, IngredientType, Subtag
from sqlalchemy import delete
import json


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


def preflight_check_ingredients(ingredients_dir: Path) -> bool:
    """
    Preflight check: Verify that each ingredient appears in only one file.
    Returns True if no duplicates found, False otherwise.
    """
    print("\n" + "="*70)
    print("Preflight Check: Ingredient Duplicates")
    print("="*70)
    
    ingredient_files = sorted(ingredients_dir.glob('*.txt'))
    
    if not ingredient_files:
        print("  ✗ No ingredient files found")
        return False
    
    # Track which files each ingredient appears in (case-insensitive)
    ingredient_locations = {}  # ingredient_name_lower -> list of (file_path, original_name)
    duplicates_found = []
    
    for file_path in ingredient_files:
        type_name = file_path.stem
        ingredient_names = load_ingredients_from_file(file_path)
        
        for ing_name in ingredient_names:
            # Normalize to lowercase for comparison
            ing_name_lower = ing_name.strip().lower()
            
            if ing_name_lower not in ingredient_locations:
                ingredient_locations[ing_name_lower] = []
            
            ingredient_locations[ing_name_lower].append((type_name, ing_name))
    
    # Find duplicates
    for ing_name_lower, locations in ingredient_locations.items():
        if len(locations) > 1:
            # Found a duplicate
            file_names = [loc[0] for loc in locations]
            original_names = [loc[1] for loc in locations]
            duplicates_found.append({
                'name': original_names[0],  # Use first occurrence as canonical name
                'name_lower': ing_name_lower,
                'files': file_names,
                'all_names': original_names
            })
    
    if duplicates_found:
        print(f"\n  ✗ Found {len(duplicates_found)} duplicate ingredient(s):\n")
        for dup in duplicates_found:
            print(f"    '{dup['name']}' appears in:")
            for file_name in dup['files']:
                print(f"      - {file_name}.txt")
            # Check if the names differ (case differences)
            unique_names = set(dup['all_names'])
            if len(unique_names) > 1:
                print(f"      Note: Name variations found: {', '.join(repr(n) for n in unique_names)}")
            print()
        print("  Please remove duplicates before proceeding.")
        return False
    else:
        print(f"\n  ✓ No duplicates found ({len(ingredient_locations)} unique ingredients across {len(ingredient_files)} files)")
        return True


def reset_database(db):
    """Delete all existing data (recipes, articles, ingredients, tags, types, subtags)."""
    print("Resetting database...")
    
    # Delete in order to respect foreign key constraints
    # Start with junction tables and association objects
    from models import (
        RecipeIngredient, recipe_tags, article_tags,
        recipe_secondary_ingredients, recipe_clashing_ingredients,
        recipe_want_to_try_ingredients
    )
    db.execute(delete(RecipeIngredient))
    db.execute(recipe_tags.delete())
    db.execute(article_tags.delete())
    db.execute(recipe_secondary_ingredients.delete())
    db.execute(recipe_clashing_ingredients.delete())
    db.execute(recipe_want_to_try_ingredients.delete())
    
    # Then delete main entities
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


def bootload_recipes(db, recipes_dir: Path) -> int:
    """Load all recipes from basics/recipes/ folder."""
    print("\n" + "="*70)
    print("Loading Recipes")
    print("="*70)
    
    recipe_files = sorted(recipes_dir.glob('*.json'))
    
    if not recipe_files:
        print("  ✗ No recipe files found")
        return 0
    
    total_recipe_files = len(recipe_files)
    total_recipes = 0
    failed_recipes = 0
    
    for json_path in recipe_files:
        try:
            # Read JSON file
            with open(json_path, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
            
            if not json_data:
                print(f"\n  {json_path.name}: (empty file, skipped)")
                failed_recipes += 1
                continue
            
            # Validate required fields
            name = json_data.get('name', '').strip()
            if not name:
                print(f"\n  {json_path.name}: (missing name, skipped)")
                failed_recipes += 1
                continue
            
            # Check if recipe already exists - if so, delete it and recreate to ensure it matches JSON
            existing = get_recipe(db, name=name)
            if existing:
                # Silently delete and recreate - only print if there's an error
                from db_operations import delete_recipe
                delete_recipe(db, recipe_id=existing.id)
            
            # Get ingredients and tags from JSON
            ingredients = json_data.get('ingredients', [])
            tags = json_data.get('tags', [])
            
            # Validate ingredients exist
            from db_operations import get_ingredient
            missing_ingredients = []
            for ing_name in ingredients:
                if not get_ingredient(db, name=ing_name):
                    missing_ingredients.append(ing_name)
            
            if missing_ingredients:
                print(f"\n  {json_path.name}: {name}")
                print(f"    ✗ Missing ingredients: {', '.join(missing_ingredients)}")
                failed_recipes += 1
                continue
            
            # Validate tags exist
            from db_operations import get_tag
            missing_tags = []
            for tag_name in tags:
                if not get_tag(db, name=tag_name):
                    missing_tags.append(tag_name)
            
            if missing_tags:
                print(f"\n  {json_path.name}: {name}")
                print(f"    ✗ Missing tags: {', '.join(missing_tags)}")
                failed_recipes += 1
                continue
            
            # Add recipe
            recipe = add_recipe(
                db,
                name=name,
                instructions=json_data.get('instructions'),
                notes=json_data.get('notes'),
                ingredients=ingredients,
                tags=tags
            )
            
            # Add secondary_ingredients if provided
            secondary_ingredients = json_data.get('secondary_ingredients', [])
            if secondary_ingredients:
                from db_operations import add_secondary_ingredients_to_recipe, get_ingredient
                # Validate secondary ingredients exist
                missing_secondary = []
                for ing_name in secondary_ingredients:
                    if not get_ingredient(db, name=ing_name):
                        missing_secondary.append(ing_name)
                
                if missing_secondary:
                    print(f"\n  {json_path.name}: {name}")
                    print(f"    ✗ Missing secondary ingredients: {', '.join(missing_secondary)}")
                    failed_recipes += 1
                    continue
                
                add_secondary_ingredients_to_recipe(db, recipe_id=recipe.id, ingredient_names=secondary_ingredients)
            
            # Add clashing_ingredients if provided
            clashing_ingredients = json_data.get('clashing_ingredients', [])
            if clashing_ingredients:
                from db_operations import add_clashing_ingredients_to_recipe
                # Validate clashing ingredients exist
                missing_clashing = []
                for ing_name in clashing_ingredients:
                    if not get_ingredient(db, name=ing_name):
                        missing_clashing.append(ing_name)
                
                if missing_clashing:
                    print(f"\n  {json_path.name}: {name}")
                    print(f"    ✗ Missing clashing ingredients: {', '.join(missing_clashing)}")
                    failed_recipes += 1
                    continue
                
                add_clashing_ingredients_to_recipe(db, recipe_id=recipe.id, ingredient_names=clashing_ingredients)
            
            # Add want_to_try_ingredients if provided
            want_to_try_ingredients = json_data.get('want_to_try', [])
            if want_to_try_ingredients:
                from db_operations import add_want_to_try_ingredients_to_recipe
                # Validate want to try ingredients exist
                missing_want_to_try = []
                for ing_name in want_to_try_ingredients:
                    if not get_ingredient(db, name=ing_name):
                        missing_want_to_try.append(ing_name)
                
                if missing_want_to_try:
                    print(f"\n  {json_path.name}: {name}")
                    print(f"    ✗ Missing want_to_try ingredients: {', '.join(missing_want_to_try)}")
                    failed_recipes += 1
                    continue
                
                add_want_to_try_ingredients_to_recipe(db, recipe_id=recipe.id, ingredient_names=want_to_try_ingredients)
            
            # Only print failures, not successes
            total_recipes += 1
            
        except ValueError as e:
            print(f"\n  {json_path.name}:")
            print(f"    ✗ Error: {e}")
            failed_recipes += 1
        except Exception as e:
            print(f"\n  {json_path.name}:")
            print(f"    ✗ Unexpected error: {e}")
            failed_recipes += 1
    
    print(f"\n  {total_recipes} of {total_recipe_files} recipe request(s) added successfully")
    if failed_recipes > 0:
        print(f"  ({failed_recipes} recipe(s) failed to load)")
    
    return total_recipes


def verify_recipes(db, recipes_dir: Path):
    """Verify all recipes in database match their JSON files."""
    print("\n" + "="*70)
    print("Verifying Recipes")
    print("="*70)
    
    # Get all recipes from database
    from db_operations import list_recipes
    all_recipes = list_recipes(db)
    
    if not all_recipes:
        print("  No recipes in database to verify")
        return
    
    # Get all JSON files
    json_files = {f.stem: f for f in recipes_dir.glob('*.json')}
    
    issues_found = []
    verified_count = 0
    
    for recipe in all_recipes:
        if not recipe:
            continue
        
        # Find matching JSON file (by normalized name)
        normalized_name = recipe.name.lower().replace(' ', '-')
        json_path = None
        
        # Try to find matching JSON file
        for json_stem, json_file in json_files.items():
            # Normalize JSON filename for comparison
            json_normalized = json_stem.replace('-', ' ').lower()
            recipe_normalized = recipe.name.lower()
            if json_normalized == recipe_normalized:
                json_path = json_file
                break
        
        if not json_path:
            issues_found.append({
                'recipe_id': recipe.id,
                'recipe_name': recipe.name,
                'issue': 'No matching JSON file found'
            })
            continue
        
        # Read JSON file
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
        except Exception as e:
            issues_found.append({
                'recipe_id': recipe.id,
                'recipe_name': recipe.name,
                'issue': f'Error reading JSON file: {e}'
            })
            continue
        
        # Compare recipe with JSON
        json_name = json_data.get('name', '').strip().lower()
        recipe_name_normalized = recipe.name.lower()
        
        if json_name != recipe_name_normalized:
            issues_found.append({
                'recipe_id': recipe.id,
                'recipe_name': recipe.name,
                'json_name': json_data.get('name', ''),
                'issue': 'Name mismatch'
            })
            continue
        
        # Compare ingredients
        json_ingredients = set(ing.lower() for ing in json_data.get('ingredients', []))
        recipe_ingredients = set(ing.name.lower() for ing in recipe.ingredients if ing and ing.name)
        
        if json_ingredients != recipe_ingredients:
            missing = json_ingredients - recipe_ingredients
            extra = recipe_ingredients - json_ingredients
            issues_found.append({
                'recipe_id': recipe.id,
                'recipe_name': recipe.name,
                'issue': 'Ingredient mismatch',
                'missing': list(missing),
                'extra': list(extra)
            })
            continue
        
        # Compare tags
        json_tags = set(tag.lower() for tag in json_data.get('tags', []))
        recipe_tags = set(tag.name.lower() for tag in recipe.tags if tag and tag.name)
        
        if json_tags != recipe_tags:
            missing = json_tags - recipe_tags
            extra = recipe_tags - json_tags
            issues_found.append({
                'recipe_id': recipe.id,
                'recipe_name': recipe.name,
                'issue': 'Tag mismatch',
                'missing': list(missing),
                'extra': list(extra)
            })
            continue
        
        # Compare secondary_ingredients
        json_secondary = set(ing.lower() for ing in json_data.get('secondary_ingredients', []))
        recipe_secondary = set(ing.name.lower() for ing in recipe.secondary_ingredients if ing and ing.name)
        
        if json_secondary != recipe_secondary:
            missing = json_secondary - recipe_secondary
            extra = recipe_secondary - json_secondary
            issues_found.append({
                'recipe_id': recipe.id,
                'recipe_name': recipe.name,
                'issue': 'Secondary ingredient mismatch',
                'missing': list(missing),
                'extra': list(extra)
            })
            continue
        
        # Compare clashing_ingredients
        json_clashing = set(ing.lower() for ing in json_data.get('clashing_ingredients', []))
        recipe_clashing = set(ing.name.lower() for ing in recipe.clashing_ingredients if ing and ing.name)
        
        if json_clashing != recipe_clashing:
            missing = json_clashing - recipe_clashing
            extra = recipe_clashing - json_clashing
            issues_found.append({
                'recipe_id': recipe.id,
                'recipe_name': recipe.name,
                'issue': 'Clashing ingredient mismatch',
                'missing': list(missing),
                'extra': list(extra)
            })
            continue
        
        # Compare want_to_try_ingredients
        json_want_to_try = set(ing.lower() for ing in json_data.get('want_to_try', []))
        recipe_want_to_try = set(ing.name.lower() for ing in recipe.want_to_try_ingredients if ing and ing.name)
        
        if json_want_to_try != recipe_want_to_try:
            missing = json_want_to_try - recipe_want_to_try
            extra = recipe_want_to_try - json_want_to_try
            issues_found.append({
                'recipe_id': recipe.id,
                'recipe_name': recipe.name,
                'issue': 'Want to try ingredient mismatch',
                'missing': list(missing),
                'extra': list(extra)
            })
            continue
        
        verified_count += 1
    
    total_recipes_in_db = len(all_recipes)
    
    if issues_found:
        print(f"\n  ✗ Found {len(issues_found)} verification issue(s):")
        for issue in issues_found:
            print(f"\n    Recipe #{issue['recipe_id']}: {issue['recipe_name']}")
            print(f"      Issue: {issue['issue']}")
            if 'missing' in issue:
                if issue['missing']:
                    print(f"      Missing from database: {', '.join(issue['missing'])}")
                if issue.get('extra'):
                    print(f"      Extra in database: {', '.join(issue['extra'])}")
        print(f"\n  {verified_count}/{total_recipes_in_db} recipe(s) verified successfully")
        print()
    else:
        print(f"\n  ✓ {verified_count}/{total_recipes_in_db} recipe(s) verified successfully!")
        print()


def main():
    """Main bootload function."""
    print("="*70)
    print("BOOTLOAD: Initializing Database")
    print("="*70)
    
    # Get paths
    project_root = Path(__file__).parent
    ingredients_dir = project_root / 'basics' / 'ingredients'
    tags_dir = project_root / 'basics' / 'tags'
    recipes_dir = project_root / 'basics' / 'recipes'
    
    # Check directories exist
    if not ingredients_dir.exists():
        print(f"✗ Error: {ingredients_dir} does not exist")
        sys.exit(1)
    
    if not tags_dir.exists():
        print(f"✗ Error: {tags_dir} does not exist")
        sys.exit(1)
    
    # Recipes directory is optional
    if not recipes_dir.exists():
        recipes_dir.mkdir(parents=True, exist_ok=True)
    
    # Preflight check: verify no duplicate ingredients
    if not preflight_check_ingredients(ingredients_dir):
        print("\n✗ Preflight check failed. Please fix duplicate ingredients and try again.")
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
        
        # Load ingredients (must be first - recipes depend on ingredients)
        bootload_ingredients(db, ingredients_dir)
        db.commit()  # Ensure ingredients are committed before loading tags/recipes
        
        # Load tags (must be second - recipes depend on tags)
        bootload_tags(db, tags_dir)
        db.commit()  # Ensure tags are committed before loading recipes
        
        # Load recipes (must be last - depends on ingredients and tags)
        bootload_recipes(db, recipes_dir)
        db.commit()  # Ensure recipes are committed
        
        # Verify all recipes match their JSON files
        verify_recipes(db, recipes_dir)
        
        print("\n" + "="*70)
        print("BOOTLOAD COMPLETE")
        print("="*70)
        print("\nDatabase initialized with:")
        print("  - Ingredients (from basics/ingredients/)")
        print("  - Tags (from basics/tags/)")
        print("  - Recipes (from basics/recipes/)")
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
