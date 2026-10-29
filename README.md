# Walking the Walk

### Written by Quan Thai

### Current implementation: Version 1.7 — Organic Trees and Compass Practice

A first-person exploration and PvE survival game set in **CS Jungle**. Navigate winding rainforest paths, scavenge materials, craft equipment, survive dogs, giant spiders and venom runners, defeat the Demon Thing, and activate the northern end beacon. Skull signs warn of dangerous shortcuts; longer detours offer fewer encounters. An axe can open alternative routes through trees.

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

Nine inventory slots show quantities, item names and the selected item's name/action. Cans and bottles enter the pack as consumables. **Scrap appears only after consumption**, once per container. Food and water heal ten. Water also restores the configured stamina amount (currently 75) and cures poison. They may be consumed at full health to obtain crafting scrap; the HUD reports the actual healing. Bandages roll 20–35 once per completed use and cannot be wasted at full health. Healing takes one second and continues while taking nonfatal damage; E must be released between uses. Death, changing slots, opening a menu or releasing E still cancels an unfinished use. Dropping and recovering a container does not award scrap.

| Recipe | Ingredients |
| --- | --- |
| Compass | 1 metal scrap + 1 plastic scrap |
| Stone spear | 2 sticks + 1 stone |
| Stone axe | 4 sticks + 5 stone |
| Bandage | 2 leaves |

Stone uses the existing `rock` inventory item. Decorative pebbles are smaller and cannot be collected. Four in-range axe chops start a base-pivoted fall lasting up to 1.8 seconds. The moving trunk can hit you for exactly **99 health**, once per tree. In the main game it also deals 100 damage to mobs it actually strikes, once per tree/mob; ordinary enemies can be killed, while the Demon retains its activation gate and armour. Step away: leaves appear when it lands. The felled tree stays removed across chunk reloads. Nearby terrain and solid obstacles can stop the fall early. Chopping costs no stamina. The guaranteed route is traversable without an axe. Recipes, weapon parameters and difficulty settings are defined in `run_recipes.py`, `run_config.py` and `items.py`.

Dogs are faster than walking and slower than sprinting. They patrol, check vision and investigate walking, sprinting, fighting and chopping noises. They pursue the last known location after losing sight, then search a widening area before disengaging. Spiders can drop from trees with a visible warning, pursue, intercept and approach from different angles. Enemies advance during ordinary windups and recovery; hits check current reach, direction, height and cover once per attack. Bodies block movement. Easy/Medium allow one nearby attack windup at a time; Hard allows two, spaced apart. Back away, use cover and pick your fights. Survival stamina recovers while walking and more quickly while resting.

Venom runners appear on dangerous routes within 100 m of the beacon on Short and 500 m on Normal/Long, measured as remaining straight-line ground distance. Their opportunities are finite, spaced and subject to a cooldown and active-population limit. A valid bite poisons: two health every two seconds until water is consumed. Repeated bites retain one ticking effect. The purple HUD status stays visible; drinking can finish through both bites and poison ticks. Guaranteed water caches precede the final clearing.

The horned Demon Thing emerges before the beacon. Dodge its locked red slam circle, break the reach of its claw sweep, then attack during recovery for full damage. Attacks outside recovery meet its guard. At half health it becomes brighter and faster. Leaving the clearing preserves its health, and returning resumes the encounter. The beacon remains sealed until the Demon Thing is defeated.

Hold the compass's numbered slot to see its dial and red needle pointing towards the fixed beacon, including across unloaded chunks. It provides a bearing; route choices remain yours. Play has an objective line and contextual prompts, with no tutorial arrows or lessons. Pause/crafting stops encounters and the run timer. F starts a 0.8-second beacon link; leaving interaction range or taking damage interrupts it. Death and completion show distinct results, elapsed time, configuration and new-run/menu/exit options. Returning to the title discards the run.

The tutorial keeps the original v1.6 teaching sequence and extends its route for compass practice while using the **same chunk, terrain and tree generator as Play**. Both forests use one seeded tree builder: curved tapered trunks grow asymmetric boughs, forks and shoots with individual folded leaves attached along them. There is no solid canopy shell or clump geometry. Four merged meshes per tree keep batching bounded, with 216–288 leaf blades and fewer than 1,600 triangles per tree. Tutorial clearings protect its authored route and pickups; the main game's routes, tree placement, supplies and balance remain unchanged.

Movement, looking, supply use, compass crafting, material gathering, spear crafting and the dog encounter remain. After combat, collect five rocks and four sticks, now spread along alternating sides of the path, then craft an axe and **chop any reachable tree**. The practice step **sets health to 85 once**. Collect leaves, craft/use a bandage, then equip the compass and follow the extended trail to the beacon, 80 path metres (roughly 57 metres directly in seed 42) beyond the axe-material station. Starting health remains 80. Inventory, tree state and encounters stay isolated from Play. Pickup labels follow the actual item projection; the objective arrow, world marker and nearby interaction use the same target. Instructions name the action and relevant key, start centred, and settle lower in yellow with the original readable PSF text. Contextual arrows point to the required hotbar slot, recipe, Craft or Close button. Consumption shows a wide progress strip above the hotbar. A larger red HUD arrow includes an explicit turn instruction; a red arrow follows the terrain towards the same waypoint. Directional arrows hide during the final beacon lesson so the player practises compass navigation. H opens controls; R replays after completion.

Trees fall directly **away from the chopping position**, and keep that direction even when the player moves. Obstructions stop the fall instead of redirecting it. Damage uses the moving trunk’s actual radius and a new contact, with the stationary base excluded; standing close on the chopping side causes no proximity damage. Moving into a falling trunk can still cause one 99-HP hit. The axe’s resting blade now points straight forward relative to the camera.

Run `timeout --kill-after=1s 900s bash tests/run_shared_forest_checks.sh` for the current validation suite. Each compilation, dependency check, unit-test batch, seed check, tutorial simulation, screenshot process and launch smoke test has a ten-second deadline. Heavier suites are split into smaller batches. The launch smoke test intentionally stops with status 124 after verifying clean title frames; functional test processes must exit successfully. The v1.7 and tutorial-restore entry points forward to this suite. Historical validation scripts and reports describe their original builds.

Tests use SDL offscreen and real OpenGL, with current results under `doc/validation/organic-forest-2026_10_30/final/`. The [organic tree and tutorial review](doc/IMPLEMENTATION-organic-forest-2026_10_30.md) records architecture, requirement checks, commands and reviewed screenshots. Human usability and timings remain pending the arranged playtests. Automated traversal establishes availability and sequencing; desktop mouse feel, difficulty assessment and hardware GPU performance still need playtesting. This environment uses Mesa software OpenGL. The legacy Python rasteriser is not an application launch mode.

Streaming retains at most 36 chunks (including up to eight pinned encounter chunks), two pending generation jobs and one generation worker, with no unloaded terrain cache. Rendering uploads at most one changed chunk per frame after initial loading. Exploration is bounded at ±8,192 metres; there is room well beyond the route without an immediate tree-line wall. Per-run edits are in memory, with limits of 4,096 chopped trees, 4,096 saved partial chops and 512 loose stacks. There is no save-to-disk feature. `doc/` and `tests/` remain ignored by the repository's existing Git rules.

_Walking the Walk, Version 1.7, Written by Quan Thai, October 2026_


The v1.7 runner includes readability, damage-through-consumption, directional hit, exact PSF pixel and power-attack regressions. The original font renderer reference lives in `tests/fixtures/original_psf_ui.py`; no temporary old-game checkout is required. Normal spear and axe swings remain free. Power attacks retain the existing range, guard and hit checks; both mouse buttons share recovery so alternating them cannot bypass the power cooldown.

Effects use short, bounded mesh bursts and UI highlights. Successful pickup, crafting and consumption produce subtle feedback. Defeated ordinary enemies fall sideways and evaporate; the Demon Thing collapses into a three-second red vortex and sinks below the arena. Death has a brief downward view/fade, and a successfully linked beacon emits a turquoise pulse and beam before results. Gameplay outcomes are committed before these animations. Pause and crafting freeze world/effect timers; only visual transitions continue after a confirmed death or completion.
