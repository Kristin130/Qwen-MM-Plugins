# Local Development / Debugging

**English** · [中文](../zh/local_development.md)

Four ways to debug locally; all commands are run from the repository root.

## 1. Write Python / run pytest directly — editable install

Install qwen-mm-plugins into the current environment in editable mode; afterward `import qwen_mm_plugins_core` just works and code changes take effect immediately (no reinstall). Use this to debug basic functionality.

```bash
scripts/dev-install.sh          # base dependencies only (enough to import and to run a server from source)
scripts/dev-install.sh core     # vision + the full visualize stack
scripts/dev-install.sh all      # everything (incl. heavy deps like geopandas/trimesh/playwright)

python -c "import qwen_mm_plugins_core as p; print(len(p.SPECS), 'tools')"
python -m pytest tests/
```

Installed into the currently active venv (uses uv when `uv` + a venv are present, otherwise pip). Only re-run it after changing dependencies.

## 2. Run a server straight from source

```bash
python3 src/capabilities/core/qwen_mm_plugins_core --version
python3 src/capabilities/core/qwen_mm_plugins_core --check-system
# stdio test:
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' \
  | python3 src/capabilities/core/qwen_mm_plugins_core
```

`__main__.py` automatically adds `src/` and its own capability directory to `sys.path`, so it starts from any cwd.

## 3. Debug server logic inside a harness

The registration corresponding to installation Option 2:

```bash
# skill: symlink the local skill directory
ln -s "$(pwd)/src/capabilities/core/skill" ~/.claude/skills/qwen-mm-plugins-core
# MCP: running this directory with python3 = executing its __main__.py (the server entry, equivalent to the console qwen-mm-plugins-core); reconnect after editing to take effect, with no build cache
claude mcp add qwen-mm-plugins-core -- python3 "$(pwd)/src/capabilities/core/qwen_mm_plugins_core"
```

The tool name is `mcp__qwen-mm-plugins-core__<tool>` (manual install, no plugin prefix). Running directly uses the dependencies of the current Python environment — so first run `scripts/dev-install.sh core` (or `all`) once to have the deps ready. After editing code, have the harness reconnect to that MCP (restart the session or reconnect via `/mcp`) to load the new code.

To get closer to production (isolated environment + profile-based dependency install), swap the command for `uvx --from "$(pwd)[core]" qwen-mm-plugins-core`. uvx rebuilds from local source whenever it changes, so a harness reconnect picks up your edits (add `--refresh` only to force a rebuild if it ever serves a stale one).

## 4. Exercise the whole plugin chain (marketplace + install) with local code

To verify plugin.json / marketplace.json / the install-and-register flow itself, but using local un-pushed code: temporarily point the capability's plugin manifest at your local checkout, install and test, then revert.

```bash
scripts/dev-plugin.sh core          # switch core's --from from git@main to file://<repo>
claude plugin marketplace add "$(pwd)"      # point the marketplace at the local directory → reads the workspace manifest
claude plugin install qwen-mm-plugins-core@qwen-mm-plugins
# ... test (tool names carry the prefix: mcp__plugin_qwen-mm-plugins-core_qwen-mm-plugins-core__<tool>) ...
scripts/dev-plugin.sh core --revert         # restore the manifest, run before committing
```

When `marketplace add` is given a local directory path it reads the workspace files, so locally-edited manifests take effect directly. Codex's `.mcp.json` is updated along with it.

**Note**: when `dev-plugin.sh` flips the manifest it already adds `--refresh` to uvx, so every launch rebuilds from local source (slightly slower, but server code changes take effect immediately). Don't forget `--revert` after testing, or you'll commit the `file://` local path.
