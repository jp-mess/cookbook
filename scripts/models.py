"""
Database models for the recipe storage system.
"""
from sqlalchemy import Column, Integer, String, Text, ForeignKey, Table
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.ext.associationproxy import association_proxy

Base = declarative_base()


# Junction table for many-to-many: Recipe ↔ Tags
recipe_tags = Table(
    'recipe_tags',
    Base.metadata,
    Column('recipe_id', Integer, ForeignKey('recipes.id'), primary_key=True),
    Column('tag_id', Integer, ForeignKey('tags.id'), primary_key=True)
)

# Removed ingredient_tags table - ingredients no longer have tags

# Junction table for many-to-many: Article ↔ Tags
article_tags = Table(
    'article_tags',
    Base.metadata,
    Column('article_id', Integer, ForeignKey('articles.id'), primary_key=True),
    Column('tag_id', Integer, ForeignKey('tags.id'), primary_key=True)
)


# Association object for many-to-many: Recipe ↔ Ingredients (with quantity and notes)
class RecipeIngredient(Base):
    """Association object linking recipes to ingredients with quantity and notes."""
    __tablename__ = 'recipe_ingredients'
    
    recipe_id = Column(Integer, ForeignKey('recipes.id'), primary_key=True)
    ingredient_id = Column(Integer, ForeignKey('ingredients.id'), primary_key=True)
    quantity = Column(String(100))  # e.g., "2 cups", "1 lb", "to taste"
    notes = Column(Text)  # Optional notes about this ingredient in this recipe
    
    # Relationships
    recipe = relationship('Recipe', back_populates='ingredient_associations')
    ingredient = relationship('Ingredient', back_populates='recipe_associations')


class Recipe(Base):
    """Recipe model - can have multiple tags (many-to-many)"""
    __tablename__ = 'recipes'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    instructions = Column(Text)
    notes = Column(Text)  # General notes about the recipe
    
    # Many-to-many relationship with Tags
    tags = relationship('Tag', secondary=recipe_tags, back_populates='recipes')
    
    # Many-to-many relationship with Ingredients (via association object for quantity/notes)
    ingredient_associations = relationship('RecipeIngredient', back_populates='recipe', cascade='all, delete-orphan')
    
    # Transparent proxy to access ingredients directly (maintains backward compatibility)
    ingredients = association_proxy('ingredient_associations', 'ingredient',
                                     creator=lambda ing: RecipeIngredient(ingredient=ing))
    
    def get_ingredient_association(self, ingredient):
        """Get the association object for a specific ingredient."""
        for assoc in self.ingredient_associations:
            if assoc.ingredient_id == ingredient.id:
                return assoc
        return None
    
    def get_ingredient_quantity(self, ingredient):
        """Get quantity for a specific ingredient in this recipe."""
        assoc = self.get_ingredient_association(ingredient)
        return assoc.quantity if assoc else None
    
    def get_ingredient_notes(self, ingredient):
        """Get notes for a specific ingredient in this recipe."""
        assoc = self.get_ingredient_association(ingredient)
        return assoc.notes if assoc else None


class Subtag(Base):
    """Subtag model - formal subtag types (e.g., "region", "flavor", "food-type")"""
    __tablename__ = 'subtags'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)  # e.g., "region", "flavor", "food-type"
    
    # One-to-many relationship: one subtag can have many tags
    tags = relationship('Tag', back_populates='subtag')


class Tag(Base):
    """Tag model - can be applied to multiple recipes, ingredients, and articles (many-to-many)"""
    __tablename__ = 'tags'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)  # e.g., "italian", "french"
    subtag_id = Column(Integer, ForeignKey('subtags.id'), nullable=True)  # Optional subtag reference
    
    # Many-to-one relationship: many tags can belong to one subtag (nullable - can be subtagless)
    subtag = relationship('Subtag', back_populates='tags')
    
    # Many-to-many relationship with Recipes
    recipes = relationship('Recipe', secondary=recipe_tags, back_populates='tags')
    
    # Removed ingredients relationship - ingredients no longer have tags
    
    # Many-to-many relationship with Articles
    articles = relationship('Article', secondary=article_tags, back_populates='tags')


class IngredientType(Base):
    """Ingredient type model - one type can have many ingredients (one-to-many)"""
    __tablename__ = 'ingredient_types'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)  # e.g., "vinegar", "fruit", "vegetable"
    
    # One-to-many relationship: one type has many ingredients
    ingredients = relationship('Ingredient', back_populates='type')


class Ingredient(Base):
    """Ingredient model - has ONE type (many-to-one)"""
    __tablename__ = 'ingredients'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False, unique=True)
    notes = Column(Text)  # General notes about the ingredient
    
    # Many-to-one relationship: many ingredients belong to one type (nullable - can be typeless)
    type_id = Column(Integer, ForeignKey('ingredient_types.id'), nullable=True)
    type = relationship('IngredientType', back_populates='ingredients')
    
    # Many-to-many relationship with Recipes (via association object)
    recipe_associations = relationship('RecipeIngredient', back_populates='ingredient', cascade='all, delete-orphan')
    
    # Transparent proxy to access recipes directly (maintains backward compatibility)
    recipes = association_proxy('recipe_associations', 'recipe',
                                creator=lambda rec: RecipeIngredient(recipe=rec))


class Article(Base):
    """Article model - has notes and can have multiple tags (many-to-many)"""
    __tablename__ = 'articles'
    
    id = Column(Integer, primary_key=True)
    notes = Column(Text)  # Notes/content of the article
    
    # Many-to-many relationship with Tags
    tags = relationship('Tag', secondary=article_tags, back_populates='articles')
