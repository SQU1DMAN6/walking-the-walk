# Walking the Walk

### Written by Quan Thai

### Current release: Version 0

A first-person survival and navigation tutorial set in **CS Jungle**. Follow winding forest paths, scavenge a can and bottle, recover your health, turn their scrap into a compass, gather a spear's materials, survive a hostile dog, and find the end beacon. At least... that's the tutorial level.

The world is one deterministic, bounded jungle chunk. Procedural trees surround a carved-out route; generation verifies clearance after placing vegetation. The existing OpenGL engine renders terrain, forest, recognisable resource models, world-attached objective arrows, and the beacon's turquoise ring.

## Run

Use Python with the dependencies in `requirements.txt` and an OpenGL 3.3 compatibility context:

```sh
python -m pip install -r requirements.txt
python src/main.py
```

The game starts fullscreen at the desktop resolution. Want a window? Run `wtw-venv/bin/python src/main.py --windowed`; `--width` and `--height` flags set its initial size (1280×800 by default). Choose another reproducible world with `--seed <seed>`.

The title screen loads first, with **Play**, **Tutorial**, and **About This Game**. Play opens a temporary panel saying the main gameplay loop is still in progress. Tutorial loads CS Jungle with a spinner while the forest is generated. About is a help/info placeholder; its text lives in `src/engine/menu.py` for later editing. Click a button or use Up/Down and Enter. Esc goes back from these panels and quits from the title.

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
| Click while paused | Resume |
| R after death or completion | Restart |
| Ctrl+Q | Quit |

The tutorial starts at 80/100 health. Each consumable heals 10 up to 100. Collection gives just the can or bottle, each in its own slot. Holding E to finish it replaces that same slot with metal or plastic scrap; scrap appears only after consumption. A compass costs **1 metal scrap + 1 plastic scrap**; a spear costs **2 sticks + 1 rock**. Crafting shows material counts and pauses the encounter while you choose. Pick a tool's number slot to hold it. Later interactions and the dog encounter are gated by tutorial progression. The beacon requires F, not just proximity.

Hold the compass slot to see its dial and red needle pointing toward the beacon relative to your view. Keep to the winding path. Bushes are scenery you can walk through; trees and the world boundary still stop you. Large tutorial prompts sit above the inventory bar, under a blue sky.

Mouse-look uses SDL relative motion, with stale input flushed when capture changes. Opening crafting, pausing, or losing focus releases the pointer; returning to play briefly discards capture-transition motion.

That's all for now.

_Walking the Walk, Version 0, Written by Quan Thai, October 2026_
