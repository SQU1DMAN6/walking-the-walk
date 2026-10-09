from engine.items import ITEMS, RECIPES, CONSUMED_CONTAINER


class Inventory:
    def __init__(self, capacity=9):
        if not 1 <= capacity <= 9:
            raise ValueError('Inventory needs 1 to 9 slots')
        self.capacity = capacity
        self.slots = [None] * capacity
        self.selected_slot = 9

    @property
    def selected_item(self):
        slot = self.slots[self.selected_slot] if self.selected_slot < self.capacity else None
        return slot[0] if slot else None

    def select_slot(self, number):
        if number == 0:
            self.selected_slot = 9
        elif 1 <= number <= self.capacity:
            self.selected_slot = number-1
        else:
            return False
        return True

    def number_for(self, item):
        return next((i+1 for i, slot in enumerate(self.slots) if slot and slot[0] == item), None)

    def count(self, item_id):
        return sum(slot[1] for slot in self.slots if slot and slot[0] == item_id)

    def has(self, item_id, qty=1):
        return self.count(item_id) >= qty

    @staticmethod
    def _insert(slots, item, qty):
        limit = ITEMS[item][2]
        for i, slot in enumerate(slots):
            if slot and slot[0] == item and slot[1] < limit:
                amount = min(qty, limit-slot[1])
                slots[i] = (item, slot[1]+amount)
                qty -= amount
        for i, slot in enumerate(slots):
            if slot is None and qty:
                amount = min(qty, limit)
                slots[i] = (item, amount)
                qty -= amount
        return qty == 0

    @staticmethod
    def _subtract(slots, item, qty):
        if sum(s[1] for s in slots if s and s[0] == item) < qty:
            return False
        for i, slot in enumerate(slots):
            if slot and slot[0] == item and qty:
                amount = min(qty, slot[1])
                slots[i] = (item, slot[1]-amount) if slot[1] > amount else None
                qty -= amount
        return True

    def add_many(self, items):
        if any(item not in ITEMS or type(qty) is not int or qty <= 0 for item, qty in items.items()):
            return False
        candidate = self.slots.copy()
        for item, qty in items.items():
            if not self._insert(candidate, item, qty):
                return False
        self.slots = candidate
        return True

    def add(self, item_id, qty=1):
        return 0 if self.add_many({item_id: qty}) else qty

    def remove(self, item_id, qty=1):
        return type(qty) is int and qty > 0 and self._subtract(self.slots, item_id, qty)

    def consume_selected(self):
        item = self.selected_item
        scrap = CONSUMED_CONTAINER.get(item)
        if scrap is None or self.slots[self.selected_slot][1] != 1:
            return None
        # Empty the container; its slot keeps the leftovers.
        self.slots[self.selected_slot] = (scrap, 1)
        return scrap

    def _crafted_slots(self, recipe_id):
        recipe = RECIPES.get(recipe_id)
        if recipe is None:
            return None
        # Try the whole swap first. No half-finished crafts.
        candidate = self.slots.copy()
        for item, qty in recipe['materials'].items():
            if not self._subtract(candidate, item, qty):
                return None
        if not self._insert(candidate, recipe['output'], recipe['quantity']):
            return None
        return candidate

    def can_craft(self, recipe_id):
        return self._crafted_slots(recipe_id) is not None

    def craft(self, recipe_id):
        candidate = self._crafted_slots(recipe_id)
        if candidate is None:
            return False
        self.slots = candidate
        return True

    def listed(self):
        return [(item, ITEMS[item][0], ITEMS[item][1], qty) for slot in self.slots if slot
                for item, qty in [slot]]
