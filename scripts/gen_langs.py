#!/usr/bin/env python3
"""Gera langs-dark.svg e langs-light.svg a partir das linguagens dos repos públicos.

Sem dependências externas — só a stdlib. Roda no CI (.github/workflows/update-langs.yml)
ou local:  GITHUB_TOKEN=$(gh auth token) python3 scripts/gen_langs.py
"""

import html
import json
import os
import sys
import urllib.error
import urllib.request
from collections import Counter

USER = os.environ.get("GH_USER", "MatheusRibeir098")
SKIP_REPOS = {USER}  # o próprio repo de perfil não conta
MIN_PCT = 1.0  # abaixo disso, agrupa em "Outros"

# Cores oficiais do linguist (github/linguist/lib/linguist/languages.yml)
LANG_COLORS = {
    "TypeScript": "#3178c6",
    "JavaScript": "#f1e05a",
    "Python": "#3572A5",
    "Java": "#b07219",
    "Shell": "#89e051",
    "HTML": "#e34c26",
    "CSS": "#663399",
    "C#": "#178600",
    "Go": "#00ADD8",
    "Rust": "#dea584",
    "Ruby": "#701516",
    "PHP": "#4F5D95",
    "Dockerfile": "#384d54",
    "Makefile": "#427819",
    "Vue": "#41b883",
    "Svelte": "#ff3e00",
}
OTHER_COLOR = "#8b949e"

THEMES = {
    "dark": {
        "bg": "#0D1117", "stroke": "#30363D", "title": "#7C3AED",
        "text": "#C9D1D9", "muted": "#8B949E", "track": "#21262D",
    },
    "light": {
        "bg": "#FFFFFF", "stroke": "#D0D7DE", "title": "#6D28D9",
        "text": "#24292F", "muted": "#57606A", "track": "#EAEEF2",
    },
}


def api(path):
    req = urllib.request.Request(
        f"https://api.github.com{path}",
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"{USER}-langs-graph",
        },
    )
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def collect():
    totals = Counter()
    repos_counted = 0
    page = 1
    while True:
        batch = api(f"/users/{USER}/repos?per_page=100&page={page}&type=owner")
        if not batch:
            break
        for repo in batch:
            if repo["fork"] or repo["name"] in SKIP_REPOS:
                continue
            try:
                langs = api(f"/repos/{USER}/{repo['name']}/languages")
            except urllib.error.HTTPError as e:
                print(f"  ! pulando {repo['name']}: HTTP {e.code}", file=sys.stderr)
                continue
            if langs:
                totals.update(langs)
                repos_counted += 1
        page += 1
    return totals, repos_counted


def bucket(totals):
    """Converte bytes em fatias com percentual, agrupando as menores em 'Outros'."""
    grand = sum(totals.values())
    if not grand:
        return []
    slices, other = [], 0.0
    for name, count in totals.most_common():
        pct = count / grand * 100
        if pct < MIN_PCT:
            other += pct
        else:
            slices.append((name, pct, LANG_COLORS.get(name, OTHER_COLOR)))
    if other >= 0.05:
        slices.append(("Outros", other, OTHER_COLOR))
    return slices


def render(slices, repos_counted, theme_name):
    t = THEMES[theme_name]
    W, PAD = 840, 28
    BAR_Y, BAR_H, BAR_W = 86, 26, W - PAD * 2
    COLS = 3
    rows = (len(slices) + COLS - 1) // COLS
    LEG_Y, ROW_H = BAR_Y + BAR_H + 34, 30
    H = LEG_Y + rows * ROW_H + 14

    p = []
    p.append(
        f"<svg xmlns='http://www.w3.org/2000/svg' width='{W}' height='{H}' "
        f"viewBox='0 0 {W} {H}' role='img' "
        f"aria-label='Distribuicao de linguagens de {USER}'>"
    )
    p.append(
        "<style>"
        "text{font-family:'Segoe UI',Ubuntu,Helvetica,Arial,sans-serif}"
        ".t{font-size:19px;font-weight:600}"
        ".s{font-size:12px}"
        ".l{font-size:13.5px;font-weight:500}"
        ".p{font-size:13.5px}"
        "</style>"
    )
    p.append(
        f"<rect x='0.5' y='0.5' width='{W - 1}' height='{H - 1}' rx='10' "
        f"fill='{t['bg']}' stroke='{t['stroke']}'/>"
    )
    p.append(f"<text class='t' x='{PAD}' y='40' fill='{t['title']}'>Linguagens mais usadas</text>")
    p.append(
        f"<text class='s' x='{PAD}' y='62' fill='{t['muted']}'>"
        f"agregado de {repos_counted} repositórios públicos</text>"
    )

    # barra empilhada, com as fatias recortadas pelos cantos arredondados
    p.append(
        f"<clipPath id='bar'><rect x='{PAD}' y='{BAR_Y}' width='{BAR_W}' "
        f"height='{BAR_H}' rx='{BAR_H / 2}'/></clipPath>"
    )
    p.append(
        f"<rect x='{PAD}' y='{BAR_Y}' width='{BAR_W}' height='{BAR_H}' "
        f"rx='{BAR_H / 2}' fill='{t['track']}'/>"
    )
    p.append(f"<g clip-path='url(#bar)'>")
    x = float(PAD)
    for name, pct, color in slices:
        w = BAR_W * pct / 100
        p.append(
            f"<rect x='{x:.2f}' y='{BAR_Y}' width='{w:.2f}' height='{BAR_H}' fill='{color}'>"
            f"<title>{html.escape(name)} {pct:.1f}%</title></rect>"
        )
        x += w
    p.append("</g>")

    # legenda em grade
    col_w = BAR_W / COLS
    for i, (name, pct, color) in enumerate(slices):
        cx = PAD + (i % COLS) * col_w
        cy = LEG_Y + (i // COLS) * ROW_H
        p.append(f"<circle cx='{cx + 7:.1f}' cy='{cy:.1f}' r='6.5' fill='{color}'/>")
        p.append(
            f"<text class='l' x='{cx + 22:.1f}' y='{cy + 5:.1f}' fill='{t['text']}'>"
            f"{html.escape(name)}</text>"
        )
        p.append(
            f"<text class='p' x='{cx + col_w - 20:.1f}' y='{cy + 5:.1f}' "
            f"fill='{t['muted']}' text-anchor='end'>{pct:.1f}%</text>"
        )

    p.append("</svg>")
    return "".join(p)


def main():
    totals, repos_counted = collect()
    slices = bucket(totals)
    if not slices:
        print("nenhuma linguagem encontrada — abortando sem escrever", file=sys.stderr)
        return 1
    for theme in THEMES:
        path = f"langs-{theme}.svg"
        with open(path, "w", encoding="utf-8") as f:
            f.write(render(slices, repos_counted, theme))
        print(f"escrito {path}")
    print(f"\n{repos_counted} repos, {sum(totals.values()):,} bytes")
    for name, pct, _ in slices:
        print(f"  {name:14} {pct:5.1f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
