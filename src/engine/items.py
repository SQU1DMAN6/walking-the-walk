"""Item and recipe definitions for Walking the Walk 1.1."""

# Item catalogue: item_id -> (display name, category, max stack size)
ITEMS = {
    "wood":        ("Wood",            "Resource", 20),
    "stone":       ("Stone",           "Resource", 20),
    "fibre":       ("Fibre",           "Resource", 30),
    "spinifex":    ("Spinifex",        "Resource", 30),
    "bark":        ("Eucalyptus Bark", "Resource", 20),
    "rope":        ("Rope",            "Resource", 10),
    "bush_tomato": ("Bush Tomato",     "Food",      5),
    "water":       ("Water",           "Water",     3),
    "stone_tool":  ("Stone Tool",      "Tool",      1),
    "spear":       ("Wooden Spear",    "Tool",      1),
    "bandage":     ("Bandage",         "Medical",   5),
}


# Crafting recipes: recipe_id -> definition
#   materials: {item_id: qty}   output: item_id   quantity: n
RECIPES = {
    "rope": {
        "name": "Rope",
        "materials": {"fibre": 2},
        "output": "rope",
        "quantity": 1,
    },
    "stone_tool": {
        "name": "Stone Tool",
        "materials": {"wood": 1, "stone": 1},
        "output": "stone_tool",
        "quantity": 1,
    },
    "spear": {
        "name": "Wooden Spear",
        "materials": {"wood": 2, "rope": 1},
        "output": "spear",
        "quantity": 1,
    },
    "bandage": {
        "name": "Bandage",
        "materials": {"fibre": 2, "bark": 1},
        "output": "bandage",
        "quantity": 1,
    },
}


RECIPE_ORDER = ["rope", "stone_tool", "spear", "bandage"]
