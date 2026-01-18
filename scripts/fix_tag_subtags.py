"""
Script to fix tag subtags after migration.
Assigns the correct subtags to tags based on their names.
"""
import sys
from pathlib import Path

# Add scripts directory to path
scripts_dir = Path(__file__).parent
sys.path.insert(0, str(scripts_dir))

from database import SessionLocal
from db_operations import get_tag, get_subtag, update_tag

def fix_tag_subtags():
    """Fix all tag subtags."""
    db = SessionLocal()
    try:
        # Get subtags
        region_subtag = get_subtag(db, name='region')
        flavor_subtag = get_subtag(db, name='flavor')
        food_type_subtag = get_subtag(db, name='food-type')
        
        if not region_subtag or not flavor_subtag or not food_type_subtag:
            print("✗ Error: Required subtags not found. Run migration first.")
            sys.exit(1)
        
        # Define tag to subtag mappings
        tag_mappings = {
            # Region subtag
            'american': 'region',
            'british': 'region',
            'east asian': 'region',
            'eastern european': 'region',
            'french': 'region',
            'german': 'region',
            'indian': 'region',
            'italian': 'region',
            'mexican': 'region',
            'middle eastern': 'region',
            
            # Flavor subtag
            'aromatic': 'flavor',
            'astringent': 'flavor',
            'citrus': 'flavor',
            'fat': 'flavor',
            'fishy': 'flavor',
            'fresh': 'flavor',
            'umami': 'flavor',
            
            # Food-type subtag
            'curry': 'food-type',
            'panini': 'food-type',
            'pesto': 'food-type',
            'salad': 'food-type',
            'sandwich': 'food-type',
            'sauce': 'food-type',
            'side': 'food-type',
            'snack': 'food-type',
            'spread': 'food-type',
            'vinegar': 'food-type',
            'wonton': 'food-type',
            
            # No subtag (explicitly set to None)
            'protein': None,
            'anti-inflammatory': None,
        }
        
        updated_count = 0
        not_found = []
        
        print("Updating tag subtags...")
        print("=" * 70)
        
        for tag_name, subtag_name in tag_mappings.items():
            tag = get_tag(db, name=tag_name)
            if not tag:
                not_found.append(tag_name)
                continue
            
            # Check if subtag needs updating
            current_subtag_name = tag.subtag.name if tag.subtag else None
            if current_subtag_name == subtag_name:
                print(f"  ℹ {tag_name}: already has correct subtag ({subtag_name or 'none'})")
                continue
            
            # Update the tag
            try:
                update_tag(db, tag_id=tag.id, new_subtag_name=subtag_name)
                subtag_display = subtag_name if subtag_name else '(no subtag)'
                print(f"  ✓ {tag_name}: set subtag to {subtag_display}")
                updated_count += 1
            except Exception as e:
                print(f"  ✗ {tag_name}: error - {e}")
        
        if not_found:
            print(f"\n⚠ Tags not found: {', '.join(not_found)}")
        
        print("=" * 70)
        print(f"✓ Updated {updated_count} tag(s)")
        
    except Exception as e:
        print(f"\n✗ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    fix_tag_subtags()
