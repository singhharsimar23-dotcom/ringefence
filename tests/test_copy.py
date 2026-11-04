"""Every word a person reads: no marketing words, no emoji, no exclamation marks, and every reason code has text.
Only string literals are scanned: code legitimately contains `!=` and `!==`."""
import ast
import re
from pathlib import Path

import pytest

from ringfence import copy
from ringfence.gate import REASON_CODES

ROOT = Path(__file__).resolve().parent.parent
BANNED = ["seamless", "leverage", "robust", "empower", "unlock", "effortless", "revolutionize", "cutting-edge",
          "AI-powered", "Oops", "Successfully"]
ALLOWED_BANG = {"[*_`#\\[\\]<>]|!"}  # copy.py: the sanitiser pattern that strips them
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿⭐⬆✅❌]")


def py_strings(path: Path) -> list[str]:
    return [n.value for n in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
            if isinstance(n, ast.Constant) and isinstance(n.value, str)]


def _skip_regex(s: str, i: int) -> int:
    """s[i] is the opening slash of a regex literal; return the index after its closing slash."""
    i += 1
    in_class = False
    while s[i] != "/" or in_class:
        if s[i] == "\\":
            i += 1
        elif s[i] == "[":
            in_class = True
        elif s[i] == "]":
            in_class = False
        i += 1
    return i + 1


def _scan_template(s: str, i: int, out: list[str]) -> int:
    buf = ""
    while s[i] != "`":
        if s[i] == "\\":
            buf += s[i:i + 2]
            i += 2
        elif s.startswith("${", i):
            i = _scan_code(s, i + 2, out, True)
        else:
            buf += s[i]
            i += 1
    out.append(buf)
    return i + 1


def _scan_code(s: str, i: int, out: list[str], in_expr: bool = False) -> int:
    braces = 0
    while i < len(s):
        c = s[i]
        if c in "\"'":
            j = i + 1
            while s[j] != c:
                j += 2 if s[j] == "\\" else 1
            out.append(s[i + 1:j])
            i = j + 1
        elif c == "`":
            i = _scan_template(s, i + 1, out)
        elif c == "/" and s[i + 1:i + 2] not in ("/", "*") and re.search(r"[(,=:\[!&|?{};]\s*$", s[max(0, i - 6):i]):
            i = _skip_regex(s, i)
        elif c == "{":
            braces += 1
            i += 1
        elif c == "}":
            if in_expr and braces == 0:
                return i + 1
            braces -= 1
            i += 1
        else:
            i += 1
    return i


def js_strings(src: str) -> list[str]:
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.DOTALL)
    src = re.sub(r"(?<![:\"'])//[^\n]*", "", src)
    out: list[str] = []
    _scan_code(src, 0, out)
    return out


def html_text(src: str) -> list[str]:
    markup = re.sub(r"<script.*?</script>", "", src, flags=re.DOTALL)
    attrs = re.findall(r'(?:title|aria-label|placeholder)="([^"]*)"', markup)
    text = re.findall(r">([^<>]+)<", markup)
    scripts = [js_strings(m) for m in re.findall(r"<script>(.*?)</script>", src, flags=re.DOTALL)]
    return attrs + text + [s for group in scripts for s in group]


def all_literals() -> dict[str, list[str]]:
    return {
        "copy.py": py_strings(ROOT / "ringfence" / "copy.py"),
        "copy.js": js_strings((ROOT / "static" / "copy.js").read_text(encoding="utf-8")),
        "app.js": js_strings((ROOT / "static" / "app.js").read_text(encoding="utf-8")),
        "play.js": js_strings((ROOT / "static" / "play.js").read_text(encoding="utf-8")),
        "index.html": html_text((ROOT / "static" / "index.html").read_text(encoding="utf-8")),
        "landing.js": js_strings((ROOT / "static" / "landing.js").read_text(encoding="utf-8")),
        "landing.html": html_text((ROOT / "static" / "landing.html").read_text(encoding="utf-8")),
    }


LITERALS = [(f, s) for f, strings in all_literals().items() for s in strings]


def test_the_scan_finds_the_text_it_is_supposed_to_guard():
    found = {f for f, _ in LITERALS}
    assert found == {"copy.py", "copy.js", "app.js", "play.js", "index.html", "landing.js", "landing.html"}
    assert any("Run Friday payroll" in s for _, s in LITERALS) and len(LITERALS) > 150


@pytest.mark.parametrize("word", BANNED)
def test_no_banned_words(word):
    hits = [(f, s) for f, s in LITERALS if re.search(rf"\b{re.escape(word)}\b", s, re.IGNORECASE)]
    assert not hits, hits


def test_no_emoji():
    hits = [(f, s) for f, s in LITERALS if EMOJI.search(s)]
    assert not hits, hits


def test_no_exclamation_marks():
    hits = [(f, s) for f, s in LITERALS if "!" in s and s not in ALLOWED_BANG]
    assert not hits, hits


def test_every_reason_code_has_text():
    assert set(copy.REASON_TEXT) == set(REASON_CODES)
    assert all(copy.REASON_TEXT[c].strip() for c in REASON_CODES)
    assert all(copy.reason(c, "northwind") for c in REASON_CODES)


def test_the_scanner_sees_strings_after_nested_templates_and_regex_literals():
    src = 'const r = s.replace(/[&<>"\']/g, "x"); const a = `p ${f(`q`)} r`; const b = "Oops!";'
    assert "Oops!" in js_strings(src) and "q" in js_strings(src)
