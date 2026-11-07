"""Builds the publishing guides 2027 decks.

Each deck is a JSON file in decks/. The build writes, for every deck,
docs/<slug>/index.html (the deck as a readable web page, one section per
slide) and docs/<slug>/<slug>.pdf (the same slides, 1280 x 720 px per page),
plus the hub page docs/index.html, sitemap.xml and robots.txt.

    python build.py            # HTML only
    python build.py --pdf      # HTML, PDF and the overflow check per slide
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DECKS = ROOT / "decks"
DOCS = ROOT / "docs"
BASE_URL = "https://orbita-media.github.io/publishing-guides-2027"

LATIN = ("U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, "
         "U+0304, U+0308, U+0329, U+2000-206F, U+20AC, U+2122, U+2191, U+2193, "
         "U+2212, U+2215, U+FEFF, U+FFFD")
LATIN_EXT = ("U+0100-02BA, U+02BD-02C5, U+02C7-02CC, U+02CE-02D7, U+02DD-02FF, "
             "U+0304, U+0308, U+0329, U+1D00-1DBF, U+1E00-1E9F, U+1EF2-1EFF, U+2020, "
             "U+20A0-20AB, U+20AD-20C0, U+2113, U+2C60-2C7F, U+A720-A7FF")

# Brand themes. Colours and fonts are taken from the brands' live sites.
THEMES = {
    "shelf": {
        "name": "Shelf Publisher",
        "site": "https://shelfpublisher.com",
        "display": "Sora", "body": "Manrope",
        "fonts": [("Sora", "sora-latin.woff2", "400 800", LATIN),
                  ("Sora", "sora-latin-ext.woff2", "400 800", LATIN_EXT),
                  ("Manrope", "manrope-latin.woff2", "200 800", LATIN),
                  ("Manrope", "manrope-latin-ext.woff2", "200 800", LATIN_EXT)],
        "ink": "#0B1220", "dark": "#071232", "accent": "#2A5BFF", "accent2": "#16C8F0",
        "soft": "#EEF3FF", "line": "#E7EBF4", "muted": "#5A6584", "paper": "#FFFFFF",
        "on_dark_muted": "#AEB9D6", "dark_card": "#0F1E4D",
    },
    "pageseal": {
        "name": "Pageseal",
        "site": "https://pageseal.app",
        "display": "Plus Jakarta Sans", "body": "Inter",
        "fonts": [("Plus Jakarta Sans", "plus-jakarta-sans.woff2", "600 800", None),
                  ("Inter", "inter.woff2", "400 700", None)],
        "ink": "#11302C", "dark": "#0B2F2B", "accent": "#137A6C", "accent2": "#F2C14E",
        "soft": "#EAF2EF", "line": "#D5E3DE", "muted": "#4C6661", "paper": "#FFFFFF",
        "on_dark_muted": "#A9C4BD", "dark_card": "#14514A",
    },
    "orbita": {
        "name": "Orbita Media",
        "site": "https://orbita-media.de",
        "display": "Instrument Sans", "body": "Instrument Sans",
        "fonts": [("Instrument Sans", "instrument-sans-normal-latin.woff2", "400 700", LATIN),
                  ("Instrument Sans", "instrument-sans-normal-latin-ext.woff2", "400 700", LATIN_EXT)],
        "ink": "#211A12", "dark": "#211A12", "accent": "#C08A28", "accent2": "#E3B866",
        "soft": "#F7F0E4", "line": "#E8DCC8", "muted": "#6B5F51", "paper": "#FFFDF9",
        "on_dark_muted": "#CDBFA9", "dark_card": "#3A2E20",
    },
}

UI = {
    "en": {"answer": "Short answer", "slides": "slides", "updated": "Updated",
           "pdf": "Download the slides (PDF)", "by": "A presentation by",
           "more": "More guides 2027", "hub_title": "Publishing guides 2027",
           "hub_lead": "Free presentations for authors, creators and publishers who plan their next book in 2027. "
                       "Each deck answers one question in full, with sources.",
           "sources": "Sources", "slide": "Slide", "read": "Read online",
           "months": ["January", "February", "March", "April", "May", "June", "July",
                      "August", "September", "October", "November", "December"]},
    "de": {"answer": "Kurze Antwort", "slides": "Folien", "updated": "Stand",
           "pdf": "Folien herunterladen (PDF)", "by": "Eine Präsentation von",
           "more": "Weitere Ratgeber 2027", "hub_title": "Publishing-Ratgeber 2027",
           "hub_lead": "Kostenlose Präsentationen für Autorinnen, Autoren und Creator, die ihr nächstes Buch 2027 planen.",
           "sources": "Quellen", "slide": "Folie", "read": "Online lesen",
           "months": ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
                      "August", "September", "Oktober", "November", "Dezember"]},
}

INLINE_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
BOLD = re.compile(r"\*\*(.+?)\*\*")


def md(text: str) -> str:
    """Escape, then allow **bold** and [label](https://url)."""
    out = html.escape(text or "", quote=False)
    out = BOLD.sub(r"<strong>\1</strong>", out)
    return INLINE_LINK.sub(lambda m: f'<a href="{html.escape(m.group(2))}">{m.group(1)}</a>', out)


def plain(text: str) -> str:
    text = INLINE_LINK.sub(r"\1", text or "")
    return BOLD.sub(r"\1", text)


def fmt_date(iso: str, lang: str) -> str:
    d = dt.date.fromisoformat(iso)
    month = UI[lang]["months"][d.month - 1]
    return f"{d.day}. {month} {d.year}" if lang == "de" else f"{d.day} {month} {d.year}"


STATIC_WEIGHTS = (400, 600, 700, 800)


def static_instance(file: str, weight: int) -> str:
    """A static instance of a variable font at one weight.

    Chromium embeds variable fonts as Type 3 in a PDF, which makes the slide
    text unsearchable for Google and for slide platforms; static instances are
    embedded as real fonts with a text layer.
    """
    out_dir = DOCS / "assets" / "fonts" / "static"
    name = f"{Path(file).stem}-w{weight}.woff2"
    target = out_dir / name
    if not target.exists():
        from fontTools.ttLib import TTFont
        from fontTools.varLib import instancer
        out_dir.mkdir(parents=True, exist_ok=True)
        font = TTFont(DOCS / "assets" / "fonts" / file)
        static = instancer.instantiateVariableFont(font, {"wght": weight}, updateFontNames=False)
        static.flavor = "woff2"
        static.save(target)
    return f"static/{name}"


def font_css(theme: dict, prefix: str) -> str:
    rules = []
    for family, file, weight, rng in theme["fonts"]:
        r = f"unicode-range:{rng};" if rng else ""
        lo, hi = (int(x) for x in weight.split())
        for w in STATIC_WEIGHTS:
            if lo <= w <= hi:
                rules.append(f"@font-face{{font-family:'{family}';src:url({prefix}assets/fonts/{static_instance(file, w)}) "
                             f"format('woff2');font-weight:{w};font-style:normal;font-display:swap;{r}}}")
    return "\n".join(rules)


# ── Slides ───────────────────────────────────────────────────────────────────

def slide_html(s: dict, i: int, total: int, deck: dict, theme: dict, ui: dict) -> str:
    kind = s["type"]
    kicker = f'<p class="kicker">{md(s["kicker"])}</p>' if s.get("kicker") else ""
    lead = f'<p class="lead">{md(s["lead"])}</p>' if s.get("lead") else ""
    tag = "h1" if kind == "cover" else "h2"
    title = f'<{tag} class="title">{md(s["title"])}</{tag}>'
    body = ""

    if kind == "cover":
        body = (f'<div class="answer"><p class="answer-label">{ui["answer"]}</p>'
                f'<p class="answer-text">{md(s["answer"])}</p></div>')
    elif kind == "points":
        items = s["items"]
        cols = min(len(items), 4) if len(items) != 4 else 2
        cards = "".join(
            f'<div class="card"><h3>{md(it["h"])}</h3><p>{md(it["t"])}</p></div>' for it in items)
        body = f'<div class="grid cols-{cols}">{cards}</div>'
    elif kind == "steps":
        rows = "".join(
            f'<li><span class="num">{n:02d}</span><div><h3>{md(it["h"])}</h3><p>{md(it["t"])}</p></div></li>'
            for n, it in enumerate(s["items"], start=s.get("start", 1)))
        cls = " two" if len(s["items"]) > 3 else ""
        body = f'<ol class="steps{cls}">{rows}</ol>'
    elif kind == "stats":
        tiles = "".join(
            f'<div class="stat"><p class="value">{md(it["value"])}</p><p class="label">{md(it["label"])}</p></div>'
            for it in s["items"])
        note = f'<p class="note">{md(s["note"])}</p>' if s.get("note") else ""
        body = f'<div class="stats cols-{len(s["items"])}">{tiles}</div>{note}'
    elif kind == "checklist":
        rows = "".join(f"<li>{md(t)}</li>" for t in s["items"])
        cls = " two" if len(s["items"]) > 4 else ""
        body = f'<ul class="checks{cls}">{rows}</ul>'
    elif kind == "split":
        def col(c, cls):
            li = "".join(f"<li>{md(t)}</li>" for t in c["items"])
            return f'<div class="col {cls}"><h3>{md(c["h"])}</h3><ul>{li}</ul></div>'
        body = f'<div class="split">{col(s["left"], "left")}{col(s["right"], "right")}</div>'
    elif kind == "faq":
        rows = "".join(f'<div class="qa"><h3>{md(it["q"])}</h3><p>{md(it["a"])}</p></div>' for it in s["items"])
        body = f'<div class="faq">{rows}</div>'
    elif kind == "statement":
        body = f'<p class="statement">{md(s["text"])}</p>'
        if s.get("source"):
            body += f'<p class="note">{md(s["source"])}</p>'
    elif kind == "cta":
        links = "".join(f'<li><a href="{html.escape(l["url"])}">{md(l["label"])}</a></li>'
                        for l in s.get("links", []))
        body = (f'<p class="button-row"><a class="button" href="{html.escape(s["button"]["url"])}">'
                f'{md(s["button"]["label"])}</a></p>' + (f'<ul class="links">{links}</ul>' if links else ""))
    elif kind == "sources":
        rows = "".join(f'<li><a href="{html.escape(l["url"])}">{md(l["label"])}</a></li>' for l in s["items"])
        body = f'<ol class="sources">{rows}</ol>'
    else:
        raise ValueError(f"unknown slide type {kind!r} in {deck['slug']}")

    dark = " dark" if kind in ("cover", "cta", "statement") else ""
    foot_site = deck.get("site", theme["site"]).replace("https://", "")
    return (f'<section class="slide s-{kind}{dark}" id="slide-{i}" aria-label="{ui["slide"]} {i}">'
            f'<div class="frame"><header class="bar"><span class="brand">{theme["name"]}</span>'
            f'<span class="count">{i:02d} / {total:02d}</span></header>'
            f'<div class="content">{kicker}{title}{lead}{body}</div>'
            f'<footer class="bar foot"><span>{md(deck["short_title"])}</span><span>{foot_site}</span></footer>'
            f'</div></section>')


CSS = """
:root{--ink:%(ink)s;--dark:%(dark)s;--accent:%(accent)s;--accent2:%(accent2)s;--soft:%(soft)s;
--line:%(line)s;--muted:%(muted)s;--paper:%(paper)s;--odm:%(on_dark_muted)s;--dcard:%(dark_card)s;
--display:'%(display)s',system-ui,sans-serif;--body:'%(body)s',system-ui,sans-serif}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%%}
body{margin:0;background:var(--soft);color:var(--ink);font-family:var(--body);line-height:1.5;
font-variant-ligatures:no-contextual}
a{color:var(--accent)}
.page{max-width:1120px;margin:0 auto;padding:28px 18px 64px}
.top{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:18px;
font-size:15px}
.top a{text-decoration:none;font-weight:600}
.meta{color:var(--muted);font-size:15px;margin:0 0 22px}
.meta a{font-weight:600}
.deck{display:flex;flex-direction:column;gap:22px}
.slide{container-type:inline-size;width:100%%;aspect-ratio:16/9;background:var(--paper);border:1px solid var(--line);
border-radius:14px;overflow:hidden}
.frame{position:relative;width:100%%;height:100%%;display:flex;flex-direction:column;padding:3.4cqw 4.4cqw 2.6cqw}
.bar{display:flex;justify-content:space-between;align-items:center;font-size:1.25cqw;color:var(--muted);
letter-spacing:.02em}
.bar .brand{font-family:var(--display);font-weight:700;color:var(--ink);font-size:1.45cqw}
.foot{margin-top:auto;padding-top:1.4cqw;border-top:1px solid var(--line)}
.content{flex:1;display:flex;flex-direction:column;justify-content:center;min-height:0;padding:1.6cqw 0}
.kicker{margin:0 0 1cqw;font-size:1.35cqw;font-weight:700;text-transform:uppercase;letter-spacing:.12em;color:var(--accent)}
.title{margin:0;font-family:var(--display);font-weight:700;font-size:3.5cqw;line-height:1.12;letter-spacing:-.015em;
max-width:88%%}
h1.title{font-size:4.6cqw;max-width:92%%}
.lead{margin:1.3cqw 0 0;font-size:1.75cqw;color:var(--muted);max-width:82%%;line-height:1.45}
.content p,.content li{hyphens:none}
.grid{display:grid;gap:1.6cqw;margin-top:2.4cqw}
.grid.cols-1{grid-template-columns:1fr}.grid.cols-2{grid-template-columns:1fr 1fr}
.grid.cols-3{grid-template-columns:repeat(3,1fr)}
.card{background:var(--soft);border-radius:1.1cqw;padding:1.8cqw 2cqw;border-top:.35cqw solid var(--accent)}
.card h3{margin:0 0 .6cqw;font-family:var(--display);font-size:1.75cqw;line-height:1.25}
.card p{margin:0;font-size:1.45cqw;line-height:1.45;color:var(--ink)}
.steps{list-style:none;margin:2.2cqw 0 0;padding:0;display:grid;gap:1.4cqw}
.steps.two{grid-template-columns:1fr 1fr;column-gap:3cqw}
.steps li{display:flex;gap:1.5cqw;align-items:flex-start}
.steps .num{flex:0 0 auto;font-family:var(--display);font-weight:800;font-size:1.9cqw;color:var(--paper);
background:var(--accent);border-radius:.8cqw;width:4.2cqw;height:4.2cqw;display:flex;align-items:center;justify-content:center}
.steps h3{margin:.2cqw 0 .3cqw;font-family:var(--display);font-size:1.7cqw;line-height:1.25}
.steps p{margin:0;font-size:1.42cqw;line-height:1.45;color:var(--muted)}
.stats{display:grid;gap:2cqw;margin-top:2.6cqw}
.stats.cols-2{grid-template-columns:1fr 1fr}.stats.cols-3{grid-template-columns:repeat(3,1fr)}
.stats.cols-4{grid-template-columns:repeat(4,1fr)}.stats.cols-1{grid-template-columns:1fr}
.stat{border-left:.45cqw solid var(--accent);padding:.4cqw 0 .4cqw 1.6cqw}
.stat .value{margin:0;font-family:var(--display);font-weight:800;font-size:4.4cqw;line-height:1.05;color:var(--accent)}
.stat .label{margin:.7cqw 0 0;font-size:1.45cqw;line-height:1.4}
.note{margin:2.2cqw 0 0;font-size:1.25cqw;color:var(--muted);max-width:85%%}
.checks{list-style:none;margin:2.2cqw 0 0;padding:0;display:grid;gap:1.1cqw}
.checks.two{grid-template-columns:1fr 1fr;column-gap:3cqw}
.checks li{position:relative;padding-left:3cqw;font-size:1.6cqw;line-height:1.4}
.checks li:before{content:"";position:absolute;left:0;top:.35cqw;width:1.6cqw;height:1.6cqw;border-radius:50%%;
background:var(--accent)}
.checks li:after{content:"";position:absolute;left:.52cqw;top:.62cqw;width:.45cqw;height:.8cqw;
border:solid var(--paper);border-width:0 .22cqw .22cqw 0;transform:rotate(45deg)}
.split{display:grid;grid-template-columns:1fr 1fr;gap:2cqw;margin-top:2.4cqw}
.split .col{border-radius:1.1cqw;padding:2cqw 2.2cqw}
.split .left{background:var(--soft)}
.split .right{background:var(--dark);color:#fff}
.split h3{margin:0 0 1cqw;font-family:var(--display);font-size:1.9cqw}
.split .right h3{color:var(--accent2)}
.split ul{margin:0;padding-left:2cqw}
.split li{font-size:1.5cqw;line-height:1.45;margin:.5cqw 0}
.faq{display:grid;grid-template-columns:1fr 1fr;gap:1.6cqw 3cqw;margin-top:2.2cqw}
.qa h3{margin:0 0 .5cqw;font-family:var(--display);font-size:1.65cqw;line-height:1.3}
.qa p{margin:0;font-size:1.4cqw;line-height:1.45;color:var(--muted)}
.sources{margin:2cqw 0 0;padding-left:2.4cqw;columns:2;column-gap:3cqw}
.sources li{font-size:1.3cqw;line-height:1.4;margin:0 0 .8cqw;break-inside:avoid}
.sources a{color:var(--ink);text-decoration-color:var(--accent)}
.dark{background:var(--dark);border-color:var(--dark)}
.dark .frame{color:#fff}
.dark .bar{color:var(--odm)}.dark .bar .brand{color:#fff}
.dark .foot{border-top-color:var(--dcard)}
.dark .lead{color:var(--odm)}
.dark .kicker{color:var(--accent2)}
.answer{margin-top:2.6cqw;background:var(--dcard);border-left:.5cqw solid var(--accent2);border-radius:1cqw;
padding:1.8cqw 2.2cqw;max-width:86%%}
.answer-label{margin:0 0 .5cqw;font-size:1.25cqw;font-weight:700;text-transform:uppercase;letter-spacing:.12em;
color:var(--accent2)}
.answer-text{margin:0;font-size:1.9cqw;line-height:1.45;color:#fff}
.answer-text a,.dark a{color:#fff}
.statement{margin:2cqw 0 0;font-family:var(--display);font-size:3cqw;line-height:1.3;max-width:88%%;color:#fff}
.dark .note{color:var(--odm)}
.button-row{margin:2.8cqw 0 0}
.button{display:inline-block;background:var(--accent2);color:var(--dark)!important;text-decoration:none;
font-weight:800;font-size:1.8cqw;padding:1.3cqw 2.4cqw;border-radius:.9cqw}
.links{list-style:none;margin:2.2cqw 0 0;padding:0;display:flex;flex-wrap:wrap;gap:1cqw 2.6cqw}
.links li{font-size:1.45cqw}.links a{color:#fff;text-decoration-color:var(--accent2)}
.about{margin-top:34px;background:var(--paper);border:1px solid var(--line);border-radius:14px;padding:22px 24px}
.about h2{margin:0 0 8px;font-family:var(--display);font-size:20px}
.about p{margin:0 0 10px}
.about ul{margin:0;padding-left:20px}
.hub h1{font-family:var(--display);font-size:clamp(28px,5vw,44px);line-height:1.15;margin:8px 0 10px}
.hub .intro{color:var(--muted);max-width:720px;font-size:17px}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:18px;margin-top:26px}
.tile{display:block;background:var(--paper);border:1px solid var(--line);border-radius:14px;padding:20px;text-decoration:none;
color:var(--ink)}
.tile .b{font-size:13px;font-weight:700;text-transform:uppercase;letter-spacing:.1em;color:var(--accent)}
.tile h2{font-family:var(--display);font-size:20px;line-height:1.25;margin:8px 0}
.tile p{margin:0;color:var(--muted);font-size:15px}
@media screen and (max-width:700px){
 .page{padding:18px 12px 48px}.deck{gap:14px}
 .slide{aspect-ratio:auto;border-radius:12px}
 .frame{padding:16px 16px 12px}
 .bar{font-size:12px}.bar .brand{font-size:13px}
 .content{padding:14px 0}
 .kicker{font-size:12px;margin-bottom:6px}
 .title{font-size:22px;max-width:none}h1.title{font-size:27px}
 .lead{font-size:15px;max-width:none;margin-top:8px}
 .grid,.stats,.split,.faq,.steps.two,.checks.two{grid-template-columns:1fr!important}
 .grid{gap:10px;margin-top:14px}
 .card{padding:12px 14px;border-radius:10px;border-top-width:3px}.card h3{font-size:16px}.card p{font-size:14.5px}
 .steps{gap:12px;margin-top:14px}.steps li{gap:12px}
 .steps .num{width:32px;height:32px;font-size:14px;border-radius:8px}.steps h3{font-size:16px}.steps p{font-size:14.5px}
 .stats{gap:12px;margin-top:14px}.stat{border-left-width:3px;padding-left:12px}.stat .value{font-size:30px}.stat .label{font-size:14.5px}
 .note{font-size:13px;margin-top:12px;max-width:none}
 .checks{gap:8px;margin-top:14px}.checks li{font-size:15px;padding-left:26px}
 .checks li:before{width:16px;height:16px;top:3px}.checks li:after{left:5px;top:6px;width:5px;height:8px;border-width:0 2px 2px 0}
 .split{gap:10px;margin-top:14px}.split .col{padding:14px;border-radius:10px}.split h3{font-size:17px}
 .split ul{padding-left:18px}.split li{font-size:14.5px}
 .faq{gap:12px;margin-top:14px}.qa h3{font-size:16px}.qa p{font-size:14.5px}
 .sources{columns:1;padding-left:20px}.sources li{font-size:13.5px}
 .answer{padding:12px 14px;max-width:none;border-left-width:4px;border-radius:10px;margin-top:14px}
 .answer-label{font-size:12px}.answer-text{font-size:15.5px}
 .statement{font-size:21px;max-width:none}
 .button{font-size:15px;padding:12px 18px;border-radius:10px}.button-row{margin-top:16px}
 .links{gap:8px 16px;margin-top:14px}.links li{font-size:14.5px}
 .foot{padding-top:10px}
}
@media print{
 @page{size:1280px 720px;margin:0}
 body{background:#fff}
 .top,.meta,.about,.noprint{display:none!important}
 .page{max-width:none;padding:0;margin:0}
 .deck{display:block}
 .slide{width:1280px;height:720px;aspect-ratio:auto;border:0;border-radius:0;break-after:page;page-break-after:always}
 *{box-shadow:none!important}
}
"""


def page_css(theme: dict, prefix: str) -> str:
    return font_css(theme, prefix) + CSS % theme


def head(title: str, desc: str, canonical: str, lang: str, theme: dict, prefix: str, extra: str = "",
         alternates: list | None = None) -> str:
    alt = "".join(f'<link rel="alternate" hreflang="{h}" href="{u}">' for h, u in (alternates or []))
    return (f'<!doctype html><html lang="{lang}"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{html.escape(title)}</title><meta name="description" content="{html.escape(desc)}">'
            f'<link rel="canonical" href="{canonical}">{alt}'
            f'<meta property="og:type" content="article"><meta property="og:title" content="{html.escape(title)}">'
            f'<meta property="og:description" content="{html.escape(desc)}"><meta property="og:url" content="{canonical}">'
            f'<meta name="twitter:card" content="summary">'
            f'<style>{page_css(theme, prefix)}</style>{extra}</head>')


def build_deck(deck: dict, all_decks: list[dict]) -> str:
    theme = THEMES[deck["brand"]]
    lang = deck["lang"]
    ui = UI[lang]
    slides = deck["slides"]
    total = len(slides)
    url = f"{BASE_URL}/{deck['slug']}/"
    pdf_name = f"{deck['slug']}.pdf"
    body_slides = "".join(slide_html(s, i, total, deck, theme, ui) for i, s in enumerate(slides, 1))

    faq = [it for s in slides if s["type"] == "faq" for it in s["items"]]
    graph = [{
        "@type": "Article", "@id": url + "#article", "headline": plain(deck["title"]),
        "description": deck["description"], "inLanguage": lang, "url": url,
        "datePublished": deck["published"], "dateModified": deck["updated"],
        "author": {"@type": "Organization", "name": theme["name"], "url": deck.get("site", theme["site"])},
        "publisher": {"@type": "Organization", "name": "Orbita Media GmbH", "url": "https://orbita-media.de"},
        "about": deck["keyword"],
        "encoding": {"@type": "MediaObject", "contentUrl": url + pdf_name, "encodingFormat": "application/pdf"},
        "mainEntityOfPage": url,
    }]
    if faq:
        graph.append({"@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": plain(q["q"]),
             "acceptedAnswer": {"@type": "Answer", "text": plain(q["a"])}} for q in faq]})
    ld = '<script type="application/ld+json">' + json.dumps(
        {"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False) + "</script>"

    alternates = []
    other = next((d for d in all_decks if d["slug"] == deck.get("alternate")), None)
    if other:
        alternates = [(lang, url), (other["lang"], f"{BASE_URL}/{other['slug']}/")]

    others = [d for d in all_decks if d["slug"] != deck["slug"] and d["lang"] == lang][:4]
    more = "".join(f'<li><a href="../{d["slug"]}/">{html.escape(plain(d["title"]))}</a></li>' for d in others)
    about = (f'<aside class="about"><h2>{ui["by"]} {theme["name"]}</h2>'
             f'<p>{md(deck["about"])}</p>'
             + (f'<h2>{ui["more"]}</h2><ul>{more}</ul>' if more else "") + "</aside>")

    return (head(deck["seo_title"], deck["description"], url, lang, theme, "../", ld, alternates)
            + f'<body><div class="page"><nav class="top"><a href="../">{ui["hub_title"]}</a>'
            f'<a href="{deck.get("site", theme["site"])}">{theme["name"]}</a></nav>'
            f'<p class="meta">{ui["by"]} {theme["name"]} · {total} {ui["slides"]} · {ui["updated"]} '
            f'{fmt_date(deck["updated"], lang)} · <a href="{pdf_name}">{ui["pdf"]}</a></p>'
            f'<main class="deck">{body_slides}</main>{about}</div></body></html>')


def build_hub(decks: list[dict]) -> str:
    theme = THEMES["shelf"]
    ui = UI["en"]
    tiles = "".join(
        f'<a class="tile" href="{d["slug"]}/"><span class="b">{THEMES[d["brand"]]["name"]} · '
        f'{d["lang"].upper()}</span><h2>{html.escape(plain(d["title"]))}</h2>'
        f'<p>{html.escape(d["description"])}</p></a>' for d in decks)
    ld = '<script type="application/ld+json">' + json.dumps({
        "@context": "https://schema.org", "@type": "CollectionPage", "name": ui["hub_title"],
        "url": BASE_URL + "/", "description": ui["hub_lead"],
        "publisher": {"@type": "Organization", "name": "Orbita Media GmbH", "url": "https://orbita-media.de"},
        "hasPart": [{"@type": "Article", "headline": plain(d["title"]), "url": f"{BASE_URL}/{d['slug']}/"} for d in decks],
    }, ensure_ascii=False) + "</script>"
    return (head("Publishing guides 2027 – free presentations for authors and creators", ui["hub_lead"],
                 BASE_URL + "/", "en", theme, "", ld)
            + f'<body><div class="page hub"><nav class="top"><span>Orbita Media</span>'
            f'<a href="https://shelfpublisher.com">Shelf Publisher</a></nav>'
            f'<h1>{ui["hub_title"]}</h1><p class="intro">{ui["hub_lead"]}</p>'
            f'<div class="cards">{tiles}</div>'
            f'<aside class="about"><h2>Who makes these</h2><p>The presentations are written by the teams of '
            f'<a href="https://shelfpublisher.com">Shelf Publisher</a>, <a href="https://pageseal.app">Pageseal</a> '
            f'and <a href="https://orbitamediapublishing.com">Orbita Media</a>, a book publisher in Hamburg. '
            f'Free tools: <a href="https://orbita-media.github.io/book-spine-calculator/">Book spine width calculator</a>.'
            f'</p></aside></div></body></html>')


def load_decks() -> list[dict]:
    decks = []
    for f in sorted(DECKS.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        for key in ("slug", "lang", "brand", "title", "short_title", "seo_title", "description", "keyword",
                    "published", "updated", "about", "slides"):
            if key not in d:
                sys.exit(f"{f.name}: missing {key}")
        if d["slides"][0]["type"] != "cover":
            sys.exit(f"{f.name}: slide 1 must be the cover with the answer")
        decks.append(d)
    return decks


def render_pdfs(decks: list[dict]) -> int:
    from playwright.sync_api import sync_playwright
    problems = 0
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        for d in decks:
            src = (DOCS / d["slug"] / "index.html").as_uri()
            page.goto(src)
            page.emulate_media(media="print")
            page.evaluate("document.fonts.ready")
            over = page.evaluate("""() => [...document.querySelectorAll('.slide')].map((s,i)=>{
                const c=s.querySelector('.content'); const f=s.querySelector('.frame');
                const bad=[];
                if(c.scrollHeight>c.clientHeight+1) bad.push('content '+c.scrollHeight+'>'+c.clientHeight);
                if(f.scrollWidth>f.clientWidth+1) bad.push('width');
                return bad.length? (i+1)+': '+bad.join(', '):null}).filter(Boolean)""")
            for o in over:
                print(f"OVERFLOW {d['slug']} slide {o}")
                problems += 1
            fonts = page.evaluate("[...document.fonts].filter(f=>f.status==='loaded').map(f=>f.family)")
            if not fonts:
                print(f"FONTS not loaded in {d['slug']}")
                problems += 1
            page.pdf(path=str(DOCS / d["slug"] / f"{d['slug']}.pdf"), width="1280px", height="720px",
                     print_background=True, prefer_css_page_size=True)
            page.emulate_media(media="screen")
            print(f"pdf {d['slug']} ({len(d['slides'])} slides)")
        browser.close()
    return problems


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", action="store_true")
    ap.add_argument("--only", help="render the PDF of this slug only")
    args = ap.parse_args()
    decks = load_decks()
    for d in decks:
        out = DOCS / d["slug"]
        out.mkdir(parents=True, exist_ok=True)
        (out / "index.html").write_text(build_deck(d, decks), encoding="utf-8")
    (DOCS / "index.html").write_text(build_hub(decks), encoding="utf-8")
    today = max(d["updated"] for d in decks) if decks else dt.date.today().isoformat()
    urls = [(BASE_URL + "/", today)] + [(f"{BASE_URL}/{d['slug']}/", d["updated"]) for d in decks]
    (DOCS / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{u}</loc><lastmod>{m}</lastmod></url>\n" for u, m in urls) + "</urlset>\n",
        encoding="utf-8")
    (DOCS / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {BASE_URL}/sitemap.xml\n", encoding="utf-8")
    (DOCS / ".nojekyll").write_text("", encoding="utf-8")
    print(f"{len(decks)} decks built")
    targets = [d for d in decks if not args.only or d["slug"] == args.only]
    if args.pdf and render_pdfs(targets):
        sys.exit(1)


if __name__ == "__main__":
    main()
