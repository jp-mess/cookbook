"""
Database models for the recipe storage system.
"""
from sqlalchemy import Column, Integer, String, Text, ForeignKey, Table, Boolean
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()


# Junction table for many-to-many: Recipe ↔ Tags
recipe_tags = Table(
    'recipe_tags',
    Base.metadata,
    Column('recipe_id', Integer, ForeignKey('recipes.id'), primary_key=True),
    Column('tag_id', Integer, ForeignKey('tags.id'), primary_key=True)
)

# Junction table for many-to-many: Ingredient ↔ Tags
ingredient_tags = Table(
    'ingredient_tags',
    Base.metadata,
    Column('ingredient_id', Integer, ForeignKey('ingredients.id'), primary_key=True),
    Column('tag_id', Integer, ForeignKey('tags.id'), primary_key=True)
)

# Junction table for many-to-many: Article ↔ Tags
article_tags = Table(
    'article_tags',
    Base.metadata,
    Column('article_id', Integer, ForeignKey('articles.id'), primary_key=True),
    Column('tag_id', Integer, ForeignKey('tags.id'), primary_key=True)
)


# Junction table for many-to-many: Recipe ↔ Ingredients
recipe_ingredients = Table(
    'recipe_ingredients',
    Base.metadata,
    Column('recipe_id', Integer, ForeignKey('recipes.id'), primary_key=True),
    Column('ingredient_id', Integer, ForeignKey('ingredients.id'), primary_key=True),
    Column('quantity', String(100)),  # e.g., "2 cups", "1 lb", "to taste"
    Column('notes', Text)  # Optional notes about this ingredient in this recipe
)


class Recipe(Base):
    """Recipe model - can have multiple tags (many-to-many)"""
    __tablename__ = 'recipes'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    instructions = Column(Text)
    notes = Column(Text)  # General notes about the recipe
    stale_embedding = Column(Boolean, default=True, nullable=False)  # True if embedding needs regeneration
    
    # Many-to-many relationship with Tags
    tags = relationship('Tag', secondary=recipe_tags, back_populates='recipes')
    
    # Many-to-many relationship with Ingredients
    ingredients = relationship(
        'Ingredient',
        secondary=recipe_ingredients,
        back_populates='recipes'
    )


class Tag(Base):
    """Tag model - can be applied to multiple recipes, ingredients, and articles (many-to-many)"""
    __tablename__ = 'tags'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)  # e.g., "italian", "french"
    
    # Many-to-many relationship with Recipes
    recipes = relationship('Recipe', secondary=recipe_tags, back_populates='tags')
    
    # Many-to-many relationship with Ingredients
    ingredients = relationship('Ingredient', secondary=ingredient_tags, back_populates='tags')
    
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
    """Ingredient model - has ONE type (many-to-one) and can have multiple tags (many-to-many)"""
    __tablename__ = 'ingredients'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False, unique=True)
    alias = Column(Text)  # Comma-separated aliases (e.g., "garbanzo bean, ceci")
    notes = Column(Text)  # General notes about the ingredient
    stale_embedding = Column(Boolean, default=True, nullable=False)  # True if embedding needs regeneration
    
    # Many-to-one relationship: many ingredients belong to one type
    type_id = Column(Integer, ForeignKey('ingredient_types.id'), nullable=False)
    type = relationship('IngredientType', back_populates='ingredients')
    
    # Many-to-many relationship with Tags
    tags = relationship('Tag', secondary=ingredient_tags, back_populates='ingredients')
    
    # Many-to-many relationship with Recipes
    recipes = relationship(
        'Recipe',
        secondary=recipe_ingredients,
        back_populates='ingredients'
    )


class Article(Base):
    """Article model - has notes and can have multiple tags (many-to-many)"""
    __tablename__ = 'articles'
    
    id = Column(Integer, primary_key=True)
    notes = Column(Text)  # Notes/content of the article
    stale_embedding = Column(Boolean, default=True, nullable=False)  # True if embedding needs regeneration
    
    # Many-to-many relationship with Tags
    tags = relationship('Tag', secondary=article_tags, back_populates='articles')
