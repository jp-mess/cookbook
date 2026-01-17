"""
Script to fix tag inconsistencies in the database.
"""
import sys
from pathlib import Path

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent))

from database import SessionLocal
from models import Tag, Recipe, Ingredient, Article


def merge_tags(db, source_tag_name: str, target_tag_name: str):
    """Merge source tag into target tag, then delete source tag."""
    source_tag = db.query(Tag).filter(Tag.name == source_tag_name).first()
    target_tag = db.query(Tag).filter(Tag.name == target_tag_name).first()
    
    if not source_tag:
        print(f"  Warning: Source tag '{source_tag_name}' not found")
        return
    
    if not target_tag:
        print(f"  Warning: Target tag '{target_tag_name}' not found, creating it")
        target_tag = Tag(name=target_tag_name)
        db.add(target_tag)
        db.flush()
    
    # Transfer recipes
    for recipe in list(source_tag.recipes):
        if target_tag not in recipe.tags:
            recipe.tags.append(target_tag)
        recipe.tags.remove(source_tag)
    
    # Transfer ingredients
    for ingredient in list(source_tag.ingredients):
        if target_tag not in ingredient.tags:
            ingredient.tags.append(target_tag)
        ingredient.tags.remove(source_tag)
    
    # Transfer articles
    for article in list(source_tag.articles):
        if target_tag not in article.tags:
            article.tags.append(target_tag)
        article.tags.remove(source_tag)
    
    # Delete source tag
    db.delete(source_tag)
    print(f"  ✓ Merged '{source_tag_name}' into '{target_tag_name}'")


def remove_tag(db, tag_name: str):
    """Remove tag from all relationships and delete it."""
    tag = db.query(Tag).filter(Tag.name == tag_name).first()
    
    if not tag:
        print(f"  Warning: Tag '{tag_name}' not found")
        return
    
    # Remove from recipes
    for recipe in list(tag.recipes):
        recipe.tags.remove(tag)
    
    # Remove from ingredients
    for ingredient in list(tag.ingredients):
        ingredient.tags.remove(tag)
    
    # Remove from articles
    for article in list(tag.articles):
        article.tags.remove(tag)
    
    # Delete tag
    db.delete(tag)
    print(f"  ✓ Removed tag '{tag_name}'")


def remove_article(db, article_id: int):
    """Remove an article."""
    article = db.query(Article).filter(Article.id == article_id).first()
    
    if not article:
        print(f"  Warning: Article #{article_id} not found")
        return
    
    db.delete(article)
    print(f"  ✓ Removed article #{article_id}")


def main():
    """Main cleanup function."""
    db = SessionLocal()
    try:
        print("=" * 70)
        print("Database Tag Cleanup")
        print("=" * 70)
        print()
        
        # 1. Remove "acid" tag from lemon (acid is lemon's type, not a tag)
        print("1. Removing 'acid' tag from lemon...")
        remove_tag(db, 'acid')
        
        # 2. Remove "arugula" tag from mixed greens
        print("\n2. Removing 'arugula' tag...")
        remove_tag(db, 'arugula')
        
        # 3. Remove "cooking" tag and article
        print("\n3. Removing 'cooking' tag and associated article...")
        cooking_tag = db.query(Tag).filter(Tag.name == 'cooking').first()
        if cooking_tag and cooking_tag.articles:
            for article in list(cooking_tag.articles):
                remove_article(db, article.id)
        remove_tag(db, 'cooking')
        
        # 4. Remove "melting" tag
        print("\n4. Removing 'melting' tag...")
        remove_tag(db, 'melting')
        
        # 5. Merge "middle east" into "middle eastern"
        print("\n5. Merging 'middle east' into 'middle eastern'...")
        merge_tags(db, 'middle east', 'middle eastern')
        
        # 6. Remove "mixed green" tag
        print("\n6. Removing 'mixed green' tag...")
        remove_tag(db, 'mixed green')
        
        # 7. Remove "mustard" tag
        print("\n7. Removing 'mustard' tag...")
        remove_tag(db, 'mustard')
        
        # 8. Merge "new american" into "american"
        print("\n8. Merging 'new american' into 'american'...")
        merge_tags(db, 'new american', 'american')
        
        # 9. Remove "radicchio" tag
        print("\n9. Removing 'radicchio' tag...")
        remove_tag(db, 'radicchio')
        
        # 10. Remove "soft" tag
        print("\n10. Removing 'soft' tag...")
        remove_tag(db, 'soft')
        
        # 11. Remove "tang" tag
        print("\n11. Removing 'tang' tag...")
        remove_tag(db, 'tang')
        
        # 12. Remove "techniques" tag and article
        print("\n12. Removing 'techniques' tag and associated article...")
        techniques_tag = db.query(Tag).filter(Tag.name == 'techniques').first()
        if techniques_tag and techniques_tag.articles:
            for article in list(techniques_tag.articles):
                remove_article(db, article.id)
        remove_tag(db, 'techniques')
        
        # 13. Merge "umami booster" into "umami"
        print("\n13. Merging 'umami booster' into 'umami'...")
        merge_tags(db, 'umami booster', 'umami')
        
        # 14. Remove "vegan" tag
        print("\n14. Removing 'vegan' tag...")
        remove_tag(db, 'vegan')
        
        # 15. Merge "mamie" into "umami" (misspelling)
        print("\n15. Merging 'mamie' (misspelling) into 'umami'...")
        merge_tags(db, 'mamie', 'umami')
        
        # Commit all changes
        print("\n" + "=" * 70)
        print("Committing changes to database...")
        db.commit()
        print("✓ All changes committed successfully!")
        print("=" * 70)
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == '__main__':
    main()
