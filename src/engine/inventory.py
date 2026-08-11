"""Slot-based inventory with stacking for Walking the Walk."""

from engine.items import ITEMS


DEFAULT_CAPACITY = 12


class Inventory:
    """A simple slot-based inventory.

    slots is a list of [item_id, quantity] pairs. Items of the same id stack
    up to their max stack size. Adding beyond capacity returns the leftover
    quantity that could not fit.
    """

    def __init__(self, capacity=DEFAULT_CAPACITY):
        self.capacity = capacity
        self.slots = []  # list of [item_id, qty]

    def count(self, item_id):
        """Total quantity of item_id currently held."""
        return sum(q for iid, q in self.slots if iid == item_id)

    def has(self, item_id, qty=1):
        return self.count(item_id) >= qty

    def _find_open_slot(self, item_id):
        max_stack = ITEMS[item_id][2]
        for s in self.slots:
            if s[0] == item_id and s[1] < max_stack:
                return s
        return None

    def add(self, item_id, qty=1):
        """Add qty of item_id, stacking where possible. Returns leftover."""
        max_stack = ITEMS[item_id][2]
        remaining = qty
        while remaining > 0:
            slot = self._find_open_slot(item_id)
            if slot is not None:
                space = max_stack - slot[1]
                take = min(space, remaining)
                slot[1] += take
                remaining -= take
            else:
                if len(self.slots) >= self.capacity:
                    return remaining
                self.slots.append([item_id, 0])
        return 0

    def remove(self, item_id, qty=1):
        """Remove up to qty of item_id. Returns True if fully removed."""
        if self.count(item_id) < qty:
            return False
        for s in list(self.slots):
            if s[0] == item_id:
                if s[1] > qty:
                    s[1] -= qty
                    return True
                qty -= s[1]
                self.slots.remove(s)
                if qty <= 0:
                    return True
        return True

    def listed(self):
        """Return slots as [(item_id, name, category, qty)] for UI display."""
        out = []
        for item_id, qty in self.slots:
            name, category, _ = ITEMS[item_id]
            out.append((item_id, name, category, qty))
        return out


# --- Item usage effects (used by main.py) ---
USABLE_EFFECTS = {
    "bush_tomato": {"kind": "heal", "amount": 20, "msg": "Sustenance (+20 health)."},
    "water":       {"kind": "stamina", "amount": 40, "msg": "Refreshing drink (+40 stamina)."},
    "bandage":     {"kind": "heal", "amount": 40, "msg": "Wound dressed (+40 health)."},
}
