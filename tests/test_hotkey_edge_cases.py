"""Regression coverage for custom hotkey names used by Qt and pynput."""

from unittest.mock import patch

from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QKeySequenceEdit

from src.sayit.core.input.hotkey import _normalize_trigger_key
from src.sayit.core.settings import HotkeyConfig, Settings
from src.sayit.ui.tabs.configuration_tab import ConfigurationTab


def test_special_key_names_normalize_to_pynput_names():
    assert _normalize_trigger_key("Page Up") == "page_up"
    assert _normalize_trigger_key("Page Down") == "page_down"
    assert _normalize_trigger_key("Print Screen") == "print_screen"
    assert _normalize_trigger_key("Caps Lock") == "caps_lock"
    assert _normalize_trigger_key("Num Lock") == "num_lock"
    assert _normalize_trigger_key("Scroll Lock") == "scroll_lock"
    assert _normalize_trigger_key("Backspace") == "backspace"


def test_character_and_function_keys_remain_usable():
    assert _normalize_trigger_key("k") == "k"
    assert _normalize_trigger_key("F9") == "f9"
    assert _normalize_trigger_key("space") == "space"


def test_ctrl_page_up_round_trips_through_qt_parser(qtbot):
    edit = QKeySequenceEdit()
    qtbot.addWidget(edit)
    edit.setKeySequence(QKeySequence("Ctrl+Page Up"))

    tab = ConfigurationTab.__new__(ConfigurationTab)
    tab._hotkey_edit = edit

    result = tab._parse_key_sequence()

    # Qt 6 normalizes Page Up to its short display name "PgUp". The runtime
    # normalizer must translate that persisted value back to pynput's
    # "page_up" key name.
    assert result == HotkeyConfig(modifiers=["ctrl"], key="pgup")
    assert _normalize_trigger_key(result.key) == "page_up"


def test_custom_hotkey_survives_settings_disk_roundtrip(tmp_path):
    settings = Settings(hotkey=HotkeyConfig(modifiers=["ctrl", "alt"], key="page up"))

    with patch("src.sayit.core.settings.settings.get_config_dir", return_value=tmp_path):
        settings.save()
        restored = Settings.load()

    assert restored.hotkey == settings.hotkey
