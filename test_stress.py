#!/usr/bin/env python3
"""
Stress test for the cookbook database system.
Creates a recipe, performs many random operations, then verifies the recipe is still intact.
"""
import sys
import random
from pathlib import Path

# Add scripts directory to path
scripts_dir = Path(__file__).parent / 'scripts'
if str(scripts_dir) not in sys.path:
    sys.path.insert(0, str(scripts_dir))

from database import SessionLocal
from db_operations import (
    add_recipe, get_recipe, delete_recipe, list_recipes, update_recipe,
    add_ingredient, get_ingredient, delete_ingredient, list_ingredients, update_ingredient,
    add_tag, get_tag, delete_tag, list_tags, update_tag,
    add_ingredient_type, get_ingredient_type, delete_ingredient_type, list_ingredient_types, update_ingredient_type,
    add_subtag, get_subtag, delete_subtag, list_subtags, update_subtag,
    add_tags_to_recipe, remove_tags_from_recipe,
    add_ingredients_to_recipe, remove_ingredients_from_recipe
)
from models import Article


class RecipeSnapshot:
    """Stores a snapshot of a recipe for later verification."""
    def __init__(self, recipe):
        self.recipe_id = recipe.id
        self.name = recipe.name
        self.instructions = recipe.instructions
        self.notes = recipe.notes
        self.ingredient_names = sorted([ing.name for ing in recipe.ingredients])
        self.tag_names = sorted([tag.name for tag in recipe.tags])
    
    def verify(self, recipe):
        """Verify that a recipe matches this snapshot."""
        assert recipe.id == self.recipe_id, f"Recipe ID mismatch: {recipe.id} != {self.recipe_id}"
        assert recipe.name == self.name, f"Recipe name mismatch: {recipe.name} != {self.name}"
        assert recipe.instructions == self.instructions, f"Instructions mismatch"
        assert recipe.notes == self.notes, f"Notes mismatch"
        
        current_ingredients = sorted([ing.name for ing in recipe.ingredients])
        assert current_ingredients == self.ingredient_names, \
            f"Ingredients mismatch: {current_ingredients} != {self.ingredient_names}"
        
        current_tags = sorted([tag.name for tag in recipe.tags])
        assert current_tags == self.tag_names, \
            f"Tags mismatch: {current_tags} != {self.tag_names}"
        
        return True


def get_random_ingredients(db, count=3, exclude_names=None):
    """Get random ingredients from the database."""
    all_ingredients = list_ingredients(db)
    if exclude_names:
        all_ingredients = [ing for ing in all_ingredients if ing and ing.name not in exclude_names]
    else:
        all_ingredients = [ing for ing in all_ingredients if ing]
    
    if not all_ingredients:
        return []
    
    return random.sample(all_ingredients, min(count, len(all_ingredients)))


def get_random_tags(db, count=2, exclude_names=None):
    """Get random tags from the database."""
    all_tags = list_tags(db)
    if exclude_names:
        all_tags = [tag for tag in all_tags if tag and tag.name not in exclude_names]
    else:
        all_tags = [tag for tag in all_tags if tag]
    
    if not all_tags:
        return []
    
    return random.sample(all_tags, min(count, len(all_tags)))


def run_consistency_check(db):
    """Run consistency check and return True if no issues found."""
    from db_operations import list_recipes, list_ingredients, list_tags, list_ingredient_types, list_subtags
    
    all_recipes = list_recipes(db)
    all_ingredients = list_ingredients(db)
    all_tags = list_tags(db)
    all_types = list_ingredient_types(db)
    all_subtags = list_subtags(db)
    
    # Create sets for quick lookup
    ingredient_names = {ing.name.lower() for ing in all_ingredients if ing}
    tag_ids = {tag.id for tag in all_tags}
    type_ids = {t.id for t in all_types}
    subtag_ids = {st.id for st in all_subtags}
    
    issues_found = []
    
    # Check recipe ingredients
    for recipe in all_recipes:
        if not recipe:
            continue
        for ingredient in recipe.ingredients:
            if not ingredient:
                continue
            if ingredient.name.lower() not in ingredient_names:
                issues_found.append({
                    'type': 'recipe_ingredient',
                    'recipe_id': recipe.id,
                    'recipe_name': recipe.name,
                    'ingredient_name': ingredient.name
                })
    
    # Check recipe tags
    for recipe in all_recipes:
        if not recipe:
            continue
        for tag in recipe.tags:
            if not tag:
                continue
            if tag.id not in tag_ids:
                issues_found.append({
                    'type': 'recipe_tag',
                    'recipe_id': recipe.id,
                    'recipe_name': recipe.name,
                    'tag_id': tag.id,
                    'tag_name': tag.name
                })
    
    # Check ingredient types
    for ingredient in all_ingredients:
        if not ingredient:
            continue
        if ingredient.type and ingredient.type.id not in type_ids:
            issues_found.append({
                'type': 'ingredient_type',
                'ingredient_id': ingredient.id,
                'ingredient_name': ingredient.name,
                'type_id': ingredient.type.id,
                'type_name': ingredient.type.name if ingredient.type else 'unknown'
            })
    
    # Check tag subtags
    for tag in all_tags:
        if not tag:
            continue
        if tag.subtag and tag.subtag.id not in subtag_ids:
            issues_found.append({
                'type': 'tag_subtag',
                'tag_id': tag.id,
                'tag_name': tag.name,
                'subtag_id': tag.subtag.id,
                'subtag_name': tag.subtag.name if tag.subtag else 'unknown'
            })
    
    # Check articles
    all_articles = db.query(Article).all()
    for article in all_articles:
        if not article:
            continue
        for tag in article.tags:
            if not tag:
                continue
            if tag.id not in tag_ids:
                issues_found.append({
                    'type': 'article_tag',
                    'article_id': article.id,
                    'tag_id': tag.id,
                    'tag_name': tag.name
                })
    
    if issues_found:
        print(f"  Found {len(issues_found)} consistency issue(s):")
        for issue in issues_found[:10]:  # Show first 10
            print(f"    - {issue['type']}: {issue}")
        if len(issues_found) > 10:
            print(f"    ... and {len(issues_found) - 10} more")
        return False
    
    return True


def random_operation(db, created_items, operation_counts):
    """Perform a random database operation."""
    operation = random.choice([
        'add_ingredient',
        'delete_ingredient',
        'update_ingredient',
        'add_tag',
        'delete_tag',
        'update_tag',
        'add_type',
        'delete_type',
        'update_type',
        'add_subtag',
        'delete_subtag',
        'update_subtag',
        'add_recipe',
        'delete_recipe',
        'update_recipe',
    ])
    
    try:
        if operation == 'add_ingredient':
            # Add a random ingredient with a random type
            types = list_ingredient_types(db)
            type_name = random.choice(types).name if types else None
            name = f"test_ingredient_{random.randint(10000, 99999)}"
            ing = add_ingredient(db, name=name, type_name=type_name)
            created_items['ingredients'].append(ing.id)
            operation_counts['add_ingredient'] = operation_counts.get('add_ingredient', 0) + 1
            return f"Added ingredient: {name}"
        
        elif operation == 'delete_ingredient':
            # Delete a random ingredient (not used in our test recipe)
            ingredients = list_ingredients(db)
            if ingredients:
                ing = random.choice([ing for ing in ingredients if ing])
                # Don't delete ingredients used in our test recipes
                if ing.id not in created_items.get('protected_ingredients', []):
                    delete_ingredient(db, ingredient_id=ing.id)
                    if ing.id in created_items['ingredients']:
                        created_items['ingredients'].remove(ing.id)
                    operation_counts['delete_ingredient'] = operation_counts.get('delete_ingredient', 0) + 1
                    return f"Deleted ingredient: {ing.name}"
            return "No ingredients to delete"
        
        elif operation == 'update_ingredient':
            # Update a random ingredient
            ingredients = list_ingredients(db)
            if ingredients:
                ing = random.choice([ing for ing in ingredients if ing])
                # Don't modify protected ingredients
                if ing.id not in created_items.get('protected_ingredients', []):
                    new_notes = f"Updated notes {random.randint(1, 1000)}"
                    update_ingredient(db, ingredient_id=ing.id, notes=new_notes)
                    operation_counts['update_ingredient'] = operation_counts.get('update_ingredient', 0) + 1
                    return f"Updated ingredient: {ing.name}"
            return "No ingredients to update"
        
        elif operation == 'add_tag':
            # Add a random tag with a random subtag
            subtags = list_subtags(db)
            subtag_name = random.choice(subtags).name if subtags else None
            name = f"test_tag_{random.randint(10000, 99999)}"
            tag = add_tag(db, name=name, subtag_name=subtag_name)
            created_items['tags'].append(tag.id)
            operation_counts['add_tag'] = operation_counts.get('add_tag', 0) + 1
            return f"Added tag: {name}"
        
        elif operation == 'delete_tag':
            # Delete a random tag (not used in our test recipe)
            tags = list_tags(db)
            if tags:
                tag = random.choice([tag for tag in tags if tag])
                # Don't delete tags used in our test recipes
                if tag.id not in created_items.get('protected_tags', []):
                    delete_tag(db, tag_id=tag.id)
                    if tag.id in created_items['tags']:
                        created_items['tags'].remove(tag.id)
                    operation_counts['delete_tag'] = operation_counts.get('delete_tag', 0) + 1
                    return f"Deleted tag: {tag.name}"
            return "No tags to delete"
        
        elif operation == 'update_tag':
            # Update a random tag
            tags = list_tags(db)
            if tags:
                tag = random.choice([tag for tag in tags if tag])
                # Don't modify protected tags
                if tag.id not in created_items.get('protected_tags', []):
                    new_name = f"updated_tag_{random.randint(10000, 99999)}"
                    update_tag(db, tag_id=tag.id, new_name=new_name)
                    operation_counts['update_tag'] = operation_counts.get('update_tag', 0) + 1
                    return f"Updated tag: {tag.name} -> {new_name}"
            return "No tags to update"
        
        elif operation == 'add_type':
            name = f"test_type_{random.randint(10000, 99999)}"
            type_obj = add_ingredient_type(db, name=name)
            created_items['types'].append(type_obj.id)
            operation_counts['add_type'] = operation_counts.get('add_type', 0) + 1
            return f"Added type: {name}"
        
        elif operation == 'delete_type':
            types = list_ingredient_types(db)
            if types:
                type_obj = random.choice(types)
                # Only delete if no ingredients use it
                if not type_obj.ingredients:
                    delete_ingredient_type(db, type_id=type_obj.id)
                    if type_obj.id in created_items['types']:
                        created_items['types'].remove(type_obj.id)
                    operation_counts['delete_type'] = operation_counts.get('delete_type', 0) + 1
                    return f"Deleted type: {type_obj.name}"
            return "No types to delete"
        
        elif operation == 'update_type':
            # Update a random type
            types = list_ingredient_types(db)
            if types:
                type_obj = random.choice(types)
                new_name = f"updated_type_{random.randint(10000, 99999)}"
                update_ingredient_type(db, type_id=type_obj.id, new_name=new_name)
                operation_counts['update_type'] = operation_counts.get('update_type', 0) + 1
                return f"Updated type: {type_obj.name} -> {new_name}"
            return "No types to update"
        
        elif operation == 'add_subtag':
            name = f"test_subtag_{random.randint(10000, 99999)}"
            subtag = add_subtag(db, name=name)
            created_items['subtags'].append(subtag.id)
            operation_counts['add_subtag'] = operation_counts.get('add_subtag', 0) + 1
            return f"Added subtag: {name}"
        
        elif operation == 'delete_subtag':
            subtags = list_subtags(db)
            if subtags:
                subtag = random.choice(subtags)
                # Only delete if no tags use it
                if not subtag.tags:
                    delete_subtag(db, subtag_id=subtag.id)
                    if subtag.id in created_items['subtags']:
                        created_items['subtags'].remove(subtag.id)
                    operation_counts['delete_subtag'] = operation_counts.get('delete_subtag', 0) + 1
                    return f"Deleted subtag: {subtag.name}"
            return "No subtags to delete"
        
        elif operation == 'update_subtag':
            # Update a random subtag
            subtags = list_subtags(db)
            if subtags:
                subtag = random.choice(subtags)
                new_name = f"updated_subtag_{random.randint(10000, 99999)}"
                update_subtag(db, subtag_id=subtag.id, new_name=new_name)
                operation_counts['update_subtag'] = operation_counts.get('update_subtag', 0) + 1
                return f"Updated subtag: {subtag.name} -> {new_name}"
            return "No subtags to update"
        
        elif operation == 'add_recipe':
            # Add a random recipe
            ingredients = get_random_ingredients(db, count=random.randint(2, 5))
            tags = get_random_tags(db, count=random.randint(1, 3))
            name = f"test_recipe_{random.randint(10000, 99999)}"
            recipe = add_recipe(
                db,
                name=name,
                instructions=f"Test instructions for {name}",
                notes=f"Test notes for {name}",
                ingredients=[ing.name for ing in ingredients],
                tags=[tag.name for tag in tags] if tags else None
            )
            created_items['recipes'].append(recipe.id)
            operation_counts['add_recipe'] = operation_counts.get('add_recipe', 0) + 1
            return f"Added recipe: {name}"
        
        elif operation == 'delete_recipe':
            # Delete a random recipe (not our test recipe)
            recipes = list_recipes(db)
            if recipes:
                recipe = random.choice([r for r in recipes if r])
                # Don't delete our test recipe
                if recipe.id not in created_items.get('protected_recipes', []):
                    delete_recipe(db, recipe_id=recipe.id)
                    if recipe.id in created_items['recipes']:
                        created_items['recipes'].remove(recipe.id)
                    operation_counts['delete_recipe'] = operation_counts.get('delete_recipe', 0) + 1
                    return f"Deleted recipe: {recipe.name}"
            return "No recipes to delete"
        
        elif operation == 'update_recipe':
            # Update a random recipe
            recipes = list_recipes(db)
            if recipes:
                recipe = random.choice([r for r in recipes if r])
                # Don't modify protected recipes
                if recipe.id not in created_items.get('protected_recipes', []):
                    new_notes = f"Updated notes {random.randint(1, 1000)}"
                    update_recipe(db, recipe_id=recipe.id, notes=new_notes)
                    operation_counts['update_recipe'] = operation_counts.get('update_recipe', 0) + 1
                    return f"Updated recipe: {recipe.name}"
            return "No recipes to update"
    
    except (ValueError, Exception) as e:
        # Many operations may fail (e.g., deleting items that don't exist, adding duplicates)
        # This is expected in a stress test
        operation_counts[f'{operation}_failed'] = operation_counts.get(f'{operation}_failed', 0) + 1
        return f"Operation {operation} failed (expected): {str(e)[:50]}"


def test_stress():
    """Main stress test function."""
    print("="*70)
    print("STRESS TEST: Database Operations")
    print("="*70)
    
    db = SessionLocal()
    created_items = {
        'ingredients': [],
        'tags': [],
        'types': [],
        'subtags': [],
        'recipes': [],
        'protected_ingredients': [],
        'protected_tags': [],
        'protected_recipes': []
    }
    operation_counts = {}
    
    try:
        # Step 1: Create initial test recipe
        print("\n" + "="*70)
        print("STEP 1: Creating initial test recipe")
        print("="*70)
        
        # Check if test recipe already exists and delete it
        existing_recipe = get_recipe(db, name="Stress Test Recipe")
        if existing_recipe:
            print(f"  Found existing test recipe (ID: {existing_recipe.id}), deleting...")
            delete_recipe(db, recipe_id=existing_recipe.id)
            print("  ✓ Deleted existing test recipe")
        
        # Get some existing ingredients and tags
        test_ingredients = get_random_ingredients(db, count=3)
        test_tags = get_random_tags(db, count=2)
        
        if not test_ingredients:
            print("✗ Error: Need at least 3 ingredients in database. Run bootload.py first.")
            return False
        
        if not test_tags:
            print("✗ Error: Need at least 2 tags in database. Run bootload.py first.")
            return False
        
        test_recipe = add_recipe(
            db,
            name="Stress Test Recipe",
            instructions="Mix all ingredients together. Cook for 30 minutes.",
            notes="This is a test recipe for stress testing.",
            ingredients=[ing.name for ing in test_ingredients],
            tags=[tag.name for tag in test_tags]
        )
        
        # Store snapshot
        snapshot = RecipeSnapshot(test_recipe)
        created_items['protected_recipes'].append(test_recipe.id)
        created_items['protected_ingredients'].extend([ing.id for ing in test_ingredients])
        created_items['protected_tags'].extend([tag.id for tag in test_tags])
        
        print(f"✓ Created test recipe: {test_recipe.name} (ID: {test_recipe.id})")
        print(f"  Ingredients: {', '.join([ing.name for ing in test_ingredients])}")
        print(f"  Tags: {', '.join([tag.name for tag in test_tags])}")
        
        # Step 2: Perform 50+ random operations
        print("\n" + "="*70)
        print("STEP 2: Performing 50+ random operations")
        print("="*70)
        
        num_operations = 50
        for i in range(num_operations):
            result = random_operation(db, created_items, operation_counts)
            if (i + 1) % 10 == 0:
                print(f"  Completed {i + 1}/{num_operations} operations...")
        
        print(f"✓ Completed {num_operations} random operations")
        
        # Step 3: Add 5 more recipes
        print("\n" + "="*70)
        print("STEP 3: Adding 5 more recipes")
        print("="*70)
        
        for i in range(5):
            ingredients = get_random_ingredients(db, count=random.randint(2, 4))
            tags = get_random_tags(db, count=random.randint(1, 2))
            # Use unique name with random number to avoid conflicts
            unique_id = random.randint(100000, 999999)
            recipe = add_recipe(
                db,
                name=f"Additional Test Recipe {i+1} {unique_id}",
                instructions=f"Instructions for recipe {i+1}",
                notes=f"Notes for recipe {i+1}",
                ingredients=[ing.name for ing in ingredients] if ingredients else None,
                tags=[tag.name for tag in tags] if tags else None
            )
            created_items['recipes'].append(recipe.id)
            print(f"  ✓ Added recipe: {recipe.name} (ID: {recipe.id})")
        
        # Step 4: Perform 50 more random operations
        print("\n" + "="*70)
        print("STEP 4: Performing 50 more random operations")
        print("="*70)
        
        for i in range(num_operations):
            result = random_operation(db, created_items, operation_counts)
            if (i + 1) % 10 == 0:
                print(f"  Completed {i + 1}/{num_operations} operations...")
        
        print(f"✓ Completed {num_operations} more random operations")
        
        # Step 5: Validation tests - verify that invalid operations fail
        print("\n" + "="*70)
        print("STEP 5: Validation tests (should fail)")
        print("="*70)
        
        validation_passed = True
        
        # Test 1: Try to add ingredient with non-existent type
        try:
            add_ingredient(db, name="test_invalid_type_ingredient", type_name="nonexistent_type_xyz123")
            print("  ✗ FAILED: Should not allow adding ingredient with non-existent type")
            validation_passed = False
        except ValueError as e:
            print(f"  ✓ PASSED: Correctly rejected ingredient with non-existent type: {str(e)[:60]}")
        
        # Test 2: Try to add recipe with non-existent ingredient
        try:
            add_recipe(db, name="test_invalid_ingredient_recipe", ingredients=["nonexistent_ingredient_xyz123"])
            print("  ✗ FAILED: Should not allow adding recipe with non-existent ingredient")
            validation_passed = False
        except ValueError as e:
            print(f"  ✓ PASSED: Correctly rejected recipe with non-existent ingredient: {str(e)[:60]}")
        
        # Test 3: Try to add recipe with non-existent tag
        try:
            add_recipe(db, name="test_invalid_tag_recipe", tags=["nonexistent_tag_xyz123"])
            print("  ✗ FAILED: Should not allow adding recipe with non-existent tag")
            validation_passed = False
        except ValueError as e:
            print(f"  ✓ PASSED: Correctly rejected recipe with non-existent tag: {str(e)[:60]}")
        
        # Test 4: Try to add tag with non-existent subtag
        try:
            add_tag(db, name="test_invalid_subtag_tag", subtag_name="nonexistent_subtag_xyz123")
            print("  ✗ FAILED: Should not allow adding tag with non-existent subtag")
            validation_passed = False
        except ValueError as e:
            print(f"  ✓ PASSED: Correctly rejected tag with non-existent subtag: {str(e)[:60]}")
        
        if not validation_passed:
            print("\n  ✗ Some validation tests failed!")
            return False
        
        # Step 6: Verify original recipe
        print("\n" + "="*70)
        print("STEP 6: Verifying original test recipe")
        print("="*70)
        
        retrieved_recipe = get_recipe(db, recipe_id=snapshot.recipe_id)
        
        if not retrieved_recipe:
            print(f"✗ ERROR: Test recipe (ID: {snapshot.recipe_id}) not found!")
            return False
        
        try:
            snapshot.verify(retrieved_recipe)
            print("✓ Test recipe verification PASSED!")
            print(f"  Recipe ID: {retrieved_recipe.id}")
            print(f"  Name: {retrieved_recipe.name}")
            print(f"  Ingredients: {', '.join([ing.name for ing in retrieved_recipe.ingredients])}")
            print(f"  Tags: {', '.join([tag.name for tag in retrieved_recipe.tags])}")
        except AssertionError as e:
            print(f"✗ ERROR: Test recipe verification FAILED!")
            print(f"  {e}")
            return False
        
        # Print operation statistics
        print("\n" + "="*70)
        print("OPERATION STATISTICS")
        print("="*70)
        
        # Group operations by type
        operation_groups = {
            'Ingredient Operations': ['add_ingredient', 'delete_ingredient', 'update_ingredient'],
            'Tag Operations': ['add_tag', 'delete_tag', 'update_tag'],
            'Type Operations': ['add_type', 'delete_type', 'update_type'],
            'Subtag Operations': ['add_subtag', 'delete_subtag', 'update_subtag'],
            'Recipe Operations': ['add_recipe', 'delete_recipe', 'update_recipe'],
        }
        
        for group_name, ops in operation_groups.items():
            print(f"\n{group_name}:")
            for op in ops:
                count = operation_counts.get(op, 0)
                failed = operation_counts.get(f'{op}_failed', 0)
                if count > 0 or failed > 0:
                    print(f"  {op}: {count} succeeded, {failed} failed")
        
        total_succeeded = sum(count for key, count in operation_counts.items() if not key.endswith('_failed'))
        total_failed = sum(count for key, count in operation_counts.items() if key.endswith('_failed'))
        print(f"\nTotal: {total_succeeded} operations succeeded, {total_failed} operations failed")
        
        # Step 7: Run consistency check
        print("\n" + "="*70)
        print("STEP 7: Running consistency check")
        print("="*70)
        
        consistency_ok = run_consistency_check(db)
        
        if not consistency_ok:
            print("\n  ✗ Consistency check found issues!")
            return False
        
        print("\n  ✓ Consistency check passed!")
        
        return True
    
    except Exception as e:
        print(f"\n✗ ERROR during stress test: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        db.close()


if __name__ == '__main__':
    success = test_stress()
    print("\n" + "="*70)
    if success:
        print("STRESS TEST: PASSED ✓")
    else:
        print("STRESS TEST: FAILED ✗")
    print("="*70)
    sys.exit(0 if success else 1)
