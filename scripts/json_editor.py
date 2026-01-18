"""
JSON-based recipe editing functionality.
"""
import json
import time
import sys
import warnings
from pathlib import Path
from database import SessionLocal

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
from db_operations import (
    get_recipe, update_recipe, add_ingredients_to_recipe, remove_ingredients_from_recipe,
    add_tags_to_recipe, remove_tags_from_recipe, get_ingredient, add_ingredient,
    update_ingredient, add_tags_to_ingredient, remove_tags_from_ingredient,
    get_article, update_article, add_article, add_tags_to_article, remove_tags_from_article,
    get_tag
)
from models import Recipe, Ingredient, Article, Tag

# Get directory paths from config
from config_loader import get_config

_config = get_config()
_project_root = Path(__file__).parent.parent
EDITABLE_DIR = _project_root / _config.get('staging', {}).get('editable_dir', 'editable')
ADDABLE_DIR = _project_root / _config.get('staging', {}).get('addable_dir', 'addable')


def ensure_editable_dir():
    """Ensure the editable directory exists."""
    EDITABLE_DIR.mkdir(parents=True, exist_ok=True)


def ensure_addable_dir():
    """Ensure the addable directory exists."""
    ADDABLE_DIR.mkdir(parents=True, exist_ok=True)


def get_json_path(recipe_id: int) -> Path:
    """Get the JSON file path for a recipe ID."""
    ensure_editable_dir()
    return EDITABLE_DIR / f"recipe_{recipe_id}.json"


def recipe_to_json(recipe: Recipe) -> dict:
    """Convert a recipe object to a JSON-serializable dictionary."""
    # Convert literal \n to actual newlines for better readability
    instructions = recipe.instructions or ''
    if instructions:
        instructions = instructions.replace('\\n', '\n')
    
    notes = recipe.notes or ''
    if notes:
        notes = notes.replace('\\n', '\n')
    
    return {
        'id': recipe.id,
        'name': recipe.name,
        'instructions': instructions,
        'notes': notes,
        'tags': [tag.name for tag in recipe.tags],
        'ingredients': [ing.name for ing in recipe.ingredients]
    }


def json_to_recipe_data(json_data: dict) -> tuple[dict, list[tuple[str, str]]]:
    """
    Convert JSON data to a format suitable for updating the recipe.
    Applies spell checking and normalization to all text fields.
    Returns: (recipe_data_dict, list of (original, corrected) tuples for corrections made)
    """
    corrections = []
    
    # Handle instructions and notes - preserve newlines and normalize
    instructions = json_data.get('instructions', '').strip()
    if instructions:
        instructions = instructions.replace('\\n', '\n')
        from db_operations import normalize_text_words
        instructions, inst_corrections = normalize_text_words(instructions)
        corrections.extend(inst_corrections)
    
    notes = json_data.get('notes', '').strip()
    if notes:
        notes = notes.replace('\\n', '\n')
        from db_operations import normalize_text_words
        notes, note_corrections = normalize_text_words(notes)
        corrections.extend(note_corrections)
    
    from db_operations import normalize_name
    
    name = json_data.get('name', '').strip()
    # Don't normalize name here - let update_recipe handle it
    # This allows users to fix typos
    
    # Normalize tags with spell checking
    raw_tags = [t.strip() for t in json_data.get('tags', []) if t.strip()]
    from db_operations import normalize_tags
    normalized_tags, tag_corrections = normalize_tags(raw_tags)
    corrections.extend(tag_corrections)
    
    # Normalize ingredient names with spell checking
    raw_ingredients = [ing.strip() for ing in json_data.get('ingredients', []) if ing.strip()]
    normalized_ingredients = []
    for ing in raw_ingredients:
        normalized_ing, ing_corrections = normalize_name(ing, check_spelling=True)
        normalized_ingredients.append(normalized_ing)
        corrections.extend(ing_corrections)
    
    return {
        'name': name,
        'instructions': instructions or None,
        'notes': notes or None,
        'tags': normalized_tags,
        'ingredients': normalized_ingredients
    }, corrections


def export_recipe_to_json(recipe_id: int) -> Path:
    """Export a recipe to a JSON file. Returns the path to the JSON file."""
    db = SessionLocal()
    try:
        recipe = get_recipe(db, recipe_id=recipe_id)
        if not recipe:
            raise ValueError(f"Recipe with ID {recipe_id} not found")
        
        json_path = get_json_path(recipe_id)
        recipe_data = recipe_to_json(recipe)
        
        # Write JSON with indentation for readability
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(recipe_data, f, indent=2, ensure_ascii=False)
        
        return json_path
    finally:
        db.close()


def import_recipe_from_json(recipe_id: int) -> Recipe:
    """Import a recipe from a JSON file and update the database. Deletes the JSON file after import."""
    json_path = get_json_path(recipe_id)
    
    if not json_path.exists():
        raise ValueError(f"No JSON file found for recipe {recipe_id}. Run edit command first to create it.")
    
    db = SessionLocal()
    try:
        # Read JSON file
        with open(json_path, 'r', encoding='utf-8') as f:
            json_data = json.load(f)
        
        if not json_data:
            raise ValueError("JSON file is empty or invalid")
        
        # Get the recipe
        recipe = get_recipe(db, recipe_id=recipe_id)
        if not recipe:
            raise ValueError(f"Recipe with ID {recipe_id} not found in database")
        
        # Convert JSON to recipe data (with spell checking)
        recipe_data, corrections = json_to_recipe_data(json_data)
        
        # Update basic fields
        # Compare names after normalization to detect actual changes
        from db_operations import normalize_name
        new_name_normalized, name_corrections = normalize_name(recipe_data['name']) if recipe_data['name'] else ('', [])
        current_name_normalized = recipe.name  # Already normalized in database
        
        # Combine all corrections
        all_corrections = corrections + name_corrections
        
        # Display all corrections if any
        if all_corrections:
            print("  Spell-check corrections applied:")
            for original, corrected in all_corrections:
                print(f"    '{original}' → '{corrected}'")
        
        recipe = update_recipe(
            db,
            recipe_id=recipe_id,
            new_name=recipe_data['name'] if new_name_normalized != current_name_normalized else None,
            instructions=recipe_data['instructions'],
            notes=recipe_data['notes']
        )
        
        # Update tags - remove all, then add new ones
        current_tag_names = {tag.name for tag in recipe.tags}
        new_tag_names = set(recipe_data['tags'])
        
        # Remove tags that are no longer in the list
        tags_to_remove = current_tag_names - new_tag_names
        if tags_to_remove:
            recipe = remove_tags_from_recipe(db, recipe_id=recipe_id, tag_names=list(tags_to_remove))
        
        # Add new tags
        tags_to_add = new_tag_names - current_tag_names
        if tags_to_add:
            recipe = add_tags_to_recipe(db, recipe_id=recipe_id, tag_names=list(tags_to_add))
        
        # Update ingredients - remove all, then add new ones
        current_ingredient_names = {ing.name for ing in recipe.ingredients}
        new_ingredient_names = set(recipe_data['ingredients'])
        
        # Remove ingredients that are no longer in the list
        ingredients_to_remove = current_ingredient_names - new_ingredient_names
        if ingredients_to_remove:
            recipe = remove_ingredients_from_recipe(db, recipe_id=recipe_id, ingredient_names=list(ingredients_to_remove))
        
        # Add new ingredients (create them automatically if they don't exist)
        ingredients_to_add = new_ingredient_names - current_ingredient_names
        if ingredients_to_add:
            # Create any missing ingredients automatically with default type "other"
            for ing_name in ingredients_to_add:
                if not get_ingredient(db, name=ing_name):
                    # Automatically create the ingredient with type "other"
                    add_ingredient(db, ing_name, "other")
            recipe = add_ingredients_to_recipe(db, recipe_id=recipe_id, ingredient_names=list(ingredients_to_add))
        
        # Delete the JSON file after successful import
        json_path.unlink()
        
        return recipe
    finally:
        db.close()


def check_json_exists(recipe_id: int) -> bool:
    """Check if a JSON file exists for a recipe."""
    json_path = get_json_path(recipe_id)
    return json_path.exists()


def create_new_recipe_template() -> dict:
    """Create a template JSON structure for a new recipe."""
    return {
        'name': '',
        'instructions': '',
        'notes': '',
        'tags': [],
        'ingredients': []
    }


def get_addable_json_path(name_hint: str = None) -> Path:
    """Get the path for the addable recipe JSON file. Creates unique filename if name_hint provided."""
    ensure_addable_dir()
    if name_hint:
        # Create unique filename with timestamp and sanitized name
        safe_name = "".join(c for c in name_hint if c.isalnum() or c in (' ', '-', '_')).strip()[:30]
        safe_name = safe_name.replace(' ', '_').lower()
        timestamp = int(time.time())
        return ADDABLE_DIR / f"recipe_{safe_name}_{timestamp}.json"
    return ADDABLE_DIR / "new_recipe.json"


def check_addable_json_exists() -> bool:
    """Check if any addable recipe JSON files exist."""
    ensure_addable_dir()
    # Check for the default file or any recipe_*.json files
    default_path = ADDABLE_DIR / "new_recipe.json"
    if default_path.exists():
        return True
    # Check for any recipe_*.json files
    recipe_files = list(ADDABLE_DIR.glob("recipe_*.json"))
    return len(recipe_files) > 0


def get_addable_recipe_files() -> list:
    """Get all addable recipe JSON files."""
    ensure_addable_dir()
    files = list(ADDABLE_DIR.glob("recipe_*.json"))
    files.extend([ADDABLE_DIR / "new_recipe.json"] if (ADDABLE_DIR / "new_recipe.json").exists() else [])
    return sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)  # Most recent first


# ==================== INGREDIENT JSON OPERATIONS ====================

def get_ingredient_json_path(ingredient_id: int) -> Path:
    """Get the JSON file path for an ingredient ID."""
    ensure_editable_dir()
    return EDITABLE_DIR / f"ingredient_{ingredient_id}.json"


def ingredient_to_json(ingredient: Ingredient) -> dict:
    """Convert an ingredient object to a JSON-serializable dictionary."""
    notes = ingredient.notes or ''
    if notes:
        notes = notes.replace('\\n', '\n')
    
    # Parse aliases from comma-separated string or empty list
    aliases = []
    if ingredient.alias:
        aliases = [a.strip() for a in ingredient.alias.split(',') if a.strip()]
    
    return {
        'id': ingredient.id,
        'name': ingredient.name,
        'type': ingredient.type.name if ingredient.type else '',
        'alias': aliases,
        'notes': notes,
        'tags': [tag.name for tag in ingredient.tags]
    }


def json_to_ingredient_data(json_data: dict) -> tuple[dict, list[tuple[str, str]]]:
    """
    Convert JSON data to a format suitable for updating the ingredient.
    Applies spell checking and normalization to all text fields.
    Returns: (ingredient_data_dict, list of (original, corrected) tuples for corrections made)
    """
    corrections = []
    
    notes = json_data.get('notes', '').strip()
    if notes:
        notes = notes.replace('\\n', '\n')
        # Normalize notes with spell checking
        from db_operations import normalize_text_words
        notes, note_corrections = normalize_text_words(notes)
        corrections.extend(note_corrections)
    
    # Handle aliases - can be list or comma-separated string
    aliases = json_data.get('alias', [])
    if isinstance(aliases, str):
        aliases = [a.strip() for a in aliases.split(',') if a.strip()]
    elif isinstance(aliases, list):
        aliases = [a.strip() for a in aliases if a.strip()]
    else:
        aliases = []
    
    # Normalize aliases with spell checking
    normalized_aliases = []
    for alias in aliases:
        from db_operations import normalize_name
        normalized_alias, alias_corrections = normalize_name(alias, check_spelling=True)
        normalized_aliases.append(normalized_alias)
        corrections.extend(alias_corrections)
    
    # Convert aliases list to comma-separated string for storage
    alias_str = ', '.join(normalized_aliases) if normalized_aliases else None
    
    # Don't normalize the name here - let update_ingredient handle normalization
    # This allows users to fix typos (e.g., "asparagu" -> "asparagus")
    name = json_data.get('name', '').strip()
    
    # Normalize tags with spell checking
    raw_tags = [t.strip() for t in json_data.get('tags', []) if t.strip()]
    from db_operations import normalize_tags
    normalized_tags, tag_corrections = normalize_tags(raw_tags)
    corrections.extend(tag_corrections)
    
    return {
        'name': name,
        'type': json_data.get('type', '').strip().lower(),
        'alias': alias_str,
        'notes': notes or None,
        'tags': normalized_tags
    }, corrections


def export_ingredient_to_json(ingredient_id: int) -> Path:
    """Export an ingredient to a JSON file. Returns the path to the JSON file."""
    db = SessionLocal()
    try:
        ingredient = get_ingredient(db, ingredient_id=ingredient_id)
        if not ingredient:
            raise ValueError(f"Ingredient with ID {ingredient_id} not found")
        
        json_path = get_ingredient_json_path(ingredient_id)
        ingredient_data = ingredient_to_json(ingredient)
        
        # Write JSON with indentation for readability
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(ingredient_data, f, indent=2, ensure_ascii=False)
        
        return json_path
    finally:
        db.close()


def import_ingredient_from_json(ingredient_id: int) -> Ingredient:
    """Import an ingredient from a JSON file and update the database. Deletes the JSON file after import."""
    json_path = get_ingredient_json_path(ingredient_id)
    
    if not json_path.exists():
        raise ValueError(f"No JSON file found for ingredient {ingredient_id}. Run edit command first to create it.")
    
    db = SessionLocal()
    try:
        # Read JSON file
        with open(json_path, 'r', encoding='utf-8') as f:
            json_data = json.load(f)
        
        if not json_data:
            raise ValueError("JSON file is empty or invalid")
        
        # Get the ingredient
        ingredient = get_ingredient(db, ingredient_id=ingredient_id)
        if not ingredient:
            raise ValueError(f"Ingredient with ID {ingredient_id} not found in database")
        
        # Convert JSON to ingredient data (with spell checking)
        ingredient_data, corrections = json_to_ingredient_data(json_data)
        
        # Update basic fields
        # Compare names after normalization to detect actual changes
        # This handles cases where user fixes typos (e.g., "asparagu" -> "asparagus")
        from db_operations import normalize_name
        new_name_normalized, name_corrections = normalize_name(ingredient_data['name']) if ingredient_data['name'] else ('', [])
        current_name_normalized = ingredient.name  # Already normalized in database
        
        # Combine all corrections
        all_corrections = corrections + name_corrections
        
        # Display all corrections if any
        if all_corrections:
            print("  Spell-check corrections applied:")
            for original, corrected in all_corrections:
                print(f"    '{original}' → '{corrected}'")
        
        current_alias = ingredient.alias or ''
        new_alias = ingredient_data.get('alias') or ''
        # Handle type update - check if type changed or if it should be removed (empty string)
        current_type_name = ingredient.type.name if ingredient.type else ''
        new_type_name = ingredient_data.get('type') or ''
        type_changed = new_type_name != current_type_name
        
        ingredient = update_ingredient(
            db,
            ingredient_id=ingredient_id,
            new_name=ingredient_data['name'] if new_name_normalized != current_name_normalized else None,
            type_name=new_type_name if type_changed else None,
            alias=ingredient_data['alias'] if new_alias != current_alias else None,
            notes=ingredient_data['notes']
        )
        
        # Update tags - remove all, then add new ones
        current_tag_names = {tag.name for tag in ingredient.tags}
        new_tag_names = set(ingredient_data['tags'])
        
        # Remove tags that are no longer in the list
        tags_to_remove = current_tag_names - new_tag_names
        if tags_to_remove:
            ingredient = remove_tags_from_ingredient(db, ingredient_id=ingredient_id, tag_names=list(tags_to_remove))
        
        # Add new tags
        tags_to_add = new_tag_names - current_tag_names
        if tags_to_add:
            ingredient = add_tags_to_ingredient(db, ingredient_id=ingredient_id, tag_names=list(tags_to_add))
        
        # Delete the JSON file after successful import
        json_path.unlink()
        
        return ingredient
    finally:
        db.close()


def check_ingredient_json_exists(ingredient_id: int) -> bool:
    """Check if a JSON file exists for an ingredient."""
    json_path = get_ingredient_json_path(ingredient_id)
    return json_path.exists()


def create_new_ingredient_template() -> dict:
    """Create a template JSON structure for a new ingredient."""
    return {
        'name': '',
        'type': '',
        'alias': [],
        'notes': '',
        'tags': []
    }


def get_addable_ingredient_json_path(name_hint: str = None) -> Path:
    """Get the path for the addable ingredient JSON file. Creates unique filename if name_hint provided."""
    ensure_addable_dir()
    if name_hint:
        # Create unique filename with timestamp and sanitized name
        safe_name = "".join(c for c in name_hint if c.isalnum() or c in (' ', '-', '_')).strip()[:30]
        safe_name = safe_name.replace(' ', '_').lower()
        timestamp = int(time.time())
        return ADDABLE_DIR / f"ingredient_{safe_name}_{timestamp}.json"
    return ADDABLE_DIR / "new_ingredient.json"


def check_addable_ingredient_json_exists() -> bool:
    """Check if any addable ingredient JSON files exist."""
    ensure_addable_dir()
    # Check for the default file or any ingredient_*.json files
    default_path = ADDABLE_DIR / "new_ingredient.json"
    if default_path.exists():
        return True
    # Check for any ingredient_*.json files
    ingredient_files = list(ADDABLE_DIR.glob("ingredient_*.json"))
    return len(ingredient_files) > 0


# ==================== ARTICLE JSON FUNCTIONS ====================

def get_article_json_path(article_id: int) -> Path:
    """Get the path to an article's editable JSON file."""
    ensure_editable_dir()
    return EDITABLE_DIR / f"article_{article_id}.json"


def get_addable_article_json_path() -> Path:
    """Get the path to a new article's addable JSON file."""
    ensure_addable_dir()
    return ADDABLE_DIR / "new_article.json"


def check_article_json_exists(article_id: int) -> bool:
    """Check if an editable article JSON file exists."""
    json_path = get_article_json_path(article_id)
    return json_path.exists()


def check_addable_article_json_exists() -> bool:
    """Check if any addable article JSON files exist."""
    ensure_addable_dir()
    default_path = ADDABLE_DIR / "new_article.json"
    return default_path.exists()


def get_addable_article_files() -> list:
    """Get all addable article JSON files."""
    ensure_addable_dir()
    files = [ADDABLE_DIR / "new_article.json"] if (ADDABLE_DIR / "new_article.json").exists() else []
    return sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)  # Most recent first


def article_to_json(article: Article) -> dict:
    """Convert an Article object to a JSON-serializable dict."""
    notes = article.notes or ''
    if notes:
        notes = notes.replace('\n', '\\n')
    return {
        'id': article.id,
        'notes': notes,
        'tags': [tag.name for tag in article.tags]
    }


def json_to_article_data(json_data: dict) -> tuple[dict, list[tuple[str, str]]]:
    """
    Convert JSON data to article data format.
    Applies spell checking and normalization to all text fields.
    Returns: (article_data_dict, list of (original, corrected) tuples for corrections made)
    """
    corrections = []
    
    notes = json_data.get('notes', '').strip()
    if notes:
        notes = notes.replace('\\n', '\n')
        from db_operations import normalize_text_words
        notes, note_corrections = normalize_text_words(notes)
        corrections.extend(note_corrections)
    
    # Normalize tags with spell checking
    raw_tags = [t.strip() for t in json_data.get('tags', []) if t.strip()]
    from db_operations import normalize_tags
    normalized_tags, tag_corrections = normalize_tags(raw_tags)
    corrections.extend(tag_corrections)
    
    return {
        'notes': notes or None,
        'tags': normalized_tags
    }, corrections


def create_new_article_template() -> dict:
    """Create a template dict for a new article."""
    return {
        "notes": "",
        "tags": []
    }


def export_article_to_json(article_id: int) -> Path:
    """Export an article to a JSON file for editing."""
    db = SessionLocal()
    try:
        article = get_article(db, article_id=article_id)
        if not article:
            raise ValueError(f"Article with ID {article_id} not found")
        
        json_path = get_article_json_path(article_id)
        
        # Only create if it doesn't exist, or if it's empty
        if not json_path.exists() or json_path.stat().st_size == 0:
            article_data = article_to_json(article)
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(article_data, f, indent=2, ensure_ascii=False)
        
        return json_path
    finally:
        db.close()


def import_article_from_json(article_id: int) -> Article:
    """Import an article from a JSON file and update the database."""
    json_path = get_article_json_path(article_id)
    if not json_path.exists():
        raise ValueError(f"No JSON file found for article {article_id}. Run edit command first to create it.")
    
    db = SessionLocal()
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            json_data = json.load(f)
        if not json_data:
            raise ValueError("JSON file is empty or invalid")
        
        article = get_article(db, article_id=article_id)
        if not article:
            raise ValueError(f"Article with ID {article_id} not found in database")
        
        article_data, corrections = json_to_article_data(json_data)
        
        # Display corrections if any
        if corrections:
            print("  Spell-check corrections applied:")
            for original, corrected in corrections:
                print(f"    '{original}' → '{corrected}'")
        
        article = update_article(
            db,
            article_id=article_id,
            notes=article_data['notes']
        )
        
        current_tag_names = {tag.name for tag in article.tags}
        new_tag_names = set(article_data['tags'])
        
        tags_to_remove = current_tag_names - new_tag_names
        if tags_to_remove:
            article = remove_tags_from_article(db, article_id=article_id, tag_names=list(tags_to_remove))
        
        tags_to_add = new_tag_names - current_tag_names
        if tags_to_add:
            article = add_tags_to_article(db, article_id=article_id, tag_names=list(tags_to_add))
        
        json_path.unlink()
        return article
    finally:
        db.close()


def export_new_article_template() -> Path:
    """Create a new article template JSON file."""
    json_path = get_addable_article_json_path()
    if json_path.exists():
        return json_path
    template = create_new_article_template()
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(template, f, indent=2, ensure_ascii=False)
    return json_path


def import_new_article_from_json(json_path: Path = None) -> Article:
    """Import a new article from the addable JSON file and add it to the database."""
    if json_path is None:
        default_path = ADDABLE_DIR / "new_article.json"
        if default_path.exists():
            json_path = default_path
        else:
            article_files = get_addable_article_files()
            if not article_files:
                raise ValueError("No JSON file found in addable folder. Run 'article add' command first to create it.")
            json_path = article_files[0]
    
    if not json_path.exists():
        raise ValueError(f"JSON file not found: {json_path}")
    
    db = SessionLocal()
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            json_data = json.load(f)
        if not json_data:
            raise ValueError("JSON file is empty or invalid")
        
        try:
            article_data, corrections = json_to_article_data(json_data)
        except Exception as e:
            # Preserve JSON file on spell-check/normalization errors
            raise ValueError(f"Failed to process article data: {e}. Please check your JSON file and try again.")
        
        # Display corrections if any
        if corrections:
            print("  Spell-check corrections applied:")
            for original, corrected in corrections:
                print(f"    '{original}' → '{corrected}'")
        
        try:
            article = add_article(
                db,
                notes=article_data['notes'],
                tags=article_data['tags']
            )
        except Exception as e:
            # Preserve JSON file on database errors
            raise ValueError(f"Failed to add article to database: {e}. JSON file preserved for editing.")
        
        # Only delete JSON file after successful import
        json_path.unlink()
        return article
    finally:
        db.close()


def get_addable_ingredient_files() -> list:
    """Get all addable ingredient JSON files."""
    ensure_addable_dir()
    files = list(ADDABLE_DIR.glob("ingredient_*.json"))
    files.extend([ADDABLE_DIR / "new_ingredient.json"] if (ADDABLE_DIR / "new_ingredient.json").exists() else [])
    return sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)  # Most recent first


def export_new_ingredient_template(name_hint: str = None) -> Path:
    """Create a new ingredient template JSON file. Returns the path to the JSON file."""
    json_path = get_addable_ingredient_json_path(name_hint)
    
    # If file already exists, don't overwrite it
    if json_path.exists():
        return json_path
    
    template = create_new_ingredient_template()
    
    # If name_hint provided, pre-fill the name
    if name_hint:
        template['name'] = name_hint
    
    # Write JSON with indentation for readability
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(template, f, indent=2, ensure_ascii=False)
    
    return json_path


def import_new_ingredient_from_json(json_path: Path = None) -> Ingredient:
    """Import a new ingredient from the addable JSON file and add it to the database. Deletes the JSON file after import."""
    if json_path is None:
        # Use default file or most recent ingredient file
        default_path = ADDABLE_DIR / "new_ingredient.json"
        if default_path.exists():
            json_path = default_path
        else:
            ingredient_files = get_addable_ingredient_files()
            if not ingredient_files:
                raise ValueError("No JSON file found in addable folder. Run 'ingredient add' command first to create it.")
            json_path = ingredient_files[0]  # Use most recent
    
    if not json_path.exists():
        raise ValueError(f"JSON file not found: {json_path}")
    
    db = SessionLocal()
    try:
        # Read JSON file
        with open(json_path, 'r', encoding='utf-8') as f:
            json_data = json.load(f)
        
        if not json_data:
            db.rollback()
            raise ValueError("JSON file is empty or invalid")
        
        # Validate required fields
        name = json_data.get('name', '').strip()
        if not name:
            db.rollback()
            raise ValueError("Ingredient name is required")
        
        type_name = json_data.get('type', '').strip()
        # Type is optional - empty string means typeless ingredient
        
        # Convert JSON to ingredient data (with spell checking)
        try:
            ingredient_data, corrections = json_to_ingredient_data(json_data)
        except Exception as e:
            # Preserve JSON file on spell-check/normalization errors
            db.rollback()
            raise ValueError(f"Failed to process ingredient data: {e}. Please check your JSON file and try again.")
        
        # Display corrections if any
        if corrections:
            print("  Spell-check corrections applied:")
            for original, corrected in corrections:
                print(f"    '{original}' → '{corrected}'")
        
        # Normalize name and check for corrections
        from db_operations import normalize_name
        normalized_name, name_corrections = normalize_name(ingredient_data['name']) if ingredient_data['name'] else ('', [])
        
        # Display name corrections if any
        if name_corrections:
            print("  Name corrections applied:")
            for original, corrected in name_corrections:
                print(f"    '{original}' → '{corrected}'")
        
        
        # Create the ingredient
        try:
            ingredient = add_ingredient(
                db,
                name=ingredient_data['name'],
                type_name=ingredient_data['type'] if ingredient_data['type'] else None,
                notes=ingredient_data['notes'],
                tags=ingredient_data['tags']
            )
        except Exception as e:
            # Preserve JSON file on database errors
            db.rollback()
            raise ValueError(f"Failed to add ingredient to database: {e}. JSON file preserved for editing.")
        
        # Update alias separately if provided
        if ingredient_data.get('alias'):
            try:
                update_ingredient(db, ingredient_id=ingredient.id, alias=ingredient_data['alias'])
                db.refresh(ingredient)
            except Exception as e:
                # Preserve JSON file on alias update errors
                db.rollback()
                raise ValueError(f"Failed to update ingredient alias: {e}. JSON file preserved for editing.")
        
        # Get fresh instance to ensure relationships are loaded
        ingredient_id = ingredient.id
        db.expunge(ingredient)  # Remove from session
        ingredient = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
        
        # Only delete JSON file after successful import
        json_path.unlink()
        
        return ingredient
    except Exception:
        # Rollback any uncommitted changes on any error
        db.rollback()
        raise
    finally:
        db.close()


def export_new_recipe_template(name_hint: str = None) -> Path:
    """Create a new recipe template JSON file. Returns the path to the JSON file."""
    json_path = get_addable_json_path(name_hint)
    
    # If file already exists, don't overwrite it
    if json_path.exists():
        return json_path
    
    template = create_new_recipe_template()
    
    # If name_hint provided, pre-fill the name
    if name_hint:
        template['name'] = name_hint
    
    # Write JSON with indentation for readability
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(template, f, indent=2, ensure_ascii=False)
    
    return json_path


def import_new_recipe_from_json(json_path: Path = None) -> Recipe:
    """Import a new recipe from the addable JSON file and add it to the database. Deletes the JSON file after import."""
    if json_path is None:
        # Use default file or most recent recipe file
        default_path = ADDABLE_DIR / "new_recipe.json"
        if default_path.exists():
            json_path = default_path
        else:
            recipe_files = get_addable_recipe_files()
            if not recipe_files:
                raise ValueError("No JSON file found in addable folder. Run 'recipe add' command first to create it.")
            json_path = recipe_files[0]  # Use most recent
    
    if not json_path.exists():
        raise ValueError(f"JSON file not found: {json_path}")
    
    db = SessionLocal()
    try:
        # Read JSON file
        with open(json_path, 'r', encoding='utf-8') as f:
            json_data = json.load(f)
        
        if not json_data:
            raise ValueError("JSON file is empty or invalid")
        
        # Validate required fields
        name = json_data.get('name', '').strip()
        if not name:
            raise ValueError("Recipe name is required")
        
        # Convert JSON to recipe data (with spell checking)
        recipe_data, corrections = json_to_recipe_data(json_data)
        
        # Display corrections if any
        if corrections:
            print("  Spell-check corrections applied:")
            for original, corrected in corrections:
                print(f"    '{original}' → '{corrected}'")
        
        
        # Check that all ingredients exist - fail if any are missing
        missing_ingredients = []
        for ing_name in recipe_data['ingredients']:
            if not get_ingredient(db, name=ing_name):
                missing_ingredients.append(ing_name)
        
        if missing_ingredients:
            missing_list = ', '.join(missing_ingredients)
            raise ValueError(f"Missing ingredients: {missing_list}. Add them first with 'ingredient add' command. JSON file preserved for editing.")
        
        # Create the recipe
        try:
            from db_operations import add_recipe
            recipe = add_recipe(
                db,
                name=recipe_data['name'],
                instructions=recipe_data['instructions'],
                notes=recipe_data['notes'],
                tags=recipe_data['tags'],
                ingredients=recipe_data['ingredients']
            )
        except Exception as e:
            # Preserve JSON file on database errors
            raise ValueError(f"Failed to add recipe to database: {e}. JSON file preserved for editing.")
        
        # Only delete JSON file after successful import
        json_path.unlink()
        
        return recipe
    finally:
        db.close()


# ==================== TAG JSON OPERATIONS ====================

def get_tag_json_path(tag_id: int) -> Path:
    """Get the JSON file path for a tag ID."""
    ensure_editable_dir()
    return EDITABLE_DIR / f"tag_{tag_id}.json"


def tag_to_json(tag: Tag) -> dict:
    """Convert a tag object to a JSON-serializable dictionary."""
    return {
        'id': tag.id,
        'name': tag.name,
        'subtag': tag.subtag.name if tag.subtag else ''
    }


def json_to_tag_data(json_data: dict) -> tuple[dict, list[tuple[str, str]]]:
    """
    Convert JSON data to a format suitable for updating the tag.
    Returns: (tag_data_dict, empty corrections list for compatibility)
    """
    name_raw = json_data.get('name') or ''
    name = name_raw.strip().lower() if name_raw else ''
    
    subtag_raw = json_data.get('subtag') or ''
    if subtag_raw and subtag_raw.strip():
        subtag = subtag_raw.strip().lower()
    else:
        subtag = None
    
    return {
        'name': name,
        'subtag': subtag
    }, []  # No corrections


def export_tag_to_json(tag_id: int) -> Path:
    """Export a tag to a JSON file. Returns the path to the JSON file."""
    db = SessionLocal()
    try:
        tag = get_tag(db, tag_id=tag_id)
        if not tag:
            raise ValueError(f"Tag with ID {tag_id} not found")
        
        json_path = get_tag_json_path(tag_id)
        tag_data = tag_to_json(tag)
        
        # Write JSON with indentation for readability
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(tag_data, f, indent=2, ensure_ascii=False)
        
        return json_path
    finally:
        db.close()


def import_tag_from_json(tag_id: int) -> Tag:
    """Import a tag from a JSON file and update the database. Deletes the JSON file after import."""
    json_path = get_tag_json_path(tag_id)
    
    if not json_path.exists():
        raise ValueError(f"No JSON file found for tag {tag_id}. Run edit command first to create it.")
    
    db = SessionLocal()
    try:
        # Read JSON file
        with open(json_path, 'r', encoding='utf-8') as f:
            json_data = json.load(f)
        
        if not json_data:
            raise ValueError("JSON file is empty or invalid")
        
        # Get the tag
        tag = get_tag(db, tag_id=tag_id)
        if not tag:
            raise ValueError(f"Tag with ID {tag_id} not found in database")
        
        # Convert JSON to tag data
        tag_data, corrections = json_to_tag_data(json_data)
        
        # Update tag
        from db_operations import update_tag
        # Compare subtags properly (handle None vs empty string)
        current_subtag_name = tag.subtag.name if tag.subtag else ''
        new_subtag_raw = json_data.get('subtag', '')  # Get raw value before normalization
        new_subtag_normalized = tag_data['subtag'] or ''  # Normalized value
        subtag_changed = new_subtag_normalized != current_subtag_name
        
        # If subtag changed, pass the normalized value (None for empty, or the actual value)
        # Use Ellipsis (...) to mean "don't update this field"
        tag = update_tag(
            db,
            tag_id=tag_id,
            new_name=tag_data['name'] if tag_data['name'] != tag.name else ...,
            new_subtag_name=tag_data['subtag'] if subtag_changed else ...
        )
        
        # Delete the JSON file after successful import
        json_path.unlink()
        
        return tag
    finally:
        db.close()


def check_tag_json_exists(tag_id: int) -> bool:
    """Check if a JSON file exists for a tag."""
    json_path = get_tag_json_path(tag_id)
    return json_path.exists()
