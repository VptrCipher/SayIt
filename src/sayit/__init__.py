"""SayIt package metadata and Linux runtime bootstrap."""

from __future__ import annotations

import ctypes
import sys
from pathlib import Path

__version__ = "0.1.2"

# Technical identifier — used for data/config directory names, the autostart
# registry key, QApplication.setApplicationName, and logging. MUST remain
# "SayIt" so existing installations, settings, and autostart entries keep
# working. Do not change this without a dedicated migration.
__app_name__ = "SayIt"

# User-facing product name. This is what people see in the window titles, tray,
# onboarding, and overlays.
__display_name__ = "SayIt"


# Linux only: python-sounddevice expects PortAudio to be available as a system
# shared library. The release AppImage is intentionally self-contained, so the
# release pipeline vendors a known-good PortAudio build and preloads it before
# sounddevice can resolve the library. Keeping the handle alive also prevents
# the library from being unloaded while Python extension modules use it.
_bundled_portaudio = None


def _preload_bundled_portaudio() -> None:
    global _bundled_portaudio

    if not sys.platform.startswith("linux"):
        return

    vendor_dir = Path(__file__).resolve().parent / "_vendor" / "linux"
    candidates = sorted(vendor_dir.glob("libportaudio.so*"), reverse=True)
    if not candidates:
        return

    for library in candidates:
        try:
            _bundled_portaudio = ctypes.CDLL(str(library), mode=ctypes.RTLD_GLOBAL)
            return
        except OSError:
            continue


_preload_bundled_portaudio()
