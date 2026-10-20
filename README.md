# Walking the Walk

### Written by Quan Thai

### Current release: Version 1

A first-person exploration and PvE survival game set in **CS Jungle**. Navigate winding rainforest paths, scavenge materials, craft equipment, survive dogs and giant spiders, and activate the northern end beacon. Skull signs warn of dangerous shortcuts; longer detours offer fewer encounters. An axe can open alternative routes through trees.

**Play** opens configuration: Easy, Medium or Hard, and Short, Normal or Long. Choose with the mouse or Up/Down and Left/Right, then select Start run. Generation happens behind a loading screen and verifies a connected route before play. Every run starts with full health/stamina, an empty inventory and fresh world state. The **Tutorial** remains a separate guided level. About retains the project's authored information.

## Run

Use Python with the dependencies in `requirements.txt` and an OpenGL 3.3 compatibility context:

```sh
python -m pip install -r requirements.txt
python src/main.py
```

In future, pre-build binaries targeting Windows and Linux will be made and deployed with each release.

The game starts fullscreen. Use `--windowed --width 1280 --height 800` for a window, and `--seed <seed>` for a reproducible world. The publisher intro can be skipped with a key or click. Esc quits from the title.

| Main-game control | Action |
| --- | --- |
| WASD / mouse | Walk / look |
| Shift | Sprint |
| F | Collect, read a sign, chop with a held axe, or activate the beacon |
| 1–9 / 0 | Select inventory slot / empty hand |
| Hold E | Use selected food, water or bandage; release between uses |
| C | Open/close crafting |
| Up/Down, Enter | Choose recipe, craft; clicking also works |
| Left click | Swing the held spear or axe, including in empty space |
| G | Drop the selected stack; recover it with F |
| H | Pause with controls and Resume/Menu/Exit options |
| Esc | Close a panel, pause, or return to title while paused |
| Enter while paused | Resume |
| R after death/completion | Configure another run |
| Ctrl+Q | Exit |

Nine inventory slots show quantities, item names and the selected item's type/action. Pick up cans and bottles to receive food/water **and their scrap immediately** in the main game. Food and water heal ten; bandages roll 20–35 healing once per completed use, capped at maximum health. Full-health use does not waste supplies. Dropped stacks remain recoverable and do not generate extra scrap.

| Recipe | Ingredients |
| --- | --- |
| Compass | 1 metal scrap + 1 plastic scrap |
| Stone spear | 2 sticks + 1 stone |
| Stone axe | 4 sticks + 5 stone |
| Bandage | 3 leaves |

Stone uses the existing `rock` inventory item. Decorative pebbles are smaller and cannot be collected. Three in-range axe chops remove a tree, update collision and drop three leaves. The guaranteed route is traversable without an axe. Recipes, weapon parameters and difficulty settings are defined in `run_recipes.py`, `run_config.py` and `items.py`.

Hold the compass's numbered slot to see its dial and red needle pointing towards the beacon. It shows the destination, leaving route choice to the player. Play has no tutorial objective arrows or lessons; its persistent H hint opens controls. Pause/crafting stops the encounter and run timer. Death and completion show distinct results, with new-run/menu/exit options. Returning to the title discards the run.

Tutorial retains its established sequence and balances: 80 starting health, food/water replaced by scrap after consumption, guided resource/equipment steps and the centred-then-yellow lesson panel. H opens its control reference. Mouse-look still uses SDL relative capture with stale motion flushed on focus changes. Blue sky, pass-through bushes and collision with trees/world bounds remain.

Run `bash tests/run_v1_checks.sh` for tutorial regressions, v1 tests, the configuration/seed matrix, survival simulations and OpenGL captures. Every execution has a ten-second timeout. Tests use SDL offscreen by default; desktop input feel and subjective difficulty remain playtest checks. See the [v1 change report](doc/IMPLEMENTATION-v1-2026_10_20.md) and [requirement audit](doc/SPEC-COMPLIANCE-v1-2026_10_20.md).

_Walking the Walk, Version 1, Written by Quan Thai, October 2026_
