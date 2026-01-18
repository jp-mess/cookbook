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
    get_addable_ingredient_files
)


def print_ingredient(ingredient):
    """Print ingredient information (simple format for lists)."""
    recipe_count = len(ingredient.recipes) if ingredient.recipes else 0
    type_name = ingredient.type.name if ingredient.type else '(no type)'
    print(f"  [{ingredient.id:3d}] {ingredient.name:30s} ({type_name:15s}) {recipe_count:2d} recipe{'s' if recipe_count != 1 else ''}")


def print_ingredient_info(ingredient):
    """Pretty print detailed ingredient information."""
    print(f"\n{'='*70}")
    print(f"Ingredient #{ingredient.id}: {ingredient.name}")
    print(f"{'='*70}")
    
    type_name = ingredient.type.name if ingredient.type else '(no type)'
    print(f"Type: {type_name}")
    
    # Removed alias and tags - ingredients no longer have these fields
    
    if ingredient.notes:
        print(f"\nNotes:")
        print(ingredient.notes)
    
    # Show recipes that use this ingredient
    if ingredient.recipes:
        recipe_names = [recipe.name for recipe in ingredient.recipes if recipe]
        if recipe_names:
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


def print_recipe_info(recipe):
    """Pretty print detailed recipe information."""
    print(f"\n{'='*70}")
    print(f"Recipe #{recipe.id}: {recipe.name}")
    print(f"{'='*70}")
    
    if recipe.tags:
        tags_str = ', '.join([tag.name for tag in recipe.tags])
        print(f"Tags: {tags_str}")
    else:
        print("Tags: (none)")
    
    if recipe.ingredients:
        valid_ingredients = [ing for ing in recipe.ingredients if ing and ing.type]
        if valid_ingredients:
            print(f"\nIngredients ({len(valid_ingredients)} total):")
            for ingredient in valid_ingredients:
                type_name = ingredient.type.name if ingredient.type else '(no type)'
                assoc = recipe.get_ingredient_association(ingredient)
                quantity_str = f" - {assoc.quantity}" if assoc and assoc.quantity else ""
                notes_str = f" ({assoc.notes})" if assoc and assoc.notes else ""
                print(f"  • {ingredient.name} ({type_name}){quantity_str}{notes_str}")
        else:
            print("\nIngredients: (none)")
    else:
        print("\nIngredients: (none)")
    
    if recipe.instructions:
        print(f"\nInstructions:")
        print(recipe.instructions)
    
    if recipe.notes:
        print(f"\nNotes:")
        print(recipe.notes)
    
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
            
            # Import the ingredient
            ingredient = import_new_ingredient_from_json(json_path)
            # Get fresh instance to access relationships (ingredient from import may be detached)
            db = SessionLocal()
            try:
                from db_operations import get_ingredient
                fresh_ingredient = get_ingredient(db, ingredient_id=ingredient.id)
                if fresh_ingredient:
                    type_name = fresh_ingredient.type.name if fresh_ingredient.type else "(no type)"
                    print(f"✓ Added ingredient: {fresh_ingredient.name} (type: {type_name})")
                else:
                    print(f"✓ Added ingredient: {ingredient.name}")
                print(f"  JSON file deleted.")
            finally:
                db.close()
        except (ValueError, Exception) as e:
            # Preserve JSON file on error so user can fix it
            print(f"\n✗ Error: {e}", file=sys.stderr)
            if json_path and json_path.exists():
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


def cmd_list_ingredients_by_type(args):
    """List all ingredients, organized by type."""
    db = SessionLocal()
    try:
        ingredients = list_ingredients(db)
        if not ingredients:
            print("No ingredients found.")
        else:
            # Filter out None ingredients
            ingredients = [ing for ing in ingredients if ing]
            
            # Group ingredients by type
            ingredients_by_type = {}
            for ingredient in ingredients:
                if not ingredient:
                    continue
                type_name = ingredient.type.name if ingredient.type else '(no type)'
                if type_name not in ingredients_by_type:
                    ingredients_by_type[type_name] = []
                ingredients_by_type[type_name].append(ingredient)
            
            # Sort types alphabetically, with '(no type)' at the end
            sorted_types = sorted(ingredients_by_type.keys(), key=lambda x: (x == '(no type)', x))
            
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


def cmd_list_ingredients(args):
    """List all ingredients, search ingredients by name, or list ingredients by subtag."""
    db = SessionLocal()
    try:
        from db_operations import list_ingredients, list_tags
        
        if hasattr(args, 'search') and args.search:
            search_term = args.search.lower()
            
            # Removed subtag search - ingredients no longer have tags
            # Just do name-based fuzzy search
            ingredients = list_ingredients(db)
            if not ingredients:
                print("No ingredients found.")
            else:
                # Simple fuzzy matching: check if search term is in ingredient name (case-insensitive)
                matches = []
                for ingredient in ingredients:
                    if ingredient and search_term in ingredient.name.lower():
                        matches.append(ingredient)
                
                # Sort by relevance (exact match first, then by position)
                matches.sort(key=lambda i: (i.name.lower().startswith(search_term), i.name.lower().find(search_term)))
                
                # Show top 3
                top_matches = matches[:3]
                if not top_matches:
                    print(f"No ingredients found matching '{args.search}'")
                else:
                    print(f"\n{'='*70}")
                    print(f"Ingredients matching '{args.search}' (showing top {len(top_matches)})")
                    print(f"{'='*70}")
                    for ingredient in top_matches:
                        type_name = ingredient.type.name if ingredient.type else '(no type)'
                        print(f"  [{ingredient.id:3d}] {ingredient.name} ({type_name})")
                    print()
        else:
            # List all ingredients (compact format)
            ingredients = list_ingredients(db)
            if not ingredients:
                print("No ingredients found.")
            else:
                for ingredient in ingredients:
                    if ingredient:
                        print(f"[{ingredient.id:3d}] {ingredient.name}")
                
                # Removed subtag check - ingredients no longer have tags
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
            # Use exact name matching (case-insensitive)
            ingredient = get_ingredient(db, name=args.name)
            if not ingredient:
                print(f"✗ Error: No ingredient found with name '{args.name}'", file=sys.stderr)
                print(f"  Use --id to specify an ingredient by ID", file=sys.stderr)
                sys.exit(1)
            ingredient_id = ingredient.id
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
            # Use exact name matching (case-insensitive)
            ingredient = get_ingredient(db, name=args.name)
            if not ingredient:
                print(f"✗ Error: No ingredient found with name '{args.name}'", file=sys.stderr)
                print(f"  Use --id to specify an ingredient by ID", file=sys.stderr)
                sys.exit(1)
            ingredient_id = ingredient.id
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
        except Exception as e:
            # Preserve JSON file on error (unless user cancelled)
            json_path = EDITABLE_DIR / f"ingredient_{ingredient_id}.json"
            if not isinstance(e, KeyboardInterrupt):
                if json_path.exists():
                    # Don't delete - preserve for user to fix
                    pass
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
            
            # Import the recipe
            recipe = import_new_recipe_from_json(json_path)
            print(f"✓ Added recipe: {recipe.name}")
            print(f"  JSON file deleted.")
        except (ValueError, Exception) as e:
            # Preserve JSON file on error so user can fix it
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
    """List all recipes, search recipes by name, or list recipes by subtag."""
    db = SessionLocal()
    try:
        from db_operations import list_recipes, list_tags
        
        if hasattr(args, 'search') and args.search:
            search_term = args.search.lower()
            
            # Check if this is a subtag search (check if any tags have this subtag)
            all_tags = list_tags(db)
            tags_with_subtag = [t for t in all_tags if t.subtag and t.subtag.name.lower() == search_term]
            
            if tags_with_subtag:
                # This is a subtag search - list recipes grouped by tag
                all_recipes = list_recipes(db)
                
                # Group recipes by tag name
                recipes_by_tag = {}
                tags_with_no_recipes = []
                for tag in tags_with_subtag:
                    recipes_with_tag = []
                    for recipe in all_recipes:
                        if recipe and tag in recipe.tags:
                            recipes_with_tag.append(recipe)
                    if recipes_with_tag:
                        recipes_by_tag[tag.name] = recipes_with_tag
                    else:
                        tags_with_no_recipes.append(tag.name)
                
                if not recipes_by_tag and not tags_with_no_recipes:
                    print(f"No tags found with subtag '{args.search}'")
                else:
                    print(f"\n{'='*70}")
                    print(f"Recipes with tags (subtag: '{args.search}')")
                    print(f"{'='*70}")
                    
                    # Sort tags alphabetically
                    for tag_name in sorted(recipes_by_tag.keys(), key=lambda x: x.upper()):
                        recipes = recipes_by_tag[tag_name]
                        print(f"\n{tag_name.upper()}")
                        for recipe in sorted(recipes, key=lambda r: r.name.lower()):
                            print(f"  [{recipe.id:3d}] {recipe.name}")
                    
                    # Show tags with no recipes at the end
                    if tags_with_no_recipes:
                        print(f"\nTags with no recipes:")
                        for tag_name in sorted(tags_with_no_recipes, key=lambda x: x.upper()):
                            print(f"  {tag_name}")
                    
                    # Show recipes with no tags
                    recipes_with_no_tags = []
                    for recipe in all_recipes:
                        if recipe and not recipe.tags:
                            recipes_with_no_tags.append(recipe)
                    
                    if recipes_with_no_tags:
                        print(f"\nRecipes with no tags:")
                        for recipe in sorted(recipes_with_no_tags, key=lambda r: r.name.lower()):
                            print(f"  [{recipe.id:3d}] {recipe.name}")
                    
                    print()
            else:
                # Search mode: fuzzy match recipe names
                recipes = list_recipes(db)
                if not recipes:
                    print("No recipes found.")
                else:
                    # Simple fuzzy matching: check if search term is in recipe name (case-insensitive)
                    matches = []
                    for recipe in recipes:
                        if recipe and search_term in recipe.name.lower():
                            matches.append(recipe)
                    
                    # Sort by relevance (exact match first, then by position)
                    matches.sort(key=lambda r: (r.name.lower().startswith(search_term), r.name.lower().find(search_term)))
                    
                    # Show top 3
                    top_matches = matches[:3]
                    if not top_matches:
                        print(f"No recipes found matching '{args.search}'")
                    else:
                        print(f"\n{'='*70}")
                        print(f"Recipes matching '{args.search}' (showing top {len(top_matches)})")
                        print(f"{'='*70}")
                        for recipe in top_matches:
                            print(f"  [{recipe.id:3d}] {recipe.name}")
                        print()
        else:
            # List all recipes (compact format)
            recipes = list_recipes(db)
            if not recipes:
                print("No recipes found.")
            else:
                for recipe in recipes:
                    if recipe:
                        print(f"[{recipe.id:3d}] {recipe.name}")
                
                # Check for subtags with no recipes
                from db_operations import list_subtags, list_tags
                all_subtags = list_subtags(db)
                all_recipes = list_recipes(db)
                all_tags = list_tags(db)
                
                # Get all tags that are used in recipes
                tags_in_recipes = set()
                for recipe in all_recipes:
                    if recipe:
                        tags_in_recipes.update(tag.id for tag in recipe.tags if tag)
                
                # Find subtags that have no recipes (tags with this subtag are not in any recipes)
                subtags_with_no_recipes = []
                for subtag in all_subtags:
                    # Get all tags with this subtag
                    tags_with_subtag = [tag for tag in all_tags if tag and tag.subtag and tag.subtag.id == subtag.id]
                    # Check if any of these tags are in recipes
                    if tags_with_subtag:
                        has_recipes = any(tag.id in tags_in_recipes for tag in tags_with_subtag)
                        if not has_recipes:
                            subtags_with_no_recipes.append(subtag.name)
                
                if subtags_with_no_recipes:
                    subtags_str = ', '.join(sorted(subtags_with_no_recipes))
                    print(f"\nNote: Subtags with no recipes: {subtags_str}")
    finally:
        db.close()


def cmd_recipe_info(args):
    """Display detailed information about a recipe."""
    recipe_id = None
    
    # Check for positional recipe_id first
    if hasattr(args, 'recipe_id') and args.recipe_id:
        recipe_id = args.recipe_id
    elif hasattr(args, 'id') and args.id:
        recipe_id = args.id
    elif hasattr(args, 'name') and args.name:
        db = SessionLocal()
        try:
            # Use exact name matching (case-insensitive)
            recipe = get_recipe(db, name=args.name)
            if not recipe:
                print(f"✗ Error: No recipe found with name '{args.name}'", file=sys.stderr)
                print(f"  Use recipe ID (positional) or --id to specify a recipe by ID", file=sys.stderr)
                sys.exit(1)
            recipe_id = recipe.id
        finally:
            db.close()
    
    if not recipe_id:
        print("✗ Error: Must provide recipe ID (positional or --id) or --name", file=sys.stderr)
        sys.exit(1)
    
    # Get and display recipe info
    db = SessionLocal()
    try:
        recipe = get_recipe(db, recipe_id=recipe_id)
        if not recipe:
            print(f"✗ Error: Recipe not found (ID: {recipe_id})", file=sys.stderr)
            sys.exit(1)
        
        print_recipe_info(recipe)
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
            # Use exact name matching (case-insensitive)
            recipe = get_recipe(db, name=args.name)
            if not recipe:
                print(f"✗ Error: No recipe found with name '{args.name}'", file=sys.stderr)
                print(f"  Use --id to specify a recipe by ID", file=sys.stderr)
                sys.exit(1)
            recipe_id = recipe.id
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
        except Exception as e:
            # Preserve JSON file on error (unless user cancelled)
            json_path = EDITABLE_DIR / f"recipe_{recipe_id}.json"
            if not isinstance(e, KeyboardInterrupt):
                if json_path.exists():
                    # Don't delete - preserve for user to fix
                    pass
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
                if not article:
                    continue
                tags_str = ', '.join([tag.name for tag in article.tags if tag]) if article.tags else 'none'
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
            for type_obj in sorted(types, key=lambda t: t.name):
                ingredient_count = len(type_obj.ingredients) if type_obj.ingredients else 0
                print(f"  [{type_obj.id:3d}] {type_obj.name:30s} ({ingredient_count} ingredient{'s' if ingredient_count != 1 else ''})")
            print()
    finally:
        db.close()


def cmd_add_type(args):
    """Add a new ingredient type."""
    db = SessionLocal()
    try:
        from db_operations import add_ingredient_type
        ingredient_type = add_ingredient_type(db, args.name)
        print(f"✓ Added ingredient type: {ingredient_type.name} (ID: {ingredient_type.id})")
    except ValueError as e:
        print(f"✗ Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


def cmd_remove_type(args):
    """Remove an ingredient type by ID."""
    db = SessionLocal()
    try:
        from db_operations import delete_ingredient_type
        deleted = delete_ingredient_type(db, args.id)
        if deleted:
            print(f"✓ Removed ingredient type (ID: {args.id})")
        else:
            print(f"✗ Error: Ingredient type not found (ID: {args.id})", file=sys.stderr)
            sys.exit(1)
    except ValueError as e:
        print(f"✗ Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


def cmd_list_subtags(args):
    """List all subtags."""
    db = SessionLocal()
    try:
        from db_operations import list_subtags
        subtags = list_subtags(db)
        if not subtags:
            print("No subtags found.")
        else:
            print(f"\n{'='*70}")
            print(f"Subtags ({len(subtags)} total)")
            print(f"{'='*70}")
            for subtag in sorted(subtags, key=lambda s: s.name):
                # Count tags using this subtag
                tag_count = len(subtag.tags) if subtag.tags else 0
                print(f"  [{subtag.id:3d}] {subtag.name:30s} ({tag_count} tag{'s' if tag_count != 1 else ''})")
            print()
    finally:
        db.close()


def cmd_add_subtag(args):
    """Add a new subtag."""
    db = SessionLocal()
    try:
        from db_operations import add_subtag
        subtag = add_subtag(db, args.name)
        print(f"✓ Added subtag: {subtag.name} (ID: {subtag.id})")
    except ValueError as e:
        print(f"✗ Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


def cmd_remove_subtag(args):
    """Remove a subtag by ID."""
    db = SessionLocal()
    try:
        from db_operations import delete_subtag
        deleted = delete_subtag(db, args.id)
        if deleted:
            print(f"✓ Removed subtag (ID: {args.id})")
        else:
            print(f"✗ Error: Subtag not found (ID: {args.id})", file=sys.stderr)
            sys.exit(1)
    except ValueError as e:
        print(f"✗ Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


def cmd_list_tags(args):
    """List all tags, organized by subtag."""
    db = SessionLocal()
    try:
        from db_operations import list_tags
        tags = list_tags(db)
        if not tags:
            print("No tags found.")
        else:
            print(f"\n{'='*70}")
            print(f"Tags ({len(tags)} total)")
            print(f"{'='*70}")
            
            # Group tags by subtag
            tags_by_subtag = {}
            tags_without_subtag = []
            
            for tag in tags:
                if tag.subtag:
                    subtag_name = tag.subtag.name
                    if subtag_name not in tags_by_subtag:
                        tags_by_subtag[subtag_name] = []
                    tags_by_subtag[subtag_name].append(tag)
                else:
                    tags_without_subtag.append(tag)
            
            # Sort subtags alphabetically
            sorted_subtags = sorted(tags_by_subtag.keys())
            
            # Print tags grouped by subtag
            for subtag_name in sorted_subtags:
                print(f"\n{subtag_name.upper()}:")
                # Sort tags within each subtag alphabetically by name
                for tag in sorted(tags_by_subtag[subtag_name], key=lambda t: t.name):
                    tag_display = f"{tag.name} --> {tag.subtag.name}"
                    print(f"  [{tag.id:3d}] {tag_display}")
            
            # Print tags without subtags (if any)
            if tags_without_subtag:
                print(f"\n(no subtag):")
                for tag in sorted(tags_without_subtag, key=lambda t: t.name):
                    print(f"  [{tag.id:3d}] {tag.name}")
            
            print()
    finally:
        db.close()


def cmd_add_tag(args):
    """Add a new tag."""
    db = SessionLocal()
    try:
        from db_operations import add_tag
        tag = add_tag(db, args.name, subtag_name=args.subtag if hasattr(args, 'subtag') and args.subtag else None)
        subtag_str = f" (subtag: {tag.subtag.name})" if tag.subtag else ""
        print(f"✓ Added tag: {tag.name}{subtag_str} (ID: {tag.id})")
    except ValueError as e:
        print(f"✗ Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


def cmd_remove_tag(args):
    """Remove a tag by ID."""
    db = SessionLocal()
    try:
        from db_operations import delete_tag
        deleted = delete_tag(db, args.id)
        if deleted:
            print(f"✓ Removed tag (ID: {args.id})")
        else:
            print(f"✗ Error: Tag not found (ID: {args.id})", file=sys.stderr)
            sys.exit(1)
    except ValueError as e:
        print(f"✗ Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


def cmd_edit_tag(args):
    """Edit a tag using JSON file workflow."""
    tag_id = args.id
    
    from json_editor import export_tag_to_json, import_tag_from_json, check_tag_json_exists
    
    if check_tag_json_exists(tag_id):
        # JSON file exists, import it
        try:
            tag = import_tag_from_json(tag_id)
            # Refresh tag from database to ensure we can access relationships
            db = SessionLocal()
            try:
                from db_operations import get_tag
                tag = get_tag(db, tag_id=tag_id)
                print(f"✓ Updated tag (ID: {tag.id})")
                print(f"  Name: {tag.name}")
                if tag.subtag:
                    print(f"  Subtag: {tag.subtag.name}")
                print(f"  JSON file deleted.")
            finally:
                db.close()
        except Exception as e:
            # Preserve JSON file on error so user can fix it
            print(f"\n✗ Error: {e}", file=sys.stderr)
            json_path = export_tag_to_json(tag_id)  # Get path for error message
            if json_path.exists():
                print(f"  JSON file preserved at: {json_path}", file=sys.stderr)
                print(f"  Please fix the issue and run the command again.", file=sys.stderr)
            sys.exit(1)
    else:
        # JSON file doesn't exist, create it
        try:
            json_path = export_tag_to_json(tag_id)
            print(f"✓ Created JSON file: {json_path}")
            print(f"  Edit the file with your tag details, then run the same command again to update it.")
            print(f"  (Delete the file to cancel)")
        except Exception as e:
            print(f"✗ Error: {e}", file=sys.stderr)
            sys.exit(1)


def cmd_recipe_cook(args):
    """Search recipes by ingredients (exact matching)."""
    db = SessionLocal()
    try:
        from db_operations import search_recipes_by_ingredients_exact
        # Handle ingredients with spaces:
        # - Join all arguments with spaces first (so "pumpkin puree" becomes one ingredient)
        # - Then split by commas if present (so "pumpkin puree, black beans" becomes two ingredients)
        # - If no commas, treat the entire joined string as a single ingredient
        joined_args = ' '.join(args.ingredients)
        
        # Split by comma if commas are present, otherwise treat as single ingredient
        if ',' in joined_args:
            ingredient_list = [i.strip() for i in joined_args.split(',') if i.strip()]
        else:
            ingredient_list = [joined_args.strip()] if joined_args.strip() else []
        
        ingredient_query = ', '.join(ingredient_list)
        results = search_recipes_by_ingredients_exact(
            db,
            ingredient_query,
            min_matches=1
        )
        
        if not results:
            print(f"No recipes found with ingredients: {ingredient_query}")
        else:
            print(f"\n{'='*70}")
            print(f"Recipes with ingredients: {ingredient_query} ({len(results)} found)")
            print(f"{'='*70}")
            for recipe, match_count in results:
                if recipe:
                    print(f"  [{recipe.id:3d}] {recipe.name:40s} (Matches: {match_count})")
            print()
    except ValueError as e:
        print(f"✗ {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"✗ Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


def cmd_recipe_tag(args):
    """List recipes with a specific tag."""
    db = SessionLocal()
    try:
        from db_operations import get_tag, list_recipes
        
        # Join all tag arguments with spaces to handle tags with spaces
        tag_name = ' '.join(args.tag)
        
        # Check if tag exists (exact match)
        tag = get_tag(db, name=tag_name)
        if not tag:
            print(f"✗ Error: Tag '{tag_name}' not found. Use 'python cli.py tag list' to see available tags.", file=sys.stderr)
            sys.exit(1)
        
        # Get all recipes and filter by tag (use explicit ID comparison for reliability)
        all_recipes = list_recipes(db)
        matching_recipes = []
        for recipe in all_recipes:
            if recipe:
                # Use explicit tag ID comparison instead of object identity
                recipe_tag_ids = {t.id for t in recipe.tags if t}
                if tag.id in recipe_tag_ids:
                    matching_recipes.append(recipe)
        
        if not matching_recipes:
            print(f"No recipes found with tag '{tag_name}'")
        else:
            print(f"\n{'='*70}")
            print(f"Recipes with tag '{tag_name}' ({len(matching_recipes)} found)")
            print(f"{'='*70}")
            for recipe in matching_recipes:
                print(f"  [{recipe.id:3d}] {recipe.name}")
            print()
    finally:
        db.close()


def cmd_search(args):
    """
    Search command for recipes (exact ingredient matching).
    
    Usage:
        python cli.py search "cucumber, dill, mint" recipe --n 1
    """
    db = SessionLocal()
    try:
        if args.entity_type == 'recipe':
            try:
                from db_operations import search_recipes_by_ingredients_exact
                results = search_recipes_by_ingredients_exact(
                    db,
                    args.query,
                    min_matches=args.n
                )
                
                if not results:
                    print(f"No recipes found matching '{args.query}' (minimum {args.n} match(es) required)")
                else:
                    print(f"\n{'='*70}")
                    print(f"Search Results for '{args.query}' ({len(results)} found)")
                    print(f"{'='*70}")
                    for recipe, match_count in results:
                        if recipe:
                            print(f"  [{recipe.id:3d}] {recipe.name:40s} (Matches: {match_count})")
                    print()
            except ValueError as e:
                # This is the safety check error - show it clearly
                print(f"✗ {e}", file=sys.stderr)
                sys.exit(1)
            except Exception as e:
                print(f"✗ Error: {e}", file=sys.stderr)
                sys.exit(1)
        else:
            print(f"✗ Error: Search only supports 'recipe' entity type. Ingredient search has been removed.", file=sys.stderr)
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
        # Filter out None ingredients
        all_ingredients = db.query(Ingredient).all()
        ingredient_count = len([ing for ing in all_ingredients if ing])
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
            total_ingredients_in_recipes = sum(len([ing for ing in recipe.ingredients if ing]) for recipe in recipes_with_ingredients if recipe)
            if recipe_count > 0:
                avg_ingredients_per_recipe = total_ingredients_in_recipes / recipe_count
        
        # Calculate average tags per recipe
        avg_tags_per_recipe = 0.0
        if recipe_count > 0:
            recipes_with_tags = db.query(Recipe).filter(Recipe.tags.any()).all()
            total_tags_in_recipes = sum(len([tag for tag in recipe.tags if tag]) for recipe in recipes_with_tags if recipe)
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


def cmd_backup(args):
    """Create a timestamped backup copy of the database."""
    from config_loader import get_database_path
    from pathlib import Path
    import shutil
    from datetime import datetime
    
    db_path = get_database_path()
    if not db_path.exists():
        print(f"✗ Error: Database file not found: {db_path}", file=sys.stderr)
        sys.exit(1)
    
    # Create backup directory in data/ folder
    backup_dir = db_path.parent / "backups"
    backup_dir.mkdir(exist_ok=True)
    
    # Generate timestamped filename: backup_YYYYMMDD_HHMMSS.db
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"backup_{timestamp}.db"
    backup_path = backup_dir / backup_filename
    
    try:
        # Deep copy the database file
        shutil.copy2(db_path, backup_path)
        print(f"✓ Backup created: {backup_path}")
        print(f"  Original database: {db_path}")
    except Exception as e:
        print(f"✗ Error creating backup: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_cleanup(args):
    """Delete all JSON staging files in staging/addable/ and staging/editable/ directories."""
    from pathlib import Path
    from config_loader import get_config
    
    _config = get_config()
    project_root = Path(__file__).parent
    
    deleted_count = 0
    
    # Get staging directories from config
    addable_dir = project_root / _config.get('staging', {}).get('addable_dir', 'staging/addable')
    editable_dir = project_root / _config.get('staging', {}).get('editable_dir', 'staging/editable')
    
    # Clean all JSON files in addable directory and subdirectories
    if addable_dir.exists():
        for json_file in addable_dir.rglob("*.json"):
            json_file.unlink()
            deleted_count += 1
            print(f"  Deleted: {json_file}")
    
    # Clean all JSON files in editable directory and subdirectories
    if editable_dir.exists():
        for json_file in editable_dir.rglob("*.json"):
            json_file.unlink()
            deleted_count += 1
            print(f"  Deleted: {json_file}")
    
    if deleted_count == 0:
        print("✓ No staging files found to clean up.")
    else:
        print(f"✓ Cleaned up {deleted_count} staging file(s).")


def cmd_consistent(args):
    """Check database consistency: verify all recipe ingredients exist in ingredients database, all tags exist in tag list, all types exist in types list, and all subtags exist in subtag list."""
    db = SessionLocal()
    try:
        from db_operations import list_recipes, list_ingredients, list_tags, list_ingredient_types, list_subtags
        
        all_recipes = list_recipes(db)
        all_ingredients = list_ingredients(db)
        all_tags = list_tags(db)
        all_types = list_ingredient_types(db)
        all_subtags = list_subtags(db)
        
        # Create a set of all ingredient names (normalized to lowercase)
        ingredient_names = {ing.name.lower() for ing in all_ingredients if ing}
        
        # Create a set of all tag IDs
        tag_ids = {tag.id for tag in all_tags}
        
        # Create a set of all type IDs
        type_ids = {t.id for t in all_types}
        
        # Create a set of all subtag IDs
        subtag_ids = {st.id for st in all_subtags}
        
        print(f"\n{'='*70}")
        print("Database Consistency Check")
        print(f"{'='*70}")
        print(f"Checking {len(all_recipes)} recipe(s) and {len(all_ingredients)} ingredient(s)...")
        print(f"Verifying against {len(all_ingredients)} ingredient(s), {len(all_tags)} tag(s), {len(all_types)} type(s), and {len(all_subtags)} subtag(s)...")
        print()
        
        issues_found = []
        
        # Check recipe ingredients
        for recipe in all_recipes:
            if not recipe:
                continue
            recipe_ingredients = recipe.ingredients
            for ingredient in recipe_ingredients:
                if not ingredient:
                    continue
                # Check if ingredient name exists in ingredients database
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
            recipe_tags = recipe.tags
            for tag in recipe_tags:
                if not tag:
                    continue
                # Check if tag ID exists in tags database
                if tag.id not in tag_ids:
                    issues_found.append({
                        'type': 'recipe_tag',
                        'recipe_id': recipe.id,
                        'recipe_name': recipe.name,
                        'tag_id': tag.id,
                        'tag_name': tag.name
                    })
        
        # Removed ingredient tag check - ingredients no longer have tags
        
        # Check ingredient types (only if ingredient has a type - typeless is allowed)
        for ingredient in all_ingredients:
            if not ingredient:
                continue
            if ingredient.type:
                # Check if type ID exists in types database
                if ingredient.type.id not in type_ids:
                    issues_found.append({
                        'type': 'ingredient_type',
                        'ingredient_id': ingredient.id,
                        'ingredient_name': ingredient.name,
                        'type_id': ingredient.type.id,
                        'type_name': ingredient.type.name if ingredient.type else 'unknown'
                    })
        
        # Check tag subtags (only if tag has a subtag - subtagless is allowed)
        for tag in all_tags:
            if not tag:
                continue
            if tag.subtag:
                # Check if subtag ID exists in subtags database
                if tag.subtag.id not in subtag_ids:
                    issues_found.append({
                        'type': 'tag_subtag',
                        'tag_id': tag.id,
                        'tag_name': tag.name,
                        'subtag_id': tag.subtag.id,
                        'subtag_name': tag.subtag.name if tag.subtag else 'unknown'
                    })
        
        # Find unused items and items without optional fields
        # Unused types (types not used in any ingredients)
        used_type_ids = {ing.type.id for ing in all_ingredients if ing and ing.type}
        unused_types = [t for t in all_types if t.id not in used_type_ids]
        
        # Unused tags (tags not used in recipes, ingredients, or articles)
        used_tag_ids = set()
        for recipe in all_recipes:
            if recipe:
                used_tag_ids.update(tag.id for tag in recipe.tags if tag)
        # Removed ingredient tag tracking - ingredients no longer have tags
        # Check articles too
        from models import Article
        all_articles = db.query(Article).all()
        for article in all_articles:
            if article:
                used_tag_ids.update(tag.id for tag in article.tags if tag)
        unused_tags = [t for t in all_tags if t.id not in used_tag_ids]
        
        # Unused ingredients (ingredients not in any recipes)
        used_ingredient_ids = set()
        for recipe in all_recipes:
            if recipe:
                used_ingredient_ids.update(ing.id for ing in recipe.ingredients if ing)
        unused_ingredients = [ing for ing in all_ingredients if ing and ing.id not in used_ingredient_ids]
        
        # Tags without subtags
        tags_without_subtags = [t for t in all_tags if not t.subtag]
        
        # Ingredients without types
        ingredients_without_types = [ing for ing in all_ingredients if ing and not ing.type]
        
        if not issues_found:
            print("✓ Database is consistent!")
            print(f"  All recipe ingredients exist in the ingredients database.")
            print(f"  All tags used in recipes exist in the tag list.")
            print(f"  All types used in ingredients exist in the types list.")
            print(f"  All subtags used in tags exist in the subtag list.")
        else:
            print(f"✗ Found {len(issues_found)} consistency issue(s):")
            print()
            
            # Group issues by type for better reporting
            ingredient_issues = [i for i in issues_found if i['type'] == 'recipe_ingredient']
            recipe_tag_issues = [i for i in issues_found if i['type'] == 'recipe_tag']
            ingredient_tag_issues = [i for i in issues_found if i['type'] == 'ingredient_tag']
            ingredient_type_issues = [i for i in issues_found if i['type'] == 'ingredient_type']
            tag_subtag_issues = [i for i in issues_found if i['type'] == 'tag_subtag']
            
            if ingredient_issues:
                print(f"  Missing Ingredients ({len(ingredient_issues)} issue(s)):")
                for issue in ingredient_issues:
                    print(f"    Recipe #{issue['recipe_id']}: {issue['recipe_name']}")
                    print(f"      Missing ingredient: {issue['ingredient_name']}")
                print()
            
            if recipe_tag_issues:
                print(f"  Invalid Recipe Tags ({len(recipe_tag_issues)} issue(s)):")
                for issue in recipe_tag_issues:
                    print(f"    Recipe #{issue['recipe_id']}: {issue['recipe_name']}")
                    print(f"      Invalid tag: {issue['tag_name']} (ID: {issue['tag_id']})")
                print()
            
            if ingredient_tag_issues:
                print(f"  Invalid Ingredient Tags ({len(ingredient_tag_issues)} issue(s)):")
                for issue in ingredient_tag_issues:
                    print(f"    Ingredient #{issue['ingredient_id']}: {issue['ingredient_name']}")
                    print(f"      Invalid tag: {issue['tag_name']} (ID: {issue['tag_id']})")
                print()
            
            if ingredient_type_issues:
                print(f"  Invalid Ingredient Types ({len(ingredient_type_issues)} issue(s)):")
                for issue in ingredient_type_issues:
                    print(f"    Ingredient #{issue['ingredient_id']}: {issue['ingredient_name']}")
                    print(f"      Invalid type: {issue['type_name']} (ID: {issue['type_id']})")
                print()
            
            if tag_subtag_issues:
                print(f"  Invalid Tag Subtags ({len(tag_subtag_issues)} issue(s)):")
                for issue in tag_subtag_issues:
                    print(f"    Tag #{issue['tag_id']}: {issue['tag_name']}")
                    print(f"      Invalid subtag: {issue['subtag_name']} (ID: {issue['subtag_id']})")
                print()
            
            print(f"Total: {len(issues_found)} issue(s) found")
            print()
        
        # Report unused items and items without optional fields
        # Note: unused_subtags is not currently tracked, so we skip it in the condition
        if unused_types or unused_tags or unused_ingredients or tags_without_subtags or ingredients_without_types:
            print("=" * 70)
            print("Additional Information (Not Errors)")
            print("=" * 70)
            print()
            
            if unused_types:
                print(f"Unused Types ({len(unused_types)}):")
                for t in sorted(unused_types, key=lambda x: x.name):
                    print(f"  [{t.id:3d}] {t.name}")
                print()
            
            if unused_tags:
                print(f"Unused Tags ({len(unused_tags)}):")
                for t in sorted(unused_tags, key=lambda x: x.name):
                    subtag_str = f" --> {t.subtag.name}" if t.subtag else ""
                    print(f"  [{t.id:3d}] {t.name}{subtag_str}")
                print()
            
            if unused_ingredients:
                print(f"Unused Ingredients ({len(unused_ingredients)}):")
                for ing in sorted(unused_ingredients, key=lambda x: x.name):
                    type_name = ing.type.name if ing.type else '(no type)'
                    print(f"  [{ing.id:3d}] {ing.name} ({type_name})")
                print()
            
            if tags_without_subtags:
                print(f"Tags Without Subtags ({len(tags_without_subtags)}):")
                for t in sorted(tags_without_subtags, key=lambda x: x.name):
                    print(f"  [{t.id:3d}] {t.name}")
                print()
            
            if ingredients_without_types:
                print(f"Ingredients Without Types ({len(ingredients_without_types)}):")
                for ing in sorted(ingredients_without_types, key=lambda x: x.name):
                    print(f"  [{ing.id:3d}] {ing.name}")
                print()
        
        print()
    finally:
        db.close()


# REMOVED: cmd_embed and cmd_ask - semantic search and Ollama removed


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


# REMOVED: cmd_embed_help - embeddings removed
    except Exception as e:
        print(f"✗ Error reading help file: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_edit_shortcut(args):
    """Shortcut command: edit recipe/ingredient/article by ID (defaults to recipe)."""
    # Create a namespace object with the expected arguments
    class EditArgs:
        def __init__(self, entity_id, entity_type):
            self.id = entity_id
            if entity_type in ['recipe', 'ingredient']:
                self.name = None
    
    # Route to the appropriate edit command
    if args.entity_type == 'recipe':
        edit_args = EditArgs(args.entity_id, 'recipe')
        cmd_edit_recipe(edit_args)
    elif args.entity_type == 'ingredient':
        edit_args = EditArgs(args.entity_id, 'ingredient')
        cmd_edit_ingredient(edit_args)
    elif args.entity_type == 'article':
        edit_args = EditArgs(args.entity_id, 'article')
        cmd_edit_article(edit_args)


def cmd_info_shortcut(args):
    """Shortcut command: show info for recipe/ingredient/article by ID (defaults to recipe)."""
    # Create a namespace object with the expected arguments
    class InfoArgs:
        def __init__(self, entity_id, entity_type):
            self.id = entity_id
            if entity_type in ['recipe', 'ingredient']:
                self.name = None
    
    # Route to the appropriate info command
    if args.entity_type == 'recipe':
        info_args = InfoArgs(args.entity_id, 'recipe')
        cmd_recipe_info(info_args)
    elif args.entity_type == 'ingredient':
        info_args = InfoArgs(args.entity_id, 'ingredient')
        cmd_ingredient_info(info_args)
    elif args.entity_type == 'article':
        # Articles don't have an info command yet, but we can create a simple one
        db = SessionLocal()
        try:
            from models import Article
            article = db.query(Article).filter(Article.id == args.entity_id).first()
            if not article:
                print(f"✗ Error: Article not found (ID: {args.entity_id})", file=sys.stderr)
                sys.exit(1)
            print_article(article)
        finally:
            db.close()


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
    
    list_ing_parser = ingredient_subparsers.add_parser('list', help='List all ingredients or search ingredients by name')
    list_ing_parser.add_argument('search', nargs='?', help='Optional search string to filter ingredients by name, or subtag name to list by subtag')
    list_ing_parser.set_defaults(func=cmd_list_ingredients)
    
    type_ing_parser = ingredient_subparsers.add_parser('type', help='List all ingredients organized by type')
    type_ing_parser.set_defaults(func=cmd_list_ingredients_by_type)
    
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
    
    list_recipe_parser = recipe_subparsers.add_parser('list', help='List all recipes, or search recipes by name if search string provided')
    list_recipe_parser.add_argument('search', nargs='?', help='Optional search string to filter recipes by name')
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
    
    # Info recipe command (accepts positional INT or --id/--name)
    info_recipe_parser = recipe_subparsers.add_parser('info', help='Display detailed information about a recipe')
    info_recipe_parser.add_argument('recipe_id', nargs='?', type=int, help='Recipe ID (positional)')
    info_recipe_group = info_recipe_parser.add_mutually_exclusive_group(required=False)
    info_recipe_group.add_argument('--name', help='Recipe name (fuzzy matching)')
    info_recipe_group.add_argument('--id', type=int, help='Recipe ID')
    info_recipe_parser.set_defaults(func=cmd_recipe_info)
    
    # Cook command (ingredient matching)
    cook_recipe_parser = recipe_subparsers.add_parser('cook', help='Search recipes by ingredients (exact matching)')
    cook_recipe_parser.add_argument('ingredients', nargs='+', help='Ingredient names (spaces are preserved; use commas to separate multiple ingredients, e.g., "pumpkin puree, black beans")')
    cook_recipe_parser.set_defaults(func=cmd_recipe_cook)
    
    # Tag command (list recipes with tag)
    tag_recipe_parser = recipe_subparsers.add_parser('tag', help='List recipes with a specific tag')
    tag_recipe_parser.add_argument('tag', nargs='+', help='Tag name (spaces are preserved, e.g., "chlorophyll sauce")')
    tag_recipe_parser.set_defaults(func=cmd_recipe_tag)
    
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
    
    # Type commands
    type_parser = subparsers.add_parser('type', help='Ingredient type operations')
    type_subparsers = type_parser.add_subparsers(dest='type_action')
    
    add_type_parser = type_subparsers.add_parser('add', help='Add a new ingredient type')
    add_type_parser.add_argument('name', help='Name of the ingredient type')
    add_type_parser.set_defaults(func=cmd_add_type)
    
    list_type_parser = type_subparsers.add_parser('list', help='List all ingredient types')
    list_type_parser.set_defaults(func=cmd_list_types)
    
    remove_type_parser = type_subparsers.add_parser('remove', help='Remove an ingredient type by ID')
    remove_type_parser.add_argument('--id', type=int, required=True, help='Ingredient type ID')
    remove_type_parser.set_defaults(func=cmd_remove_type)
    
    # Tag commands
    tag_parser = subparsers.add_parser('tag', help='Tag operations')
    tag_subparsers = tag_parser.add_subparsers(dest='tag_action')
    
    add_tag_parser = tag_subparsers.add_parser('add', help='Add a new tag')
    add_tag_parser.add_argument('name', help='Name of the tag')
    add_tag_parser.add_argument('--subtag', help='Optional subtag')
    add_tag_parser.set_defaults(func=cmd_add_tag)
    
    list_tag_parser = tag_subparsers.add_parser('list', help='List all tags')
    list_tag_parser.set_defaults(func=cmd_list_tags)
    
    edit_tag_parser = tag_subparsers.add_parser('edit', help='Edit a tag using JSON file')
    edit_tag_parser.add_argument('--id', type=int, required=True, help='Tag ID')
    edit_tag_parser.set_defaults(func=cmd_edit_tag)
    
    remove_tag_parser = tag_subparsers.add_parser('remove', help='Remove a tag by ID')
    remove_tag_parser.add_argument('--id', type=int, required=True, help='Tag ID')
    remove_tag_parser.set_defaults(func=cmd_remove_tag)
    
    # Subtag commands
    subtag_parser = subparsers.add_parser('subtag', help='Subtag operations')
    subtag_subparsers = subtag_parser.add_subparsers(dest='subtag_action')
    
    add_subtag_parser = subtag_subparsers.add_parser('add', help='Add a new subtag')
    add_subtag_parser.add_argument('name', help='Name of the subtag')
    add_subtag_parser.set_defaults(func=cmd_add_subtag)
    
    list_subtag_parser = subtag_subparsers.add_parser('list', help='List all subtags')
    list_subtag_parser.set_defaults(func=cmd_list_subtags)
    
    remove_subtag_parser = subtag_subparsers.add_parser('remove', help='Remove a subtag by ID')
    remove_subtag_parser.add_argument('--id', type=int, required=True, help='Subtag ID')
    remove_subtag_parser.set_defaults(func=cmd_remove_subtag)
    
    # Unified search command
    search_parser = subparsers.add_parser('search', help='Search recipes by exact ingredient matching')
    search_parser.add_argument('query', help='Comma-delimited list of ingredients (e.g., "cucumber, dill, mint")')
    search_parser.add_argument('entity_type', nargs='?', choices=['recipe'], default='recipe', help='Type of entity to search (default: recipe)')
    search_parser.add_argument('--n', type=int, default=1, help='Minimum ingredient matches required (default: 1)')
    search_parser.set_defaults(func=cmd_search)
    
    # Edit shortcut command
    edit_shortcut_parser = subparsers.add_parser('edit', help='Edit a recipe, ingredient, or article by ID (defaults to recipe)')
    edit_shortcut_parser.add_argument('entity_id', type=int, help='ID of the entity to edit')
    edit_shortcut_parser.add_argument('entity_type', nargs='?', choices=['recipe', 'ingredient', 'article'], default='recipe', help='Type of entity to edit (default: recipe)')
    edit_shortcut_parser.set_defaults(func=cmd_edit_shortcut)
    
    # Info shortcut command
    info_shortcut_parser = subparsers.add_parser('info', help='Display detailed information about a recipe, ingredient, or article by ID (defaults to recipe)')
    info_shortcut_parser.add_argument('entity_id', type=int, help='ID of the entity to show info for')
    info_shortcut_parser.add_argument('entity_type', nargs='?', choices=['recipe', 'ingredient', 'article'], default='recipe', help='Type of entity (default: recipe)')
    info_shortcut_parser.set_defaults(func=cmd_info_shortcut)
    
    help_parser = subparsers.add_parser('help', help='Show help information for all commands')
    help_parser.set_defaults(func=cmd_help)
    
    stats_parser = subparsers.add_parser('stats', help='Display database statistics')
    stats_parser.set_defaults(func=cmd_stats)
    
    backup_parser = subparsers.add_parser('backup', help='Create a timestamped backup copy of the database')
    backup_parser.set_defaults(func=cmd_backup)
    
    cleanup_parser = subparsers.add_parser('cleanup', help='Delete all JSON staging files (staging/addable/ and staging/editable/)')
    cleanup_parser.set_defaults(func=cmd_cleanup)
    
    # Consistency check command
    consistent_parser = subparsers.add_parser('consistent', help='Check database consistency: verify all recipe ingredients exist in ingredients database, and all tags exist in tag list')
    consistent_parser.set_defaults(func=cmd_consistent)
    
    # REMOVED: ask and embed commands - Ollama and semantic search removed
    
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
