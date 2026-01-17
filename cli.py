#!/usr/bin/env python3
"""
CLI interface for managing recipes and ingredients.
"""
import argparse
import sys
import json
import warnings
from pathlib import Path

# Suppress urllib3/OpenSSL warnings
try:
    import urllib3
    # urllib3 2.x has NotOpenSSLWarning, 1.x doesn't
    try:
        urllib3.disable_warnings(urllib3.exceptions.NotOpenSSLWarning)
    except AttributeError:
        # urllib3 1.x - no NotOpenSSLWarning exception
        urllib3.disable_warnings()
except ImportError:
    pass
warnings.filterwarnings('ignore', message='.*urllib3.*')
warnings.filterwarnings('ignore', message='.*OpenSSL.*')

# Add scripts directory to path
import sys
from pathlib import Path
scripts_dir = Path(__file__).parent / 'scripts'
if str(scripts_dir) not in sys.path:
    sys.path.insert(0, str(scripts_dir))

from database import SessionLocal, init_db
from db_operations import (
    add_ingredient, list_ingredients, delete_ingredient, get_ingredient,
    add_recipe, list_recipes, delete_recipe,
    update_recipe,
    list_ingredient_types, get_recipe,
    add_article, list_articles, get_article, update_article, delete_article
)
from models import Ingredient
from json_editor import (
    export_recipe_to_json, import_recipe_from_json, check_json_exists,
    export_new_recipe_template, import_new_recipe_from_json, check_addable_json_exists,
    get_addable_recipe_files, ADDABLE_DIR, EDITABLE_DIR,
    export_ingredient_to_json, import_ingredient_from_json, check_ingredient_json_exists,
    export_new_ingredient_template, import_new_ingredient_from_json, check_addable_ingredient_json_exists,
    get_addable_ingredient_files, SimilarityDetected
)


def print_ingredient(ingredient):
    """Print ingredient information (simple format for lists)."""
    print(f"  [{ingredient.id:3d}] {ingredient.name:30s} ({ingredient.type.name})")


def print_ingredient_info(ingredient):
    """Pretty print detailed ingredient information."""
    print(f"\n{'='*70}")
    print(f"Ingredient #{ingredient.id}: {ingredient.name}")
    print(f"{'='*70}")
    
    print(f"Type: {ingredient.type.name}")
    
    if ingredient.alias:
        aliases = [a.strip() for a in ingredient.alias.split(',') if a.strip()]
        if aliases:
            print(f"Aliases: {', '.join(aliases)}")
    
    if ingredient.tags:
        tags_str = ', '.join([tag.name for tag in ingredient.tags])
        print(f"Tags: {tags_str}")
    
    if ingredient.notes:
        print(f"\nNotes:")
        print(ingredient.notes)
    
    # Show recipes that use this ingredient
    if ingredient.recipes:
        recipe_names = [recipe.name for recipe in ingredient.recipes]
        print(f"\nUsed in {len(recipe_names)} recipe(s):")
        for recipe_name in recipe_names:
            print(f"  • {recipe_name}")
    
    print()


def print_recipe(recipe):
    """Print recipe information in a readable format."""
    print(f"\n{'='*70}")
    print(f"Recipe #{recipe.id}: {recipe.name}")
    print(f"{'='*70}")
    if recipe.tags:
        tags_str = ', '.join([tag.name for tag in recipe.tags])
        print(f"Tags: {tags_str}")
    if recipe.ingredients:
        ingredients_str = ', '.join([ing.name for ing in recipe.ingredients])
        print(f"Ingredients: {ingredients_str}")
    if recipe.instructions:
        print(f"\nInstructions:\n{recipe.instructions}")
    if recipe.notes:
        print(f"\nNotes: {recipe.notes}")
    print()


def print_article(article):
    """Print article information in a readable format."""
    print(f"\n{'='*70}")
    print(f"Article #{article.id}")
    print(f"{'='*70}")
    if article.tags:
        tags_str = ', '.join([tag.name for tag in article.tags])
        print(f"Tags: {tags_str}")
    if article.notes:
        print(f"\nNotes:\n{article.notes}")
    print()


def handle_merge_prompt(item_type: str, new_data: dict, existing_item, score: float) -> str:
    """Prompt user for merge decision. Returns 'A', 'B', or 'N'."""
    print(f"\n{'='*70}")
    print(f"⚠️  Similarity Detected ({score:.1f}% match)")
    print(f"{'='*70}")
    print(f"New {item_type}:")
    if item_type == "ingredient":
        print(f"  Name: {new_data.get('name')}")
        print(f"  Type: {new_data.get('type')}")
        print(f"  Alias: {new_data.get('alias', [])}")
    else:
        print(f"  Name: {new_data.get('name')}")
    
    print(f"\nExisting {item_type} (ID: {existing_item.id}):")
    if item_type == "ingredient":
        print(f"  Name: {existing_item.name}")
        print(f"  Type: {existing_item.type.name}")
        alias_str = existing_item.alias if existing_item.alias else "none"
        print(f"  Alias: {alias_str}")
    else:
        print(f"  Name: {existing_item.name}")
    
    print(f"\n{'='*70}")
    print("Merge options:")
    print("  A - Keep existing (skip adding new)")
    print("  B - Use new (replace existing)")
    print("  C - Keep both (add new and keep existing)")
    print("  N - Cancel (do nothing)")
    
    while True:
        response = input("\nChoose (A/B/C/N): ").strip().upper()
        if response in ['A', 'B', 'C', 'N']:
            return response
        print("Invalid choice. Please enter A, B, C, or N.")


def cmd_add_ingredient(args):
    """Add a new ingredient using JSON file workflow."""
    # Check if addable JSON file already exists
    if check_addable_ingredient_json_exists():
        # JSON exists - list available files and import the most recent or specified one
        ingredient_files = get_addable_ingredient_files()
        if len(ingredient_files) > 1:
            print(f"\nFound {len(ingredient_files)} ingredient files in addable/:")
            for i, f in enumerate(ingredient_files, 1):
                print(f"  {i}. {f.name}")
            print(f"\nImporting most recent: {ingredient_files[0].name}")
        
        try:
            # Read JSON first to check for similarity
            json_path = ingredient_files[0] if ingredient_files else None
            if json_path is None:
                json_path = ADDABLE_DIR / "new_ingredient.json"
            
            with open(json_path, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
            
            # Check for similarity before importing
            db = SessionLocal()
            try:
                name = json_data.get('name', '').strip()
                if name:
                    from db_operations import find_similar_ingredients
                    similar = find_similar_ingredients(db, name, min_score=80)
                    if similar:
                        best_match, score = similar[0]
                        choice = handle_merge_prompt("ingredient", json_data, best_match, score)
                        
                        if choice == 'A':
                            # Keep existing - delete JSON file and exit
                            json_path.unlink()
                            print(f"✓ Kept existing ingredient: {best_match.name} (ID: {best_match.id})")
                            print(f"  JSON file deleted.")
                            return
                        elif choice == 'B':
                            # Use new - delete existing and continue with import
                            from db_operations import delete_ingredient
                            delete_ingredient(db, ingredient_id=best_match.id)
                            print(f"✓ Deleted existing ingredient (ID: {best_match.id})")
                        elif choice == 'C':
                            # Keep both - continue with import (don't delete existing)
                            print(f"✓ Keeping existing ingredient: {best_match.name} (ID: {best_match.id})")
                            print(f"  Adding new ingredient as well...")
                            # Continue with import below
                        elif choice == 'N':
                            # Cancel - keep JSON file
                            print("Cancelled. JSON file kept for editing.")
                            return
            finally:
                db.close()
            
            # Import the ingredient
            try:
                ingredient = import_new_ingredient_from_json(json_path)
                # Get fresh instance to access relationships
                db = SessionLocal()
                try:
                    fresh_ingredient = db.query(Ingredient).filter(Ingredient.id == ingredient.id).first()
                    type_name = fresh_ingredient.type.name if fresh_ingredient else "unknown"
                finally:
                    db.close()
                print(f"✓ Added ingredient: {ingredient.name} (type: {type_name})")
                print(f"  JSON file deleted.")
            except Exception as e:
                # Preserve JSON file on error so user can fix it
                print(f"\n✗ Error: {e}", file=sys.stderr)
                if json_path.exists():
                    print(f"  JSON file preserved at: {json_path}", file=sys.stderr)
                    print(f"  Please fix the issue and run the command again.", file=sys.stderr)
                sys.exit(1)
        except SimilarityDetected as e:
            # Preserve JSON file on similarity detection
            print(f"\n✗ {e}", file=sys.stderr)
            if json_path.exists():
                print(f"  JSON file preserved at: {json_path}", file=sys.stderr)
            sys.exit(1)
        except ValueError as e:
            # Preserve JSON file on validation errors
            print(f"\n✗ Error: {e}", file=sys.stderr)
            if json_path.exists():
                print(f"  JSON file preserved at: {json_path}", file=sys.stderr)
                print(f"  Please fix the issue and run the command again.", file=sys.stderr)
            sys.exit(1)
    else:
        # JSON doesn't exist - create template
        try:
            json_path = export_new_ingredient_template()
            print(f"✓ Created JSON template: {json_path}")
            print(f"  Edit the file with your ingredient details, then run the same command again to add it.")
            print(f"  (Delete the file to cancel)")
        except Exception as e:
            print(f"✗ Error: {e}", file=sys.stderr)
            sys.exit(1)


def cmd_list_ingredients(args):
    """List all ingredients, organized by type."""
    db = SessionLocal()
    try:
        ingredients = list_ingredients(db)
        if not ingredients:
            print("No ingredients found.")
        else:
            # Group ingredients by type
            ingredients_by_type = {}
            for ingredient in ingredients:
                type_name = ingredient.type.name
                if type_name not in ingredients_by_type:
                    ingredients_by_type[type_name] = []
                ingredients_by_type[type_name].append(ingredient)
            
            # Sort types alphabetically
            sorted_types = sorted(ingredients_by_type.keys())
            
            # Sort ingredients within each type alphabetically by name
            for type_name in sorted_types:
                ingredients_by_type[type_name].sort(key=lambda x: x.name.lower())
            
            print(f"\n{'='*70}")
            print(f"Ingredients ({len(ingredients)} total)")
            print(f"{'='*70}")
            
            # Print ingredients grouped by type
            for type_name in sorted_types:
                type_ingredients = ingredients_by_type[type_name]
                print(f"\n{type_name.upper()} ({len(type_ingredients)} ingredient{'s' if len(type_ingredients) != 1 else ''})")
                print("-" * 70)
                for ingredient in type_ingredients:
                    print_ingredient(ingredient)
            
            print()
    finally:
        db.close()


def cmd_ingredient_info(args):
    """Display detailed information about an ingredient."""
    ingredient_id = None
    if args.id:
        ingredient_id = args.id
    elif args.name:
        db = SessionLocal()
        try:
            # Use fuzzy matching to find the ingredient
            from db_operations import find_similar_ingredients
            similar = find_similar_ingredients(db, args.name, min_score=50)
            
            if not similar:
                print(f"✗ Error: No ingredient found matching '{args.name}'", file=sys.stderr)
                sys.exit(1)
            
            # Show top 5 matches if multiple found
            if len(similar) > 1:
                print(f"\nTop matches for '{args.name}':")
                print(f"{'='*70}")
                for i, (ing, score) in enumerate(similar[:5], 1):
                    print(f"  {i}. [{ing.id:3d}] {ing.name:40s} (Score: {score:.1f}%)")
                print(f"{'='*70}")
            
            # Use the best match
            best_match, best_score = similar[0]
            if len(similar) > 1:
                print(f"\n✓ Using best match: [{best_match.id}] {best_match.name} (Score: {best_score:.1f}%)")
            ingredient_id = best_match.id
        finally:
            db.close()
    
    # Get and display ingredient info
    db = SessionLocal()
    try:
        ingredient = get_ingredient(db, ingredient_id=ingredient_id)
        if not ingredient:
            print(f"✗ Error: Ingredient not found (ID: {ingredient_id})", file=sys.stderr)
            sys.exit(1)
        
        print_ingredient_info(ingredient)
    finally:
        db.close()


def cmd_delete_ingredient(args):
    """Delete an ingredient by ID only."""
    if not args.id:
        print("✗ Error: Must specify --id", file=sys.stderr)
        sys.exit(1)
    
    db = SessionLocal()
    try:
        delete_ingredient(db, ingredient_id=args.id)
        print(f"✓ Deleted ingredient (ID: {args.id})")
    except ValueError as e:
        print(f"✗ Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


def cmd_edit_ingredient(args):
    """Edit an ingredient using JSON file workflow."""
    # Determine ingredient ID
    ingredient_id = None
    if args.id:
        ingredient_id = args.id
    elif args.name:
        db = SessionLocal()
        try:
            # Always use fuzzy matching to show top matches
            from db_operations import find_similar_ingredients
            similar = find_similar_ingredients(db, args.name, min_score=50)
            
            if not similar:
                print(f"✗ Error: No ingredient found matching '{args.name}'", file=sys.stderr)
                sys.exit(1)
            
            # Show top 5 matches
            print(f"\nTop matches for '{args.name}':")
            print(f"{'='*70}")
            for i, (ing, score) in enumerate(similar[:5], 1):
                print(f"  {i}. [{ing.id:3d}] {ing.name:40s} (Score: {score:.1f}%)")
            print(f"{'='*70}")
            
            # Use the best match
            best_match, best_score = similar[0]
            print(f"\n✓ Using best match: [{best_match.id}] {best_match.name} (Score: {best_score:.1f}%)")
            ingredient_id = best_match.id
        finally:
            db.close()
    
    if not ingredient_id:
        print("✗ Error: Must specify either --id or --name", file=sys.stderr)
        sys.exit(1)
    
    # Check if JSON file already exists
    if check_ingredient_json_exists(ingredient_id):
        # JSON exists - import it and update the ingredient
        try:
            ingredient = import_ingredient_from_json(ingredient_id)
            print(f"✓ Updated ingredient: {ingredient.name}")
            print(f"  JSON file deleted.")
        except SimilarityDetected as e:
            # Handle similarity during edit
            db = SessionLocal()
            try:
                # Read the JSON file to get new data
                json_path = EDITABLE_DIR / f"ingredient_{ingredient_id}.json"
                with open(json_path, 'r', encoding='utf-8') as f:
                    json_data = json.load(f)
                
                choice = handle_merge_prompt("ingredient", json_data, e.existing_item, e.score)
                
                if choice == 'A':
                    # Keep existing - delete JSON file
                    json_path.unlink()
                    print(f"✓ Kept existing ingredient: {e.existing_item.name} (ID: {e.existing_item.id})")
                    print(f"  JSON file deleted.")
                elif choice == 'B':
                    # Use new - delete existing and update current
                    from db_operations import delete_ingredient
                    delete_ingredient(db, ingredient_id=e.existing_item.id)
                    print(f"✓ Deleted similar ingredient (ID: {e.existing_item.id})")
                    # Retry import
                    ingredient = import_ingredient_from_json(ingredient_id)
                    print(f"✓ Updated ingredient: {ingredient.name}")
                    print(f"  JSON file deleted.")
                elif choice == 'C':
                    # Keep both - can't update existing, so this doesn't apply to edit workflow
                    # For edit, we can't keep both since we're editing a specific item
                    print("⚠️  Option C (keep both) not available when editing.")
                    print("  When editing, you can only keep existing (A) or replace (B).")
                    print("  To add a new similar item, use 'ingredient add' instead.")
                    json_path.unlink()
                    return
                elif choice == 'N':
                    # Cancel - keep JSON file
                    print("Cancelled. JSON file kept for editing.")
            finally:
                db.close()
        except Exception as e:
            # Clean up JSON file on error (unless user cancelled)
            json_path = EDITABLE_DIR / f"ingredient_{ingredient_id}.json"
            if json_path.exists() and not isinstance(e, KeyboardInterrupt):
                json_path.unlink()
            if not isinstance(e, (SimilarityDetected, KeyboardInterrupt)):
                print(f"✗ Error: {e}", file=sys.stderr)
                sys.exit(1)
    else:
        # JSON doesn't exist - create it
        try:
            json_path = export_ingredient_to_json(ingredient_id)
            print(f"✓ Created JSON file: {json_path}")
            print(f"  Edit the file, then run the same command again to apply changes.")
            print(f"  (Delete the file to cancel editing)")
        except ValueError as e:
            print(f"✗ Error: {e}", file=sys.stderr)
            sys.exit(1)


def cmd_add_recipe(args):
    """Add a new recipe using JSON file workflow."""
    # Check if addable JSON file already exists
    if check_addable_json_exists():
        # JSON exists - list available files and import the most recent or specified one
        recipe_files = get_addable_recipe_files()
        if len(recipe_files) > 1:
            print(f"\nFound {len(recipe_files)} recipe files in addable/:")
            for i, f in enumerate(recipe_files, 1):
                print(f"  {i}. {f.name}")
            print(f"\nImporting most recent: {recipe_files[0].name}")
        
        try:
            # Read JSON first to check for similarity
            json_path = recipe_files[0] if recipe_files else None
            if json_path is None:
                json_path = ADDABLE_DIR / "new_recipe.json"
            
            with open(json_path, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
            
            # Check for similarity before importing
            db = SessionLocal()
            try:
                name = json_data.get('name', '').strip()
                if name:
                    from db_operations import find_similar_recipes
                    similar = find_similar_recipes(db, name, min_score=80)
                    if similar:
                        best_match, score = similar[0]
                        choice = handle_merge_prompt("recipe", json_data, best_match, score)
                        
                        if choice == 'A':
                            # Keep existing - delete JSON file and exit
                            json_path.unlink()
                            print(f"✓ Kept existing recipe: {best_match.name} (ID: {best_match.id})")
                            print(f"  JSON file deleted.")
                            return
                        elif choice == 'B':
                            # Use new - delete existing and continue with import
                            from db_operations import delete_recipe
                            delete_recipe(db, recipe_id=best_match.id)
                            print(f"✓ Deleted existing recipe (ID: {best_match.id})")
                        elif choice == 'C':
                            # Keep both - continue with import (don't delete existing)
                            print(f"✓ Keeping existing recipe: {best_match.name} (ID: {best_match.id})")
                            print(f"  Adding new recipe as well...")
                            # Continue with import below
                        elif choice == 'N':
                            # Cancel - keep JSON file
                            print("Cancelled. JSON file kept for editing.")
                            return
            finally:
                db.close()
            
            # Import the recipe
            try:
                recipe = import_new_recipe_from_json(json_path)
                print(f"✓ Added recipe: {recipe.name}")
                print(f"  JSON file deleted.")
            except Exception as e:
                # Preserve JSON file on error so user can fix it
                print(f"\n✗ Error: {e}", file=sys.stderr)
                if json_path and json_path.exists():
                    print(f"  JSON file preserved at: {json_path}", file=sys.stderr)
                    print(f"  Please fix the issue and run the command again.", file=sys.stderr)
                sys.exit(1)
        except SimilarityDetected as e:
            # Preserve JSON file on similarity detection
            print(f"\n✗ {e}", file=sys.stderr)
            if json_path and json_path.exists():
                print(f"  JSON file preserved at: {json_path}", file=sys.stderr)
            sys.exit(1)
        except ValueError as e:
            # Preserve JSON file on validation errors
            print(f"\n✗ Error: {e}", file=sys.stderr)
            if json_path and json_path.exists():
                print(f"  JSON file preserved at: {json_path}", file=sys.stderr)
                print(f"  Please fix the issue and run the command again.", file=sys.stderr)
            sys.exit(1)
    else:
        # JSON doesn't exist - create template
        try:
            json_path = export_new_recipe_template()
            print(f"✓ Created JSON template: {json_path}")
            print(f"  Edit the file with your recipe details, then run the same command again to add it.")
            print(f"  (Delete the file to cancel)")
        except Exception as e:
            print(f"✗ Error: {e}", file=sys.stderr)
            sys.exit(1)


def cmd_list_recipes(args):
    """List all recipes."""
    db = SessionLocal()
    try:
        recipes = list_recipes(db)
        if not recipes:
            print("No recipes found.")
        else:
            print(f"\n{'='*70}")
            print(f"Recipes ({len(recipes)} total)")
            print(f"{'='*70}")
            for recipe in recipes:
                print_recipe(recipe)
    finally:
        db.close()


def cmd_delete_recipe(args):
    """Delete a recipe by ID only."""
    if not args.id:
        print("✗ Error: Must specify --id", file=sys.stderr)
        sys.exit(1)
    
    db = SessionLocal()
    try:
        delete_recipe(db, recipe_id=args.id)
        print(f"✓ Deleted recipe (ID: {args.id})")
    except ValueError as e:
        print(f"✗ Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


def cmd_edit_recipe(args):
    """Edit a recipe using JSON file workflow."""
    # Determine recipe ID
    recipe_id = None
    if args.id:
        recipe_id = args.id
    elif args.name:
        db = SessionLocal()
        try:
            # Always use fuzzy matching to show top matches
            from db_operations import find_similar_recipes
            similar = find_similar_recipes(db, args.name, min_score=50)
            
            if not similar:
                print(f"✗ Error: No recipe found matching '{args.name}'", file=sys.stderr)
                sys.exit(1)
            
            # Show top 5 matches
            print(f"\nTop matches for '{args.name}':")
            print(f"{'='*70}")
            for i, (rec, score) in enumerate(similar[:5], 1):
                print(f"  {i}. [{rec.id:3d}] {rec.name:40s} (Score: {score:.1f}%)")
            print(f"{'='*70}")
            
            # Use the best match
            best_match, best_score = similar[0]
            print(f"\n✓ Using best match: [{best_match.id}] {best_match.name} (Score: {best_score:.1f}%)")
            recipe_id = best_match.id
        finally:
            db.close()
    
    if not recipe_id:
        print("✗ Error: Must specify either --id or --name", file=sys.stderr)
        sys.exit(1)
    
    # Check if JSON file already exists
    if check_json_exists(recipe_id):
        # JSON exists - import it and update the recipe
        try:
            recipe = import_recipe_from_json(recipe_id)
            print(f"✓ Updated recipe: {recipe.name}")
            print(f"  JSON file deleted.")
        except SimilarityDetected as e:
            # Handle similarity during edit
            db = SessionLocal()
            try:
                # Read the JSON file to get new data
                json_path = EDITABLE_DIR / f"recipe_{recipe_id}.json"
                with open(json_path, 'r', encoding='utf-8') as f:
                    json_data = json.load(f)
                
                choice = handle_merge_prompt("recipe", json_data, e.existing_item, e.score)
                
                if choice == 'A':
                    # Keep existing - delete JSON file
                    json_path.unlink()
                    print(f"✓ Kept existing recipe: {e.existing_item.name} (ID: {e.existing_item.id})")
                    print(f"  JSON file deleted.")
                elif choice == 'B':
                    # Use new - delete existing and update current
                    from db_operations import delete_recipe
                    delete_recipe(db, recipe_id=e.existing_item.id)
                    print(f"✓ Deleted similar recipe (ID: {e.existing_item.id})")
                    # Retry import
                    recipe = import_recipe_from_json(recipe_id)
                    print(f"✓ Updated recipe: {recipe.name}")
                    print(f"  JSON file deleted.")
                elif choice == 'C':
                    # Keep both - can't update existing, so this doesn't apply to edit workflow
                    # For edit, we can't keep both since we're editing a specific item
                    print("⚠️  Option C (keep both) not available when editing.")
                    print("  When editing, you can only keep existing (A) or replace (B).")
                    print("  To add a new similar item, use 'recipe add' instead.")
                    json_path.unlink()
                    return
                elif choice == 'N':
                    # Cancel - keep JSON file
                    print("Cancelled. JSON file kept for editing.")
            finally:
                db.close()
        except Exception as e:
            # Clean up JSON file on error (unless user cancelled)
            json_path = EDITABLE_DIR / f"recipe_{recipe_id}.json"
            if json_path.exists() and not isinstance(e, KeyboardInterrupt):
                json_path.unlink()
            if not isinstance(e, (SimilarityDetected, KeyboardInterrupt)):
                print(f"✗ Error: {e}", file=sys.stderr)
                sys.exit(1)
    else:
        # JSON doesn't exist - create it
        try:
            json_path = export_recipe_to_json(recipe_id)
            print(f"✓ Created JSON file: {json_path}")
            print(f"  Edit the file, then run the same command again to apply changes.")
            print(f"  (Delete the file to cancel editing)")
        except ValueError as e:
            print(f"✗ Error: {e}", file=sys.stderr)
            sys.exit(1)




def cmd_add_article(args):
    """Add a new article using JSON file workflow."""
    from json_editor import (
        export_new_article_template, import_new_article_from_json,
        check_addable_article_json_exists, get_addable_article_files
    )
    
    if check_addable_article_json_exists():
        article_files = get_addable_article_files()
        if len(article_files) > 1:
            print(f"\nFound {len(article_files)} article files in addable/:")
            for i, f in enumerate(article_files, 1):
                print(f"  {i}. {f.name}")
            print(f"\nImporting most recent: {article_files[0].name}")
        
        json_path = article_files[0] if article_files else None
        
        try:
            article = import_new_article_from_json(json_path)
            print(f"✓ Added article (ID: {article.id})")
            print(f"  JSON file deleted.")
        except Exception as e:
            # Preserve JSON file on error so user can fix it
            print(f"\n✗ Error: {e}", file=sys.stderr)
            if json_path and json_path.exists():
                print(f"  JSON file preserved at: {json_path}", file=sys.stderr)
                print(f"  Please fix the issue and run the command again.", file=sys.stderr)
            sys.exit(1)
    else:
        try:
            json_path = export_new_article_template()
            print(f"✓ Created JSON template: {json_path}")
            print(f"  Edit the file with your article details, then run the same command again to add it.")
            print(f"  (Delete the file to cancel)")
        except Exception as e:
            print(f"✗ Error: {e}", file=sys.stderr)
            sys.exit(1)


def cmd_list_articles(args):
    """List all articles."""
    db = SessionLocal()
    try:
        articles = list_articles(db)
        if not articles:
            print("No articles found.")
        else:
            print(f"\n{'='*70}")
            print(f"Articles ({len(articles)} total)")
            print(f"{'='*70}")
            for article in articles:
                tags_str = ', '.join([tag.name for tag in article.tags]) if article.tags else 'none'
                notes_preview = (article.notes[:50] + '...') if article.notes and len(article.notes) > 50 else (article.notes or '')
                print(f"  [{article.id:3d}] Tags: {tags_str}")
                if notes_preview:
                    print(f"       Notes: {notes_preview}")
            print()
    finally:
        db.close()


def cmd_edit_article(args):
    """Edit an article using JSON file workflow."""
    from json_editor import (
        export_article_to_json, import_article_from_json,
        check_article_json_exists, EDITABLE_DIR
    )
    
    if not args.id:
        print("✗ Error: Must specify --id", file=sys.stderr)
        sys.exit(1)
    
    article_id = args.id
    
    if check_article_json_exists(article_id):
        try:
            article = import_article_from_json(article_id)
            print(f"✓ Updated article (ID: {article.id})")
            print(f"  JSON file deleted.")
        except Exception as e:
            json_path = EDITABLE_DIR / f"article_{article_id}.json"
            if json_path.exists():
                json_path.unlink()
            print(f"✗ Error: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        try:
            json_path = export_article_to_json(article_id)
            print(f"✓ Created JSON file: {json_path}")
            print(f"  Edit the file, then run the same command again to apply changes.")
            print(f"  (Delete the file to cancel editing)")
        except ValueError as e:
            print(f"✗ Error: {e}", file=sys.stderr)
            sys.exit(1)


def cmd_delete_article(args):
    """Delete an article."""
    if not args.id:
        print("✗ Error: Must specify --id", file=sys.stderr)
        sys.exit(1)
    
    db = SessionLocal()
    try:
        delete_article(db, article_id=args.id)
        print(f"✓ Deleted article (ID: {args.id})")
    except ValueError as e:
        print(f"✗ Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()




def cmd_list_types(args):
    """List all ingredient types."""
    db = SessionLocal()
    try:
        types = list_ingredient_types(db)
        if not types:
            print("No ingredient types found.")
        else:
            print(f"\n{'='*70}")
            print(f"Ingredient Types ({len(types)} total)")
            print(f"{'='*70}")
            for type_obj in types:
                print(f"  • {type_obj.name}")
            print()
    finally:
        db.close()


def cmd_search(args):
    """
    Unified semantic search command.
    
    Usage:
        python cli.py search "umami, basil, herb" ingredient --n 10
        python cli.py search "pasta, italian" recipe --n 5
    """
    db = SessionLocal()
    try:
        if args.entity_type == 'ingredient':
            try:
                from db_operations_semantic import semantic_search_ingredients_by_query
                results = semantic_search_ingredients_by_query(
                    db,
                    args.query,
                    limit=args.n,
                    min_similarity=0.0  # No minimum threshold, return top N
                )
                
                if not results:
                    print(f"No ingredients found matching '{args.query}'")
                else:
                    print(f"\n{'='*70}")
                    print(f"Search Results for '{args.query}' ({len(results)} found, semantic search)")
                    print(f"{'='*70}")
                    for ingredient, score in results:
                        # Convert similarity (0-1) to percentage (0-100)
                        score_percent = score * 100
                        print(f"  [{ingredient.id:3d}] {ingredient.name:40s} ({ingredient.type.name}) (Score: {score_percent:.1f}%)")
                    print()
            except ValueError as e:
                print(f"✗ Error: {e}", file=sys.stderr)
                sys.exit(1)
        elif args.entity_type == 'recipe':
            try:
                from db_operations_semantic import semantic_search_recipes_by_query
                results = semantic_search_recipes_by_query(
                    db,
                    args.query,
                    limit=args.n,
                    min_similarity=0.0  # No minimum threshold, return top N
                )
                
                if not results:
                    print(f"No recipes found matching '{args.query}'")
                else:
                    print(f"\n{'='*70}")
                    print(f"Search Results for '{args.query}' ({len(results)} found, semantic search)")
                    print(f"{'='*70}")
                    for recipe, score in results:
                        # Convert similarity (0-1) to percentage (0-100)
                        score_percent = score * 100
                        print(f"  [{recipe.id:3d}] {recipe.name:40s} (Score: {score_percent:.1f}%)")
                    print()
            except ValueError as e:
                print(f"✗ Error: {e}", file=sys.stderr)
                sys.exit(1)
        else:
            print(f"✗ Error: Unknown entity type '{args.entity_type}'. Use 'ingredient' or 'recipe'.", file=sys.stderr)
            sys.exit(1)
    finally:
        db.close()








def cmd_stats(args):
    """Display database statistics."""
    from models import Recipe, Ingredient, IngredientType, Tag, Article
    
    db = SessionLocal()
    try:
        # Count entities
        recipe_count = db.query(Recipe).count()
        ingredient_count = db.query(Ingredient).count()
        ingredient_type_count = db.query(IngredientType).count()
        tag_count = db.query(Tag).count()
        article_count = db.query(Article).count()
        
        # Get next IDs (max ID + 1, or 1 if empty)
        next_recipe_id = 1
        if recipe_count > 0:
            max_recipe_id = db.query(Recipe.id).order_by(Recipe.id.desc()).first()[0]
            next_recipe_id = max_recipe_id + 1
        
        next_ingredient_id = 1
        if ingredient_count > 0:
            max_ingredient_id = db.query(Ingredient.id).order_by(Ingredient.id.desc()).first()[0]
            next_ingredient_id = max_ingredient_id + 1
        
        next_article_id = 1
        if article_count > 0:
            max_article_id = db.query(Article.id).order_by(Article.id.desc()).first()[0]
            next_article_id = max_article_id + 1
        
        # Calculate average ingredients per recipe
        avg_ingredients_per_recipe = 0.0
        if recipe_count > 0:
            total_ingredient_links = db.query(Recipe).join(Recipe.ingredients).count()
            # Better approach: count total ingredients across all recipes
            recipes_with_ingredients = db.query(Recipe).filter(Recipe.ingredients.any()).all()
            total_ingredients_in_recipes = sum(len(recipe.ingredients) for recipe in recipes_with_ingredients)
            if recipe_count > 0:
                avg_ingredients_per_recipe = total_ingredients_in_recipes / recipe_count
        
        # Calculate average tags per recipe
        avg_tags_per_recipe = 0.0
        if recipe_count > 0:
            recipes_with_tags = db.query(Recipe).filter(Recipe.tags.any()).all()
            total_tags_in_recipes = sum(len(recipe.tags) for recipe in recipes_with_tags)
            if recipe_count > 0:
                avg_tags_per_recipe = total_tags_in_recipes / recipe_count
        
        # Display stats
        print(f"\n{'='*70}")
        print(f"Database Statistics")
        print(f"{'='*70}")
        print(f"\nRECIPES")
        print(f"  Total: {recipe_count}")
        print(f"  Next ID: {next_recipe_id}")
        if recipe_count > 0:
            print(f"  Avg ingredients per recipe: {avg_ingredients_per_recipe:.1f}")
            print(f"  Avg tags per recipe: {avg_tags_per_recipe:.1f}")
        
        print(f"\nINGREDIENTS")
        print(f"  Total: {ingredient_count}")
        print(f"  Next ID: {next_ingredient_id}")
        
        print(f"\nINGREDIENT TYPES")
        print(f"  Total: {ingredient_type_count}")
        
        print(f"\nTAGS")
        print(f"  Total: {tag_count}")
        
        print(f"\nARTICLES")
        print(f"  Total: {article_count}")
        print(f"  Next ID: {next_article_id}")
        
        print(f"\n{'='*70}\n")
    finally:
        db.close()


def cmd_cleanup(args):
    """Delete all JSON staging files in addable/ and editable/ directories."""
    from pathlib import Path
    
    deleted_count = 0
    
    # Clean all JSON files in addable directory and subdirectories
    addable_dir = Path("addable")
    if addable_dir.exists():
        for json_file in addable_dir.rglob("*.json"):
            json_file.unlink()
            deleted_count += 1
            print(f"  Deleted: {json_file}")
    
    # Clean all JSON files in editable directory and subdirectories
    editable_dir = Path("editable")
    if editable_dir.exists():
        for json_file in editable_dir.rglob("*.json"):
            json_file.unlink()
            deleted_count += 1
            print(f"  Deleted: {json_file}")
    
    if deleted_count == 0:
        print("✓ No staging files found to clean up.")
    else:
        print(f"✓ Cleaned up {deleted_count} staging file(s).")


def cmd_embed(args):
    """Generate embeddings for recipes, ingredients, and articles."""
    import time
    
    try:
        from embeddings import (
            batch_generate_recipe_embeddings,
            batch_generate_ingredient_embeddings,
            batch_generate_article_embeddings
        )
    except ImportError:
        print("✗ Error: embeddings module not available. Make sure Ollama is installed.", file=sys.stderr)
        sys.exit(1)
    
    # Get only_stale from args (set by subcommand or default)
    only_stale = getattr(args, 'only_stale', True)
    
    print(f"\n{'='*70}")
    print("Generating Embeddings")
    print(f"{'='*70}")
    if only_stale:
        print("Processing entries with stale_embedding=True")
    else:
        print("Processing ALL entries (force mode)")
    print()
    
    start_time = time.time()
    
    # Generate embeddings for recipes
    recipe_start = time.time()
    recipe_embeddings = batch_generate_recipe_embeddings(only_stale=only_stale)
    recipe_time = time.time() - recipe_start
    
    # Generate embeddings for ingredients
    ingredient_start = time.time()
    ingredient_embeddings = batch_generate_ingredient_embeddings(only_stale=only_stale)
    ingredient_time = time.time() - ingredient_start
    
    # Generate embeddings for articles
    article_start = time.time()
    article_embeddings = batch_generate_article_embeddings(only_stale=only_stale)
    article_time = time.time() - article_start
    
    total_time = time.time() - start_time
    total = len(recipe_embeddings) + len(ingredient_embeddings) + len(article_embeddings)
    
    print(f"\n{'='*70}")
    print(f"Summary:")
    print(f"  Recipes: {len(recipe_embeddings)} embedding(s) generated ({recipe_time:.2f}s)")
    if len(recipe_embeddings) > 0:
        print(f"    Average: {recipe_time / len(recipe_embeddings):.2f}s per recipe")
    print(f"  Ingredients: {len(ingredient_embeddings)} embedding(s) generated ({ingredient_time:.2f}s)")
    if len(ingredient_embeddings) > 0:
        print(f"    Average: {ingredient_time / len(ingredient_embeddings):.2f}s per ingredient")
    print(f"  Articles: {len(article_embeddings)} embedding(s) generated ({article_time:.2f}s)")
    if len(article_embeddings) > 0:
        print(f"    Average: {article_time / len(article_embeddings):.2f}s per article")
    print(f"  Total: {total} embedding(s) generated in {total_time:.2f}s")
    if total > 0:
        print(f"    Average: {total_time / total:.2f}s per embedding")
    print(f"{'='*70}\n")


def cmd_ask(args):
    """Answer natural language questions about the recipe database using Ollama."""
    try:
        from ollama_query import query_with_ollama
    except ImportError:
        print("✗ Error: ollama package not installed. Run: pip install ollama", file=sys.stderr)
        sys.exit(1)
    
    if not args.question:
        print("✗ Error: Please provide a question", file=sys.stderr)
        sys.exit(1)
    
    print(f"\n{'='*70}")
    print(f"Question: {args.question}")
    print(f"{'='*70}\n")
    
    try:
        response = query_with_ollama(args.question, model=args.model)
        print(response)
        print()
    except Exception as e:
        print(f"✗ Error: {e}", file=sys.stderr)
        print("\nMake sure Ollama is installed and running:")
        print("  1. Install Ollama from https://ollama.com")
        print(f"  2. Pull a model: ollama pull {args.model}")
        print("  3. Make sure Ollama is running")
        sys.exit(1)


def cmd_help(args):
    """Show help information for all available commands."""
    help_file = Path(__file__).parent / "help" / "help.txt"
    try:
        with open(help_file, 'r', encoding='utf-8') as f:
            print(f.read())
    except FileNotFoundError:
        print(f"✗ Error: Help file not found: {help_file}", file=sys.stderr)
        print("Please ensure help.txt exists in the project directory.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"✗ Error reading help file: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_recipe_help(args):
    """Show help for recipe commands."""
    help_file = Path(__file__).parent / "help" / "help_recipe.txt"
    try:
        with open(help_file, 'r', encoding='utf-8') as f:
            print(f.read())
    except FileNotFoundError:
        print(f"✗ Error: Help file not found: {help_file}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"✗ Error reading help file: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_ingredient_help(args):
    """Show help for ingredient commands."""
    help_file = Path(__file__).parent / "help" / "help_ingredient.txt"
    try:
        with open(help_file, 'r', encoding='utf-8') as f:
            print(f.read())
    except FileNotFoundError:
        print(f"✗ Error: Help file not found: {help_file}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"✗ Error reading help file: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_article_help(args):
    """Show help for article commands."""
    help_file = Path(__file__).parent / "help" / "help_article.txt"
    try:
        with open(help_file, 'r', encoding='utf-8') as f:
            print(f.read())
    except FileNotFoundError:
        print(f"✗ Error: Help file not found: {help_file}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"✗ Error reading help file: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_embed_help(args):
    """Show help for embedding and semantic search commands."""
    help_file = Path(__file__).parent / "help" / "help_embed.txt"
    try:
        with open(help_file, 'r', encoding='utf-8') as f:
            print(f.read())
    except FileNotFoundError:
        print(f"✗ Error: Help file not found: {help_file}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"✗ Error reading help file: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description='Recipe Storage System CLI')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Initialize database
    init_db()
    
    # Ingredient commands
    ingredient_parser = subparsers.add_parser('ingredient', help='Ingredient operations')
    ingredient_subparsers = ingredient_parser.add_subparsers(dest='ingredient_action')
    
    add_ing_parser = ingredient_subparsers.add_parser('add', help='Add an ingredient using JSON file')
    add_ing_parser.set_defaults(func=cmd_add_ingredient)
    
    list_ing_parser = ingredient_subparsers.add_parser('list', help='List all ingredients')
    list_ing_parser.set_defaults(func=cmd_list_ingredients)
    
    edit_ing_parser = ingredient_subparsers.add_parser('edit', help='Edit an ingredient using JSON file')
    edit_ing_group = edit_ing_parser.add_mutually_exclusive_group(required=True)
    edit_ing_group.add_argument('--name', help='Ingredient name')
    edit_ing_group.add_argument('--id', type=int, help='Ingredient ID')
    edit_ing_parser.set_defaults(func=cmd_edit_ingredient)
    
    delete_ing_parser = ingredient_subparsers.add_parser('delete', help='Delete an ingredient by ID')
    delete_ing_parser.add_argument('--id', type=int, required=True, help='Ingredient ID')
    delete_ing_parser.set_defaults(func=cmd_delete_ingredient)
    
    # Info ingredient command
    info_ing_parser = ingredient_subparsers.add_parser('info', help='Display detailed information about an ingredient')
    info_ing_group = info_ing_parser.add_mutually_exclusive_group(required=True)
    info_ing_group.add_argument('--name', help='Ingredient name (fuzzy matching)')
    info_ing_group.add_argument('--id', type=int, help='Ingredient ID')
    info_ing_parser.set_defaults(func=cmd_ingredient_info)
    
    
    
    # Ingredient help
    help_ingredient_parser = ingredient_subparsers.add_parser('help', help='Show help for ingredient commands')
    help_ingredient_parser.set_defaults(func=cmd_ingredient_help)
    
    # Recipe commands
    recipe_parser = subparsers.add_parser('recipe', help='Recipe operations')
    recipe_subparsers = recipe_parser.add_subparsers(dest='recipe_action')
    
    add_recipe_parser = recipe_subparsers.add_parser('add', help='Add a recipe using JSON file')
    add_recipe_parser.set_defaults(func=cmd_add_recipe)
    
    list_recipe_parser = recipe_subparsers.add_parser('list', help='List all recipes')
    list_recipe_parser.set_defaults(func=cmd_list_recipes)
    
    delete_recipe_parser = recipe_subparsers.add_parser('delete', help='Delete a recipe by ID')
    delete_recipe_parser.add_argument('--id', type=int, required=True, help='Recipe ID')
    delete_recipe_parser.set_defaults(func=cmd_delete_recipe)
    
    # Edit recipe command (JSON-based)
    edit_recipe_parser = recipe_subparsers.add_parser('edit', help='Edit a recipe using JSON file')
    edit_recipe_group = edit_recipe_parser.add_mutually_exclusive_group(required=True)
    edit_recipe_group.add_argument('--name', help='Recipe name')
    edit_recipe_group.add_argument('--id', type=int, help='Recipe ID')
    edit_recipe_parser.set_defaults(func=cmd_edit_recipe)
    
    
    # Recipe help
    help_recipe_parser = recipe_subparsers.add_parser('help', help='Show help for recipe commands')
    help_recipe_parser.set_defaults(func=cmd_recipe_help)
    
    # Article commands
    article_parser = subparsers.add_parser('article', help='Article operations')
    article_subparsers = article_parser.add_subparsers(dest='article_action')
    
    add_article_parser = article_subparsers.add_parser('add', help='Add an article using JSON file')
    add_article_parser.set_defaults(func=cmd_add_article)
    
    list_article_parser = article_subparsers.add_parser('list', help='List all articles')
    list_article_parser.set_defaults(func=cmd_list_articles)
    
    edit_article_parser = article_subparsers.add_parser('edit', help='Edit an article using JSON file')
    edit_article_parser.add_argument('--id', type=int, required=True, help='Article ID')
    edit_article_parser.set_defaults(func=cmd_edit_article)
    
    delete_article_parser = article_subparsers.add_parser('delete', help='Delete an article')
    delete_article_parser.add_argument('--id', type=int, required=True, help='Article ID')
    delete_article_parser.set_defaults(func=cmd_delete_article)
    
    # Article help
    help_article_parser = article_subparsers.add_parser('help', help='Show help for article commands')
    help_article_parser.set_defaults(func=cmd_article_help)
    
    # Utility commands
    types_parser = subparsers.add_parser('types', help='List all ingredient types')
    types_parser.set_defaults(func=cmd_list_types)
    
    # Unified search command
    search_parser = subparsers.add_parser('search', help='Semantic search for ingredients or recipes')
    search_parser.add_argument('query', help='Search query (can be comma-separated terms like "umami, basil, herb")')
    search_parser.add_argument('entity_type', choices=['ingredient', 'recipe'], help='Type of entity to search')
    search_parser.add_argument('--n', type=int, default=10, help='Number of results to return (default: 10)')
    search_parser.set_defaults(func=cmd_search)
    
    help_parser = subparsers.add_parser('help', help='Show help information for all commands')
    help_parser.set_defaults(func=cmd_help)
    
    stats_parser = subparsers.add_parser('stats', help='Display database statistics')
    stats_parser.set_defaults(func=cmd_stats)
    
    ask_parser = subparsers.add_parser('ask', help='Ask natural language questions about your recipes (requires Ollama)')
    ask_parser.add_argument('question', help='Your question about recipes, ingredients, or articles')
    ask_parser.add_argument('--model', default='llama3.2', help='Ollama model to use (default: llama3.2)')
    ask_parser.set_defaults(func=cmd_ask)
    
    cleanup_parser = subparsers.add_parser('cleanup', help='Delete all JSON staging files (addable/ and editable/)')
    cleanup_parser.set_defaults(func=cmd_cleanup)
    
    embed_parser = subparsers.add_parser('embed', help='Generate embeddings for recipes, ingredients, and articles')
    embed_subparsers = embed_parser.add_subparsers(dest='embed_action', help='Embedding operations')
    
    embed_default_parser = embed_subparsers.add_parser('default', help='Generate embeddings for entries with stale_embedding=True (default)')
    embed_default_parser.set_defaults(func=cmd_embed, only_stale=True)
    
    embed_force_parser = embed_subparsers.add_parser('force', help='Force regenerate embeddings for ALL entries (ignore stale_embedding flag)')
    embed_force_parser.set_defaults(func=cmd_embed, only_stale=False)
    
    # Embed help
    help_embed_parser = embed_subparsers.add_parser('help', help='Show help for embedding and semantic search commands')
    help_embed_parser.set_defaults(func=cmd_embed_help)
    
    # For backward compatibility, if no subcommand is provided, use default behavior
    embed_parser.set_defaults(func=cmd_embed, only_stale=True)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    if hasattr(args, 'func'):
        args.func(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
