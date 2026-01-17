"""
Ollama integration for natural language queries about the recipe database.
"""
import json
import ollama
from database import SessionLocal
from db_operations import (
    list_recipes, list_ingredients, list_articles, list_tags, list_ingredient_types,
    search_recipes, search_ingredients, suggest_recipes_by_ingredients
)
from models import Recipe, Ingredient, Article


def format_recipe_summary(recipe: Recipe) -> dict:
    """Format a recipe for inclusion in context."""
    return {
        'id': recipe.id,
        'name': recipe.name,
        'tags': [tag.name for tag in recipe.tags],
        'ingredients': [ing.name for ing in recipe.ingredients],
        'has_instructions': bool(recipe.instructions),
        'has_notes': bool(recipe.notes)
    }


def format_ingredient_summary(ingredient: Ingredient) -> dict:
    """Format an ingredient for inclusion in context."""
    return {
        'id': ingredient.id,
        'name': ingredient.name,
        'type': ingredient.type.name,
        'tags': [tag.name for tag in ingredient.tags],
        'has_notes': bool(ingredient.notes),
        'alias': ingredient.alias.split(', ') if ingredient.alias else []
    }


def format_article_summary(article: Article) -> dict:
    """Format an article for inclusion in context."""
    return {
        'id': article.id,
        'tags': [tag.name for tag in article.tags],
        'notes_preview': article.notes[:200] if article.notes else None
    }


def get_database_context(db, question: str) -> dict:
    """
    Analyze the question and retrieve relevant database context.
    Returns a dictionary with recipes, ingredients, articles, etc.
    """
    context = {
        'recipes': [],
        'ingredients': [],
        'articles': [],
        'tags': [],
        'types': []
    }
    
    question_lower = question.lower()
    
    # Always include summary stats
    all_recipes = list_recipes(db)
    all_ingredients = list_ingredients(db)
    all_articles = list_articles(db)
    all_tags = list_tags(db)
    all_types = list_ingredient_types(db)
    
    context['stats'] = {
        'total_recipes': len(all_recipes),
        'total_ingredients': len(all_ingredients),
        'total_articles': len(all_articles),
        'total_tags': len(all_tags),
        'total_types': len(all_types)
    }
    
    # If question mentions specific ingredients, get recipes with those ingredients
    ingredient_keywords = ['ingredient', 'mushroom', 'basil', 'tomato', 'wine', 'cheese', 'pasta', 
                          'vegetable', 'meat', 'herb', 'spice', 'dairy', 'sauce']
    if any(keyword in question_lower for keyword in ingredient_keywords):
        # Try to extract ingredient names from question
        words = question_lower.split()
        potential_ingredients = [w for w in words if len(w) > 3 and w not in ['what', 'which', 'how', 'when', 'where', 'with', 'that', 'have', 'contains']]
        
        if potential_ingredients:
            # Use suggest_recipes_by_ingredients to find relevant recipes
            try:
                recipe_results = suggest_recipes_by_ingredients(db, potential_ingredients, min_match_score=60)
                context['recipes'] = [format_recipe_summary(recipe) for recipe, _, _ in recipe_results[:10]]
            except:
                pass
    
    # If question mentions tags, search by tags
    if 'tag' in question_lower or any(tag.name in question_lower for tag in all_tags[:10]):
        # Include tag information
        context['tags'] = [tag.name for tag in all_tags]
    
    # If question asks about recipes in general
    if 'recipe' in question_lower or 'dish' in question_lower or 'food' in question_lower:
        if not context['recipes']:
            # Include a sample of recipes
            context['recipes'] = [format_recipe_summary(recipe) for recipe in all_recipes[:10]]
    
    # If question asks about ingredients
    if 'ingredient' in question_lower and 'recipe' not in question_lower:
        context['ingredients'] = [format_ingredient_summary(ing) for ing in all_ingredients[:20]]
    
    # If question asks about articles
    if 'article' in question_lower or 'note' in question_lower:
        context['articles'] = [format_article_summary(article) for article in all_articles[:10]]
    
    # Always include types for context
    context['types'] = [type_obj.name for type_obj in all_types]
    
    return context


def query_with_ollama(question: str, model: str = "llama3.2") -> str:
    """
    Query Ollama with a natural language question about the recipe database.
    
    Args:
        question: Natural language question
        model: Ollama model to use (default: llama3.2)
    
    Returns:
        Response from Ollama
    """
    db = SessionLocal()
    try:
        # Get relevant database context
        context = get_database_context(db, question)
        
        # Build system prompt
        system_prompt = """You are a helpful assistant for a recipe database system. 
The database contains:
- Recipes: with names, ingredients, tags, instructions, and notes
- Ingredients: with names, types (e.g., vegetable, fruit, dairy), tags, and notes
- Articles: with notes and tags
- Tags: can be applied to recipes, ingredients, and articles
- Ingredient Types: categories like vegetable, fruit, dairy, etc.

When answering questions:
- Be specific and cite recipe/ingredient names when relevant
- If you mention a recipe, include its ID if available
- Use the provided context to answer accurately
- If information isn't in the context, say so
- Format lists clearly with bullet points or numbers
"""
        
        # Build user prompt with context
        context_str = json.dumps(context, indent=2)
        user_prompt = f"""Here is the current state of the recipe database:

{context_str}

Question: {question}

Please answer the question based on the database information provided above. Be specific and helpful."""
        
        # Query Ollama
        try:
            response = ollama.chat(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            )
            return response['message']['content']
        except Exception as e:
            # Fallback if Ollama isn't running or model isn't available
            return f"Error querying Ollama: {e}\n\nMake sure Ollama is installed and running. Install it from https://ollama.com\nThen pull a model: ollama pull {model}"
    
    finally:
        db.close()
