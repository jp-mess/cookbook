"""
Flask API for managing recipes and ingredients.
"""
from flask import Flask, request, jsonify
from database import SessionLocal, init_db
from db_operations import (
    add_ingredient, list_ingredients, delete_ingredient, get_ingredient,
    add_recipe, list_recipes, delete_recipe, get_recipe,
    update_recipe, add_ingredients_to_recipe, remove_ingredients_from_recipe,
    add_tags_to_recipe, remove_tags_from_recipe,
    list_ingredient_types, list_tags, search_recipes,
    add_article, list_articles, get_article, update_article, delete_article,
    add_tags_to_article, remove_tags_from_article
)

app = Flask(__name__)

# Initialize database on startup
init_db()


def get_db_session():
    """Get a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ==================== INGREDIENT ENDPOINTS ====================

@app.route('/api/ingredients', methods=['GET'])
def get_ingredients():
    """Get all ingredients."""
    db = next(get_db_session())
    try:
        ingredients = list_ingredients(db)
        return jsonify([{
            'id': ing.id,
            'name': ing.name,
            'type': ing.type.name
        } for ing in ingredients])
    finally:
        db.close()


@app.route('/api/ingredients', methods=['POST'])
def create_ingredient():
    """Add a new ingredient."""
    data = request.get_json()
    if not data or 'name' not in data or 'type' not in data:
        return jsonify({'error': 'Missing required fields: name, type'}), 400
    
    db = next(get_db_session())
    try:
        ingredient = add_ingredient(db, data['name'], data['type'])
        return jsonify({
            'id': ingredient.id,
            'name': ingredient.name,
            'type': ingredient.type.name
        }), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    finally:
        db.close()


@app.route('/api/ingredients/<int:ingredient_id>', methods=['GET'])
def get_ingredient_by_id(ingredient_id):
    """Get an ingredient by ID."""
    db = next(get_db_session())
    try:
        ingredient = get_ingredient(db, ingredient_id=ingredient_id)
        if not ingredient:
            return jsonify({'error': 'Ingredient not found'}), 404
        return jsonify({
            'id': ingredient.id,
            'name': ingredient.name,
            'type': ingredient.type.name
        })
    finally:
        db.close()


@app.route('/api/ingredients/<int:ingredient_id>', methods=['DELETE'])
def delete_ingredient_by_id(ingredient_id):
    """Delete an ingredient by ID."""
    db = next(get_db_session())
    try:
        delete_ingredient(db, ingredient_id=ingredient_id)
        return jsonify({'message': 'Ingredient deleted successfully'}), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    finally:
        db.close()


@app.route('/api/ingredients/name/<name>', methods=['DELETE'])
def delete_ingredient_by_name(name):
    """Delete an ingredient by name."""
    db = next(get_db_session())
    try:
        delete_ingredient(db, name=name)
        return jsonify({'message': 'Ingredient deleted successfully'}), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    finally:
        db.close()


# ==================== RECIPE ENDPOINTS ====================

@app.route('/api/recipes', methods=['GET'])
def get_recipes():
    """Get all recipes."""
    db = next(get_db_session())
    try:
        recipes = list_recipes(db)
        return jsonify([{
            'id': recipe.id,
            'name': recipe.name,
            'instructions': recipe.instructions,
            'notes': recipe.notes,
            'tags': [tag.name for tag in recipe.tags],
            'ingredients': [ing.name for ing in recipe.ingredients]
        } for recipe in recipes])
    finally:
        db.close()


@app.route('/api/recipes', methods=['POST'])
def create_recipe():
    """Add a new recipe."""
    data = request.get_json()
    if not data or 'name' not in data:
        return jsonify({'error': 'Missing required field: name'}), 400
    
    db = next(get_db_session())
    try:
        recipe = add_recipe(
            db,
            name=data['name'],
            instructions=data.get('instructions'),
            tags=data.get('tags', []),
            ingredients=data.get('ingredients', [])
        )
        return jsonify({
            'id': recipe.id,
            'name': recipe.name,
            'instructions': recipe.instructions,
            'notes': recipe.notes,
            'tags': [tag.name for tag in recipe.tags],
            'ingredients': [ing.name for ing in recipe.ingredients]
        }), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    finally:
        db.close()


@app.route('/api/recipes/<int:recipe_id>', methods=['GET'])
def get_recipe_by_id(recipe_id):
    """Get a recipe by ID."""
    db = next(get_db_session())
    try:
        recipe = get_recipe(db, recipe_id=recipe_id)
        if not recipe:
            return jsonify({'error': 'Recipe not found'}), 404
        return jsonify({
            'id': recipe.id,
            'name': recipe.name,
            'instructions': recipe.instructions,
            'notes': recipe.notes,
            'tags': [tag.name for tag in recipe.tags],
            'ingredients': [ing.name for ing in recipe.ingredients]
        })
    finally:
        db.close()


@app.route('/api/recipes/<int:recipe_id>', methods=['DELETE'])
def delete_recipe_by_id(recipe_id):
    """Delete a recipe by ID."""
    db = next(get_db_session())
    try:
        delete_recipe(db, recipe_id=recipe_id)
        return jsonify({'message': 'Recipe deleted successfully'}), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    finally:
        db.close()


@app.route('/api/recipes/name/<name>', methods=['DELETE'])
def delete_recipe_by_name(name):
    """Delete a recipe by name."""
    db = next(get_db_session())
    try:
        delete_recipe(db, name=name)
        return jsonify({'message': 'Recipe deleted successfully'}), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    finally:
        db.close()


@app.route('/api/recipes/search', methods=['GET'])
def search_recipes_endpoint():
    """Search for recipes by approximate name matching."""
    query = request.args.get('q', '')
    limit = request.args.get('limit', 10, type=int)
    min_score = request.args.get('min_score', 50, type=int)
    
    if not query:
        return jsonify({'error': 'Missing required parameter: q (query)'}), 400
    
    db = next(get_db_session())
    try:
        results = search_recipes(db, query, limit=limit, min_score=min_score)
        return jsonify([{
            'id': recipe.id,
            'name': recipe.name,
            'instructions': recipe.instructions,
            'notes': recipe.notes,
            'tags': [tag.name for tag in recipe.tags],
            'ingredients': [ing.name for ing in recipe.ingredients],
            'score': float(score)
        } for recipe, score in results])
    finally:
        db.close()


@app.route('/api/recipes/<int:recipe_id>', methods=['PUT', 'PATCH'])
def update_recipe_by_id(recipe_id):
    """Update a recipe's basic fields."""
    data = request.get_json() or {}
    db = next(get_db_session())
    try:
        recipe = update_recipe(
            db,
            recipe_id=recipe_id,
            new_name=data.get('name'),
            instructions=data.get('instructions'),
            notes=data.get('notes')
        )
        return jsonify({
            'id': recipe.id,
            'name': recipe.name,
            'instructions': recipe.instructions,
            'notes': recipe.notes,
            'tags': [tag.name for tag in recipe.tags],
            'ingredients': [ing.name for ing in recipe.ingredients]
        }), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    finally:
        db.close()


@app.route('/api/recipes/<int:recipe_id>/ingredients', methods=['POST'])
def add_ingredients_to_recipe_by_id(recipe_id):
    """Add ingredients to a recipe."""
    data = request.get_json()
    if not data or 'ingredients' not in data:
        return jsonify({'error': 'Missing required field: ingredients'}), 400
    
    db = next(get_db_session())
    try:
        recipe = add_ingredients_to_recipe(
            db,
            recipe_id=recipe_id,
            ingredient_names=data['ingredients']
        )
        return jsonify({
            'id': recipe.id,
            'name': recipe.name,
            'ingredients': [ing.name for ing in recipe.ingredients]
        }), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    finally:
        db.close()


@app.route('/api/recipes/<int:recipe_id>/ingredients', methods=['DELETE'])
def remove_ingredients_from_recipe_by_id(recipe_id):
    """Remove ingredients from a recipe."""
    data = request.get_json()
    if not data or 'ingredients' not in data:
        return jsonify({'error': 'Missing required field: ingredients'}), 400
    
    db = next(get_db_session())
    try:
        recipe = remove_ingredients_from_recipe(
            db,
            recipe_id=recipe_id,
            ingredient_names=data['ingredients']
        )
        return jsonify({
            'id': recipe.id,
            'name': recipe.name,
            'ingredients': [ing.name for ing in recipe.ingredients]
        }), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    finally:
        db.close()


@app.route('/api/recipes/<int:recipe_id>/tags', methods=['POST'])
def add_tags_to_recipe_by_id(recipe_id):
    """Add tags to a recipe."""
    data = request.get_json()
    if not data or 'tags' not in data:
        return jsonify({'error': 'Missing required field: tags'}), 400
    
    db = next(get_db_session())
    try:
        recipe = add_tags_to_recipe(
            db,
            recipe_id=recipe_id,
            tag_names=data['tags']
        )
        return jsonify({
            'id': recipe.id,
            'name': recipe.name,
            'tags': [tag.name for tag in recipe.tags]
        }), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    finally:
        db.close()


@app.route('/api/recipes/<int:recipe_id>/tags', methods=['DELETE'])
def remove_tags_from_recipe_by_id(recipe_id):
    """Remove tags from a recipe."""
    data = request.get_json()
    if not data or 'tags' not in data:
        return jsonify({'error': 'Missing required field: tags'}), 400
    
    db = next(get_db_session())
    try:
        recipe = remove_tags_from_recipe(
            db,
            recipe_id=recipe_id,
            tag_names=data['tags']
        )
        return jsonify({
            'id': recipe.id,
            'name': recipe.name,
            'tags': [tag.name for tag in recipe.tags]
        }), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    finally:
        db.close()


# ==================== ARTICLE ENDPOINTS ====================

@app.route('/api/articles', methods=['GET'])
def get_articles():
    """Get all articles."""
    db = next(get_db_session())
    try:
        articles = list_articles(db)
        return jsonify([{
            'id': article.id,
            'notes': article.notes,
            'tags': [tag.name for tag in article.tags]
        } for article in articles])
    finally:
        db.close()


@app.route('/api/articles', methods=['POST'])
def create_article():
    """Add a new article."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Missing request body'}), 400

    db = next(get_db_session())
    try:
        article = add_article(
            db,
            notes=data.get('notes'),
            tags=data.get('tags', [])
        )
        return jsonify({
            'id': article.id,
            'notes': article.notes,
            'tags': [tag.name for tag in article.tags]
        }), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    finally:
        db.close()


@app.route('/api/articles/<int:article_id>', methods=['GET'])
def get_article_by_id(article_id):
    """Get an article by ID."""
    db = next(get_db_session())
    try:
        article = get_article(db, article_id=article_id)
        if not article:
            return jsonify({'error': 'Article not found'}), 404
        return jsonify({
            'id': article.id,
            'notes': article.notes,
            'tags': [tag.name for tag in article.tags]
        })
    finally:
        db.close()


@app.route('/api/articles/<int:article_id>', methods=['PUT', 'PATCH'])
def update_article_by_id(article_id):
    """Update an article by ID."""
    data = request.get_json() or {}
    db = next(get_db_session())
    try:
        article = update_article(
            db,
            article_id=article_id,
            notes=data.get('notes')
        )
        return jsonify({
            'id': article.id,
            'notes': article.notes,
            'tags': [tag.name for tag in article.tags]
        }), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    finally:
        db.close()


@app.route('/api/articles/<int:article_id>', methods=['DELETE'])
def delete_article_by_id(article_id):
    """Delete an article by ID."""
    db = next(get_db_session())
    try:
        delete_article(db, article_id=article_id)
        return jsonify({'message': 'Article deleted'}), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    finally:
        db.close()


@app.route('/api/articles/<int:article_id>/tags', methods=['POST'])
def add_tags_to_article_by_id(article_id):
    """Add tags to an article."""
    data = request.get_json()
    if not data or 'tags' not in data:
        return jsonify({'error': 'Missing tags in request body'}), 400

    db = next(get_db_session())
    try:
        article = add_tags_to_article(
            db,
            article_id=article_id,
            tag_names=data['tags']
        )
        return jsonify({
            'id': article.id,
            'notes': article.notes,
            'tags': [tag.name for tag in article.tags]
        }), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    finally:
        db.close()


@app.route('/api/articles/<int:article_id>/tags', methods=['DELETE'])
def remove_tags_from_article_by_id(article_id):
    """Remove tags from an article."""
    data = request.get_json()
    if not data or 'tags' not in data:
        return jsonify({'error': 'Missing tags in request body'}), 400

    db = next(get_db_session())
    try:
        article = remove_tags_from_article(
            db,
            article_id=article_id,
            tag_names=data['tags']
        )
        return jsonify({
            'id': article.id,
            'notes': article.notes,
            'tags': [tag.name for tag in article.tags]
        }), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    finally:
        db.close()


# ==================== UTILITY ENDPOINTS ====================

@app.route('/api/types', methods=['GET'])
def get_ingredient_types():
    """Get all ingredient types."""
    db = next(get_db_session())
    try:
        types = list_ingredient_types(db)
        return jsonify([{'id': t.id, 'name': t.name} for t in types])
    finally:
        db.close()


@app.route('/api/tags', methods=['GET'])
def get_tags():
    """Get all tags."""
    db = next(get_db_session())
    try:
        tags = list_tags(db)
        return jsonify([{'id': t.id, 'name': t.name} for t in tags])
    finally:
        db.close()


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({'status': 'healthy'}), 200


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
