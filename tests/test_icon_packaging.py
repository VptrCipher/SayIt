from pathlib import Path
import tomllib

ROOT = Path(__file__).resolve().parents[1]

def test_briefcase_uses_canonical_sayit_icon():
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert data["tool"]["briefcase"]["app"]["sayit"]["icon"] == "icons/sayit"

def test_canonical_icon_exists():
    icon = ROOT / "icons" / "sayit.svg"
    assert icon.is_file()
    text = icon.read_text(encoding="utf-8")
    assert "<svg " in text
    assert 'fill="#0C0C0C"' in text
    assert 'id="si-orange"' in text

def test_canonical_icon_matches_web_icon():
    a = (ROOT / "icons" / "sayit.svg").read_text(encoding="utf-8")
    b = (ROOT / "website" / "src" / "app" / "icon.svg").read_text(encoding="utf-8")
    assert a == b

def test_inno_installer_icon_is_configured():
    text = (ROOT / "installer.iss").read_text(encoding="utf-8")
    assert '#define MyAppIcon "icons\\sayit.ico"' in text
    assert "SetupIconFile={#MyAppIcon}" in text

def test_inno_app_shortcuts_use_exe_icon():
    text = (ROOT / "installer.iss").read_text(encoding="utf-8")
    assert 'IconFilename: "{app}\\{#MyAppExeName}"' in text

def test_uninstall_icon_uses_exe():
    text = (ROOT / "installer.iss").read_text(encoding="utf-8")
    assert 'UninstallDisplayIcon={app}\\{#MyAppExeName}' in text

def test_build_script_generates_icons():
    text = (ROOT / "scripts" / "build.py").read_text(encoding="utf-8")
    assert "generate_icons(project_root)" in text

def test_generator_sizes():
    text = (ROOT / "scripts" / "generate_icons.py").read_text(encoding="utf-8")
    assert "SIZES = (16, 32, 48, 64, 128, 256, 512)" in text
    assert "ICO_SIZES = (16, 32, 48, 64, 128, 256)" in text

def test_generated_icons_are_gitignored():
    text = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "icons/sayit-*.png" in text
    assert "icons/sayit.ico" in text
