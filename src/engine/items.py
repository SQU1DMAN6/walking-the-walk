from engine.run_recipes import EXTRA_RECIPES

ITEMS = {
    "food": ("Canned food", "Consumable", 5),
    "water": ("Bottled water", "Consumable", 3),
    "metal_scrap": ("Metal scrap", "Material", 20),
    "plastic_scrap": ("Plastic scrap", "Material", 20),
    "stick": ("Stick", "Material", 20),
    "rock": ("Rock", "Material", 20),
    "compass": ("Compass", "Tool", 1),
    "spear": ("Stone spear", "Weapon", 1),
    "axe": ("Stone axe", "Weapon", 1),
    "leaves": ("Leaves", "Material", 20),
    "bandage": ("Bandage", "Consumable", 15),
}
RECIPES = {
    "compass": {
        "name": "Compass",
        "materials": {"metal_scrap": 1, "plastic_scrap": 1},
        "output": "compass",
        "quantity": 1,
    },
    "spear": {
        "name": "Stone spear",
        "materials": {"stick": 2, "rock": 1},
        "output": "spear",
        "quantity": 1,
    },
}
RECIPES.update(EXTRA_RECIPES)
RECIPE_ORDER = ["compass", "spear"]
RUN_RECIPE_ORDER = ["compass", "spear", "axe", "bandage"]
RESOURCE_LOOT = {
    "can": {"food": 1},
    "bottle": {"water": 1},
    "stick": {"stick": 1},
    "rock": {"rock": 1},
}
CONSUMED_CONTAINER = {"food": "metal_scrap", "water": "plastic_scrap"}
HEAL_AMOUNT = 10
PLAYER_SPEED = 3.6
DOG_SPEED = 4.6
SPEAR_RANGE = 4.5
SPEAR_DAMAGE = 25
SPEAR_COOLDOWN = 0.38
SPEAR_ANIMATION = 0.4
DOG_HEALTH = 100
DOG_DAMAGE = 20
DOG_RANGE = 2.7
DOG_DETECTION = 28.0
DOG_WINDUP = 0.45
DOG_COOLDOWN = 0.65
DOG_RECOVERY = 0.34

USE_DURATION = 1.0
