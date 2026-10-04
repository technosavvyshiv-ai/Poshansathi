# 🍛 Poshansathi

**Poshan** (nutrition) + **Sathi** (companion) — a Python nutrition companion
that helps a user understand and track their diet.

Poshansathi is a complete, **dependency-free** project: it uses only the Python
standard library, so it runs on any machine with Python 3.10+ and needs no
`pip install`.

---

## Features

- **Profiles** — height, weight, age, gender, activity level and goal.
- **Health metrics** — BMI + category, BMR (Mifflin-St Jeor), TDEE,
  a goal-based daily calorie target, macro targets and a healthy weight range.
- **Food database** — ~55 common Indian foods seeded from a CSV
  (`poshansathi/data/foods.csv`) with calories, protein, carbs, fat, fibre,
  iron, calcium and vitamin C.
- **Meal tracking** — log breakfast/lunch/dinner/snacks with serving counts.
- **Daily analysis** — calories vs target, macro bars, nutrient gaps against
  RDA values, and specific food suggestions to close each gap.
- **Weekly report** — per-day totals and averages.
- **Two front-ends** — a terminal menu (`cli.py`) and a browser UI
  (`webapp.py`) built on `http.server`.

## Project structure

```
Poshansathi/
├── main.py                 # launcher: choose CLI / web / seed
├── cli.py                  # terminal interface
├── webapp.py               # browser interface (stdlib http.server)
├── seed_demo.py            # load a demo profile with sample meals
├── requirements.txt        # (none — standard library only)
├── poshansathi/            # the Python package (core logic)
│   ├── __init__.py
│   ├── models.py           # dataclasses: Food, User, MealEntry, NutritionTotals
│   ├── nutrition.py        # BMI / BMR / TDEE / targets / RDA
│   ├── database.py         # SQLite schema + CSV seeding
│   ├── tracker.py          # users, foods, meal logging, totals
│   ├── suggestions.py      # nutrient-gap analysis + recommendations
│   ├── reports.py          # weekly summaries
│   └── data/foods.csv      # food nutrition dataset
└── tests/test_nutrition.py # unit tests
```

## Getting started

From the project folder:

```bash
# 1) (optional) load a demo profile with a week of meals
python main.py seed

# 2) run it — pick either front-end
python main.py            # interactive chooser
python main.py cli        # terminal menu
python main.py web        # then open http://localhost:8000
```

`webapp.py` accepts `--host` and `--port`:

```bash
python webapp.py --port 9000
```

## Running the tests

```bash
python -m unittest discover -s tests -t . -v
```

## How it works

**BMI** = weight (kg) / height (m)²
WHO categories: <18.5 underweight · 18.5–24.9 normal · 25–29.9 overweight · ≥30 obese.

**BMR** (Mifflin-St Jeor):

- male: `10·weight + 6.25·height − 5·age + 5`
- female: `10·weight + 6.25·height − 5·age − 161`

**TDEE** = BMR × activity factor (1.2 sedentary → 1.9 very active).

**Daily target** = TDEE + goal adjustment (−500 to lose, 0 to maintain,
+400 to gain), floored at 1200 kcal for safety.

**Macros** default to a 20% protein / 50% carbs / 30% fat split of the target.

**Suggestions** compare the day's intake against RDA values for fibre, iron,
calcium and vitamin C, then recommend the foods richest in whatever is low.

## Adding foods

Append rows to `poshansathi/data/foods.csv`, or insert through
`tracker.add_food()`. Columns:

```
name,category,serving_desc,serving_grams,calories,protein_g,carbs_g,fat_g,
fiber_g,iron_mg,calcium_mg,vitamin_c_mg,is_veg
```

The database is created automatically at `poshansathi/poshansathi.db` on first
run and seeded from the CSV (existing foods are not duplicated).

## Python concepts demonstrated

Object-oriented design (dataclasses), modules and packages, SQLite database
access, file I/O with CSV, string formatting, error handling, HTTP server and
HTML generation with the standard library, and unit testing with `unittest`.

---

*Built as a Python Programming course project.*
