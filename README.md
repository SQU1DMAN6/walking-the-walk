# Walking the Walk

### Written by Quan Thai

### Current release: Version 0.5

A first-person survival and navigation tutorial set in **CS Jungle**. Follow winding forest paths, scavenge a can and bottle, recover your health, turn their scrap into a compass, gather a spear's materials, survive a hostile dog, and find the end beacon. At least... that's the tutorial level.

The world is one deterministic, bounded jungle chunk. Procedural trees surround a carved-out route; generation verifies clearance after placing vegetation. The existing OpenGL engine renders terrain, forest, recognisable resource models, world-attached objective arrows, and the beacon's turquoise ring.

## Run

Use Python with the dependencies in `requirements.txt` and an OpenGL 3.3 compatibility context:

```sh
python -m pip install -r requirements.txt
python src/main.py
```

In future, pre-build binaries targeting Windows and Linux will be made and deployed with each release.

The game starts fullscreen at the desktop resolution. Want a window? Run `wtw-venv/bin/python src/main.py --windowed`; `--width` and `--height` flags set its initial size (1280×800 by default). Choose another reproducible world with `--seed <seed>`.

The publisher intro has a visible skip hint: press any key or click to continue to the title. The title has **Play**, **Tutorial**, and **About This Game**. Play opens a temporary panel saying the main gameplay loop is still in progress. Tutorial loads CS Jungle with a spinner while the forest is generated. About contains the game information in `src/engine/menu.py`. Click a button or use Up/Down and Enter. Esc goes back from these panels and quits from the title.

| Control | Action |
| --- | --- |
| WASD / mouse | Walk / look |
| Shift | Sprint |
| F | Collect the relevant resource or activate the beacon |
| 1–9 | Select one of nine inventory slots |
| 0 | Empty hand |
| Hold E | Use the selected food or water for one second; release between items |
| C | Open/close crafting; choose a recipe and check its materials |
| Up / Down, Enter | Select a recipe, then craft (clicking also works) |
| Left click | Thrust while holding the spear |
| Esc | Close crafting, or pause and release the pointer; press again while paused to return to title |
| H | Open/close the control reference; Esc also closes it |
| Resume button / Enter while paused | Resume |
| R after death or completion | Restart |
| Ctrl+Q | Quit |

The tutorial starts at 80/100 health. Each consumable heals 10 up to 100. Collection gives just the can or bottle, each in its own slot. Holding E to finish it replaces that same slot with metal or plastic scrap; scrap appears only after consumption. A compass costs **1 metal scrap + 1 plastic scrap**; a spear costs **2 sticks + 1 rock**. Crafting shows material counts and pauses the encounter while you choose. Pick a tool's number slot to hold it. Later interactions and the dog encounter are gated by tutorial progression. The beacon requires F, not just proximity.

Nearby targets show one floating action prompt. The prompt checks the real interaction range, equipped spear, aim and attack cooldown. Selecting a slot confirms its item and shows its name, count and available action above the inventory bar. Full inventory, unavailable use, cooldown and low stamina have short explanations. Extra consumables stay in your pack when health is full; the two required tutorial containers can still be opened for scrap to keep progression possible.

Each new lesson appears at screen centre with a slow red pulse for 1.5 seconds, then slides down over 0.45 seconds into a slightly smaller yellow reminder above the inventory. Inside the beacon ring, the F finish instruction sits at screen centre and remains visible in every look direction. Press H whenever you need the reference. Pause, game-over and completion screens have working Resume/Restart, Title and Quit buttons. Health changes briefly highlight the health panel, and notifications expire automatically.

A direction arrow names the next required resource, follows the connected paths back from branches, and flags the hostile dog. Contextual arrows highlight the actual equipment slot and the next crafting action, including a clickable Close button. Inside the beacon ring, the F finish instruction stays visible even when looking away. Beacon direction guidance requires holding the compass.

Hold the compass slot to see its dial and red needle pointing toward the beacon relative to your view. Keep to the winding path. Bushes are scenery you can walk through; trees and the world boundary still stop you. Tutorial instructions sit near screen centre, under a blue sky.

The spear eases through preparation, thrust and recovery; each click can land another hit after 0.38 seconds. The dog crouches, opens its jaw, lunges and recovers, with animated legs while chasing. Its 0.45-second bite warning gives time to back away, followed by a 0.65-second cooldown. The spear still reaches farther and the player still moves faster than the dog.

Mouse-look uses SDL relative motion, with stale input flushed when capture changes. Opening crafting, pausing, or losing focus releases the pointer; returning to play briefly discards capture-transition motion.

That's all for now.

_Walking the Walk, Version 0.5, Written by Quan Thai, October 2026_
