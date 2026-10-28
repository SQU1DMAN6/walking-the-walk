# Walking the Walk

### Written by Quan Thai

### Current implementation: Version 1.6 — Situational Awareness and Survival

A first-person exploration and PvE survival game set in **CS Jungle**. Navigate winding rainforest paths, scavenge materials, craft equipment, survive dogs, giant spiders and venom runners, defeat the Warden, and activate the northern end beacon. Skull signs warn of dangerous shortcuts; longer detours offer fewer encounters. An axe can open alternative routes through trees.

**Play** opens configuration: Easy, Medium or Hard, and Short, Normal or Long. Choose with the mouse or Up/Down and Left/Right, then select Start run. Each normal run gets a fresh, logged random seed. Routes, ridges, valleys, broadleaf trees, rocky patches and undergrowth continue into streamed chunks as you explore. Chopped trees, collected supplies, dropped stacks and enemy state survive chunk reloads during the run. Every run starts with full health/stamina and an empty inventory. The **Tutorial** remains a separate guided level; About retains the project's authored information.

Short, Normal and Long have primary routes of **400, 800 and 1,500 metres**, independent of difficulty. Distance is the horizontal centre-line length from spawn to beacon, including the boss approach; it is not straight-line displacement. Surface distance is logged separately. Signed shortcuts cut travel but bring more encounters; detours, resource branches and occasional cross-links offer other choices. Physical rocky ridges separate many alternatives. Difficulty changes supplies, population, detection escalation, pursuit memory and coordination.


## Run

Use Python with the dependencies in `requirements.txt` and an OpenGL 3.3 compatibility context:

```sh
python -m pip install -r requirements.txt
python src/main.py
```

In future, pre-build binaries targeting Windows and Linux will be made and deployed with each release.

The game starts fullscreen. Use `--windowed --width 1280 --height 800` for a window, and the developer option `--seed <seed>` for a reproducible world (normal new runs choose fresh seeds). The publisher intro can be skipped with a key or click. Esc quits from the title.

| Main-game control | Action |
| --- | --- |
| WASD / mouse | Walk / look |
| Shift | Sprint |
| F | Collect, read a sign, chop with a held axe, or activate the beacon |
| 1–9 / 0 | Select inventory slot / empty hand |
| Hold E | Use selected food, water or bandage; release between uses |
| C | Open/close crafting |
| Up/Down, Enter | Choose recipe, craft; clicking also works |
| Left click | Normal spear/axe attack, no stamina cost (including a miss) |
| Right click | Power attack: 60 base damage, 30 stamina, 1.2-second shared cooldown |
| G | Drop the selected stack; recover it with F |
| H | Pause with controls and Resume/Menu/Exit options |
| Esc | Close a panel, pause, or return to title while paused |
| Enter while paused | Resume |
| R after death/completion | Configure another run |
| Ctrl+Q | Exit |

Bitmap text uses the original fixed-width PSF artwork and smooth scaling, with a uniformly scaled original 16×32 glyphs (small text uses 90% scale, about 18 visible capital-letter pixels), larger headings and responsive layouts. Red arcs around the crosshair show the direction of recent hits and rotate as the camera turns; poison is labelled without inventing an attacker direction.

Nine inventory slots show quantities, item names and the selected item's name/action. Cans and bottles enter the pack as consumables. **Scrap appears only after consumption**, once per container. Food and water heal ten. Water also restores the configured stamina amount (currently 60) and cures poison. They may be consumed at full health to obtain crafting scrap; the HUD reports the actual healing. Bandages roll 20–35 once per completed use and cannot be wasted at full health. Healing takes one second and continues while taking nonfatal damage; E must be released between uses. Death, changing slots, opening a menu or releasing E still cancels an unfinished use. Dropping and recovering a container does not award scrap.

| Recipe | Ingredients |
| --- | --- |
| Compass | 1 metal scrap + 1 plastic scrap |
| Stone spear | 2 sticks + 1 stone |
| Stone axe | 4 sticks + 5 stone |
| Bandage | 2 leaves |

Stone uses the existing `rock` inventory item. Decorative pebbles are smaller and cannot be collected. Four in-range axe chops remove a tree, update collision and drop four leaves. Chopping costs no stamina. The guaranteed route is traversable without an axe. Recipes, weapon parameters and difficulty settings are defined in `run_recipes.py`, `run_config.py` and `items.py`.

Dogs are faster than walking and slower than sprinting. They patrol, check vision and investigate walking, sprinting, fighting and chopping noises. They pursue the last known location after losing sight, then search a widening area before disengaging. Spiders can drop from trees with a visible warning, pursue, intercept and approach from different angles. Enemies advance during ordinary windups and recovery; hits check current reach, direction, height and cover once per attack. Bodies block movement. Easy/Medium allow one nearby attack windup at a time; Hard allows two, spaced apart. Back away, use cover and pick your fights. Survival stamina recovers while walking and more quickly while resting.

Venom runners appear on dangerous routes within 100 m of the beacon on Short and 500 m on Normal/Long, measured as remaining straight-line ground distance. Their opportunities are finite, spaced and subject to a cooldown and active-population limit. A valid bite poisons: two health every two seconds until water is consumed. Repeated bites retain one ticking effect. The purple HUD status stays visible; drinking can finish through both bites and poison ticks. Guaranteed water caches precede the final clearing.

The horned Demon Thing emerges before the beacon. Dodge its locked red slam circle, break the reach of its claw sweep, then attack during recovery for full damage. Attacks outside recovery meet its guard. At half health it becomes brighter and faster. Leaving the clearing preserves its health, and returning resumes the encounter. The beacon remains sealed until the Demon Thing is defeated.

Hold the compass's numbered slot to see its dial and red needle pointing towards the fixed beacon, including across unloaded chunks. It provides a bearing; route choices remain yours. Play has an objective line and contextual prompts, with no tutorial arrows or lessons. Pause/crafting stops encounters and the run timer. F starts a 0.8-second beacon link; leaving interaction range or taking damage interrupts it. Death and completion show distinct results, elapsed time, configuration and new-run/menu/exit options. Returning to the title discards the run.

Tutorial retains its established sequence and balances: 80 starting health, food/water replaced by scrap after consumption, guided resource/equipment steps and the centred-then-yellow lesson panel. H opens its control reference. Mouse-look still uses SDL relative capture with stale motion flushed on focus changes. Blue sky, pass-through bushes and collision with trees/world bounds remain.

Run `bash tests/run_v16_checks.sh` for the complete validation suite. Optional stages are `unit`, `world`, `balance`, `visual`, `performance` and `audit`. Compilation, unit suites, world checks, captures and launch smoke tests have ten-second deadlines. Accelerated full-run simulations allow 45 seconds per process; the sustained rendering test allows 60 seconds. The old v1/v1.5 entry points forward to this suite.

Tests use SDL offscreen and real OpenGL, with results under `doc/validation/v1.6/`. The [v1.6 implementation and requirement review](doc/IMPLEMENTATION-v1_6-2026_10_27.md) records timings, screenshots, known limitations and manual checks still needed. Desktop mouse feel, peer difficulty assessment and hardware GPU performance require playtesting. This development environment uses Mesa's software OpenGL driver; its FPS is not a hardware GPU benchmark. The separate legacy Python rasteriser is not an application launch mode.

Streaming retains at most 36 chunks (including up to eight pinned encounter chunks), two pending generation jobs and one generation worker, with no unloaded terrain cache. Rendering uploads at most one changed chunk per frame after initial loading. Exploration is bounded at ±8,192 metres; there is room well beyond the route without an immediate tree-line wall. Per-run edits are in memory, with limits of 4,096 chopped trees, 4,096 saved partial chops and 512 loose stacks. There is no save-to-disk feature. `doc/` and `tests/` remain ignored by the repository's existing Git rules.

_Walking the Walk, Version 1.6, Written by Quan Thai, October 2026_


The final readability/feedback checks run with `bash tests/run_readability_checks.sh`. Every test process, screenshot capture and launch smoke test has a ten-second timeout. This suite covers the existing regressions plus large bitmap text, full-name inventory layouts, consumption through damage and directional hit feedback. See the [28 October follow-up report](doc/IMPLEMENTATION-readability-2026_10_28.md) for results and reviewed screenshots. Earlier v1.6 reports describe their original snapshots; the follow-up supersedes their damage-interrupts-consumption policy.

The original PSF font restoration is verified against `tmp/walking-the-walk-old` at identical readable scales. Run `bash tests/run_psf_checks.sh` for all regressions, pixel comparisons and timed screenshots; see the [font restoration report](doc/IMPLEMENTATION-psf-restore-2026_10_28.md).

Normal spear and axe swings are free; power attacks retain each weapon’s range and existing hit/armour rules. Both modes share recovery, so alternating mouse buttons cannot bypass the power cooldown. Run `bash tests/run_power_checks.sh` for timed regression checks and screenshots. See the [UI and power-attack report](doc/IMPLEMENTATION-power-attacks-2026_10_28.md). The original font reference is retained in a test fixture, so tests no longer depend on the removed temporary game copy.
