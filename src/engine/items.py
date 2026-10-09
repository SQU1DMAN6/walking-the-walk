ITEMS = {
    "food": ("Canned food", "Consumable", 1),
    "water": ("Bottled water", "Consumable", 1),
    "metal_scrap": ("Metal scrap", "Material", 20),
    "plastic_scrap": ("Plastic scrap", "Material", 20),
    "stick": ("Stick", "Material", 20),
    "rock": ("Rock", "Material", 20),
    "compass": ("Compass", "Tool", 1),
    "spear": ("Stone spear", "Weapon", 1),
}
RECIPES = {
    "compass": {"name": "Compass", "materials": {"metal_scrap": 1, "plastic_scrap": 1},
                "output": "compass", "quantity": 1},
    "spear": {"name": "Stone spear", "materials": {"stick": 2, "rock": 1},
              "output": "spear", "quantity": 1},
}
RECIPE_ORDER = ["compass", "spear"]
RESOURCE_LOOT = {
    "can": {"food": 1},
    "bottle": {"water": 1},
    "stick": {"stick": 1},
    "rock": {"rock": 1},
}
CONSUMED_CONTAINER = {"food": "metal_scrap", "water": "plastic_scrap"}
HEAL_AMOUNT = 10
PLAYER_SPEED = 3.6
DOG_SPEED = 3.3
SPEAR_RANGE = 3.5
SPEAR_DAMAGE = 25
SPEAR_COOLDOWN = 0.65
DOG_HEALTH = 100
DOG_DAMAGE = 20
DOG_RANGE = 2.7
DOG_DETECTION = 28.0
DOG_WINDUP = 0.45
DOG_COOLDOWN = 1.2

USE_DURATION = 1.0
