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
try:
    from db_operations_semantic import semantic_search_recipes_by_query
    SEMANTIC_SEARCH_AVAILABLE = True
except ImportError:
    SEMANTIC_SEARCH_AVAILABLE = False
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
    
    # If question asks about recipes, use semantic search
    recipe_keywords = ['recipe', 'dish', 'food', 'with', 'containing', 'has', 'have', 'ingredient', 'beans', 'legumes', 
                      'vegetable', 'meat', 'herb', 'spice', 'dairy', 'sauce', 'mushroom', 'basil', 'tomato', 'wine', 'cheese', 'pasta']
    if any(keyword in question_lower for keyword in recipe_keywords):
        # Use semantic search to find relevant recipes
        if SEMANTIC_SEARCH_AVAILABLE:
            try:
                recipe_results = semantic_search_recipes_by_query(db, question, limit=15, min_similarity=0.5)
                # Filter recipes to only include those that actually match the query
                # For ingredient/type queries, check if the recipe actually has those ingredients
                filtered_recipes = []
                for recipe, score in recipe_results:
                    recipe_summary = format_recipe_summary(recipe)
                    # If query mentions specific ingredients/types, verify the recipe actually has them
                    if any(word in question_lower for word in ['bean', 'legume', 'vegetable', 'meat', 'herb', 'spice', 'dairy']):
                        # Check if recipe has ingredients matching the query
                        recipe_ingredients = [ing.name.lower() for ing in recipe.ingredients]
                        recipe_types = [ing.type.name.lower() for ing in recipe.ingredients if ing.type]
                        all_recipe_terms = recipe_ingredients + recipe_types
                        
                        # Extract key terms from question
                        query_terms = []
                        if 'bean' in question_lower or 'legume' in question_lower:
                            query_terms.extend(['bean', 'legume'])
                        if 'vegetable' in question_lower:
                            query_terms.append('vegetable')
                        if 'meat' in question_lower:
                            query_terms.append('meat')
                        if 'herb' in question_lower:
                            query_terms.append('herb')
                        if 'spice' in question_lower:
                            query_terms.append('spice')
                        if 'dairy' in question_lower:
                            query_terms.append('dairy')
                        
                        # Only include if recipe actually has matching terms
                        if query_terms and any(term in ' '.join(all_recipe_terms) for term in query_terms):
                            filtered_recipes.append(recipe_summary)
                        elif not query_terms:
                            # No specific terms to filter on, include all
                            filtered_recipes.append(recipe_summary)
                    else:
                        # No specific ingredient/type filtering needed
                        filtered_recipes.append(recipe_summary)
                
                context['recipes'] = filtered_recipes[:10]  # Limit to top 10
            except Exception as e:
                # Fallback to old method if semantic search fails
                try:
                    words = question_lower.split()
                    potential_ingredients = [w for w in words if len(w) > 3 and w not in ['what', 'which', 'how', 'when', 'where', 'with', 'that', 'have', 'contains', 'recipes', 'recipe', 'dish', 'food']]
                    if potential_ingredients:
                        recipe_results = suggest_recipes_by_ingredients(db, potential_ingredients, min_match_score=60)
                        context['recipes'] = [format_recipe_summary(recipe) for recipe, _, _ in recipe_results[:10]]
                except:
                    pass
        else:
            # Fallback to old method if semantic search not available
            try:
                words = question_lower.split()
                potential_ingredients = [w for w in words if len(w) > 3 and w not in ['what', 'which', 'how', 'when', 'where', 'with', 'that', 'have', 'contains', 'recipes', 'recipe', 'dish', 'food']]
                if potential_ingredients:
                    recipe_results = suggest_recipes_by_ingredients(db, potential_ingredients, min_match_score=60)
                    context['recipes'] = [format_recipe_summary(recipe) for recipe, _, _ in recipe_results[:10]]
            except:
                pass
    
    # If question mentions tags, search by tags
    if 'tag' in question_lower or any(tag.name in question_lower for tag in all_tags[:10]):
        # Include tag information
        context['tags'] = [tag.name for tag in all_tags]
    
    # If question asks about recipes in general but no results yet
    if ('recipe' in question_lower or 'dish' in question_lower or 'food' in question_lower) and not context['recipes']:
        # Include a sample of recipes as fallback
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

CRITICAL RULES:
- You MUST ONLY use information that is explicitly provided in the database context below
- DO NOT add, invent, or assume any ingredients, recipes, or information that is not in the provided context
- DO NOT use your general knowledge about recipes - only use what is in the database
- If a recipe's ingredients list is provided, ONLY list those exact ingredients - do not add others
- If information isn't in the context, explicitly say "This information is not in the database"
- Be specific and cite recipe/ingredient names when relevant
- If you mention a recipe, include its ID if available
- Format lists clearly with bullet points or numbers
"""
        
        # Build user prompt with context
        context_str = json.dumps(context, indent=2)
        user_prompt = f"""Here is the EXACT current state of the recipe database. Use ONLY this information - do not add anything from your general knowledge:

{context_str}

Question: {question}

CRITICAL INSTRUCTIONS:
1. Look at each recipe's ingredients list in the database above
2. ONLY list recipes that actually contain the requested ingredients/types in their ingredients list
3. Do NOT list recipes just because they appear in the context - they must actually have the requested ingredients
4. When listing a recipe, ONLY mention the ingredients that are shown in that recipe's ingredients list above
5. Do NOT add any ingredients that are not explicitly listed for that recipe
6. If a recipe does not have the requested ingredients, do NOT include it in your answer

For example, if asked for recipes with "beans", only list recipes whose ingredients list includes something with "bean" in the name."""
        
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
