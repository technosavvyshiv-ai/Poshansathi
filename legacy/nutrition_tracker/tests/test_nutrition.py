"""Unit tests for the nutrition and suggestion logic.

Run with::

    python -m unittest discover -s tests
"""

import unittest

from poshansathi import database, tracker
from poshansathi.models import Food, NutritionTotals
from poshansathi.nutrition import (
    bmi, bmi_category, bmr, tdee, target_calories, macro_targets,
    healthy_weight_range,
)
from poshansathi.suggestions import calorie_advice, nutrient_gaps


class TestNutritionMath(unittest.TestCase):
    def test_bmi(self):
        # 70 kg, 175 cm -> 22.86
        self.assertAlmostEqual(bmi(70, 175), 22.86, places=2)

    def test_bmi_category(self):
        self.assertEqual(bmi_category(17.0), "Underweight")
        self.assertEqual(bmi_category(22.0), "Normal weight")
        self.assertEqual(bmi_category(27.0), "Overweight")
        self.assertEqual(bmi_category(32.0), "Obese")

    def test_bmr_male_female_difference(self):
        male = bmr(70, 175, 25, "male")
        female = bmr(70, 175, 25, "female")
        # Female constant is 166 lower than male (5 vs -161).
        self.assertAlmostEqual(male - female, 166.0, places=5)

    def test_tdee_scales_with_activity(self):
        base = 1500.0
        self.assertAlmostEqual(tdee(base, "sedentary"), 1800.0, places=1)
        self.assertGreater(tdee(base, "active"), tdee(base, "light"))

    def test_target_calories_goal(self):
        lose = target_calories(70, 175, 25, "male", "moderate", "lose")
        maintain = target_calories(70, 175, 25, "male", "moderate", "maintain")
        gain = target_calories(70, 175, 25, "male", "moderate", "gain")
        self.assertAlmostEqual(maintain - lose, 500.0, places=1)
        self.assertAlmostEqual(gain - maintain, 400.0, places=1)

    def test_target_calories_floor(self):
        # A tiny person cutting hard should still not go below 1200 kcal.
        self.assertGreaterEqual(
            target_calories(40, 140, 60, "female", "sedentary", "lose"), 1200.0
        )

    def test_macro_targets_sum_to_calories(self):
        targets = macro_targets(2000)
        kcal = (targets["protein_g"] * 4 + targets["carbs_g"] * 4
                + targets["fat_g"] * 9)
        self.assertAlmostEqual(kcal, 2000, delta=2)

    def test_healthy_weight_range(self):
        lo, hi = healthy_weight_range(175)
        self.assertLess(lo, hi)
        self.assertAlmostEqual(bmi(lo, 175), 18.5, delta=0.1)
        self.assertAlmostEqual(bmi(hi, 175), 25.0, delta=0.1)


class TestTotalsAndSuggestions(unittest.TestCase):
    def test_scaled_food(self):
        food = Food(1, "Dal", "Dal", "1 cup", 200, 230, protein_g=12)
        twice = food.scaled(2)
        self.assertEqual(twice.calories, 460)
        self.assertEqual(twice.protein_g, 24)

    def test_totals_add(self):
        food = Food(1, "Roti", "Cereal", "1", 40, 100, protein_g=3,
                    fiber_g=2, iron_mg=1)
        totals = NutritionTotals()
        totals.add(food, 2)
        self.assertEqual(totals.calories, 200)
        self.assertEqual(totals.protein_g, 6)
        self.assertEqual(totals.fiber_g, 4)

    def test_nutrient_gaps_identifies_low(self):
        totals = NutritionTotals(fiber_g=5, iron_mg=2, calcium_mg=100,
                                 vitamin_c_mg=10)
        gaps = nutrient_gaps(totals)
        self.assertTrue(all(g["percent"] < 100 for g in gaps))
        self.assertTrue(all(g["critical"] for g in gaps))

    def test_calorie_advice(self):
        totals = NutritionTotals(calories=2000)
        advice = calorie_advice(totals, 2000)
        self.assertEqual(advice["status"], "on_track")

        over = calorie_advice(NutritionTotals(calories=2600), 2000)
        self.assertEqual(over["status"], "over")

        under = calorie_advice(NutritionTotals(calories=1000), 2000)
        self.assertEqual(under["status"], "under")


class TestDatabaseFlow(unittest.TestCase):
    def setUp(self):
        # In-memory database for each test.
        self.conn = database.init_db(db_path=":memory:")

    def test_seeded_foods(self):
        self.assertGreater(len(tracker.list_foods(self.conn)), 40)

    def test_user_and_meal_roundtrip(self):
        uid = tracker.create_user(self.conn, "Test", 20, "male",
                                  170, 65, "moderate", "maintain")
        food = tracker.search_foods(self.conn, "Roti")[0]
        tracker.log_meal(self.conn, uid, "2026-01-01", "lunch", food.id, 2)
        totals = tracker.daily_totals(self.conn, uid, "2026-01-01")
        self.assertAlmostEqual(totals.calories, food.calories * 2, places=1)

    def test_week_bounds(self):
        from datetime import date
        start, end = tracker.week_bounds(date(2026, 1, 1))  # a Thursday
        self.assertEqual(start, "2025-12-29")  # Monday
        self.assertEqual(end, "2026-01-04")    # Sunday


if __name__ == "__main__":
    unittest.main()