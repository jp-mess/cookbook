#!/bin/bash
# Cookbook CLI Aliases
# Source this file to set up convenient aliases for recipe commands
# Usage: source setup_aliases.sh

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
COOKBOOK_CLI="$SCRIPT_DIR/cli.py"

# Check if Python virtual environment exists
if [ -d "$SCRIPT_DIR/venv" ]; then
    PYTHON_CMD="$SCRIPT_DIR/venv/bin/python"
else
    PYTHON_CMD="python3"
fi

# Recipe functions (functions work better with arguments than aliases)
recipe-search() {
    $PYTHON_CMD $COOKBOOK_CLI recipe list "$@"
}

recipe-list() {
    $PYTHON_CMD $COOKBOOK_CLI recipe list "$@"
}

recipe-cook() {
    $PYTHON_CMD $COOKBOOK_CLI recipe cook "$@"
}

recipe-tag() {
    $PYTHON_CMD $COOKBOOK_CLI recipe tag "$@"
}

recipe-info() {
    $PYTHON_CMD $COOKBOOK_CLI recipe info "$@"
}

recipe-add() {
    $PYTHON_CMD $COOKBOOK_CLI recipe add "$@"
}

recipe-edit() {
    $PYTHON_CMD $COOKBOOK_CLI recipe edit --id "$@"
}

# Ingredient functions
ing-add() {
    $PYTHON_CMD $COOKBOOK_CLI ingredient add "$@"
}

ing-edit() {
    $PYTHON_CMD $COOKBOOK_CLI ingredient edit --id "$@"
}

ing-info() {
    $PYTHON_CMD $COOKBOOK_CLI ingredient info --id "$@"
}

ing-list() {
    $PYTHON_CMD $COOKBOOK_CLI ingredient list "$@"
}

# Utility functions
cleanup() {
    $PYTHON_CMD $COOKBOOK_CLI cleanup "$@"
}

backup() {
    $PYTHON_CMD $COOKBOOK_CLI backup "$@"
}

consistent() {
    $PYTHON_CMD $COOKBOOK_CLI consistent "$@"
}

# Tag functions
tag-add() {
    $PYTHON_CMD $COOKBOOK_CLI tag add "$@"
}

tag-edit() {
    $PYTHON_CMD $COOKBOOK_CLI tag edit --id "$@"
}

tag-list() {
    $PYTHON_CMD $COOKBOOK_CLI tag list "$@"
}

# Type functions
type-add() {
    $PYTHON_CMD $COOKBOOK_CLI type add "$@"
}

type-list() {
    $PYTHON_CMD $COOKBOOK_CLI type list "$@"
}

type-remove() {
    $PYTHON_CMD $COOKBOOK_CLI type remove --id "$@"
}

# Subtag functions
subtag-add() {
    $PYTHON_CMD $COOKBOOK_CLI subtag add "$@"
}

subtag-list() {
    $PYTHON_CMD $COOKBOOK_CLI subtag list "$@"
}

subtag-remove() {
    $PYTHON_CMD $COOKBOOK_CLI subtag remove --id "$@"
}

# Remove/Delete aliases
recipe-remove() {
    $PYTHON_CMD $COOKBOOK_CLI recipe delete --id "$@"
}

ing-remove() {
    $PYTHON_CMD $COOKBOOK_CLI ingredient delete --id "$@"
}

tag-remove() {
    $PYTHON_CMD $COOKBOOK_CLI tag remove --id "$@"
}

echo "✓ Cookbook aliases loaded!"
echo ""
echo "Recipe aliases:"
echo "  recipe-search <search>   - Search recipes by name (shows top 3)"
echo "  recipe-list <subtag>     - List recipes grouped by tags with specified subtag (e.g., 'region', 'food-type')"
echo "  recipe-cook <ingredients> - Find recipes by ingredients"
echo "  recipe-tag <tag>          - List recipes with a tag"
echo "  recipe-info <id>          - Show recipe details by ID"
echo "  recipe-add                - Add a new recipe (JSON workflow)"
echo "  recipe-edit <id>          - Edit a recipe by ID (JSON workflow)"
echo ""
echo "Ingredient aliases:"
echo "  ing-add                   - Add a new ingredient (JSON workflow)"
echo "  ing-edit <id>             - Edit an ingredient by ID (JSON workflow)"
echo "  ing-info <id>             - Show ingredient details by ID"
echo "  ing-list                  - List all ingredients (organized by type)"
echo ""
echo "Tag aliases:"
echo "  tag-add <name> [--subtag] - Add a new tag"
echo "  tag-edit <id>             - Edit a tag by ID (JSON workflow)"
echo "  tag-list                  - List all tags (organized by subtag)"
echo ""
echo "Type aliases:"
echo "  type-add <name>           - Add a new ingredient type"
echo "  type-list                 - List all ingredient types"
echo "  type-remove <id>          - Remove an ingredient type by ID"
echo ""
echo "Subtag aliases:"
echo "  subtag-add <name>         - Add a new subtag"
echo "  subtag-list              - List all subtags"
echo "  subtag-remove <id>       - Remove a subtag by ID"
echo ""
echo "Remove/Delete aliases:"
echo "  recipe-remove <id>        - Delete a recipe by ID"
echo "  ing-remove <id>           - Delete an ingredient by ID"
echo "  tag-remove <id>           - Remove a tag by ID"
echo "  type-remove <id>          - Remove an ingredient type by ID"
echo ""
echo "Utility aliases:"
echo "  cleanup                   - Delete all JSON staging files"
echo "  backup                    - Create a timestamped database backup"
echo "  consistent                - Check database consistency (ingredients, tags, types)"
echo ""
echo "Examples:"
echo "  recipe-search pasta"
echo "  recipe-list region"
echo "  recipe-list food-type"
echo "  recipe-cook cucumber dill"
echo "  recipe-tag italian"
echo "  recipe-info 1"
echo "  recipe-add"
echo "  recipe-edit 5"
echo "  ing-add"
echo "  ing-edit 10"
echo "  ing-info 15"
echo "  ing-list"
echo "  tag-add umami --subtag flavor"
echo "  tag-edit 5"
echo "  tag-list"
echo "  type-add spice"
echo "  type-list"
echo "  type-remove 5"
echo "  recipe-remove 10"
echo "  ing-remove 15"
echo "  tag-remove 3"
echo "  cleanup"
echo "  backup"
echo "  consistent"