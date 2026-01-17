"""
Semantic search functions for recipes and ingredients.

These functions use vector embeddings for semantic similarity search.
"""
from sqlalchemy.orm import Session
from models import Recipe, Ingredient

# Optional semantic search support
try:
    from embeddings import (
        generate_recipe_embedding, generate_ingredient_embedding,
        generate_embedding, cosine_similarity, find_similar_by_embedding
    )
    SEMANTIC_SEARCH_AVAILABLE = True
except ImportError:
    SEMANTIC_SEARCH_AVAILABLE = False


def semantic_search_ingredients_by_query(
    db: Session,
    query: str,
    limit: int = 10,
    min_similarity: float = 0.0
) -> list:
    """
    Search ingredients using semantic similarity (vector embeddings only).
    
    Searches by ingredient name and tags (notes are excluded from embeddings).
    Uses pure semantic search - no fuzzy matching.
    
    Args:
        db: Database session
        query: Search query string (can be comma-separated terms like "umami, basil, herb")
        limit: Maximum number of results
        min_similarity: Minimum cosine similarity (0-1) for matches
    
    Returns:
        List of tuples: (ingredient, similarity_score) sorted by score descending
        similarity_score is 0-1 (cosine similarity)
    """
    if not SEMANTIC_SEARCH_AVAILABLE:
        raise ValueError("Semantic search not available. Embeddings module not found.")
    
    # Generate embedding for query
    query_embedding = generate_embedding(query)
    if not query_embedding:
        raise ValueError("Failed to generate embedding for query. Is Ollama running?")
    
    # Get all ingredients
    all_ingredients = db.query(Ingredient).all()
    if not all_ingredients:
        return []
    
    # Generate or retrieve embeddings for ingredients
    ingredient_embeddings = {}
    for ingredient in all_ingredients:
        embedding = generate_ingredient_embedding(ingredient)
        if embedding:
            ingredient_embeddings[ingredient.id] = embedding
    
    if not ingredient_embeddings:
        return []
    
    # Find semantically similar ingredients (pure semantic, no fuzzy)
    semantic_matches = find_similar_by_embedding(
        query_embedding,
        ingredient_embeddings,
        top_k=limit,
        min_similarity=min_similarity
    )
    
    # Convert to list of (ingredient, score) tuples
    results = []
    for ingredient_id, score in semantic_matches:
        ingredient = db.query(Ingredient).filter(Ingredient.id == ingredient_id).first()
        if ingredient:
            results.append((ingredient, score))
    
    return results


def semantic_search_recipes_by_query(
    db: Session,
    query: str,
    limit: int = 10,
    min_similarity: float = 0.0
) -> list:
    """
    Search recipes using semantic similarity (vector embeddings only).
    
    Searches by recipe name, tags, ingredients, and instructions (notes are excluded from embeddings).
    Uses pure semantic search - no fuzzy matching.
    
    Args:
        db: Database session
        query: Search query string (can be comma-separated terms like "umami, basil, herb")
        limit: Maximum number of results
        min_similarity: Minimum cosine similarity (0-1) for matches
    
    Returns:
        List of tuples: (recipe, similarity_score) sorted by score descending
        similarity_score is 0-1 (cosine similarity)
    """
    if not SEMANTIC_SEARCH_AVAILABLE:
        raise ValueError("Semantic search not available. Embeddings module not found.")
    
    # Generate embedding for query
    query_embedding = generate_embedding(query)
    if not query_embedding:
        raise ValueError("Failed to generate embedding for query. Is Ollama running?")
    
    # Get all recipes
    all_recipes = db.query(Recipe).all()
    if not all_recipes:
        return []
    
    # Generate or retrieve embeddings for recipes
    recipe_embeddings = {}
    for recipe in all_recipes:
        embedding = generate_recipe_embedding(recipe)
        if embedding:
            recipe_embeddings[recipe.id] = embedding
    
    if not recipe_embeddings:
        return []
    
    # Find semantically similar recipes (pure semantic, no fuzzy)
    semantic_matches = find_similar_by_embedding(
        query_embedding,
        recipe_embeddings,
        top_k=limit,
        min_similarity=min_similarity
    )
    
    # Convert to list of (recipe, score) tuples
    results = []
    for recipe_id, score in semantic_matches:
        recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
        if recipe:
            results.append((recipe, score))
    
    return results
