"""
Database operations for recipes and ingredients.
"""
import warnings
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from models import Recipe, Ingredient, Tag, IngredientType, Article

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

# ==================== SIMPLE NORMALIZATION (no spell check, no lemmatization) ====================

def normalize_name(name: str, check_spelling: bool = True) -> tuple[str, list[tuple[str, str]]]:
    """
    Normalize a name by converting to lowercase and stripping whitespace.
    No spell checking or lemmatization.
    
    Returns: (normalized_name, empty corrections list for compatibility)
    """
    if not name:
        return name, []
    return name.strip().lower(), []


def normalize_tags(tags: list[str]) -> tuple[list[str], list[tuple[str, str]]]:
    """
    Normalize a list of tags: lowercase and strip.
    No spell checking or lemmatization.
    Returns (normalized_tags, empty corrections list for compatibility).
    """
    normalized = []
    for tag in tags:
        if tag and tag.strip():
            normalized.append(tag.strip().lower())
    return normalized, []


def normalize_text_words(text: str) -> tuple[str, list[tuple[str, str]]]:
    """
    Normalize text by stripping whitespace.
    No spell checking or lemmatization.
    Returns (normalized_text, empty corrections list for compatibility).
    """
    if not text:
        return text, []
    return text.strip(), []


def check_spelling(name: str) -> tuple[bool, dict[str, list[str]]]:
    """
    Stub function for compatibility - always returns (True, {}) since spell checking is disabled.
    """
    return (True, {})


# ==================== INGREDIENT TYPE OPERATIONS ====================

def get_or_create_ingredient_type(db: Session, type_name: str) -> IngredientType:
    """Get an existing ingredient type or create it if it doesn't exist."""
    type_obj = db.query(IngredientType).filter(IngredientType.name == type_name.lower()).first()
    if not type_obj:
        type_obj = IngredientType(name=type_name.lower())
        db.add(type_obj)
        db.commit()
        db.refresh(type_obj)
    return type_obj


def list_ingredient_types(db: Session):
    """List all ingredient types."""
    return db.query(IngredientType).all()


def add_ingredient_type(db: Session, name: str) -> IngredientType:
    """Add a new ingredient type to the database."""
    normalized_name = name.strip().lower()
    
    # Check if type already exists
    existing = db.query(IngredientType).filter(IngredientType.name == normalized_name).first()
    if existing:
        raise ValueError(f"Ingredient type '{name}' already exists (ID: {existing.id})")
    
    ingredient_type = IngredientType(name=normalized_name)
    db.add(ingredient_type)
    db.commit()
    db.refresh(ingredient_type)
    return ingredient_type


def delete_ingredient_type(db: Session, type_id: int) -> bool:
    """Delete an ingredient type by ID. Returns True if deleted, False if not found."""
    ingredient_type = db.query(IngredientType).filter(IngredientType.id == type_id).first()
    if not ingredient_type:
        return False
    
    # Check if any ingredients use this type
    if ingredient_type.ingredients:
        ingredient_names = [ing.name for ing in ingredient_type.ingredients if ing]
        if ingredient_names:
            raise ValueError(f"Cannot delete ingredient type '{ingredient_type.name}' (ID: {type_id}). It is used by {len(ingredient_names)} ingredient(s): {', '.join(ingredient_names[:5])}{'...' if len(ingredient_names) > 5 else ''}")
    
    db.delete(ingredient_type)
    db.commit()
    return True


# ==================== INGREDIENT OPERATIONS ====================

def add_ingredient(
    db: Session,
    name: str,
    type_name: str,
    notes: str = None,
    tags: list = None
) -> Ingredient:
    """Add a new ingredient to the database."""
    # Normalize name (convert to singular and lowercase)
    normalized_name, _ = normalize_name(name)
    
    # Get ingredient type (must exist - no auto-creation)
    ingredient_type = get_ingredient_type(db, name=type_name)
    if not ingredient_type:
        raise ValueError(f"Ingredient type '{type_name}' not found. Add it first using 'python cli.py type add'.")
    
    # Check if ingredient already exists (using normalized name)
    existing = db.query(Ingredient).filter(Ingredient.name == normalized_name).first()
    if existing:
        raise ValueError(f"Ingredient '{name}' already exists (as '{existing.name}')")
    
    ingredient = Ingredient(name=normalized_name, type=ingredient_type, notes=notes)
    
    # Add tags (must exist - no auto-creation)
    if tags:
        tag_objects = []
        for tag_name in tags:
            tag_obj = get_tag(db, name=tag_name)
            if not tag_obj:
                raise ValueError(f"Tag '{tag_name}' not found. Add it first using 'python cli.py tag add'.")
            tag_objects.append(tag_obj)
        ingredient.tags = tag_objects
    
    db.add(ingredient)
    db.commit()
    db.refresh(ingredient)
    return ingredient


def get_ingredient(db: Session, name: str = None, ingredient_id: int = None) -> Ingredient:
    """Get an ingredient by name or ID."""
    if ingredient_id:
        return db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
    if name:
        # Normalize name for lookup (convert plural to singular)
        normalized_name, _ = normalize_name(name)
        return db.query(Ingredient).filter(Ingredient.name == normalized_name).first()
    return None


def list_ingredients(db: Session):
    """List all ingredients."""
    return db.query(Ingredient).all()


def delete_ingredient(db: Session, name: str = None, ingredient_id: int = None) -> bool:
    """Delete an ingredient by name or ID."""
    ingredient = get_ingredient(db, name, ingredient_id)
    if not ingredient:
        raise ValueError(f"Ingredient not found")
    
    db.delete(ingredient)
    db.commit()
    return True


def update_ingredient(
    db: Session,
    ingredient_id: int = None,
    name: str = None,
    new_name: str = None,
    type_name: str = None,
    alias: str = None,
    notes: str = None
) -> Ingredient:
    """Update basic ingredient fields (name, type, alias, notes)."""
    ingredient = get_ingredient(db, name=name, ingredient_id=ingredient_id)
    if not ingredient:
        raise ValueError(f"Ingredient not found")
    
    if new_name is not None:
        # Normalize new name (convert to singular and lowercase)
        normalized_new_name, _ = normalize_name(new_name)
        
        # Check if new name already exists
        existing = db.query(Ingredient).filter(Ingredient.name == normalized_new_name, Ingredient.id != ingredient.id).first()
        if existing:
            raise ValueError(f"Ingredient '{new_name}' already exists (as '{existing.name}')")
        ingredient.name = normalized_new_name
    
    if type_name is not None:
        ingredient_type = get_ingredient_type(db, name=type_name)
        if not ingredient_type:
            raise ValueError(f"Ingredient type '{type_name}' not found. Add it first using 'python cli.py type add'.")
        ingredient.type = ingredient_type
    
    if alias is not None:
        ingredient.alias = alias
    
    if notes is not None:
        ingredient.notes = notes
    
    
    db.commit()
    db.refresh(ingredient)
    return ingredient


def add_tags_to_ingredient(
    db: Session,
    ingredient_id: int = None,
    name: str = None,
    tag_names: list = None
) -> Ingredient:
    """Add tags to an existing ingredient."""
    ingredient = get_ingredient(db, name=name, ingredient_id=ingredient_id)
    if not ingredient:
        raise ValueError(f"Ingredient not found")
    
    if not tag_names:
        return ingredient
    
    current_tag_names = {tag.name for tag in ingredient.tags}
    new_tags = []
    
    for tag_name in tag_names:
        if tag_name.lower() in current_tag_names:
            continue  # Skip if already tagged
        
        tag_obj = get_tag(db, name=tag_name)
        if not tag_obj:
            raise ValueError(f"Tag '{tag_name}' not found. Add it first using 'python cli.py tag add'.")
        new_tags.append(tag_obj)
    
    if new_tags:
        ingredient.tags.extend(new_tags)
    db.commit()
    db.refresh(ingredient)
    return ingredient


def remove_tags_from_ingredient(
    db: Session,
    ingredient_id: int = None,
    name: str = None,
    tag_names: list = None
) -> Ingredient:
    """Remove tags from an existing ingredient."""
    ingredient = get_ingredient(db, name=name, ingredient_id=ingredient_id)
    if not ingredient:
        raise ValueError(f"Ingredient not found")
    
    if not tag_names:
        return ingredient
    
    tags_to_remove = []
    for tag_name in tag_names:
        tag_obj = db.query(Tag).filter(Tag.name == tag_name.lower()).first()
        if tag_obj and tag_obj in ingredient.tags:
            tags_to_remove.append(tag_obj)
    
    if tags_to_remove:
        for tag in tags_to_remove:
            ingredient.tags.remove(tag)
    db.commit()
    db.refresh(ingredient)
    return ingredient


# ==================== TAG OPERATIONS ====================

def get_or_create_tag(db: Session, tag_name: str) -> Tag:
    """
    Get an existing tag or create it if it doesn't exist.
    Normalizes tag name (spell check + lowercase + singularize) silently.
    """
    # Normalize tag name (spell check + lowercase + singularize)
    normalized_tag, _ = normalize_name(tag_name, check_spelling=True)
    
    tag = db.query(Tag).filter(Tag.name == normalized_tag).first()
    if not tag:
        tag = Tag(name=normalized_tag)
        db.add(tag)
        db.commit()
        db.refresh(tag)
    return tag


def list_tags(db: Session):
    """List all tags."""
    return db.query(Tag).all()


def add_tag(db: Session, name: str, subtag: str = None) -> Tag:
    """Add a new tag to the database."""
    normalized_name = name.strip().lower()
    normalized_subtag = subtag.strip().lower() if subtag and subtag.strip() else None
    
    # Check if tag already exists
    existing = db.query(Tag).filter(Tag.name == normalized_name).first()
    if existing:
        raise ValueError(f"Tag '{name}' already exists (ID: {existing.id})")
    
    tag = Tag(name=normalized_name, subtag=normalized_subtag)
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return tag


def delete_tag(db: Session, tag_id: int) -> bool:
    """Delete a tag by ID. Returns True if deleted, False if not found."""
    tag = db.query(Tag).filter(Tag.id == tag_id).first()
    if not tag:
        return False
    
    # Remove tag from all recipes
    for recipe in list(tag.recipes):
        recipe.tags.remove(tag)
    
    # Remove tag from all ingredients
    for ingredient in list(tag.ingredients):
        ingredient.tags.remove(tag)
    
    # Remove tag from all articles
    for article in list(tag.articles):
        article.tags.remove(tag)
    
    db.delete(tag)
    db.commit()
    return True


def get_tag(db: Session, tag_id: int = None, name: str = None) -> Tag:
    """Get a tag by ID or name."""
    if tag_id:
        return db.query(Tag).filter(Tag.id == tag_id).first()
    elif name:
        normalized_name = name.strip().lower()
        return db.query(Tag).filter(Tag.name == normalized_name).first()
    return None


def get_ingredient_type(db: Session, type_id: int = None, name: str = None) -> IngredientType:
    """Get an ingredient type by ID or name."""
    if type_id:
        return db.query(IngredientType).filter(IngredientType.id == type_id).first()
    elif name:
        normalized_name = name.strip().lower()
        return db.query(IngredientType).filter(IngredientType.name == normalized_name).first()
    return None


def update_tag(db: Session, tag_id: int, new_name: str = ..., new_subtag: str = ...) -> Tag:
    """Update a tag's name and/or subtag.
    
    Args:
        new_name: New name for the tag (Ellipsis means don't update, None means clear - but names can't be None)
        new_subtag: New subtag (Ellipsis means don't update, None means clear it)
    """
    tag = db.query(Tag).filter(Tag.id == tag_id).first()
    if not tag:
        raise ValueError(f"Tag with ID {tag_id} not found")
    
    # Update name if provided (not Ellipsis)
    if new_name is not ...:
        if new_name:
            normalized_name = new_name.strip().lower()
            if normalized_name != tag.name:
                # Check if new name already exists
                existing = db.query(Tag).filter(Tag.name == normalized_name).first()
                if existing and existing.id != tag_id:
                    raise ValueError(f"Tag with name '{new_name}' already exists (ID: {existing.id})")
                tag.name = normalized_name
        else:
            raise ValueError("Tag name cannot be empty")
    
    # Update subtag if provided (Ellipsis means don't update, None means clear it)
    if new_subtag is not ...:
        if new_subtag and new_subtag.strip():
            normalized_subtag = new_subtag.strip().lower()
        else:
            normalized_subtag = None
        tag.subtag = normalized_subtag
    
    db.commit()
    db.refresh(tag)
    return tag


# REMOVED: search_recipes_by_tag, search_ingredients_by_tag, search_articles_by_tag
# These functions used fuzzy matching which has been removed


# ==================== ARTICLE OPERATIONS ====================

def add_article(
    db: Session,
    notes: str = None,
    tags: list = None
) -> Article:
    """Add a new article to the database."""
    article = Article(notes=notes)
    
    # Add tags (must exist - no auto-creation)
    if tags:
        tag_objects = []
        for tag_name in tags:
            tag_obj = get_tag(db, name=tag_name)
            if not tag_obj:
                raise ValueError(f"Tag '{tag_name}' not found. Add it first using 'python cli.py tag add'.")
            tag_objects.append(tag_obj)
        article.tags = tag_objects
    
    db.add(article)
    db.commit()
    db.refresh(article)
    return article


def get_article(db: Session, article_id: int = None) -> Article:
    """Get an article by ID."""
    if article_id:
        return db.query(Article).filter(Article.id == article_id).first()
    return None


def list_articles(db: Session):
    """List all articles."""
    return db.query(Article).all()


def update_article(
    db: Session,
    article_id: int = None,
    notes: str = None
) -> Article:
    """Update an article's notes."""
    article = get_article(db, article_id=article_id)
    if not article:
        raise ValueError(f"Article not found")
    
    if notes is not None:
        article.notes = notes
    
    db.commit()
    db.refresh(article)
    return article


def delete_article(db: Session, article_id: int = None) -> bool:
    """Delete an article by ID."""
    article = get_article(db, article_id=article_id)
    if not article:
        raise ValueError(f"Article not found")
    
    db.delete(article)
    db.commit()
    return True


def add_tags_to_article(
    db: Session,
    article_id: int = None,
    tag_names: list = None
) -> Article:
    """Add tags to an existing article."""
    article = get_article(db, article_id=article_id)
    if not article:
        raise ValueError(f"Article not found")
    
    if not tag_names:
        return article
    
    current_tag_names = {tag.name for tag in article.tags}
    new_tags = []
    
    for tag_name in tag_names:
        if tag_name.lower() in current_tag_names:
            continue  # Skip if already tagged
        
        tag_obj = get_tag(db, name=tag_name)
        if not tag_obj:
            raise ValueError(f"Tag '{tag_name}' not found. Add it first using 'python cli.py tag add'.")
        new_tags.append(tag_obj)
    
    if new_tags:
        article.tags.extend(new_tags)
    db.commit()
    db.refresh(article)
    return article


def remove_tags_from_article(
    db: Session,
    article_id: int = None,
    tag_names: list = None
) -> Article:
    """Remove tags from an existing article."""
    article = get_article(db, article_id=article_id)
    if not article:
        raise ValueError(f"Article not found")
    
    if not tag_names:
        return article
    
    tags_to_remove = []
    for tag_name in tag_names:
        tag_obj = db.query(Tag).filter(Tag.name == tag_name.lower()).first()
        if tag_obj and tag_obj in article.tags:
            tags_to_remove.append(tag_obj)
    
    for tag in tags_to_remove:
        article.tags.remove(tag)
    
    db.commit()
    db.refresh(article)
    return article


# ==================== RECIPE OPERATIONS ====================

def add_recipe(
    db: Session,
    name: str,
    instructions: str = None,
    notes: str = None,
    tags: list = None,
    ingredients: list = None
) -> Recipe:
    """Add a new recipe to the database."""
    # Normalize name (convert to singular and lowercase)
    normalized_name, _ = normalize_name(name)
    
    # Check if recipe already exists (using normalized name)
    existing = db.query(Recipe).filter(Recipe.name == normalized_name).first()
    if existing:
        raise ValueError(f"Recipe '{name}' already exists (as '{existing.name}')")
    
    recipe = Recipe(
        name=normalized_name,
        instructions=instructions,
        notes=notes
    )
    
    # Add tags (must exist - no auto-creation)
    if tags:
        tag_objects = []
        for tag_name in tags:
            tag_obj = get_tag(db, name=tag_name)
            if not tag_obj:
                raise ValueError(f"Tag '{tag_name}' not found. Add it first using 'python cli.py tag add'.")
            tag_objects.append(tag_obj)
        recipe.tags = tag_objects
    
    # Add ingredients
    if ingredients:
        ingredient_objects = []
        for ingredient_name in ingredients:
            ingredient_obj = get_ingredient(db, name=ingredient_name)
            if not ingredient_obj:
                raise ValueError(f"Ingredient '{ingredient_name}' not found. Add it first.")
            ingredient_objects.append(ingredient_obj)
        recipe.ingredients = ingredient_objects
    
    db.add(recipe)
    db.commit()
    db.refresh(recipe)
    return recipe


def get_recipe(db: Session, name: str = None, recipe_id: int = None) -> Recipe:
    """Get a recipe by name or ID."""
    if recipe_id:
        return db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if name:
        # Normalize name for lookup (convert plural to singular)
        normalized_name, _ = normalize_name(name)
        return db.query(Recipe).filter(Recipe.name == normalized_name).first()
    return None


def list_recipes(db: Session):
    """List all recipes."""
    return db.query(Recipe).all()


# REMOVED: All fuzzy matching and semantic search functions removed
# The following functions have been removed:
# - find_similar_ingredients
# - find_similar_recipes  
# - search_recipes
# - search_ingredients
# - suggest_recipes_by_ingredients
# - search_recipes_by_tag (fuzzy)
# - search_ingredients_by_tag (fuzzy)
# - search_articles_by_tag (fuzzy)


def search_recipes_by_ingredients_exact(
    db: Session,
    ingredient_query: str,
    min_matches: int = 1
) -> list:
    """
    Search recipes by exact ingredient matching (deterministic, no semantics).
    
    Parses a comma-delimited list of ingredients and finds recipes that contain
    those ingredients. Results are ranked by number of matches (more matches = higher rank).
    Recipes with no matches are still included at the bottom.
    
    Args:
        db: Database session
        ingredient_query: Comma-delimited list of ingredient names (e.g., "cucumber, dill, mint")
        min_matches: Minimum number of ingredient matches required (default: 1)
    
    Returns:
        List of tuples: (recipe, match_count) sorted by match_count descending
        match_count is the number of requested ingredients found in the recipe
    """
    # Parse comma-delimited ingredients
    requested_ingredients = [ing.strip().lower() for ing in ingredient_query.split(',') if ing.strip()]
    if not requested_ingredients:
        return []
    
    # Validate that all requested ingredients exist in the database
    all_ingredients_in_db = {ing.name.lower() for ing in db.query(Ingredient).all()}
    missing_ingredients = [ing for ing in requested_ingredients if ing not in all_ingredients_in_db]
    
    if missing_ingredients:
        if len(missing_ingredients) == 1:
            raise ValueError(f"Ingredient \"{missing_ingredients[0]}\" does not exist in the ingredients database. Please check the spelling and try again.")
        else:
            missing_str = ", ".join(f"\"{ing}\"" for ing in missing_ingredients)
            raise ValueError(f"Ingredients {missing_str} do not exist in the ingredients database. Please check the spelling and try again.")

    # Get all recipes
    all_recipes = db.query(Recipe).all()
    if not all_recipes:
        return []
    
    # For each recipe, count exact ingredient matches
    results = []
    for recipe in all_recipes:
        # Get recipe ingredient names (normalized to lowercase)
        recipe_ingredient_names = {ing.name.lower() for ing in recipe.ingredients}
        
        # Count how many requested ingredients are found in this recipe
        match_count = 0
        for requested_ing in requested_ingredients:
            # Exact match (case-insensitive)
            if requested_ing in recipe_ingredient_names:
                match_count += 1
        
        # Only include recipes that meet the minimum match requirement
        if match_count >= min_matches:
            results.append((recipe, match_count))
    
    # Sort by match count descending (more matches = higher rank)
    # Recipes with same match count are kept in their original order
    results.sort(key=lambda x: x[1], reverse=True)
    
    return results


def delete_recipe(db: Session, name: str = None, recipe_id: int = None) -> bool:
    """Delete a recipe by name or ID."""
    recipe = get_recipe(db, name, recipe_id)
    if not recipe:
        raise ValueError(f"Recipe not found")
    
    db.delete(recipe)
    db.commit()
    return True


def update_recipe(
    db: Session,
    recipe_id: int = None,
    name: str = None,
    new_name: str = None,
    instructions: str = None,
    notes: str = None
) -> Recipe:
    """Update basic recipe fields (name, instructions, notes)."""
    recipe = get_recipe(db, name=name, recipe_id=recipe_id)
    if not recipe:
        raise ValueError(f"Recipe not found")
    
    if new_name is not None:
        # Normalize new name (convert to singular and lowercase)
        normalized_new_name, _ = normalize_name(new_name)
        
        # Check if new name already exists
        existing = db.query(Recipe).filter(Recipe.name == normalized_new_name, Recipe.id != recipe.id).first()
        if existing:
            raise ValueError(f"Recipe '{new_name}' already exists (as '{existing.name}')")
        recipe.name = normalized_new_name
    
    if instructions is not None:
        recipe.instructions = instructions
    
    if notes is not None:
        recipe.notes = notes
    
    db.commit()
    db.refresh(recipe)
    return recipe


def add_ingredients_to_recipe(
    db: Session,
    recipe_id: int = None,
    name: str = None,
    ingredient_names: list = None
) -> Recipe:
    """Add ingredients to an existing recipe."""
    recipe = get_recipe(db, name=name, recipe_id=recipe_id)
    if not recipe:
        raise ValueError(f"Recipe not found")
    
    if not ingredient_names:
        return recipe
    
    current_ingredient_names = {ing.name for ing in recipe.ingredients}
    new_ingredients = []
    
    for ingredient_name in ingredient_names:
        # Normalize ingredient name (convert plural to singular)
        normalized_name, _ = normalize_name(ingredient_name)
        if normalized_name in current_ingredient_names:
            continue  # Skip if already in recipe
        
        ingredient_obj = get_ingredient(db, name=normalized_name)
        if not ingredient_obj:
            raise ValueError(f"Ingredient '{ingredient_name}' not found. Add it first.")
        new_ingredients.append(ingredient_obj)
    
    if new_ingredients:
        recipe.ingredients.extend(new_ingredients)
    db.commit()
    db.refresh(recipe)
    return recipe


def remove_ingredients_from_recipe(
    db: Session,
    recipe_id: int = None,
    name: str = None,
    ingredient_names: list = None
) -> Recipe:
    """Remove ingredients from an existing recipe."""
    recipe = get_recipe(db, name=name, recipe_id=recipe_id)
    if not recipe:
        raise ValueError(f"Recipe not found")
    
    if not ingredient_names:
        return recipe
    
    ingredients_to_remove = []
    for ingredient_name in ingredient_names:
        # Normalize ingredient name (convert plural to singular)
        normalized_name, _ = normalize_name(ingredient_name)
        ingredient_obj = get_ingredient(db, name=normalized_name)
        if ingredient_obj and ingredient_obj in recipe.ingredients:
            ingredients_to_remove.append(ingredient_obj)
    
    if ingredients_to_remove:
        for ingredient in ingredients_to_remove:
            recipe.ingredients.remove(ingredient)
    
    db.commit()
    db.refresh(recipe)
    return recipe


def add_tags_to_recipe(
    db: Session,
    recipe_id: int = None,
    name: str = None,
    tag_names: list = None
) -> Recipe:
    """Add tags to an existing recipe."""
    recipe = get_recipe(db, name=name, recipe_id=recipe_id)
    if not recipe:
        raise ValueError(f"Recipe not found")
    
    if not tag_names:
        return recipe
    
    current_tag_names = {tag.name for tag in recipe.tags}
    new_tags = []
    
    for tag_name in tag_names:
        if tag_name.lower() in current_tag_names:
            continue  # Skip if already tagged
        
        tag_obj = get_tag(db, name=tag_name)
        if not tag_obj:
            raise ValueError(f"Tag '{tag_name}' not found. Add it first using 'python cli.py tag add'.")
        new_tags.append(tag_obj)
    
    if new_tags:
        recipe.tags.extend(new_tags)
    db.commit()
    db.refresh(recipe)
    return recipe


def remove_tags_from_recipe(
    db: Session,
    recipe_id: int = None,
    name: str = None,
    tag_names: list = None
) -> Recipe:
    """Remove tags from an existing recipe."""
    recipe = get_recipe(db, name=name, recipe_id=recipe_id)
    if not recipe:
        raise ValueError(f"Recipe not found")
    
    if not tag_names:
        return recipe
    
    tags_to_remove = []
    for tag_name in tag_names:
        tag_obj = db.query(Tag).filter(Tag.name == tag_name.lower()).first()
        if tag_obj and tag_obj in recipe.tags:
            tags_to_remove.append(tag_obj)
    
    if tags_to_remove:
        for tag in tags_to_remove:
            recipe.tags.remove(tag)
    db.commit()
    db.refresh(recipe)
    return recipe
