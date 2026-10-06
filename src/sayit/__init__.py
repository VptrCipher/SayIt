"""SayIt package metadata and Linux runtime bootstrap."""

from __future__ import annotations

import ctypes
import ctypes.util
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


_bundled_portaudio = None
_bundled_portaudio_path: Path | None = None


def _configure_bundled_portaudio() -> None:
    """Make the packaged Linux PortAudio visible to python-sounddevice.

    On Linux, sounddevice asks ctypes.util.find_library("portaudio") for a
    system library. An AppImage cannot assume that library exists on the user's
    distro. The release pipeline therefore generates a compatible PortAudio
    shared library under this package and redirects only the "portaudio" lookup
    to that exact file before sounddevice is imported.
    """
    global _bundled_portaudio, _bundled_portaudio_path

    if not sys.platform.startswith("linux"):
        return

    vendor_dir = Path(__file__).resolve().parent / "_vendor" / "linux"
    candidates = sorted(
        (path for path in vendor_dir.glob("libportaudio.so*") if path.is_file()),
        reverse=True,
    )
    if not candidates:
        return

    library = candidates[0]
    system_find_library = ctypes.util.find_library

    def find_library(name: str):
        if name == "portaudio":
            return str(library)
        return system_find_library(name)

    # sounddevice imports find_library directly, so this must be installed
    # before the first "import sounddevice" happens.
    ctypes.util.find_library = find_library
    _bundled_portaudio_path = library

    try:
        # Keep a process-wide handle alive and make PortAudio symbols available
        # to extensions that resolve them through the process loader.
        _bundled_portaudio = ctypes.CDLL(
            str(library),
            mode=getattr(ctypes, "RTLD_GLOBAL", 0),
        )
    except OSError:
        # Leave the redirected lookup in place so sounddevice can surface a
        # precise loading error rather than silently switching libraries.
        _bundled_portaudio = None


_configure_bundled_portaudio()
