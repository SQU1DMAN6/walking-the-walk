# Walking the Walk

### Written by Quan Thai

### Current implementation: Version 1.5 — The Survival Mode Revamp

A first-person exploration and PvE survival game set in **CS Jungle**. Navigate winding rainforest paths, scavenge materials, craft equipment, survive dogs and giant spiders, and activate the northern end beacon. Skull signs warn of dangerous shortcuts; longer detours offer fewer encounters. An axe can open alternative routes through trees.

**Play** opens configuration: Easy, Medium or Hard, and Short, Normal or Long. Choose with the mouse or Up/Down and Left/Right, then select Start run. Seeded routes, ridges, valleys, broadleaf trees, rocky patches and undergrowth continue into streamed chunks as you explore. Chopped trees, collected supplies, dropped stacks and enemy state survive chunk reloads during the run. Every run starts with full health/stamina and an empty inventory. The **Tutorial** remains a separate guided level; About retains the project's authored information.

Short, Normal and Long place the northern beacon roughly 1.1, 1.7 and 2.3 km from spawn. Safer winding routes are longer. The initial goals are approximately 5–7, 8–10 and 10–14 minutes, with actual times depending on combat and route choices. Difficulty changes resources, populations, group sizes, pursuit memory and northern escalation independently of length.

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

Nine inventory slots show quantities, item names and the selected item's type/action. Cans and bottles enter the pack as consumables. **Scrap appears only after consumption**, once per container. Food and water heal ten and may be consumed at full health to obtain crafting scrap; the HUD reports the actual healing. Bandages roll 20–35 once per completed use and cannot be wasted at full health. Healing takes one second, damage interrupts it, and E must be released between uses. Dropping and recovering a container does not award scrap.

| Recipe | Ingredients |
| --- | --- |
| Compass | 1 metal scrap + 1 plastic scrap |
| Stone spear | 2 sticks + 1 stone |
| Stone axe | 4 sticks + 5 stone |
| Bandage | 3 leaves |

Stone uses the existing `rock` inventory item. Decorative pebbles are smaller and cannot be collected. Three in-range axe chops remove a tree, update collision and drop three leaves. The guaranteed route is traversable without an axe. Recipes, weapon parameters and difficulty settings are defined in `run_recipes.py`, `run_config.py` and `items.py`.

Dogs patrol, check vision and investigate walking, sprinting, fighting and chopping noises. They search a last known location after losing sight. Spiders can drop from trees with a visible warning, pursue, intercept and approach from different angles. Bodies block movement; attacks require valid range and clear space. Easy/Medium allow one nearby attack windup at a time; Hard allows two, spaced apart. Back away, use cover and pick your fights. Survival stamina recovers while walking and more quickly while resting.

Hold the compass's numbered slot to see its dial and red needle pointing towards the fixed beacon, including across unloaded chunks. It provides a bearing; route choices remain yours. Play has an objective line and contextual prompts, with no tutorial arrows or lessons. Pause/crafting stops encounters and the run timer. F starts a 0.8-second beacon link; leaving interaction range or taking damage interrupts it. Death and completion show distinct results, elapsed time, configuration and new-run/menu/exit options. Returning to the title discards the run.

Tutorial retains its established sequence and balances: 80 starting health, food/water replaced by scrap after consumption, guided resource/equipment steps and the centred-then-yellow lesson panel. H opens its control reference. Mouse-look still uses SDL relative capture with stale motion flushed on focus changes. Blue sky, pass-through bushes and collision with trees/world bounds remain.

Run `bash tests/run_v15_checks.sh` for the complete validation suite. Optional stages are `unit`, `world`, `balance`, `visual`, `performance` and `audit`. Compilation, unit suites, world checks, captures and launch smoke tests have ten-second deadlines. Accelerated full-run simulations allow 45 seconds per process; the sustained rendering test allows 60 seconds. The old v1 runner forwards to this suite.

Tests use SDL offscreen and real OpenGL, with results under `doc/validation/v1.5/`. The [v1.5 implementation and requirement review](doc/IMPLEMENTATION-v1_5-2026_10_26.md) records timings, screenshots, known limitations and manual checks still needed. Desktop mouse feel, peer difficulty assessment and hardware GPU performance require playtesting. This development environment uses Mesa's software OpenGL driver; its FPS is not a hardware GPU benchmark. The separate legacy Python rasteriser is not an application launch mode.

Streaming retains at most 36 chunks, two pending generation jobs and one generation worker, with no unloaded terrain cache. Rendering uploads at most one changed chunk per frame after initial loading. Exploration is bounded at ±8,192 metres; there is room well beyond the route without an immediate tree-line wall. Per-run edits are in memory, with limits of 4,096 chopped trees, 4,096 saved partial chops and 512 loose stacks. There is no save-to-disk feature. `doc/` and `tests/` remain ignored by the repository's existing Git rules.

_Walking the Walk, Version 1.5, Written by Quan Thai, October 2026_
