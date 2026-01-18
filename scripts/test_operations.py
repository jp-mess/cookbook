#!/usr/bin/env python3
"""
Randomized test script to exercise add/remove operations and check consistency.
This will help identify bugs that cause data corruption.
"""

import sys
import random
import json
from pathlib import Path
from typing import List, Dict, Optional

# Add scripts directory to path
scripts_dir = Path(__file__).parent
sys.path.insert(0, str(scripts_dir))

from database import SessionLocal
from db_operations import (
    add_ingredient, add_recipe, delete_ingredient, delete_recipe,
    get_ingredient, get_recipe, list_ingredients, list_recipes,
    add_ingredient_type, add_tag, get_ingredient_type, get_tag
)
from json_editor import (
    export_new_ingredient_template, export_new_recipe_template,
    import_new_ingredient_from_json, import_new_recipe_from_json,
    export_ingredient_to_json, export_recipe_to_json,
    import_ingredient_from_json, import_recipe_from_json
)
# Staging directory paths are handled by json_editor functions

# Test data
INGREDIENT_NAMES = [
    "tomato", "basil", "onion", "garlic", "olive oil", "salt", "pepper",
    "chicken", "beef", "pork", "fish", "shrimp", "egg", "milk", "cheese",
    "flour", "sugar", "butter", "cream", "yogurt", "rice", "pasta",
    "potato", "carrot", "celery", "bell pepper", "mushroom", "spinach",
    "lettuce", "cucumber", "avocado", "lemon", "lime", "orange"
]

INGREDIENT_TYPES = ["vegetable", "meat", "dairy", "herb", "spice", "grain", "fruit", "other"]

RECIPE_NAMES = [
    "pasta with tomato sauce", "chicken salad", "beef stew", "fish curry",
    "vegetable soup", "rice bowl", "stir fry", "roasted vegetables",
    "grilled chicken", "pasta salad", "soup", "stew", "curry", "salad"
]

TAGS = ["italian", "french", "indian", "mexican", "american", "asian", "spicy", "mild", "vegetarian", "vegan"]

def setup_test_data(db):
    """Set up basic test data (types and tags)."""
    print("Setting up test data...")
    
    # Add ingredient types
    for type_name in INGREDIENT_TYPES:
        try:
            add_ingredient_type(db, type_name)
        except ValueError:
            pass  # Already exists
    
    # Add tags
    for tag_name in TAGS:
        try:
            add_tag(db, tag_name)
        except ValueError:
            pass  # Already exists
    
    print(f"  ✓ Added {len(INGREDIENT_TYPES)} types and {len(TAGS)} tags")

def check_consistency(db) -> List[str]:
    """Check database consistency and return list of errors."""
    errors = []
    
    # Check all recipes have valid ingredients
    recipes = list_recipes(db)
    for recipe in recipes:
        if not recipe:
            continue
        for ingredient in recipe.ingredients:
            if not ingredient:
                errors.append(f"Recipe {recipe.id} ({recipe.name}) has NULL ingredient")
                continue
            # Verify ingredient exists
            found = get_ingredient(db, ingredient_id=ingredient.id)
            if not found:
                errors.append(f"Recipe {recipe.id} ({recipe.name}) references non-existent ingredient {ingredient.id}")
    
    # Check all ingredients are referenced correctly
    ingredients = list_ingredients(db)
    for ingredient in ingredients:
        if not ingredient:
            continue
        # Check type exists if set
        if ingredient.type_id:
            type_obj = get_ingredient_type(db, type_id=ingredient.type_id)
            if not type_obj:
                errors.append(f"Ingredient {ingredient.id} ({ingredient.name}) references non-existent type {ingredient.type_id}")
    
    return errors

def random_add_ingredient(db) -> Optional[int]:
    """Randomly add an ingredient."""
    name = random.choice(INGREDIENT_NAMES)
    # Add random number to make unique
    name = f"{name} {random.randint(1, 10000)}"
    type_name = random.choice(INGREDIENT_TYPES)
    
    try:
        ingredient = add_ingredient(db, name=name, type_name=type_name)
        return ingredient.id
    except Exception as e:
        print(f"  ✗ Failed to add ingredient '{name}': {e}")
        return None

def random_add_recipe(db, available_ingredients: List[int]) -> Optional[int]:
    """Randomly add a recipe."""
    if len(available_ingredients) < 2:
        return None  # Need at least 2 ingredients
    
    name = random.choice(RECIPE_NAMES)
    name = f"{name} {random.randint(1, 10000)}"
    
    # Pick 2-5 random ingredients
    num_ingredients = random.randint(2, min(5, len(available_ingredients)))
    selected_ingredients = random.sample(available_ingredients, num_ingredients)
    
    ingredient_names = []
    for ing_id in selected_ingredients:
        ing = get_ingredient(db, ingredient_id=ing_id)
        if ing:
            ingredient_names.append(ing.name)
    
    if not ingredient_names:
        return None
    
    try:
        recipe = add_recipe(
            db,
            name=name,
            instructions=f"Instructions for {name}",
            ingredients=ingredient_names
        )
        return recipe.id
    except Exception as e:
        print(f"  ✗ Failed to add recipe '{name}': {e}")
        return None

def random_edit_ingredient_via_json(db, ingredient_id: int) -> bool:
    """Randomly edit an ingredient via JSON workflow."""
    try:
        # Export to JSON
        json_path = export_ingredient_to_json(ingredient_id)
        if not json_path.exists():
            return False
        
        # Read and modify
        with open(json_path, 'r') as f:
            data = json.load(f)
        
        # Randomly modify name or notes
        if random.random() < 0.5:
            data['name'] = f"{data['name']} (edited)"
        else:
            data['notes'] = f"Test note {random.randint(1, 1000)}"
        
        # Write back
        with open(json_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        # Import back
        import_ingredient_from_json(ingredient_id)
        return True
    except Exception as e:
        print(f"  ✗ Failed to edit ingredient {ingredient_id}: {e}")
        return False

def random_edit_recipe_via_json(db, recipe_id: int, available_ingredients: List[int]) -> bool:
    """Randomly edit a recipe via JSON workflow."""
    try:
        # Export to JSON
        json_path = export_recipe_to_json(recipe_id)
        if not json_path.exists():
            return False
        
        # Read and modify
        with open(json_path, 'r') as f:
            data = json.load(f)
        
        # Randomly modify ingredients (add or remove one)
        if data['ingredients'] and random.random() < 0.5:
            # Remove one ingredient
            data['ingredients'].pop()
        elif available_ingredients:
            # Add one ingredient
            new_ing_id = random.choice(available_ingredients)
            new_ing = get_ingredient(db, ingredient_id=new_ing_id)
            if new_ing and new_ing.name not in data['ingredients']:
                data['ingredients'].append(new_ing.name)
        
        # Write back
        with open(json_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        # Import back
        import_recipe_from_json(recipe_id)
        return True
    except Exception as e:
        print(f"  ✗ Failed to edit recipe {recipe_id}: {e}")
        return False

def random_delete_ingredient(db, ingredient_id: int) -> bool:
    """Randomly delete an ingredient."""
    try:
        ingredient = get_ingredient(db, ingredient_id=ingredient_id)
        if not ingredient:
            return False
        delete_ingredient(db, ingredient_id=ingredient_id)
        return True
    except Exception as e:
        print(f"  ✗ Failed to delete ingredient {ingredient_id}: {e}")
        return False

def random_delete_recipe(db, recipe_id: int) -> bool:
    """Randomly delete a recipe."""
    try:
        recipe = get_recipe(db, recipe_id=recipe_id)
        if not recipe:
            return False
        delete_recipe(db, recipe_id=recipe_id)
        return True
    except Exception as e:
        print(f"  ✗ Failed to delete recipe {recipe_id}: {e}")
        return False

def run_test_iterations(num_iterations: int = 100):
    """Run random test operations for specified number of iterations."""
    print("=" * 70)
    print(f"Randomized Test Suite ({num_iterations} iterations)")
    print("=" * 70)
    print()
    
    db = SessionLocal()
    try:
        # Setup
        setup_test_data(db)
        
        # Track created items
        ingredient_ids = []
        recipe_ids = []
        
        # Statistics
        stats = {
            'ingredients_added': 0,
            'ingredients_deleted': 0,
            'ingredients_edited': 0,
            'recipes_added': 0,
            'recipes_deleted': 0,
            'recipes_edited': 0,
            'consistency_errors': 0,
            'operations_failed': 0
        }
        
        for iteration in range(1, num_iterations + 1):
            if iteration % 10 == 0:
                print(f"\nIteration {iteration}/{num_iterations}...")
            
            # Choose random operation (weighted towards adds to build up data)
            if len(ingredient_ids) < 5:
                # Need more ingredients first
                operation = 'add_ingredient'
            elif len(recipe_ids) < 3:
                # Need more recipes
                operation = random.choice(['add_ingredient', 'add_recipe'])
            else:
                # Full range of operations
                operation = random.choice([
                    'add_ingredient',
                    'add_recipe',
                    'edit_ingredient',
                    'edit_recipe',
                    'delete_ingredient',
                    'delete_recipe'
                ])
            
            try:
                if operation == 'add_ingredient':
                    ing_id = random_add_ingredient(db)
                    if ing_id:
                        ingredient_ids.append(ing_id)
                        stats['ingredients_added'] += 1
                
                elif operation == 'add_recipe' and ingredient_ids:
                    recipe_id = random_add_recipe(db, ingredient_ids)
                    if recipe_id:
                        recipe_ids.append(recipe_id)
                        stats['recipes_added'] += 1
                
                elif operation == 'edit_ingredient' and ingredient_ids:
                    ing_id = random.choice(ingredient_ids)
                    if random_edit_ingredient_via_json(db, ing_id):
                        stats['ingredients_edited'] += 1
                
                elif operation == 'edit_recipe' and recipe_ids and ingredient_ids:
                    recipe_id = random.choice(recipe_ids)
                    if random_edit_recipe_via_json(db, recipe_id, ingredient_ids):
                        stats['recipes_edited'] += 1
                
                elif operation == 'delete_ingredient' and ingredient_ids:
                    ing_id = random.choice(ingredient_ids)
                    if random_delete_ingredient(db, ing_id):
                        ingredient_ids.remove(ing_id)
                        stats['ingredients_deleted'] += 1
                
                elif operation == 'delete_recipe' and recipe_ids:
                    recipe_id = random.choice(recipe_ids)
                    if random_delete_recipe(db, recipe_id):
                        recipe_ids.remove(recipe_id)
                        stats['recipes_deleted'] += 1
                
            except Exception as e:
                stats['operations_failed'] += 1
                print(f"  ✗ Operation '{operation}' failed: {e}")
            
            # Check consistency every 10 iterations
            if iteration % 10 == 0:
                errors = check_consistency(db)
                if errors:
                    stats['consistency_errors'] += len(errors)
                    print(f"  ⚠️  Found {len(errors)} consistency error(s):")
                    for error in errors[:5]:  # Show first 5
                        print(f"     - {error}")
                    if len(errors) > 5:
                        print(f"     ... and {len(errors) - 5} more")
        
        # Final consistency check
        print("\n" + "=" * 70)
        print("Final Consistency Check")
        print("=" * 70)
        errors = check_consistency(db)
        if errors:
            print(f"\n✗ Found {len(errors)} consistency error(s):")
            for error in errors:
                print(f"  - {error}")
        else:
            print("\n✓ No consistency errors found!")
        
        # Print statistics
        print("\n" + "=" * 70)
        print("Test Statistics")
        print("=" * 70)
        print(f"Ingredients: {stats['ingredients_added']} added, {stats['ingredients_deleted']} deleted, {stats['ingredients_edited']} edited")
        print(f"Recipes: {stats['recipes_added']} added, {stats['recipes_deleted']} deleted, {stats['recipes_edited']} edited")
        print(f"Operations failed: {stats['operations_failed']}")
        print(f"Consistency errors: {len(errors)}")
        print("=" * 70)
        
        return len(errors) == 0
        
    finally:
        db.close()

if __name__ == "__main__":
    num_iterations = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    success = run_test_iterations(num_iterations)
    sys.exit(0 if success else 1)
