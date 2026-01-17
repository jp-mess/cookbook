"""
Embedding generation and management for semantic search.

This module handles generating vector embeddings for recipes, ingredients, and articles
using Ollama, and provides utilities for semantic similarity search.
"""
import json
import hashlib
from pathlib import Path
from typing import Optional, List
from database import SessionLocal
from models import Recipe, Ingredient, Article

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

# Get configuration
from config_loader import get_config

_config = get_config()
_project_root = Path(__file__).parent.parent

# Embedding model to use (nomic-embed-text is fast and good quality)
EMBEDDING_MODEL = _config.get('embeddings', {}).get('model', 'nomic-embed-text')
EMBEDDING_DIM = 768  # Dimension for nomic-embed-text

# Cache directory for embeddings
cache_dir_name = _config.get('embeddings', {}).get('cache_dir', 'embeddings_cache')
CACHE_DIR = _project_root / cache_dir_name
CACHE_DIR.mkdir(exist_ok=True)


def get_cache_path(text: str, model: str = EMBEDDING_MODEL) -> Path:
    """Get cache file path for an embedding."""
    # Create hash of text + model for cache key
    cache_key = f"{model}:{text}"
    cache_hash = hashlib.md5(cache_key.encode()).hexdigest()
    return CACHE_DIR / f"{cache_hash}.json"


def generate_embedding(text: str, model: str = EMBEDDING_MODEL, use_cache: bool = True) -> Optional[List[float]]:
    """
    Generate embedding for text using Ollama.
    
    Args:
        text: Text to embed
        model: Ollama model to use (default: nomic-embed-text)
        use_cache: Whether to use cached embeddings
    
    Returns:
        List of floats representing the embedding, or None if Ollama unavailable
    """
    if not OLLAMA_AVAILABLE:
        return None
    
    if not text or not text.strip():
        return None
    
    # Check cache
    cache_path = get_cache_path(text, model)
    if use_cache and cache_path.exists():
        try:
            with open(cache_path, 'r') as f:
                cached = json.load(f)
                if cached.get('model') == model:
                    return cached.get('embedding')
        except Exception:
            pass  # Cache corrupted, regenerate
    
    try:
        # Generate embedding
        response = ollama.embeddings(
            model=model,
            prompt=text
        )
        embedding = response.get('embedding')
        
        # Cache the result
        if use_cache and embedding:
            try:
                with open(cache_path, 'w') as f:
                    json.dump({
                        'model': model,
                        'text': text,
                        'embedding': embedding
                    }, f)
            except Exception:
                pass  # Cache write failed, but embedding is valid
        
        return embedding
    except Exception as e:
        print(f"Warning: Failed to generate embedding: {e}")
        return None


def generate_recipe_embedding(recipe: Recipe, update_stale_flag: bool = False) -> Optional[List[float]]:
    """
    Generate embedding for a recipe.
    
    Combines name, instructions, tags, and ingredient names into a single text.
    
    Args:
        recipe: Recipe object
        update_stale_flag: If True, set stale_embedding=False after generating
    
    Returns:
        Embedding vector or None
    """
    parts = []
    
    # Recipe name (most important)
    if recipe.name:
        parts.append(recipe.name)
    
    # Tags (cuisine, style)
    if recipe.tags:
        tag_names = [tag.name for tag in recipe.tags]
        parts.append(" ".join(tag_names))
    
    # Ingredients (what's in it)
    if recipe.ingredients:
        ingredient_names = [ing.name for ing in recipe.ingredients]
        parts.append(" ".join(ingredient_names))
    
    # Instructions (cooking method)
    if recipe.instructions:
        # Use first 200 chars of instructions to avoid too long text
        instructions_preview = recipe.instructions[:200]
        parts.append(instructions_preview)
    
    # Notes are excluded from embeddings to avoid confusion
    
    combined_text = " ".join(parts)
    embedding = generate_embedding(combined_text)
    
    # Update stale flag if requested
    if update_stale_flag and embedding:
        from database import SessionLocal
        db = SessionLocal()
        try:
            # Re-query to get the recipe in this session
            recipe_in_session = db.query(Recipe).filter(Recipe.id == recipe.id).first()
            if recipe_in_session:
                recipe_in_session.stale_embedding = False
                db.commit()
        finally:
            db.close()
    
    return embedding


def generate_ingredient_embedding(ingredient: Ingredient, update_stale_flag: bool = False) -> Optional[List[float]]:
    """
    Generate embedding for an ingredient.
    
    Combines name, type, tags, and aliases.
    
    Args:
        ingredient: Ingredient object
        update_stale_flag: If True, set stale_embedding=False after generating
    
    Returns:
        Embedding vector or None
    """
    parts = []
    
    # Ingredient name (most important)
    if ingredient.name:
        parts.append(ingredient.name)
    
    # Type (vegetable, fruit, etc.)
    if ingredient.type:
        parts.append(ingredient.type.name)
    
    # Aliases (alternative names)
    if ingredient.alias:
        parts.append(ingredient.alias)
    
    # Tags
    if ingredient.tags:
        tag_names = [tag.name for tag in ingredient.tags]
        parts.append(" ".join(tag_names))
    
    # Notes are excluded from embeddings to avoid confusion
    
    combined_text = " ".join(parts)
    embedding = generate_embedding(combined_text)
    
    # Update stale flag if requested
    if update_stale_flag and embedding:
        from database import SessionLocal
        db = SessionLocal()
        try:
            # Re-query to get the ingredient in this session
            ingredient_in_session = db.query(Ingredient).filter(Ingredient.id == ingredient.id).first()
            if ingredient_in_session:
                ingredient_in_session.stale_embedding = False
                db.commit()
        finally:
            db.close()
    
    return embedding


def generate_article_embedding(article: Article, update_stale_flag: bool = False) -> Optional[List[float]]:
    """
    Generate embedding for an article.
    
    Uses notes and tags.
    
    Args:
        article: Article object
        update_stale_flag: If True, set stale_embedding=False after generating
    
    Returns:
        Embedding vector or None
    """
    parts = []
    
    # Notes (main content)
    if article.notes:
        # Use first 500 chars to avoid too long text
        notes_preview = article.notes[:500]
        parts.append(notes_preview)
    
    # Tags
    if article.tags:
        tag_names = [tag.name for tag in article.tags]
        parts.append(" ".join(tag_names))
    
    combined_text = " ".join(parts)
    embedding = generate_embedding(combined_text)
    
    # Update stale flag if requested
    if update_stale_flag and embedding:
        from database import SessionLocal
        db = SessionLocal()
        try:
            # Re-query to get the article in this session
            article_in_session = db.query(Article).filter(Article.id == article.id).first()
            if article_in_session:
                article_in_session.stale_embedding = False
                db.commit()
        finally:
            db.close()
    
    return embedding


def batch_generate_recipe_embeddings(limit: Optional[int] = None, only_stale: bool = True) -> dict:
    """
    Generate embeddings for recipes in the database.
    
    Args:
        limit: Maximum number of recipes to process (None for all)
        only_stale: If True, only process recipes with stale_embedding=True
    
    Returns:
        Dictionary mapping recipe_id -> embedding
    """
    db = SessionLocal()
    try:
        query = db.query(Recipe)
        if only_stale:
            query = query.filter(Recipe.stale_embedding == True)
        recipes = query.limit(limit).all() if limit else query.all()
        embeddings = {}
        
        print(f"Generating embeddings for {len(recipes)} recipe(s)...")
        for i, recipe in enumerate(recipes, 1):
            print(f"  [{i}/{len(recipes)}] {recipe.name}...", end=" ", flush=True)
            embedding = generate_recipe_embedding(recipe, update_stale_flag=True)
            if embedding:
                embeddings[recipe.id] = embedding
                print("✓")
            else:
                print("✗ (failed)")
        
        return embeddings
    finally:
        db.close()


def batch_generate_ingredient_embeddings(limit: Optional[int] = None, only_stale: bool = True) -> dict:
    """
    Generate embeddings for ingredients in the database.
    
    Args:
        limit: Maximum number of ingredients to process (None for all)
        only_stale: If True, only process ingredients with stale_embedding=True
    
    Returns:
        Dictionary mapping ingredient_id -> embedding
    """
    db = SessionLocal()
    try:
        query = db.query(Ingredient)
        if only_stale:
            query = query.filter(Ingredient.stale_embedding == True)
        ingredients = query.limit(limit).all() if limit else query.all()
        embeddings = {}
        
        print(f"Generating embeddings for {len(ingredients)} ingredient(s)...")
        for i, ingredient in enumerate(ingredients, 1):
            print(f"  [{i}/{len(ingredients)}] {ingredient.name}...", end=" ", flush=True)
            embedding = generate_ingredient_embedding(ingredient, update_stale_flag=True)
            if embedding:
                embeddings[ingredient.id] = embedding
                print("✓")
            else:
                print("✗ (failed)")
        
        return embeddings
    finally:
        db.close()


def batch_generate_article_embeddings(limit: Optional[int] = None, only_stale: bool = True) -> dict:
    """
    Generate embeddings for articles in the database.
    
    Args:
        limit: Maximum number of articles to process (None for all)
        only_stale: If True, only process articles with stale_embedding=True
    
    Returns:
        Dictionary mapping article_id -> embedding
    """
    db = SessionLocal()
    try:
        query = db.query(Article)
        if only_stale:
            query = query.filter(Article.stale_embedding == True)
        articles = query.limit(limit).all() if limit else query.all()
        embeddings = {}
        
        print(f"Generating embeddings for {len(articles)} article(s)...")
        for i, article in enumerate(articles, 1):
            print(f"  [{i}/{len(articles)}] Article #{article.id}...", end=" ", flush=True)
            embedding = generate_article_embedding(article, update_stale_flag=True)
            if embedding:
                embeddings[article.id] = embedding
                print("✓")
            else:
                print("✗ (failed)")
        
        return embeddings
    finally:
        db.close()


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """
    Calculate cosine similarity between two vectors.
    
    Returns:
        Similarity score between -1 and 1 (1 = identical, 0 = orthogonal, -1 = opposite)
    """
    if len(vec1) != len(vec2):
        return 0.0
    
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    magnitude1 = sum(a * a for a in vec1) ** 0.5
    magnitude2 = sum(b * b for b in vec2) ** 0.5
    
    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0
    
    return dot_product / (magnitude1 * magnitude2)


def find_similar_by_embedding(
    query_embedding: List[float],
    item_embeddings: dict,
    top_k: int = 10,
    min_similarity: float = 0.0
) -> List[tuple]:
    """
    Find most similar items to query embedding.
    
    Args:
        query_embedding: Query vector
        item_embeddings: Dictionary mapping item_id -> embedding
        top_k: Number of results to return
        min_similarity: Minimum similarity score (0-1)
    
    Returns:
        List of tuples: (item_id, similarity_score) sorted by score descending
    """
    similarities = []
    
    for item_id, item_embedding in item_embeddings.items():
        similarity = cosine_similarity(query_embedding, item_embedding)
        if similarity >= min_similarity:
            similarities.append((item_id, similarity))
    
    # Sort by similarity descending
    similarities.sort(key=lambda x: x[1], reverse=True)
    
    return similarities[:top_k]
