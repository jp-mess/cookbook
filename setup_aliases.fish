# Cookbook CLI Aliases for Fish Shell
# Source this file to set up convenient aliases for recipe commands
# Usage: source setup_aliases.fish

# Get the directory where this script is located
set SCRIPT_DIR (dirname (status --current-filename))
set COOKBOOK_CLI "$SCRIPT_DIR/cli.py"

# Check if Python virtual environment exists
if test -d "$SCRIPT_DIR/venv"
    set PYTHON_CMD "$SCRIPT_DIR/venv/bin/python"
else
    set PYTHON_CMD "python3"
end

# Recipe functions
function recipe-search
    $PYTHON_CMD $COOKBOOK_CLI recipe list $argv
end

function recipe-list
    $PYTHON_CMD $COOKBOOK_CLI recipe list $argv
end

function recipe-cook
    $PYTHON_CMD $COOKBOOK_CLI recipe cook $argv
end

function recipe-tag
    $PYTHON_CMD $COOKBOOK_CLI recipe tag $argv
end

function recipe-info
    $PYTHON_CMD $COOKBOOK_CLI recipe info $argv
end

function recipe-add
    $PYTHON_CMD $COOKBOOK_CLI recipe add $argv
end

function recipe-edit
    $PYTHON_CMD $COOKBOOK_CLI recipe edit --id $argv
end

# Ingredient functions
function ing-add
    $PYTHON_CMD $COOKBOOK_CLI ingredient add $argv
end

function ing-edit
    $PYTHON_CMD $COOKBOOK_CLI ingredient edit --id $argv
end

function ing-info
    $PYTHON_CMD $COOKBOOK_CLI ingredient info --id $argv
end

function ing-list
    $PYTHON_CMD $COOKBOOK_CLI ingredient list $argv
end

# Utility functions
function cleanup
    $PYTHON_CMD $COOKBOOK_CLI cleanup $argv
end

function backup
    $PYTHON_CMD $COOKBOOK_CLI backup $argv
end

function consistent
    $PYTHON_CMD $COOKBOOK_CLI consistent $argv
end

# Tag functions
function tag-add
    $PYTHON_CMD $COOKBOOK_CLI tag add $argv
end

function tag-edit
    $PYTHON_CMD $COOKBOOK_CLI tag edit --id $argv
end

function tag-list
    $PYTHON_CMD $COOKBOOK_CLI tag list $argv
end

# Type functions
function type-add
    $PYTHON_CMD $COOKBOOK_CLI type add $argv
end

function type-list
    $PYTHON_CMD $COOKBOOK_CLI type list $argv
end

function type-remove
    $PYTHON_CMD $COOKBOOK_CLI type remove --id $argv
end

# Subtag functions
function subtag-add
    $PYTHON_CMD $COOKBOOK_CLI subtag add $argv
end

function subtag-list
    $PYTHON_CMD $COOKBOOK_CLI subtag list $argv
end

function subtag-remove
    $PYTHON_CMD $COOKBOOK_CLI subtag remove --id $argv
end

# Remove/Delete aliases
function recipe-remove
    $PYTHON_CMD $COOKBOOK_CLI recipe delete --id $argv
end

function ing-remove
    $PYTHON_CMD $COOKBOOK_CLI ingredient delete --id $argv
end

function tag-remove
    $PYTHON_CMD $COOKBOOK_CLI tag remove --id $argv
end

echo "✓ Cookbook aliases loaded!"
echo ""
echo "Recipe aliases:"
echo "  recipe-search <search>   - Search recipes by name (shows top 3)"
echo "  recipe-list <subtag>     - List recipes grouped by tags with specified subtag (e.g., 'region', 'food-type')"
echo "  recipe-cook <ingredients> - Find recipes by ingredients"
echo "  recipe-tag <tag>         - List recipes with a tag"
echo "  recipe-info <id>         - Show recipe details by ID"
echo "  recipe-add               - Add a new recipe (JSON workflow)"
echo "  recipe-edit <id>          - Edit a recipe by ID (JSON workflow)"
echo ""
echo "Ingredient aliases:"
echo "  ing-add                  - Add a new ingredient (JSON workflow)"
echo "  ing-edit <id>            - Edit an ingredient by ID (JSON workflow)"
echo "  ing-info <id>            - Show ingredient details by ID"
echo "  ing-list                 - List all ingredients (organized by type)"
echo ""
echo "Tag aliases:"
echo "  tag-add <name> [--subtag] - Add a new tag"
echo "  tag-edit <id>            - Edit a tag by ID (JSON workflow)"
echo "  tag-list                 - List all tags (organized by subtag)"
echo ""
echo "Type aliases:"
echo "  type-add <name>          - Add a new ingredient type"
echo "  type-list                - List all ingredient types"
echo "  type-remove <id>         - Remove an ingredient type by ID"
echo ""
echo "Remove/Delete aliases:"
echo "  recipe-remove <id>       - Delete a recipe by ID"
echo "  ing-remove <id>          - Delete an ingredient by ID"
echo "  tag-remove <id>          - Remove a tag by ID"
echo "  type-remove <id>         - Remove an ingredient type by ID"
echo ""
echo "Utility aliases:"
echo "  cleanup                  - Delete all JSON staging files"
echo "  backup                   - Create a timestamped database backup"
echo "  consistent               - Check database consistency (ingredients, tags, types)"