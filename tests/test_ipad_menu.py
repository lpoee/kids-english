import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "index.html").read_text(encoding="utf-8")


def css_rule(selector: str) -> str:
    match = re.search(re.escape(selector) + r"\{([^}]+)\}", HTML)
    assert match, f"missing CSS rule for {selector}"
    return match.group(1)


def test_main_menu_has_ipad_sized_touch_targets():
    rule = css_rule(".tab")
    assert "min-height:48px" in rule
    assert "touch-action:manipulation" in rule


def test_submenu_has_ipad_sized_touch_targets():
    rule = css_rule(".sub-tab")
    assert "min-height:48px" in rule
    assert "touch-action:manipulation" in rule


def test_empty_submenu_cannot_intercept_main_menu_taps():
    rule = css_rule("#sub-tabs:empty")
    assert "display:none" in rule
    assert "pointer-events:none" in rule


def test_submenu_starts_below_the_larger_main_menu_row():
    rule = css_rule("#sub-tabs")
    top = re.search(r"top:(\d+)px", rule)
    assert top and int(top.group(1)) >= 56
