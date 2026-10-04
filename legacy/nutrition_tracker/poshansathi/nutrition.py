"""Nutrition science helpers: BMI, BMR, TDEE and target macros.

All formulas are well-known public-domain equations, documented so the code
can double as study material.

References
----------
* BMI - World Health Organization.
* BMR - Mifflin-St Jeor equation (1990).
* TDEE - BMR x physical activity factor.
"""

from __future__ import annotations

# Physical activity multipliers applied to BMR to estimate daily energy needs.
ACTIVITY_FACTORS = {
    "sedentary": 1.2,      # little or no exercise, desk job
    "light": 1.375,        # light exercise 1-3 days / week
    "moderate": 1.55,      # moderate exercise 3-5 days / week
    "active": 1.725,       # hard exercise 6-7 days / week
    "very_active": 1.9,    # very hard exercise / physical job
}

# Daily calorie adjustment (kcal) applied on top of TDEE based on the goal.
GOAL_ADJUSTMENT = {
    "lose": -500.0,        # ~0.5 kg fat loss per week
    "maintain": 0.0,
    "gain": +400.0,        # leaner bulk
}

# Recommended daily allowance (approx. adult values) used by the suggestion
# engine to find nutrient gaps.  Values follow ICMR/NIN style guidelines.
RDA = {
    "fiber_g": 30.0,
    "iron_mg": 17.0,
    "calcium_mg": 1000.0,
    "vitamin_c_mg": 65.0,
}

# Fraction of daily calories that should come from each macro.
MACRO_SPLIT = {
    "protein": 0.20,
    "carbs": 0.50,
    "fat": 0.30,
}

# kcal per gram of each macronutrient.
KCAL_PER_GRAM = {"protein": 4.0, "carbs": 4.0, "fat": 9.0}


def bmi(weight_kg: float, height_cm: float) -> float:
    """Body Mass Index = weight(kg) / height(m)^2."""
    if height_cm <= 0:
        raise ValueError("height_cm must be positive")
    height_m = height_cm / 100.0
    return weight_kg / (height_m ** 2)


def bmi_category(value: float) -> str:
    """Return the WHO weight category for a BMI value."""
    if value < 18.5:
        return "Underweight"
    if value < 25.0:
        return "Normal weight"
    if value < 30.0:
        return "Overweight"
    return "Obese"


def bmr(weight_kg: float, height_cm: float, age: int, gender: str) -> float:
    """Basal Metabolic Rate via the Mifflin-St Jeor equation.

    Male:   10*weight + 6.25*height - 5*age + 5
    Female: 10*weight + 6.25*height - 5*age - 161
    """
    base = (10.0 * weight_kg) + (6.25 * height_cm) - (5.0 * age)
    if gender.lower().startswith("m"):
        return base + 5.0
    if gender.lower().startswith("f"):
        return base - 161.0
    # "other" - use the midpoint of the two constants.
    return base - 78.0


def tdee(bmr_value: float, activity_level: str) -> float:
    """Total Daily Energy Expenditure = BMR x activity factor."""
    factor = ACTIVITY_FACTORS.get(activity_level.lower(), 1.2)
    return bmr_value * factor


def target_calories(weight_kg: float, height_cm: float, age: int,
                    gender: str, activity_level: str, goal: str) -> float:
    """Daily calorie target for a user's goal."""
    maintenance = tdee(bmr(weight_kg, height_cm, age, gender), activity_level)
    adjustment = GOAL_ADJUSTMENT.get(goal.lower(), 0.0)
    # Never recommend dropping below a safe floor.
    return max(1200.0, maintenance + adjustment)


def macro_targets(calories: float) -> dict:
    """Return grams of protein/carbs/fat for a calorie target."""
    targets = {}
    for macro, fraction in MACRO_SPLIT.items():
        macro_cal = calories * fraction
        targets[macro + "_g"] = round(macro_cal / KCAL_PER_GRAM[macro], 1)
    return targets


def healthy_weight_range(height_cm: float,
                         low_bmi: float = 18.5,
                         high_bmi: float = 25.0) -> tuple:
    """Weight range (kg) that keeps BMI in the healthy band."""
    height_m = height_cm / 100.0
    return (round(low_bmi * height_m ** 2, 1), round(high_bmi * height_m ** 2, 1))


def profile_summary(user) -> dict:
    """Compute a full set of derived metrics for a :class:`User`."""
    value = bmi(user.weight_kg, user.height_cm)
    bmr_value = bmr(user.weight_kg, user.height_cm, user.age, user.gender)
    tdee_value = tdee(bmr_value, user.activity_level)
    calories = target_calories(
        user.weight_kg, user.height_cm, user.age,
        user.gender, user.activity_level, user.goal,
    )
    return {
        "bmi": round(value, 1),
        "bmi_category": bmi_category(value),
        "bmr": round(bmr_value, 0),
        "tdee": round(tdee_value, 0),
        "target_calories": round(calories, 0),
        "macros": macro_targets(calories),
        "healthy_weight_range": healthy_weight_range(user.height_cm),
    }