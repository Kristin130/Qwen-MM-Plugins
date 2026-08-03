"""`qwen-mm-plugins-freecad --launch-app` — bring up a live FreeCAD carrying the bundled FreeCADMCP
addon, so the thin-client tools have a session to connect to.

The addon (`vendor/FreeCADMCP/`) ships inside this package. Launching (1) copies the addon into the
user's FreeCAD Mod directory, then (2) starts FreeCAD with `FREECAD_RPC_PORT` set, which makes the
addon auto-start its XML-RPC server on that port (see FreeCADMCP/InitGui.py). One command, no repo
checkout and no manual `cp` needed:

    qwen-mm-plugins-freecad --launch-app          # headless (xvfb), detaches once the port is up
    qwen-mm-plugins-freecad --launch-app --gui    # on a machine with a real display

Wired via mcp_framework.run_main → this package's launch_app().
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from shared.env import get_env


def _vendor_addon() -> Path:
    return Path(__file__).resolve().parent / "vendor" / "FreeCADMCP"


# Pinned to the 1.1 line the model trained against. FreeCAD ships an AppImage; we extract it FUSE-free
# (`--appimage-extract`, which works on headless boxes with no libfuse2) into the user cache and run
# the resulting AppRun — all rootless. Auto-download is Linux-x86_64 only; elsewhere fall back to the
# manual install hint. Bump as new 1.1.x releases land (see github.com/FreeCAD/FreeCAD/releases).
_FREECAD_VERSION = "1.1.1"
_FREECAD_APPIMAGE = f"FreeCAD_{_FREECAD_VERSION}-Linux-x86_64-py311.AppImage"


def _freecad_download_url() -> str | None:
    import platform

    if sys.platform != "linux" or platform.machine() not in ("x86_64", "amd64"):
        return None
    return f"https://github.com/FreeCAD/FreeCAD/releases/download/{_FREECAD_VERSION}/{_FREECAD_APPIMAGE}"


def _appimage_extract(appimage: Path, cwd: Path) -> int:
    """`<appimage> --appimage-extract` in `cwd` (yields cwd/squashfs-root). FUSE-free — the AppImage
    runtime handles extraction itself, so no libfuse2 needed. Returns the exit code."""
    return subprocess.call(
        [str(appimage), "--appimage-extract"], cwd=str(cwd), stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT
    )


def _ensure_freecad() -> str | None:
    """Return a usable FreeCAD binary (the extracted AppRun), auto-downloading the pinned AppImage into
    the user cache (rootless, FUSE-free) if it isn't already there. Linux-x86_64 only; None if it
    can't be provided."""
    from shared import applaunch

    url = _freecad_download_url()
    if not url:
        return None  # unsupported platform — caller prints the manual hint
    apps = applaunch.apps_cache_dir()
    extract_dir = apps / f"freecad-{_FREECAD_VERSION}"
    apprun = extract_dir / "squashfs-root" / "AppRun"
    if apprun.is_file():
        return str(apprun)

    appimage = apps / _FREECAD_APPIMAGE
    print(
        f"FreeCAD not found — auto-downloading {_FREECAD_VERSION} AppImage (~1 GB, one-time) into "
        f"{apps} …\n"
        "  (set QWEN_MM_NO_AUTO_INSTALL=1 to disable, or FREECAD_BINARY to point at your own)",
        file=sys.stderr,
    )
    try:
        if not appimage.is_file():
            applaunch.download_file(url, appimage)
        appimage.chmod(0o755)
        extract_dir.mkdir(parents=True, exist_ok=True)
        shutil.rmtree(extract_dir / "squashfs-root", ignore_errors=True)  # clear any stale partial
        rc = _appimage_extract(appimage, extract_dir)
        if rc != 0:
            raise RuntimeError(f"`--appimage-extract` exited {rc}")
    except Exception as e:
        print(
            f"  auto-download failed: {e}\n  install FreeCAD manually (see --check-system) or set FREECAD_BINARY.",
            file=sys.stderr,
        )
        return None
    finally:
        appimage.unlink(missing_ok=True)

    if apprun.is_file():
        apprun.chmod(0o755)
        print(f"  FreeCAD {_FREECAD_VERSION} ready at {apprun}", file=sys.stderr)
        return str(apprun)
    return None


def _mod_dir(explicit: str | None) -> Path:
    """FreeCAD user Mod directory: --mod-dir wins, then $FREECAD_MOD_DIR, then the standard
    per-user path (~/.local/share/FreeCAD/Mod on Linux 1.x; ~/.FreeCAD/Mod if that's what exists)."""
    if explicit:
        return Path(explicit).expanduser()
    env = get_env("FREECAD_MOD_DIR")
    if env:
        return Path(env).expanduser()
    legacy = Path.home() / ".FreeCAD"
    if legacy.is_dir() and not (Path.home() / ".local/share/FreeCAD").is_dir():
        return legacy / "Mod"
    return Path.home() / ".local/share/FreeCAD/Mod"


def _install_addon(mod_dir: Path) -> Path:
    src = _vendor_addon()
    if not src.is_dir():
        raise FileNotFoundError(f"bundled FreeCADMCP addon missing: {src} (reinstall the plugin)")
    mod_dir.mkdir(parents=True, exist_ok=True)
    dst = mod_dir / "FreeCADMCP"
    shutil.copytree(src, dst, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    return dst


def launch_app(argv: list[str]) -> int:
    from shared import applaunch

    ap = argparse.ArgumentParser(
        prog="qwen-mm-plugins-freecad --launch-app",
        description="Start a live FreeCAD + FreeCADMCP addon for the MCP tools to connect to.",
    )
    ap.add_argument(
        "--port",
        type=int,
        default=int(get_env("FREECAD_RPC_PORT", "9875")),
        help="XML-RPC port for the addon server (default: $FREECAD_RPC_PORT or 9875)",
    )
    ap.add_argument("--gui", action="store_true", help="use the real display (default: headless via xvfb)")
    ap.add_argument(
        "--foreground", action="store_true", help="block in the foreground instead of detaching once the port is up"
    )
    ap.add_argument(
        "--binary",
        default=get_env("FREECAD_BINARY") or None,
        help="path to the freecad binary / AppRun (default: $FREECAD_BINARY, else search PATH)",
    )
    ap.add_argument(
        "--mod-dir", default=None, help="FreeCAD Mod directory to install the addon into (default: per-user)"
    )
    ap.add_argument("--screen", default="1920x1080x24", help="xvfb virtual screen geometry (default: 1920x1080x24)")
    ap.add_argument(
        "--wait", type=float, default=120.0, help="seconds to wait for the port after launch (default: 120)"
    )
    args = ap.parse_args(argv)

    host = get_env("FREECAD_RPC_HOST", "127.0.0.1")
    if applaunch.is_port_open(host, args.port):
        # status → stderr: launch_app is reused on the in-server autolaunch path, where stdout
        # is the MCP stdio JSON-RPC channel; a stray line there corrupts the protocol stream.
        print(f"FreeCAD MCP already listening on {host}:{args.port} — nothing to do.", file=sys.stderr)
        return 0

    binary = applaunch.resolve_binary(["freecad", "FreeCAD"], explicit=args.binary)
    if not binary and applaunch.auto_install_enabled():
        binary = _ensure_freecad()
    if not binary:
        print(
            "freecad not found — install it, then retry (see --check-system).\n"
            "  apt install freecad  |  or extract the AppImage and pass --binary <AppRun>\n"
            "  (auto-download covers Linux-x86_64; QWEN_MM_NO_AUTO_INSTALL disables it)",
            file=sys.stderr,
        )
        return 3

    try:
        dst = _install_addon(_mod_dir(args.mod_dir))
    except OSError as e:
        print(f"could not install the FreeCADMCP addon: {e}", file=sys.stderr)
        return 4
    print(f"Installed FreeCADMCP addon → {dst}", file=sys.stderr)

    env = {**os.environ, "FREECAD_RPC_PORT": str(args.port)}
    cmd = [binary]
    if not args.gui:
        try:
            cmd = applaunch.wrap_xvfb(cmd, screen=args.screen)
        except FileNotFoundError as e:
            print(str(e), file=sys.stderr)
            return 3

    if args.foreground:
        print(f"Launching FreeCAD (foreground) on port {args.port} …", file=sys.stderr)
        return applaunch.run_foreground(cmd, env=env)

    log = applaunch.default_log_path("freecad")
    proc = applaunch.spawn_detached(cmd, env=env, log_path=log)
    print(
        f"Launching FreeCAD (pid {proc.pid}, headless={'no' if args.gui else 'yes'}) on {host}:{args.port}; log: {log}",
        file=sys.stderr,
    )
    if applaunch.wait_for_port(host, args.port, timeout=args.wait):
        print(f"FreeCAD MCP ready on {host}:{args.port}.", file=sys.stderr)
        return 0
    print(f"FreeCAD did not open {host}:{args.port} within {args.wait:.0f}s — see {log}.", file=sys.stderr)
    return 5
