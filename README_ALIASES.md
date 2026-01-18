# Cookbook CLI Aliases

This directory contains shell scripts to set up convenient aliases for the cookbook CLI commands.

## Setup

### Bash/Zsh

Add to your `~/.bashrc` or `~/.zshrc`:

```bash
source /path/to/cookbook/setup_aliases.sh
```

Or run it manually:
```bash
source setup_aliases.sh
```

### Fish Shell

Add to your `~/.config/fish/config.fish`:

```fish
source /path/to/cookbook/setup_aliases.fish
```

Or run it manually:
```fish
source setup_aliases.fish
```

## Available Aliases

### Recipe Commands

- `recipe-list <search>` - Search recipes by name (fuzzy match, shows top 3)
  ```bash
  recipe-list pasta
  ```

- `recipe-cook <ingredients>` - Find recipes by ingredients (exact match)
  ```bash
  recipe-cook cucumber dill
  recipe-cook "cucumber, dill, mint"
  ```

- `recipe-tag <tag>` - List recipes with a specific tag
  ```bash
  recipe-tag italian
  ```

- `recipe-info <id>` - Show detailed recipe information by ID
  ```bash
  recipe-info 1
  ```

### Short Aliases

- `rlist` - alias for `recipe-list`
- `rcook` - alias for `recipe-cook`
- `rtag` - alias for `recipe-tag`
- `rinfo` - alias for `recipe-info`

## Examples

```bash
# Search for pasta recipes
recipe-list pasta

# Find recipes with cucumber and dill
recipe-cook cucumber dill

# List all Italian recipes
recipe-tag italian

# Get details for recipe #1
recipe-info 1

# Using short aliases
rlist tomato
rcook "basil, tomato"
rtag french
rinfo 5
```

## Notes

- The aliases automatically use the Python virtual environment if it exists
- All commands work from any directory once aliases are loaded
- The aliases pass through all arguments to the underlying CLI commands
