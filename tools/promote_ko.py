#!/usr/bin/env python3
"""Turn a checkout of claude-howto (with ko/) into a Korean-only tree.

Run inside a clean worktree of the docs/ko-translation branch:

    python3 tools/promote_ko.py            # rewrites the tree in place

What it does
1. Deletes the English .md docs and the other translation trees (vi/ zh/ uk/ ja/),
   keeping code/config/assets (scripts, hooks, JSON, images) from English.
2. Moves every file under ko/ to the repo root.
3. Rewrites relative links so they still resolve from the new location.
   Links that pointed at English docs or other languages become absolute
   links to the upstream repository.
4. Localizes the website builder (nav labels, <html lang>, UI strings) and points
   repo links / Pages workflow at this fork's `ko` branch.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path.cwd()
KO = ROOT / "ko"
UPSTREAM = "https://github.com/luongnv89/claude-howto/blob/main"
FORK = "https://github.com/leesk212/claude-howto-ko"
BRANCH = "ko"
OTHER_LANGS = ["vi", "zh", "uk", "ja"]
# English-only material that has no Korean counterpart and isn't needed
DROP_DIRS = ["docs", "local-progress", "prompts", "slides"]
DROP_FILES = ["coverage.xml"]

assert KO.is_dir(), "run from the repo root of docs/ko-translation"


def git(*a: str) -> str:
    return subprocess.run(
        ["git", *a], check=True, capture_output=True, text=True
    ).stdout


tracked = [Path(p) for p in git("ls-files").splitlines()]
ko_files = [p for p in tracked if p.parts[0] == "ko"]
ko_targets = {Path(*p.parts[1:]) for p in ko_files}

# --- 1. delete English docs + other languages -------------------------------
for p in tracked:
    top = p.parts[0]
    if top == "ko" or top.startswith("."):
        continue  # keep ko/ and dotfiles/dot-dirs (.github, .claude, configs)
    if top in OTHER_LANGS or top in DROP_DIRS or str(p) in DROP_FILES:
        (ROOT / p).unlink(missing_ok=True)
        continue
    if p.suffix == ".md" and p in ko_targets:
        (ROOT / p).unlink()  # replaced by the Korean version
    elif (
        p.suffix == ".md"
        and top not in ("scripts", "resources")
        and not top.startswith("0")
        and top != "10-cli"
    ):
        (ROOT / p).unlink()  # English-only top-level doc with no translation

# --- 2/3. move ko/* to root and rewrite links --------------------------------
LINK_RE = re.compile(r"(\]\()([^)\s]+)((?:\s+\"[^\"]*\")?\))")
ATTR_RE = re.compile(r'((?:src|srcset|href)=")([^"]+)(")')
FENCE_RE = re.compile(r"^\s*(```|~~~)")


def upstream_url(rel: Path, frag: str) -> str:
    """Absolute link to the upstream repo; README.md links become folder URLs."""
    s = rel.as_posix()
    if s == "README.md":
        return "https://github.com/luongnv89/claude-howto" + frag
    if s.endswith("/README.md"):
        return f"https://github.com/luongnv89/claude-howto/tree/main/{s[: -len('/README.md')]}{frag}"
    return f"{UPSTREAM}/{s}{frag}"


def remap(target: str, old_file: Path, new_file: Path) -> str:
    if re.match(r"^(https?:|mailto:|data:|#)", target):
        return target
    path, frag = (target.split("#", 1) + [""])[:2]
    frag = "#" + frag if frag else ""
    if not path:
        return target
    old_abs = (old_file.parent / path).resolve()
    try:
        rel_old = old_abs.relative_to(ROOT)
    except ValueError:
        return target
    if rel_old.parts and rel_old.parts[0] == "ko":
        new_abs = ROOT / Path(*rel_old.parts[1:])
    elif rel_old.parts and rel_old.parts[0] in OTHER_LANGS:
        return upstream_url(rel_old, frag)
    else:
        # points at an English file: keep if it survives, else link upstream
        new_abs = ROOT / rel_old
        if not new_abs.exists() and rel_old not in ko_targets:
            return upstream_url(rel_old, frag)
        if rel_old in ko_targets and rel_old.suffix == ".md":
            # English doc that now has the Korean file in its place: the
            # original target was the English page, so keep pointing upstream
            return upstream_url(rel_old, frag)
    out = os.path.relpath(new_abs, new_file.parent).replace(os.sep, "/")
    if path.endswith("/") and not out.endswith("/"):
        out += "/"
    return out + frag


def rewrite(text: str, old_file: Path, new_file: Path) -> str:
    lines, inside = [], False
    for line in text.split("\n"):
        if FENCE_RE.match(line):
            inside = not inside
            lines.append(line)
            continue
        if not inside:
            line = LINK_RE.sub(
                lambda m: (
                    m.group(1) + remap(m.group(2), old_file, new_file) + m.group(3)
                ),
                line,
            )
            line = ATTR_RE.sub(
                lambda m: (
                    m.group(1) + remap(m.group(2), old_file, new_file) + m.group(3)
                ),
                line,
            )
        lines.append(line)
    return "\n".join(lines)


for p in ko_files:
    old = ROOT / p
    new = ROOT / Path(*p.parts[1:])
    new.parent.mkdir(parents=True, exist_ok=True)
    data = old.read_text(encoding="utf-8")
    if p.suffix == ".md":
        data = rewrite(data, old, new)
    new.write_text(data, encoding="utf-8")
shutil.rmtree(KO)

# --- README banner -----------------------------------------------------------
readme = ROOT / "README.md"
t = readme.read_text(encoding="utf-8")
banner = (
    "> **한국어판 안내:** 이 저장소는 [luongnv89/claude-howto](https://github.com/luongnv89/claude-howto)의 "
    "한국어 번역판입니다. 원문은 MIT 라이선스로 배포되며, 번역 기준 버전은 각 문서 상단의 "
    "`i18n-source-sha` 주석에 기록되어 있습니다. 웹사이트 버전: <https://leesk212.github.io/claude-howto-ko/> · 오역 제보는 이 저장소의 Issue로 남겨 주세요.\n\n"
)
t = re.sub(
    r"(🌐 \*\*Language[^\n]*\n)", r"\1\n" + banner.replace("\\", "\\\\"), t, count=1
)
readme.write_text(t, encoding="utf-8")

# --- 4. website builder + Pages ---------------------------------------------
bw = ROOT / "scripts/build_website.py"
s = bw.read_text(encoding="utf-8")
labels = {
    '"Introduction"': '"소개"',
    '"Learning Roadmap"': '"학습 로드맵"',
    '"Quick Reference"': '"빠른 참조"',
    '"Claude Concepts Guide"': '"Claude 개념 가이드"',
    '"Slash Commands"': '"슬래시 명령어"',
    '"Memory"': '"메모리"',
    '"Skills"': '"스킬"',
    '"Subagents"': '"서브에이전트"',
    '"Hooks"': '"훅"',
    '"Plugins"': '"플러그인"',
    '"Checkpoints"': '"체크포인트"',
    '"Advanced Features"': '"고급 기능"',
    '"Resources"': '"참고 자료"',
}
nav_start = s.index('("README.md", "Introduction")')
nav_end = s.index("]", nav_start)
nav = s[nav_start:nav_end]
for k, v in labels.items():
    nav = nav.replace(k, v)
s = s[:nav_start] + nav + s[nav_end:]
s = s.replace(
    'REPO_URL = "https://github.com/luongnv89/claude-howto"', f'REPO_URL = "{FORK}"'
)
s = s.replace('DEFAULT_BRANCH = "main"', f'DEFAULT_BRANCH = "{BRANCH}"')
s = s.replace(
    'site_title: str = "Claude Code How-To Guide"',
    'site_title: str = "Claude Code 사용 가이드"',
)
s = s.replace(
    'landing=(args.lang == "en"),',
    "landing=False,  # Korean-only fork: README.md is the index, like other translated sites",
)
assert "landing=False" in s
bw.write_text(s, encoding="utf-8")

tw = ROOT / "scripts/tests/test_build_website.py"
tt = tw.read_text(encoding="utf-8")
tt = tt.replace(
    "    def test_landing_real_repo(",
    '    @pytest.mark.skip(reason="Korean-only fork: English landing roadmap does not apply")\n    def test_landing_real_repo(',
    1,
)
if "import pytest" not in tt:
    tt = "import pytest\n" + tt
tw.write_text(tt, encoding="utf-8")

for tpl in ("page.html.j2", "landing.html.j2"):
    f = ROOT / "scripts/website_templates" / tpl
    x = f.read_text(encoding="utf-8").replace('<html lang="en"', '<html lang="ko"')
    x = x.replace(">Edit on GitHub<", ">GitHub에서 편집<").replace(">Home<", ">홈<")
    f.write_text(x, encoding="utf-8")

pages = ROOT / ".github/workflows/pages.yml"
y = pages.read_text(encoding="utf-8").replace(
    "      - main\n", f"      - {BRANCH}\n", 1
)
pages.write_text(y, encoding="utf-8")
# workflows that only make sense upstream (multi-language releases / main-branch CI)
for wf in ("release.yml",):
    (ROOT / ".github/workflows" / wf).unlink(missing_ok=True)

print(f"promoted {len(ko_files)} Korean files to the repo root")
