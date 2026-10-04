"""Plain data objects used across Poshansathi.

These are lightweight ``dataclasses`` that mirror the database rows.  Keeping
them separate makes the rest of the code easier to read and test.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class Food:
    """A single food item and its nutrition per serving."""

    id: int
    name: str
    category: str
    serving_desc: str
    serving_grams: float
    calories: float
    protein_g: float = 0.0
    carbs_g: float = 0.0
    fat_g: float = 0.0
    fiber_g: float = 0.0
    iron_mg: float = 0.0
    calcium_mg: float = 0.0
    vitamin_c_mg: float = 0.0
    is_veg: bool = True

    def scaled(self, quantity: float) -> "Food":
        """Return a copy with all nutrition values multiplied by ``quantity``."""
        factor = float(quantity)
        return Food(
            id=self.id,
            name=self.name,
            category=self.category,
            serving_desc=f"{quantity:g} x {self.serving_desc}",
            serving_grams=self.serving_grams * factor,
            calories=self.calories * factor,
            protein_g=self.protein_g * factor,
            carbs_g=self.carbs_g * factor,
            fat_g=self.fat_g * factor,
            fiber_g=self.fiber_g * factor,
            iron_mg=self.iron_mg * factor,
            calcium_mg=self.calcium_mg * factor,
            vitamin_c_mg=self.vitamin_c_mg * factor,
            is_veg=self.is_veg,
        )


@dataclass
class User:
    """A user profile used to compute energy and nutrient targets."""

    id: int
    name: str
    age: int
    gender: str          # "male" | "female" | "other"
    height_cm: float
    weight_kg: float
    activity_level: str  # sedentary | light | moderate | active | very_active
    goal: str            # lose | maintain | gain
    created_at: str = ""

    @staticmethod
    def from_row(row) -> "User":
        return User(
            id=row["id"],
            name=row["name"],
            age=row["age"],
            gender=row["gender"],
            height_cm=row["height_cm"],
            weight_kg=row["weight_kg"],
            activity_level=row["activity_level"],
            goal=row["goal"],
            created_at=row["created_at"],
        )


@dataclass
class MealEntry:
    """One logged food for a user on a given date and meal."""

    id: int
    user_id: int
    entry_date: date
    meal_type: str       # breakfast | lunch | dinner | snack
    food_id: int
    quantity: float
    food_name: str = field(default="", compare=False)


@dataclass
class NutritionTotals:
    """Aggregated nutrition for a set of meals."""

    calories: float = 0.0
    protein_g: float = 0.0
    carbs_g: float = 0.0
    fat_g: float = 0.0
    fiber_g: float = 0.0
    iron_mg: float = 0.0
    calcium_mg: float = 0.0
    vitamin_c_mg: float = 0.0

    def add(self, food: Food, quantity: float = 1.0) -> None:
        self.calories += food.calories * quantity
        self.protein_g += food.protein_g * quantity
        self.carbs_g += food.carbs_g * quantity
        self.fat_g += food.fat_g * quantity
        self.fiber_g += food.fiber_g * quantity
        self.iron_mg += food.iron_mg * quantity
        self.calcium_mg += food.calcium_mg * quantity
        self.vitamin_c_mg += food.vitamin_c_mg * quantity

    def as_dict(self) -> dict:
        return {
            "calories": round(self.calories, 1),
            "protein_g": round(self.protein_g, 1),
            "carbs_g": round(self.carbs_g, 1),
            "fat_g": round(self.fat_g, 1),
            "fiber_g": round(self.fiber_g, 1),
            "iron_mg": round(self.iron_mg, 1),
            "calcium_mg": round(self.calcium_mg, 1),
            "vitamin_c_mg": round(self.vitamin_c_mg, 1),
        }