# Blender / FreeCAD Usage Guide

**English** · [中文](../zh/blender-freecad-usage.md)

This guide covers how to install and use the blender and freecad plugins — letting the model drive a real, running Blender / FreeCAD to do 3D modeling and parametric CAD.

---

## 1. What These Capabilities Do

| Capability | What it does | Tools | Example |
|------------|--------------|:-----:|---------|
| **blender** | Model / shade / light / render in Blender, plus pull PolyHaven·Sketchfab assets and generate 3D from text/image | 22 | "Build a red wooden table on the floor and render it" |
| **freecad** | Build parts / edit properties / import·export STEP·STL·DXF / run FEM (von Mises stress) in FreeCAD | 14 | "Make a 40×30×8 plate with a Ø10 hole in the center, export STEP" |

> These capabilities connect to a **running** Blender / FreeCAD to do the work. You don't start the app by hand — after installing, the first query brings it up automatically (on Linux it also auto-downloads the app if missing).

---

## 2. Install

```bash
claude plugin marketplace add https://github.com/QwenLM/Qwen-MM-Plugins.git
claude plugin install qwen-mm-plugins-blender@qwen-mm-plugins   # Blender 3D modeling
claude plugin install qwen-mm-plugins-freecad@qwen-mm-plugins   # FreeCAD parametric CAD
```

On a **headless server** (a cloud host / SSH with no display), one extra step (needs root):

```bash
sudo apt install xvfb
```

> Skip this on a desktop with a real display. These capabilities need **no API key**.

---

## 3. How to Use

Just describe what you want, e.g.:

```
In Blender, build a red cube with beveled edges, place it on the ground, light it and render.
```
```
In FreeCAD, build a 40×30×8 mm base plate, drill a Ø10 mm through-hole in the center, export STEP and STL.
```

- **The first call** takes ~1–2 min (downloading the app + starting it); instant afterward.
- Artifacts (`.blend`, render PNGs, `.FCStd`, STEP, STL, etc.) are written to real files on disk.

---

## 4. Environment Variables (usually none needed)

| Variable | Capability | Purpose | Default |
|----------|------------|---------|---------|
| `BLENDER_HOST` / `BLENDER_PORT` | blender | connection target | `localhost` / `9876` |
| `FREECAD_RPC_HOST` / `FREECAD_RPC_PORT` | freecad | connection target | `localhost` / `9875` |
| `QWEN_MM_AUTOLAUNCH` | both | set to `1` to launch the app on the first tool call | off (preset to `1` in the plugin manifests) |
| `QWEN_MM_NO_AUTO_INSTALL` | both | set to `1` to disable auto-download when the app is missing | off (auto-download by default) |
| `QWEN_MM_CACHE` | both | where auto-downloaded apps live | OS cache dir |
| `BLENDER_BINARY` / `FREECAD_BINARY` | blender / freecad | path to the app binary (else search PATH, else auto-download) | unset |
| `FREECAD_MOD_DIR` | freecad | override where `--launch-app` installs the bundled addon | per-user FreeCAD Mod dir |
| `FREECAD_ONLY_TEXT_FEEDBACK` | freecad | make screenshot-bearing tools return text only | off |
| `FREECAD_MCP_HEADLESS` | freecad | set to `1` to run GUI operations headless (no FreeCAD GUI) | off |

> On non-Linux-x86_64 platforms (auto-download only covers Linux-x86_64), install Blender 4.2.x / FreeCAD 1.1.x yourself and put it on PATH, or point at it with `BLENDER_BINARY` / `FREECAD_BINARY`.

---

## 5. Examples

The two below are **verified real runs** (the tools wrote files to disk and returned screenshots).

### 5.1 Blender: beveled red cube + Cycles render

The model models the scene, lights it, and renders with Cycles, producing the project file `test.blend` and the render `blender_render.png`:

| Cycles render | Viewport screenshot |
|:---:|:---:|
| ![Blender red cube Cycles render](../assets/blender-freecad/blender-cube-render.png) | ![Blender viewport screenshot](../assets/blender-freecad/blender-viewport.png) |

### 5.2 FreeCAD: holed base plate + STEP/STL export

The model builds the base plate, cuts the hole (boolean), and exports `bracket.FCStd` + `bracket.step` + `bracket.stl`:

<p align="center">
  <img src="../assets/blender-freecad/freecad-bracket-iso.png" alt="FreeCAD holed base plate, isometric" width="520">
</p>

After the cut, volume = 40×30×8 − π·5²·8 ≈ **8971.68 mm³**, matching the analytic value — the geometry is correct and ready for downstream use.

---

## 6. Troubleshooting

- **Can't connect / first call is slow**: the first call downloads the app in the background (Blender ~300 MB, FreeCAD ~1 GB) and starts it — wait 1–2 min; subsequent queries connect instantly.
- **Headless machine reports xvfb errors**: `sudo apt install xvfb` (needs root). Not needed with a real display.
- **FEM won't run**: it needs the CalculiX solver: `sudo apt install calculix-ccx`.
- **PolyHaven / Sketchfab / Hyper3D tools report "disabled"**: those asset / generation services need their own API key configured app-side (PolyHaven is free); leaving them unset doesn't affect anything else.

---

## 7. Attribution & License

- **blender** is ported from [ahujasid/blender-mcp](https://github.com/ahujasid/blender-mcp) (MIT)
- **freecad** is ported from [neka-nat/freecad-mcp](https://github.com/neka-nat/freecad-mcp) (MIT)
- We also acknowledge the official Blender [projects.blender.org/lab/blender_mcp](https://projects.blender.org/lab/blender_mcp) (GPL-2.0-or-later, referenced only — none of its code is used)

Full third-party licenses are in each capability's `NOTICE.md`.
