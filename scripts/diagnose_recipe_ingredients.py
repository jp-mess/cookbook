#!/usr/bin/env python3
"""
Diagnostic script to identify recipes with likely incorrect ingredients.
Compares recipe names with their ingredients to find mismatches.
"""

import sys
import sqlite3
from pathlib import Path

# Add scripts directory to path
scripts_dir = Path(__file__).parent
sys.path.insert(0, str(scripts_dir))

from config_loader import get_database_path

def check_recipe_ingredients():
    """Check all recipes for suspicious ingredient mismatches."""
    db_path = get_database_path()
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # Get all recipes with their ingredients
    cursor.execute("""
        SELECT r.id, r.name, GROUP_CONCAT(i.name, ', ') as ingredients
        FROM recipes r
        LEFT JOIN recipe_ingredients ri ON r.id = ri.recipe_id
        LEFT JOIN ingredients i ON ri.ingredient_id = i.id
        GROUP BY r.id, r.name
        ORDER BY r.id
    """)
    
    recipes = cursor.fetchall()
    
    print("=" * 70)
    print("Recipe Ingredient Diagnostic")
    print("=" * 70)
    print()
    
    suspicious = []
    
    for recipe_id, recipe_name, ingredients_str in recipes:
        ingredients = [ing.strip() for ing in (ingredients_str or "").split(",") if ing.strip()]
        
        # Check for obvious mismatches based on recipe name
        issues = []
        
        recipe_lower = recipe_name.lower()
        
        # Check for key ingredients that should be present
        if "black bean" in recipe_lower or "blackbean" in recipe_lower:
            if not any("black bean" in ing.lower() for ing in ingredients):
                issues.append("Missing: black bean")
        
        if "pinto bean" in recipe_lower or "pintobean" in recipe_lower:
            if not any("pinto bean" in ing.lower() for ing in ingredients):
                issues.append("Missing: pinto bean")
        
        if "kale" in recipe_lower:
            if not any("kale" in ing.lower() for ing in ingredients):
                issues.append("Missing: kale")
        
        if "chickpea" in recipe_lower or "chick pea" in recipe_lower:
            if not any("chickpea" in ing.lower() or "chick pea" in ing.lower() for ing in ingredients):
                issues.append("Missing: chickpea")
        
        if "sweet potato" in recipe_lower:
            if not any("sweet potato" in ing.lower() for ing in ingredients):
                issues.append("Missing: sweet potato")
        
        if "avocado" in recipe_lower:
            if not any("avocado" in ing.lower() for ing in ingredients):
                issues.append("Missing: avocado")
        
        if "tomato" in recipe_lower and "pesto" in recipe_lower:
            if not any("tomato pesto" in ing.lower() for ing in ingredients):
                issues.append("Missing: tomato pesto")
        
        if "basil" in recipe_lower and "pesto" in recipe_lower:
            if not any("basil" in ing.lower() for ing in ingredients):
                issues.append("Missing: basil")
        
        if "celeriac" in recipe_lower:
            if not any("celeriac" in ing.lower() or "celery root" in ing.lower() for ing in ingredients):
                issues.append("Missing: celeriac/celery root")
        
        if "zucchini" in recipe_lower:
            if not any("zucchini" in ing.lower() for ing in ingredients):
                issues.append("Missing: zucchini")
        
        if "mushroom" in recipe_lower:
            if not any("mushroom" in ing.lower() for ing in ingredients):
                issues.append("Missing: mushroom")
        
        if "spinach" in recipe_lower:
            if not any("spinach" in ing.lower() for ing in ingredients):
                issues.append("Missing: spinach")
        
        # Check for recipes with 0 ingredients (might be incomplete)
        if len(ingredients) == 0:
            issues.append("No ingredients listed")
        
        if issues:
            suspicious.append((recipe_id, recipe_name, ingredients, issues))
    
    if suspicious:
        print(f"Found {len(suspicious)} recipe(s) with potential issues:\n")
        for recipe_id, recipe_name, ingredients, issues in suspicious:
            print(f"[{recipe_id}] {recipe_name}")
            print(f"  Current ingredients: {', '.join(ingredients) if ingredients else '(none)'}")
            print(f"  Issues:")
            for issue in issues:
                print(f"    - {issue}")
            print()
    else:
        print("No obvious issues found!")
    
    print("=" * 70)
    print(f"Total recipes checked: {len(recipes)}")
    print(f"Recipes with issues: {len(suspicious)}")
    print("=" * 70)
    
    conn.close()
    
    return suspicious

if __name__ == "__main__":
    suspicious = check_recipe_ingredients()
    if suspicious:
        print("\n⚠️  WARNING: Some recipes have incorrect ingredients!")
        print("   You may need to manually fix these recipes using the JSON editing workflow.")
        sys.exit(1)
    else:
        print("\n✓ All recipes look correct!")
        sys.exit(0)
