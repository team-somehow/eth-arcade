"""Configure SDL KMS and use system pygame (pip pygame lacks KMSDRM on Pi)."""
import importlib.util
import os
import sys

SYSTEM_PYTHON = "/usr/bin/python3"


def configure_sdl():
    # Prefer the running desktop (labwc/Wayland or X11). Only force KMSDRM
    # when nothing already owns the DRM device.
    has_session = bool(
        os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY")
    )
    if not has_session:
        os.environ.setdefault("SDL_VIDEODRIVER", "kmsdrm")
        # card2 is the Waveshare SPI panel on this Pi 5; card1 is HDMI.
        os.environ.setdefault("SDL_VIDEO_KMSDRM_DEVICE_INDEX", "2")
    os.environ.setdefault("SDL_MOUSE_RELATIVE", "0")


def _venv_free_env():
    env = os.environ.copy()
    venv = env.pop("VIRTUAL_ENV", None)
    if venv:
        venv_bin = os.path.realpath(os.path.join(venv, "bin"))
        env["PATH"] = ":".join(
            p for p in env.get("PATH", "").split(":")
            if p and os.path.realpath(p) != venv_bin
        )
    return env


def ensure_system_pygame():
    """Re-exec without venv when pip pygame is active (no KMSDRM driver)."""
    # Only force KMSDRM on Linux (Pi); desktop macOS/Windows use default drivers.
    if sys.platform.startswith("linux"):
        configure_sdl()

    spec = importlib.util.find_spec("pygame")
    if not spec or not spec.origin:
        return

    origin = spec.origin
    if "dist-packages" in origin:
        return

    if "site-packages" not in origin:
        return

    if not sys.platform.startswith("linux"):
        return

    if not os.path.exists(SYSTEM_PYTHON):
        return

    os.execve(SYSTEM_PYTHON, [SYSTEM_PYTHON, *sys.argv], _venv_free_env())
