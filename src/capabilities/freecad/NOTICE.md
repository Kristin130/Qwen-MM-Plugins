# Third-party attribution — FreeCAD capability

This capability ports and vendors code from **freecad-mcp**.

- Upstream: freecad-mcp — https://github.com/neka-nat/freecad-mcp
- Copyright: (c) 2025 Shirokuma (k tanaka)  (GitHub: neka-nat)
- License: MIT — full text vendored at `qwen_mm_plugins_freecad/vendor/FreeCADMCP/LICENSE`

Vendored / derived files:

- `qwen_mm_plugins_freecad/vendor/FreeCADMCP/` — the FreeCAD workbench + XML-RPC server addon,
  adapted (with modifications) from the upstream `addon/FreeCADMCP/` directory (RPC server,
  property mapping, object/view handling, and GUI dispatch were changed; see git history).
- `qwen_mm_plugins_freecad/loader.py` — ported from `freecad_mcp/freecad_client.py` (XML-RPC client).
- `qwen_mm_plugins_freecad/_responses.py` — ported from `freecad_mcp/responses.py`, returning plain
  content-block dicts instead of SDK objects.
- `qwen_mm_plugins_freecad/tools/*.py` — the MCP tool surface (tool names, parameters, behavior) is
  ported from `freecad_mcp/server.py` + `freecad_mcp/operations/core.py`, adapted onto
  Qwen-MM-Plugins' `mcp_framework`.

The MIT license text of the upstream project applies to the vendored/derived portions above.
