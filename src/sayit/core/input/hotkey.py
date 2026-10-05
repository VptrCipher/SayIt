"""
Hotkey listener for global keyboard shortcuts.

Uses pynput for Windows and Linux.
"""

from typing import Optional, Set

from PySide6.QtCore import QObject, Signal

from ...utils.logger import get_logger
from ..settings.settings import Settings, get_settings

logger = get_logger(__name__)


# QKeySequence uses human-readable names for several non-character keys while
# pynput exposes Python-style Key attributes. Keep the translation here so a
# value saved by the settings UI is also a value the runtime can actually bind.
_SPECIAL_KEY_ALIASES = {
    "page up": "page_up",
    "pageup": "page_up",
    "pgup": "page_up",
    "page down": "page_down",
    "pagedown": "page_down",
    "pgdown": "page_down",
    "print screen": "print_screen",
    "printscreen": "print_screen",
    "scroll lock": "scroll_lock",
    "scrolllock": "scroll_lock",
    "num lock": "num_lock",
    "numlock": "num_lock",
    "caps lock": "caps_lock",
    "capslock": "caps_lock",
    "back space": "backspace",
    "backspace": "backspace",
    "return": "enter",
    "arrow up": "up",
    "arrow down": "down",
    "arrow left": "left",
    "arrow right": "right",
}


def _normalize_trigger_key(key_name: str) -> str:
    """Normalize a persisted/UI key name to pynput's Key attribute name."""
    normalized = " ".join((key_name or "").strip().lower().split())
    return _SPECIAL_KEY_ALIASES.get(normalized, normalized.replace(" ", "_"))


class HotkeyListener(QObject):
    """
    Listens for hotkey combinations.

    Signals:
        hotkey_pressed: Emitted when the hotkey is pressed
        hotkey_released: Emitted when the hotkey is released
        cancel_requested: Emitted when the cancel key (Esc) is pressed
    """

    hotkey_pressed = Signal()
    hotkey_released = Signal()
    cancel_requested = Signal()

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)

        self._is_hotkey_active = False

        settings = get_settings()
        self._setup_hotkey(settings)

        self._impl = _PynputHotkeyListenerImpl(self)

    def update_settings(self, settings: Settings) -> None:
        """Replace the active hotkey registration with the newly saved config.

        The settings object is already persisted by SettingsWindow before this
        callback is emitted. When the listener is running, stop the old
        keyboard listener completely before registering the new configuration;
        this prevents stale registrations and guarantees the new hotkey takes
        effect immediately.
        """
        was_running = self._impl.is_running

        if self._is_hotkey_active:
            # A hotkey change while the old combination is held must not leave
            # the application believing a recording is still active.
            self._on_hotkey_released()

        # Always clear the implementation's pressed-key state. This is
        # especially important when a prior combination was partially pressed.
        self._impl.stop()

        self._setup_hotkey(settings)
        self._impl.update_config(self._trigger_key, self._required_modifier_types)

        if was_running:
            self._impl.start()

    def _setup_hotkey(self, settings: Settings) -> None:
        self._required_modifier_types: Set[str] = set(settings.hotkey.modifiers)
        self._trigger_key = settings.hotkey.key

    def start(self) -> None:
        self._impl.start()

    def stop(self) -> None:
        self._impl.stop()

    def _on_hotkey_pressed(self) -> None:
        if not self._is_hotkey_active:
            self._is_hotkey_active = True
            self.hotkey_pressed.emit()

    def _on_hotkey_released(self) -> None:
        if self._is_hotkey_active:
            self._is_hotkey_active = False
            self.hotkey_released.emit()

    def _on_cancel(self) -> None:
        self.cancel_requested.emit()


class _PynputHotkeyListenerImpl:
    """
    Pynput-based hotkey listener for Windows and Linux.
    """

    def __init__(self, listener: HotkeyListener):
        from pynput import keyboard

        self._listener = listener
        self._keyboard_listener: Optional[keyboard.Listener] = None
        self._pressed_keys: set = set()

        self._trigger_key = keyboard.Key.space
        self._required_modifier_types = listener._required_modifier_types
        self._update_trigger_key(listener._trigger_key)

    def _update_trigger_key(self, key_name: str) -> None:
        from pynput import keyboard

        normalized = _normalize_trigger_key(key_name)
        if normalized == "space":
            self._trigger_key = keyboard.Key.space
            return

        try:
            self._trigger_key = getattr(keyboard.Key, normalized)
        except AttributeError:
            # Character keys (letters, digits, punctuation) are represented as
            # KeyCode values by pynput. This also handles symbols captured by
            # QKeySequenceEdit without requiring a hard-coded key list.
            try:
                self._trigger_key = keyboard.KeyCode.from_char(key_name.strip())
            except (TypeError, ValueError):
                logger.warning(
                    "Unsupported custom hotkey key %r; falling back to Space",
                    key_name,
                )
                self._trigger_key = keyboard.Key.space

    def update_config(self, trigger_key: str, modifiers: Set[str]) -> None:
        self._required_modifier_types = set(modifiers)
        self._update_trigger_key(trigger_key)

    def _check_hotkey(self) -> bool:
        from pynput import keyboard

        if self._trigger_key not in self._pressed_keys:
            return False

        for mod_type in self._required_modifier_types:
            is_pressed = False
            if mod_type == "ctrl":
                is_pressed = (
                    keyboard.Key.ctrl_l in self._pressed_keys
                    or keyboard.Key.ctrl_r in self._pressed_keys
                )
            elif mod_type == "alt":
                is_pressed = (
                    keyboard.Key.alt_l in self._pressed_keys
                    or keyboard.Key.alt_r in self._pressed_keys
                )
            elif mod_type == "shift":
                is_pressed = (
                    keyboard.Key.shift_l in self._pressed_keys
                    or keyboard.Key.shift_r in self._pressed_keys
                )
            elif mod_type in ("cmd", "meta"):
                is_pressed = (
                    keyboard.Key.cmd_l in self._pressed_keys
                    or keyboard.Key.cmd_r in self._pressed_keys
                )

            if not is_pressed:
                return False

        return True

    def _on_press(self, key) -> None:
        from pynput import keyboard

        # Esc requests cancellation of the current dictation. This only emits a
        # signal; the app decides whether anything is active to cancel, so Esc
        # is a no-op when idle and never globally disruptive.
        if key == keyboard.Key.esc:
            self._listener._on_cancel()

        self._pressed_keys.add(key)

        if self._check_hotkey():
            self._listener._on_hotkey_pressed()

    def _on_release(self, key) -> None:
        try:
            self._pressed_keys.remove(key)
        except KeyError:
            pass

        if not self._check_hotkey():
            self._listener._on_hotkey_released()

    @property
    def is_running(self) -> bool:
        return (
            self._keyboard_listener is not None
            and self._keyboard_listener.is_alive()
        )

    def start(self) -> None:
        from pynput import keyboard

        if self.is_running:
            return

        self._keyboard_listener = keyboard.Listener(
            on_press=self._on_press, on_release=self._on_release
        )
        self._keyboard_listener.start()

        if hasattr(self._keyboard_listener, "IS_TRUSTED"):
            logger.info(
                f"Keyboard listener IS_TRUSTED: {self._keyboard_listener.IS_TRUSTED}"
            )
            if not self._keyboard_listener.IS_TRUSTED:
                logger.warning(
                    "Hotkey listener is NOT TRUSTED. Accessibility permissions not granted."
                )

    def stop(self) -> None:
        listener = self._keyboard_listener
        if listener is None:
            self._pressed_keys.clear()
            return

        try:
            listener.stop()
            # update_settings() can immediately start a replacement listener.
            # Join here so the old OS keyboard hook is fully torn down first.
            if listener.is_alive():
                listener.join()
        finally:
            self._keyboard_listener = None
            self._pressed_keys.clear()
