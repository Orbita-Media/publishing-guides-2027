# Deck-Format (decks/<slug>.json)

Ein Deck = eine JSON-Datei in `decks/`. `python build.py --pdf --only <slug>` baut `docs/<slug>/index.html` und `docs/<slug>/<slug>.pdf` (1280 × 720 px je Folie) und meldet `OVERFLOW <slug> slide <n>`, wenn Text nicht auf eine Folie passt (Exit 1). Live: https://orbita-media.github.io/publishing-guides-2027/<slug>/

## Kopf
```json
{
  "slug": "how-to-get-your-book-into-bookstores-2027",   // Keyword im Pfad, Kleinbuchstaben, Bindestriche
  "lang": "en",                                         // en | de
  "brand": "shelf",                                     // shelf | pageseal | orbita
  "alternate": "buch-in-den-buchhandel-bringen-2027",   // optional: Slug der anderen Sprachfassung (hreflang)
  "title": "How to get your book into bookstores in 2027",  // H1 = Folie 1
  "short_title": "Get your book into bookstores 2027",  // Fußzeile jeder Folie, max. ~45 Zeichen
  "seo_title": "How to Get Your Book Into Bookstores in 2027 (Free Guide, 18 Slides)", // <title>, max. ~65 Zeichen
  "description": "…",                                   // Meta-Description, 140–160 Zeichen, Antwort drin
  "keyword": "how to get your book into bookstores 2027",
  "published": "2026-11-07", "updated": "2026-11-07",
  "about": "Ein Absatz unter dem Deck: wer wir sind, mit [Link](https://…).",
  "slides": [ … ]
}
```

## Folientypen (Text: `**fett**` und `[Label](https://url)` erlaubt)
| type | Felder | Grenzen, damit es passt |
|---|---|---|
| `cover` (Pflicht als Folie 1) | `kicker`, `title`, `answer` | answer = die Antwort auf die Suchfrage, 35–55 Wörter |
| `points` | `kicker`, `title`, `lead`, `items:[{h,t}]` (1–4; 4 = 2×2) | t ≤ 30 Wörter (bei 4 Karten ≤ 24) |
| `steps` | `kicker`, `title`, `lead`, `items:[{h,t}]` (2–6), optional `start` | t ≤ 22 Wörter; ab 4 zweispaltig |
| `stats` | `kicker`, `title`, `items:[{value,label}]` (1–4), `note` | value kurz („50,000+“), label ≤ 14 Wörter |
| `checklist` | `kicker`, `title`, `lead`, `items:[text]` (3–10) | je ≤ 14 Wörter; ab 5 zweispaltig |
| `split` | `kicker`, `title`, `left:{h,items}`, `right:{h,items}` | je 3–4 Punkte ≤ 14 Wörter; rechts = unser Weg (dunkel) |
| `faq` | `kicker`, `title`, `items:[{q,a}]` (2–4) | a ≤ 35 Wörter; landet auch im FAQPage-JSON-LD |
| `statement` | `kicker`, `title`, `text`, `source` | text ≤ 30 Wörter |
| `cta` | `kicker`, `title`, `lead`, `button:{label,url}`, `links:[{label,url}]` | vorletzte oder letzte Folie |
| `sources` | `title`, `items:[{label,url}]` | ≤ 12 Einträge |

`title` jeder Folie ≤ ~70 Zeichen, `lead` ≤ ~30 Wörter.
