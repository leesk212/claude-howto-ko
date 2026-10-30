#!/usr/bin/env python3
"""Compare structure of ko/<path> against current English <path>.
Usage (from a docs/ko-translation checkout): python3 -I tools/check_ko.py <relpath> [<relpath> ...]
"""

import os
import re
import sys
from pathlib import Path

R = os.getcwd()  # run from the docs/ko-translation checkout root


def stats(text):
    inf = False
    h = code = mer = 0
    heads = []
    for line in text.split("\n"):
        if re.match(r"^\s*(```|~~~)", line):
            if not inf:
                code += 1
                if "mermaid" in line:
                    mer += 1
            inf = not inf
            continue
        if not inf and re.match(r"^#{1,6} ", line):
            h += 1
            heads.append(line.split(" ")[0])
    rows = len([l for l in text.split("\n") if re.match(r"^\s*\|.*\|\s*$", l)])
    return {
        "headings": h,
        "code_blocks": code,
        "mermaid": mer,
        "table_rows": rows,
        "levels": heads,
    }


def code_lines(text):
    out, inb, lang = [], False, ""
    for l in text.split("\n"):
        m = re.match(r"^\s*```(\w*)", l)
        if m:
            inb = not inb
            lang = m.group(1)
            continue
        if (
            inb
            and lang
            in ("bash", "sh", "json", "yaml", "python", "javascript", "typescript")
            and l.strip()
            and not l.strip().startswith(("#", "//"))
        ):
            # ignore trailing comments, which may be translated
            s = re.split(r"\s+(#|//)\s", l.strip())[0].strip()
            # ignore JSON/YAML string values that are natural language (descriptions)
            if re.search(r'"(description|prompt|message)"\s*:', s) or re.match(
                r"(description|prompt):", s
            ):
                continue
            out.append(s)
    return out


ok_all = True
for p in sys.argv[1:]:
    en_p, ko_p = f"{R}/{p}", f"{R}/ko/{p}"
    if not os.path.exists(ko_p):
        print(f"MISSING ko/{p}")
        ok_all = False
        continue
    en = Path(en_p).read_text(encoding="utf-8")
    ko = Path(ko_p).read_text(encoding="utf-8")
    a, b = stats(en), stats(ko)
    issues = [
        k for k in ("headings", "code_blocks", "mermaid", "table_rows") if a[k] != b[k]
    ]
    if a["levels"] != b["levels"] and "headings" not in issues:
        issues.append("heading_levels")
    missing_code = set(code_lines(en)) - set(code_lines(ko))
    hdr = "i18n-source-sha" in ko
    status = "OK" if not issues and len(missing_code) <= 0 else "DIFF"
    if status != "OK":
        ok_all = False
    print(
        f"{status} {p}: "
        + ", ".join(
            f"{k} en={a[k]} ko={b[k]}"
            for k in ("headings", "code_blocks", "mermaid", "table_rows")
        )
        + f", code_lines_not_verbatim={len(missing_code)}"
    )
    if issues and "headings" in issues or "heading_levels" in issues:
        import difflib

        for d in list(difflib.unified_diff(a["levels"], b["levels"], lineterm="", n=0))[
            2:12
        ]:
            print("    level-diff", d)
    for c in list(missing_code)[:5]:
        print("    code not verbatim in ko:", c[:100])
sys.exit(0 if ok_all else 1)
