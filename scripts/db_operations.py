"""
Database operations for recipes and ingredients.
"""
import warnings
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from rapidfuzz import fuzz, process
import inflect
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

# Optional semantic search support
try:
    from embeddings import (
        generate_recipe_embedding, generate_ingredient_embedding,
        generate_embedding, cosine_similarity, find_similar_by_embedding,
        batch_generate_recipe_embeddings, batch_generate_ingredient_embeddings
    )
    SEMANTIC_SEARCH_AVAILABLE = True
except ImportError:
    SEMANTIC_SEARCH_AVAILABLE = False

# Initialize inflect engine for plural/singular conversion (fallback)
_inflect_engine = inflect.engine()

# Try to load spaCy for better lemmatization
try:
    import spacy
    _spacy_nlp = None
    def _get_spacy_nlp():
        """Lazy load spaCy model."""
        global _spacy_nlp
        if _spacy_nlp is None:
            try:
                _spacy_nlp = spacy.load("en_core_web_sm")
            except OSError:
                # Model not installed, will fall back to inflect
                _spacy_nlp = False
        return _spacy_nlp if _spacy_nlp is not False else None
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False
    def _get_spacy_nlp():
        return None

# Words that should not be lemmatized (part of compound terms)
# These are often verb forms used as adjectives/nouns in compound ingredient names
NO_LEMMATIZE_WHITELIST = {
    'whipping',  # "heavy whipping cream" - whipping is part of the compound name
    'beating',   # potential compound terms
    'cooking',   # potential compound terms
    'roasting',  # potential compound terms
}

# Common cooking terms that might not be in standard dictionary
# These are added to the spell checker's dictionary
_COOKING_TERM_DICTIONARY = {
    'asparagus', 'broccoli', 'cauliflower', 'celery', 'celeriac',
    'anchovy', 'anchovies',
    'miso', 'soy', 'tofu', 'tempeh',
    'pesto', 'hummus', 'tahini',
    'zucchini', 'squash', 'pumpkin',
    'bell', 'pepper', 'peppers',
    'cream', 'cheese', 'parmesan', 'cheddar',
    'monterrey', 'jack', 'greek', 'yogurt',
    'heavy', 'whipping', 'cream',
    'tomato', 'paste',
    'bouillon', 'nutritional', 'yeast',
    'porcini', 'mushroom', 'powder',
    'rutabaga', 'rutabega',  # Accept both spellings
    'celeriac'
}

# Try to load spell checker
try:
    from spellchecker import SpellChecker
    _spell_checker = SpellChecker()
    # Add cooking terms to the dictionary
    _spell_checker.word_frequency.load_words(_COOKING_TERM_DICTIONARY)
    SPELLCHECK_AVAILABLE = True
except ImportError:
    SPELLCHECK_AVAILABLE = False
    _spell_checker = None


# ==================== PLURAL/SINGULAR CONVERSION ====================

def singularize_word(word: str, check_spelling: bool = True) -> tuple[str, list[tuple[str, str]]]:
    """
    Convert a word to its singular form using spaCy lemmatization (if available),
    falling back to inflect. Uses spell checking to detect and correct typos first.
    If a word is in the dictionary, we trust it's correct and only singularize if
    inflect confirms it's plural.
    
    Returns: (normalized_word, list of (original, corrected) tuples for corrections made)
    """
    corrections = []
    if not word:
        return word, corrections
    
    word = word.strip().lower()
    original_word = word
    
    # First, check spelling and correct if needed
    if check_spelling and SPELLCHECK_AVAILABLE and _spell_checker:
        # Check if word is misspelled
        if word not in _spell_checker:
            # Get suggestions
            candidates = _spell_checker.candidates(word)
            if candidates:
                # Get all candidates and find the best match
                candidate_list = list(candidates)
                from rapidfuzz import fuzz
                
                # Score each candidate by similarity, prefer non-possessive forms
                scored_candidates = []
                for c in candidate_list:
                    similarity = fuzz.ratio(word, c)
                    # Prefer non-possessive forms (no apostrophe)
                    bonus = 5 if "'" not in c else 0
                    scored_candidates.append((c, similarity + bonus))
                
                # Sort by similarity (highest first)
                scored_candidates.sort(key=lambda x: x[1], reverse=True)
                
                # Only auto-correct if similarity is high enough (>= 70%)
                # This distinguishes between:
                # - Close misspellings (e.g., "asparagusses" → "asparagus" at 85% similarity) ✓
                # - Nonsense words (e.g., "jflskdjlkjsdf" → no good match, similarity < 70%) ✗
                # Get similarity threshold from config
                from config_loader import get_similarity_threshold
                similarity_threshold = get_similarity_threshold()
                
                if scored_candidates and scored_candidates[0][1] >= similarity_threshold:  # At least threshold% similar (before bonus)
                    corrected = scored_candidates[0][0]
                    # Remove possessive if present (e.g., "asparagus's" -> "asparagus")
                    if corrected.endswith("'s") and corrected[:-2] in _spell_checker:
                        corrected = corrected[:-2]
                    corrections.append((original_word, corrected))
                    word = corrected
                # If similarity < 70%, word passes through unchanged (nonsense word, no good match)
    
    # Check if word is in whitelist - don't lemmatize compound term parts
    if word in NO_LEMMATIZE_WHITELIST:
        return word, corrections
    
    # If word is in dictionary (valid word), be more careful about singularization
    is_valid_word = SPELLCHECK_AVAILABLE and _spell_checker and word in _spell_checker
    
    # Try spaCy lemmatization first (more accurate)
    if SPACY_AVAILABLE:
        nlp = _get_spacy_nlp()
        if nlp:
            doc = nlp(word)
            if doc:
                lemma = doc[0].lemma_
                # Only use lemma if it's different and makes sense
                # spaCy sometimes returns weird lemmas, so validate
                if lemma and lemma != word and len(lemma) > 0:
                    # Check if lemma is actually singular (heuristic: shorter or same length)
                    if len(lemma) <= len(word) + 2:  # Allow small variations
                        # If original word is in dictionary, verify lemma is also valid
                        if is_valid_word:
                            if SPELLCHECK_AVAILABLE and _spell_checker and lemma in _spell_checker:
                                return lemma, corrections
                        else:
                            return lemma, corrections
    
    # Fall back to inflect
    singular = _inflect_engine.singular_noun(word)
    
    # If inflect returns False, the word is already singular or not recognized
    if singular:
        # If original word is in dictionary, be cautious about inflect's result
        # Inflect sometimes incorrectly treats valid singular words as plural
        if is_valid_word:
            # Check if the singular form is also in dictionary
            # If not, the original word might already be singular
            if SPELLCHECK_AVAILABLE and _spell_checker:
                if singular not in _spell_checker:
                    # Inflect says it's plural, but singular form not in dict
                    # Trust the dictionary - word is probably already singular
                    return word, corrections
        return singular, corrections
    
    # Return original word if already singular or can't be converted
    return word, corrections


def normalize_name(name: str, check_spelling: bool = True) -> tuple[str, list[tuple[str, str]]]:
    """
    Normalize a name by converting to singular form and lowercase.
    Used for ingredient and recipe names.
    Uses spell checking to detect and correct typos before singularization.
    
    Returns: (normalized_name, list of (original, corrected) tuples for corrections made)
    """
    corrections = []
    if not name:
        return name, corrections
    
    name_lower = name.lower().strip()
    
    # Split into words, singularize each (with spell checking), then rejoin
    words = name_lower.split()
    singularized_words = []
    for word in words:
        normalized_word, word_corrections = singularize_word(word, check_spelling=check_spelling)
        singularized_words.append(normalized_word)
        corrections.extend(word_corrections)
    
    normalized = ' '.join(singularized_words)
    
    return normalized, corrections


def check_spelling(name: str) -> tuple[bool, dict[str, list[str]]]:
    """
    Check spelling of ingredient/recipe name and suggest corrections.
    Returns (is_correct, suggestions_dict).
    suggestions_dict maps misspelled words to lists of suggested corrections.
    """
    if not SPELLCHECK_AVAILABLE or not _spell_checker:
        return (True, {})  # If spell checker not available, assume correct
    
    if not name:
        return (True, {})
    
    # Split into words and check each
    words = name.lower().split()
    misspelled = _spell_checker.unknown(words)
    
    if misspelled:
        suggestions = {}
        for word in misspelled:
            candidates = _spell_checker.candidates(word)
            if candidates:
                suggestions[word] = list(candidates)[:5]  # Top 5 suggestions
        return (False, suggestions)
    
    return (True, {})


def normalize_tags(tags: list[str]) -> tuple[list[str], list[tuple[str, str]]]:
    """
    Normalize a list of tags: lowercase, spell-check, and singularize.
    Returns (normalized_tags, list of (original, corrected) tuples).
    """
    corrections = []
    normalized = []
    
    for tag in tags:
        if not tag or not tag.strip():
            continue
        
        tag_lower = tag.strip().lower()
        # Normalize the tag (spell check + singularize)
        normalized_tag, tag_corrections = normalize_name(tag_lower, check_spelling=True)
        normalized.append(normalized_tag)
        corrections.extend(tag_corrections)
    
    return normalized, corrections


def normalize_text_words(text: str) -> tuple[str, list[tuple[str, str]]]:
    """
    Normalize text by spell-checking and correcting words.
    Preserves sentence structure and punctuation.
    Returns (normalized_text, list of (original, corrected) tuples).
    """
    corrections = []
    if not text:
        return text, corrections
    
    # Split into words while preserving spaces
    import re
    words = re.findall(r'\b\w+\b|\s+|[^\w\s]', text)
    normalized_words = []
    
    for word in words:
        if re.match(r'\w+', word):  # It's a word
            normalized_word, word_corrections = normalize_name(word, check_spelling=True)
            normalized_words.append(normalized_word)
            corrections.extend(word_corrections)
        else:  # It's whitespace or punctuation
            normalized_words.append(word)
    
    return ''.join(normalized_words), corrections


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
    
    # Get or create the ingredient type
    ingredient_type = get_or_create_ingredient_type(db, type_name)
    
    # Check if ingredient already exists (using normalized name)
    existing = db.query(Ingredient).filter(Ingredient.name == normalized_name).first()
    if existing:
        raise ValueError(f"Ingredient '{name}' already exists (as '{existing.name}')")
    
    ingredient = Ingredient(name=normalized_name, type=ingredient_type, notes=notes, stale_embedding=True)
    
    # Add tags
    if tags:
        tag_objects = []
        for tag_name in tags:
            tag_obj = get_or_create_tag(db, tag_name)
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
        ingredient_type = get_or_create_ingredient_type(db, type_name)
        ingredient.type = ingredient_type
    
    if alias is not None:
        ingredient.alias = alias
    
    if notes is not None:
        ingredient.notes = notes
    
    # Mark embedding as stale if any field was updated
    if new_name is not None or type_name is not None or alias is not None or notes is not None:
        ingredient.stale_embedding = True
    
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
        
        tag_obj = get_or_create_tag(db, tag_name)
        new_tags.append(tag_obj)
    
    if new_tags:
        ingredient.tags.extend(new_tags)
        ingredient.stale_embedding = True
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
        ingredient.stale_embedding = True
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


def search_recipes_by_tag(db: Session, tag_query: str, min_score: int = 70) -> list:
    """
    Search for recipes by tag name (with fuzzy matching).
    
    Args:
        db: Database session
        tag_query: Tag name to search for (will be normalized to lowercase)
        min_score: Minimum similarity score (0-100) for tag matching
    
    Returns:
        List of tuples: (recipe, tag, score) sorted by score descending
    """
    # Normalize tag query to lowercase
    tag_query_lower = tag_query.lower().strip()
    
    # Get all tags
    all_tags = db.query(Tag).all()
    if not all_tags:
        return []
    
    # Create mapping of tag names to tags
    tag_name_map = {tag.name: tag for tag in all_tags}
    tag_names_list = list(tag_name_map.keys())
    
    # Find matching tags using fuzzy matching
    matches = process.extract(
        tag_query_lower,
        tag_names_list,
        scorer=fuzz.WRatio,
        limit=10
    )
    
    # Collect tags that match above threshold
    matched_tags = []
    for matched_name, score, _ in matches:
        if score >= min_score:
            matched_tags.append((tag_name_map[matched_name], score))
    
    if not matched_tags:
        return []
    
    # Find all recipes that have any of the matched tags
    results = []
    for tag, score in matched_tags:
        for recipe in tag.recipes:
            results.append((recipe, tag, score))
    
    # Remove duplicates (same recipe might match multiple similar tags)
    seen_recipes = set()
    unique_results = []
    for recipe, tag, score in results:
        if recipe.id not in seen_recipes:
            seen_recipes.add(recipe.id)
            unique_results.append((recipe, tag, score))
    
    # Sort by score descending
    unique_results.sort(key=lambda x: x[2], reverse=True)
    return unique_results


def search_ingredients_by_tag(db: Session, tag_query: str, min_score: int = 70) -> list:
    """
    Search for ingredients by tag name (with fuzzy matching).
    
    Args:
        db: Database session
        tag_query: Tag name to search for (will be normalized to lowercase)
        min_score: Minimum similarity score (0-100) for tag matching
    
    Returns:
        List of tuples: (ingredient, tag, score) sorted by score descending
    """
    # Normalize tag query to lowercase
    tag_query_lower = tag_query.lower().strip()
    
    # Get all tags
    all_tags = db.query(Tag).all()
    if not all_tags:
        return []
    
    # Create mapping of tag names to tags
    tag_name_map = {tag.name: tag for tag in all_tags}
    tag_names_list = list(tag_name_map.keys())
    
    # Find matching tags using fuzzy matching
    matches = process.extract(
        tag_query_lower,
        tag_names_list,
        scorer=fuzz.WRatio,
        limit=10
    )
    
    # Collect tags that match above threshold
    matched_tags = []
    for matched_name, score, _ in matches:
        if score >= min_score:
            matched_tags.append((tag_name_map[matched_name], score))
    
    if not matched_tags:
        return []
    
    # Find all ingredients that have any of the matched tags
    results = []
    for tag, score in matched_tags:
        for ingredient in tag.ingredients:
            results.append((ingredient, tag, score))
    
    # Remove duplicates (same ingredient might match multiple similar tags)
    seen_ingredients = set()
    unique_results = []
    for ingredient, tag, score in results:
        if ingredient.id not in seen_ingredients:
            seen_ingredients.add(ingredient.id)
            unique_results.append((ingredient, tag, score))
    
    # Sort by score descending
    unique_results.sort(key=lambda x: x[2], reverse=True)
    return unique_results


def search_articles_by_tag(db: Session, tag_query: str, min_score: int = 70) -> list:
    """
    Search for articles by tag name (with fuzzy matching).
    
    Args:
        db: Database session
        tag_query: Tag name to search for (will be normalized to lowercase)
        min_score: Minimum similarity score (0-100) for tag matching
    
    Returns:
        List of tuples: (article, tag, score) sorted by score descending
    """
    # Normalize tag query to lowercase
    tag_query_lower = tag_query.lower().strip()
    
    # Get all tags
    all_tags = db.query(Tag).all()
    if not all_tags:
        return []
    
    # Create mapping of tag names to tags
    tag_name_map = {tag.name: tag for tag in all_tags}
    tag_names_list = list(tag_name_map.keys())
    
    # Find matching tags using fuzzy matching
    matches = process.extract(
        tag_query_lower,
        tag_names_list,
        scorer=fuzz.WRatio,
        limit=10
    )
    
    # Collect tags that match above threshold
    matched_tags = []
    for matched_name, score, _ in matches:
        if score >= min_score:
            matched_tags.append((tag_name_map[matched_name], score))
    
    if not matched_tags:
        return []
    
    # Find all articles that have any of the matched tags
    results = []
    for tag, score in matched_tags:
        for article in tag.articles:
            results.append((article, tag, score))
    
    # Remove duplicates (same article might match multiple similar tags)
    seen_articles = set()
    unique_results = []
    for article, tag, score in results:
        if article.id not in seen_articles:
            seen_articles.add(article.id)
            unique_results.append((article, tag, score))
    
    # Sort by score descending
    unique_results.sort(key=lambda x: x[2], reverse=True)
    return unique_results


# ==================== ARTICLE OPERATIONS ====================

def add_article(
    db: Session,
    notes: str = None,
    tags: list = None
) -> Article:
    """Add a new article to the database."""
    article = Article(notes=notes, stale_embedding=True)
    
    # Add tags
    if tags:
        tag_objects = []
        for tag_name in tags:
            tag_obj = get_or_create_tag(db, tag_name)
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
        # Mark embedding as stale if notes were updated
        article.stale_embedding = True
    
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
        
        tag_obj = get_or_create_tag(db, tag_name)
        new_tags.append(tag_obj)
    
    if new_tags:
        article.tags.extend(new_tags)
        article.stale_embedding = True
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
        notes=notes,
        stale_embedding=True
    )
    
    # Add tags
    if tags:
        tag_objects = []
        for tag_name in tags:
            tag_obj = get_or_create_tag(db, tag_name)
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


def find_similar_ingredients(db: Session, name: str, min_score: int = 50) -> list:
    """
    Find ingredients similar to the given name.
    
    Args:
        db: Database session
        name: Ingredient name to check
        min_score: Minimum similarity score (0-100) to consider a match
    
    Returns:
        List of tuples: (ingredient, similarity_score) sorted by score descending
    """
    all_ingredients = db.query(Ingredient).all()
    
    if not all_ingredients:
        return []
    
    # Create a list of ingredient names for matching
    ingredient_names = {ing.id: ing.name for ing in all_ingredients}
    
    # Use rapidfuzz to find best matches
    matches = process.extract(
        name.lower(),
        ingredient_names,
        scorer=fuzz.WRatio,
        limit=5
    )
    
    # Filter by minimum score and create result list
    results = []
    for matched_name, score, ingredient_id in matches:
        if score >= min_score:
            ingredient = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
            if ingredient:
                results.append((ingredient, score))
    
    return results


def find_similar_recipes(db: Session, name: str, min_score: int = 50) -> list:
    """
    Find recipes similar to the given name.
    
    Args:
        db: Database session
        name: Recipe name to check
        min_score: Minimum similarity score (0-100) to consider a match
    
    Returns:
        List of tuples: (recipe, similarity_score) sorted by score descending
    """
    all_recipes = db.query(Recipe).all()
    
    if not all_recipes:
        return []
    
    # Create a list of recipe names for matching
    recipe_names = {recipe.id: recipe.name for recipe in all_recipes}
    
    # Use rapidfuzz to find best matches
    matches = process.extract(
        name,
        recipe_names,
        scorer=fuzz.WRatio,
        limit=5
    )
    
    # Filter by minimum score and create result list
    results = []
    for matched_name, score, recipe_id in matches:
        if score >= min_score:
            recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
            if recipe:
                results.append((recipe, score))
    
    return results


def search_recipes(db: Session, query: str, limit: int = 10, min_score: int = 50) -> list:
    """
    Search for recipes by approximate name matching.
    
    Args:
        db: Database session
        query: Search query string
        limit: Maximum number of results to return
        min_score: Minimum similarity score (0-100) to include in results
    
    Returns:
        List of tuples: (recipe, similarity_score) sorted by score descending
    """
    all_recipes = db.query(Recipe).all()
    
    if not all_recipes:
        return []
    
    # Create a list of recipe names for matching
    recipe_names = {recipe.id: recipe.name for recipe in all_recipes}
    
    # Use rapidfuzz to find best matches
    # process.extract returns: [(matched_string, score, index), ...]
    matches = process.extract(
        query,
        recipe_names,
        scorer=fuzz.WRatio,  # Weighted ratio - good for partial matches
        limit=limit
    )
    
    # Filter by minimum score and create result list
    results = []
    for matched_name, score, recipe_id in matches:
        if score >= min_score:
            recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
            if recipe:
                results.append((recipe, score))
    
    return results


def search_ingredients(db: Session, query: str, limit: int = 10, min_score: int = 50) -> list:
    """
    Search for ingredients by approximate name matching.
    
    Args:
        db: Database session
        query: Search query string
        limit: Maximum number of results to return
        min_score: Minimum similarity score (0-100) to include in results
    
    Returns:
        List of tuples: (ingredient, similarity_score) sorted by score descending
    """
    all_ingredients = db.query(Ingredient).all()
    
    if not all_ingredients:
        return []
    
    # Create a list of ingredient names for matching
    ingredient_names = {ing.id: ing.name for ing in all_ingredients}
    
    # Use rapidfuzz to find best matches
    # process.extract returns: [(matched_string, score, index), ...]
    matches = process.extract(
        normalize_name(query)[0],
        ingredient_names,
        scorer=fuzz.WRatio,  # Weighted ratio - good for partial matches
        limit=limit
    )
    
    # Filter by minimum score and create result list
    results = []
    for matched_name, score, ingredient_id in matches:
        if score >= min_score:
            ingredient = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
            if ingredient:
                results.append((ingredient, score))
    
    return results


def suggest_recipes_by_ingredients(db: Session, ingredient_names: list, min_match_score: int = 70) -> list:
    """
    Suggest recipes that contain the given ingredients (with fuzzy matching).
    
    Args:
        db: Database session
        ingredient_names: List of ingredient names to search for (will be normalized)
        min_match_score: Minimum similarity score (0-100) for ingredient matching
    
    Returns:
        List of tuples: (recipe, match_score, matched_ingredients) sorted by match_score descending
        where match_score is the percentage of requested ingredients found in the recipe
    """
    if not ingredient_names:
        return []
    
    # Normalize all ingredient names (singular, lowercase)
    normalized_names = [normalize_name(name.strip())[0] for name in ingredient_names if name.strip()]
    if not normalized_names:
        return []
    
    # Get all ingredients from database
    all_ingredients = db.query(Ingredient).all()
    if not all_ingredients:
        return []
    
    # Create mapping of ingredient names to ingredient objects
    ingredient_name_map = {ing.name: ing for ing in all_ingredients}
    ingredient_names_list = list(ingredient_name_map.keys())
    
    # For each requested ingredient, find matching ingredients using fuzzy matching
    # Also check ingredient types and tags
    matched_ingredient_sets = []
    for requested_name in normalized_names:
        matched_ingredients = []
        
        # 1. Match by ingredient name (fuzzy matching)
        matches = process.extract(
            requested_name,
            ingredient_names_list,
            scorer=fuzz.WRatio,
            limit=10
        )
        
        for matched_name, score, _ in matches:
            if score >= min_match_score:
                matched_ingredients.append(ingredient_name_map[matched_name])
        
        # 2. Match by ingredient type (fuzzy matching on type name)
        # Get all ingredient types
        all_types = db.query(IngredientType).all()
        type_name_map = {type_obj.name: type_obj for type_obj in all_types}
        type_names_list = list(type_name_map.keys())
        
        type_matches = process.extract(
            requested_name,
            type_names_list,
            scorer=fuzz.WRatio,
            limit=10
        )
        
        for matched_type_name, score, _ in type_matches:
            if score >= min_match_score:
                # Find all ingredients of this type
                type_obj = type_name_map[matched_type_name]
                for ingredient in type_obj.ingredients:
                    if ingredient not in matched_ingredients:
                        matched_ingredients.append(ingredient)
        
        # 3. Match by ingredient tags (fuzzy matching on tag names)
        all_tags = db.query(Tag).all()
        tag_name_map = {tag.name: tag for tag in all_tags}
        tag_names_list = list(tag_name_map.keys())
        
        tag_matches = process.extract(
            requested_name,
            tag_names_list,
            scorer=fuzz.WRatio,
            limit=10
        )
        
        for matched_tag_name, score, _ in tag_matches:
            if score >= min_match_score:
                # Find all ingredients with this tag
                tag_obj = tag_name_map[matched_tag_name]
                for ingredient in tag_obj.ingredients:
                    if ingredient not in matched_ingredients:
                        matched_ingredients.append(ingredient)
        
        if matched_ingredients:
            matched_ingredient_sets.append(set(matched_ingredients))
        else:
            # If no match found, still add empty set to track that this ingredient wasn't found
            matched_ingredient_sets.append(set())
    
    # Get all recipes
    all_recipes = db.query(Recipe).all()
    if not all_recipes:
        return []
    
    # For each recipe, calculate how many of the requested ingredients it contains
    results = []
    for recipe in all_recipes:
        recipe_ingredients = set(recipe.ingredients)
        
        # Count how many ingredient sets match this recipe
        matches_found = 0
        matched_ingredient_names = []
        
        for i, matched_set in enumerate(matched_ingredient_sets):
            if matched_set and recipe_ingredients.intersection(matched_set):
                # Found at least one matching ingredient from this set
                matches_found += 1
                # Get the actual ingredient names that matched
                matched = recipe_ingredients.intersection(matched_set)
                matched_ingredient_names.extend([ing.name for ing in matched])
        
        if matches_found > 0:
            # Calculate match score as percentage of requested ingredients found
            match_score = (matches_found / len(normalized_names)) * 100
            results.append((recipe, match_score, matched_ingredient_names))
    
    # Sort by match score descending
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
    
    # Mark embedding as stale if any field was updated
    if new_name is not None or instructions is not None or notes is not None:
        recipe.stale_embedding = True
    
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
        recipe.stale_embedding = True
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
        recipe.stale_embedding = True
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
        
        tag_obj = get_or_create_tag(db, tag_name)
        new_tags.append(tag_obj)
    
    if new_tags:
        recipe.tags.extend(new_tags)
        recipe.stale_embedding = True
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
        recipe.stale_embedding = True
    db.commit()
    db.refresh(recipe)
    return recipe
