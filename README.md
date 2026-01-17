# Recipe Storage System

A Python-based system for storing and managing recipes and ingredients with tags and types.

## Setup

1. Create and activate a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On macOS/Linux
# or
venv\Scripts\activate  # On Windows
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Project Structure

```
cookbook/
├── cli.py                    # Main CLI interface
├── scripts/                  # Utility Python scripts
│   ├── api.py               # Flask REST API
│   ├── config_loader.py     # Configuration loader
│   ├── database.py          # Database setup and session management
│   ├── db_operations.py     # Database CRUD operations
│   ├── db_operations_semantic.py  # Semantic search operations
│   ├── embeddings.py        # Embedding generation
│   ├── json_editor.py       # JSON-based editing workflow
│   ├── models.py            # Database models
│   └── ollama_query.py      # Ollama natural language queries
├── config/                   # Configuration files
│   └── config.yaml          # Application configuration
├── data/                     # Data files
│   └── recipes.db           # SQLite database
├── help/                     # Help documentation
│   ├── help.txt
│   ├── help_recipe.txt
│   ├── help_ingredient.txt
│   ├── help_article.txt
│   └── help_embed.txt
├── addable/                  # JSON staging for new items
├── editable/                 # JSON staging for editing items
└── embeddings_cache/         # Cached embeddings
```

## CLI Usage

### Ingredients

```bash
# Add an ingredient
python cli.py ingredient add tomato vegetable

# List all ingredients
python cli.py ingredient list

# Delete an ingredient by name
python cli.py ingredient delete --name tomato

# Delete an ingredient by ID
python cli.py ingredient delete --id 1
```

### Recipes

```bash
# Add a recipe
python cli.py recipe add "Pasta with Tomato Sauce" \
  --description "Classic Italian dish" \
  --instructions "Cook pasta, make sauce, combine" \
  --tags "italian,eastern european" \
  --ingredients "tomato,onion"

# List all recipes
python cli.py recipe list

# Delete a recipe by name
python cli.py recipe delete --name "Pasta with Tomato Sauce"

# Delete a recipe by ID
python cli.py recipe delete --id 1
```

### Utilities

```bash
# List all ingredient types
python cli.py types

# List all tags
python cli.py tags
```

## API Usage

Start the Flask server:
```bash
python api.py
```

The API will be available at `http://localhost:5000`

### Endpoints

#### Ingredients
- `GET /api/ingredients` - List all ingredients
- `POST /api/ingredients` - Add an ingredient
  ```json
  {
    "name": "tomato",
    "type": "vegetable"
  }
  ```
- `GET /api/ingredients/<id>` - Get ingredient by ID
- `DELETE /api/ingredients/<id>` - Delete ingredient by ID
- `DELETE /api/ingredients/name/<name>` - Delete ingredient by name

#### Recipes
- `GET /api/recipes` - List all recipes
- `POST /api/recipes` - Add a recipe
  ```json
  {
    "name": "Pasta with Tomato Sauce",
    "description": "Classic Italian dish",
    "instructions": "Cook pasta, make sauce, combine",
    "tags": ["italian", "eastern european"],
    "ingredients": ["tomato", "onion"]
  }
  ```
- `GET /api/recipes/<id>` - Get recipe by ID
- `DELETE /api/recipes/<id>` - Delete recipe by ID
- `DELETE /api/recipes/name/<name>` - Delete recipe by name

#### Utilities
- `GET /api/types` - List all ingredient types
- `GET /api/tags` - List all tags
- `GET /api/health` - Health check

### Example API Calls

```bash
# Add an ingredient
curl -X POST http://localhost:5000/api/ingredients \
  -H "Content-Type: application/json" \
  -d '{"name": "tomato", "type": "vegetable"}'

# Add a recipe
curl -X POST http://localhost:5000/api/recipes \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Pasta with Tomato Sauce",
    "description": "Classic Italian dish",
    "tags": ["italian"],
    "ingredients": ["tomato", "onion"]
  }'

# List all recipes
curl http://localhost:5000/api/recipes

# Delete a recipe
curl -X DELETE http://localhost:5000/api/recipes/name/Pasta%20with%20Tomato%20Sauce
```
