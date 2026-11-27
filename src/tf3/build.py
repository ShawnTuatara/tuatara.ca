"""Build the Transport Fever 3 mods site (tuatara.ca/personal/shawn/gaming/tf3/).

    python src/tf3/build.py            public pages only  -> site/          (committed, deployed)
    python src/tf3/build.py --drafts   every mod, drafts marked -> build-preview/ (local preview)

Inputs (all in src/tf3/):
    content/site.toml          landing page, research cards, "find it" windows, install page
    content/mods/<slug>.toml   one page per mod (texts, figures, pins)
    mods/<slug>.json           each mod's settings, from sync_mods.py
    shots/<folder>/<id>.png    screenshot masters (converted to WebP with ffmpeg)
    assets/                    site.css, annotate.js, fonts
src/root/ holds the domain's own pages (tuatara.ca/ and its 404), copied as they are.

Python standard library only; ffmpeg must be on PATH for new or changed screenshots.
"""
from __future__ import annotations

import argparse
import hashlib
import datetime
import html
import json
import pathlib
import re
import shutil
import struct
import subprocess
import sys
import tomllib

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent.parent
ROOT_SRC = REPO / "src" / "root"
CACHE = HERE / ".cache"
TF3_PATH = "personal/shawn/gaming/tf3"
SITE_URL = "https://tuatara.ca/"
TF3_URL = SITE_URL + TF3_PATH + "/"

GROUPS = [
    ("enhancements", "Enhancements", "Additions to the game's own windows and features, one switch per feature."),
    ("tools", "Tools", "For players who run many mods: performance figures and a stutter fix."),
    ("bugfixes", "Bug fixes", "Work-arounds for game bugs, each removable once the game is fixed."),
]
STATUS = {
    "live": ("live", "On mod.io"),
    "soon": ("soon", "Coming soon"),
    "test": ("test", "In testing"),
}
WEBP_QUALITY = "90"

errors: list[str] = []
warnings: list[str] = []


def err(msg: str) -> None:
    errors.append(msg)


def warn(msg: str) -> None:
    warnings.append(msg)


# ---------------------------------------------------------------- text

def esc(s) -> str:
    return html.escape(str(s), quote=True)


def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def clean(s: str) -> str:
    """A settings tooltip as one line (the game wraps them with \\n)."""
    return re.sub(r"\s*\n\s*", " ", s or "").strip()


def asset_version(name: str) -> str:
    """A short hash of an asset, added to its link so browsers fetch a changed file at once (GitHub
    Pages lets them keep the old one 10 minutes: a new page with an old annotate.js broke its pair
    switches)."""
    return hashlib.sha256((HERE / "assets" / name).read_bytes()).hexdigest()[:10]


class Ctx:
    """The page being written: its path back to the tf3 root, and which mod pages exist."""
    prefix = ""
    visible: set[str] = set()
    pairs = 0  # before / after pairs written so far: their ids


INLINE = re.compile(r"`([^`]+)`|\*\*(.+?)\*\*|\[([^\]]+)\]\(([^)\s]+)\)")


def mod_href(target: str) -> str | None:
    """`mod:<slug>[#anchor]` -> a relative link, or None when that page isn't built."""
    slug, _, anchor = target[4:].partition("#")
    if slug not in Ctx.visible:
        return None
    return f"{Ctx.prefix}mods/{slug}/" + (f"#{anchor}" if anchor else "")


def md(s: str) -> str:
    """Inline markup: `code`, **bold**, [text](url); url may be mod:<slug>#anchor or page:<path>."""
    out, pos = [], 0
    for m in INLINE.finditer(s):
        out.append(esc(s[pos:m.start()]))
        if m.group(1) is not None:
            out.append(f"<code>{esc(m.group(1))}</code>")
        elif m.group(2) is not None:
            out.append(f"<b>{md(m.group(2))}</b>")
        else:
            text, url = m.group(3), m.group(4)
            if url.startswith("mod:"):
                href = mod_href(url)
                out.append(f'<a href="{esc(href)}">{md(text)}</a>' if href else md(text))
            elif url.startswith("page:"):
                out.append(f'<a href="{esc(Ctx.prefix + url[5:])}">{md(text)}</a>')
            else:
                out.append(f'<a href="{esc(url)}">{md(text)}</a>')
        pos = m.end()
    out.append(esc(s[pos:]))
    return "".join(out)


def paras(s: str, cls: str = "") -> str:
    c = f' class="{cls}"' if cls else ""
    return "".join(f"<p{c}>{md(p.strip())}</p>" for p in re.split(r"\n\s*\n", s or "") if p.strip())


def items(lst, ordered=False) -> str:
    tag = "ol" if ordered else "ul"
    return f"<{tag}>" + "".join(f"<li>{md(x)}</li>" for x in lst) + f"</{tag}>"


# ---------------------------------------------------------------- images

def image_size(path: pathlib.Path) -> tuple[int, int]:
    b = path.read_bytes()[:40]
    if b[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", b[16:24])
    if b[:4] == b"RIFF" and b[8:12] == b"WEBP":
        kind = b[12:16]
        if kind == b"VP8X":
            return 1 + int.from_bytes(b[24:27], "little"), 1 + int.from_bytes(b[27:30], "little")
        if kind == b"VP8 ":
            return struct.unpack("<H", b[26:28])[0] & 0x3FFF, struct.unpack("<H", b[28:30])[0] & 0x3FFF
        if kind == b"VP8L":
            bits = int.from_bytes(b[21:25], "little")
            return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    raise ValueError(f"{path}: not a PNG or WebP")


class Images:
    """Screenshot masters in shots/<folder>/; each one used is written once as img/<folder>/<id>.webp."""

    def __init__(self):
        self.used: dict[str, pathlib.Path] = {}

    def find(self, folder: str, ref: str):
        if "/" in ref:
            folder, ref = ref.split("/", 1)
        stem = ref.rsplit(".", 1)[0] if ref.endswith((".png", ".webp")) else ref
        for ext in (".png", ".webp"):
            p = HERE / "shots" / folder / (stem + ext)
            if p.exists():
                rel = f"img/{folder}/{stem}.webp"
                self.used[rel] = p
                w, h = image_size(p)
                return {"src": rel, "w": w, "h": h}
        return None

    def write(self, out_tf3: pathlib.Path) -> None:
        for rel, master in sorted(self.used.items()):
            cached = CACHE / rel
            if not cached.exists() or cached.stat().st_mtime < master.stat().st_mtime:
                cached.parent.mkdir(parents=True, exist_ok=True)
                if master.suffix == ".webp":
                    shutil.copyfile(master, cached)
                else:
                    r = subprocess.run(
                        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(master), "-c:v", "libwebp",
                         "-quality", WEBP_QUALITY, "-compression_level", "6", str(cached)],
                        capture_output=True, text=True)
                    if r.returncode:
                        err(f"ffmpeg failed on {master}: {r.stderr.strip()}")
                        continue
            if cached.stat().st_size > 700_000:
                warn(f"{rel} is {cached.stat().st_size // 1024} KB")
            dest = out_tf3 / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(cached, dest)


IMAGES = Images()


# ---------------------------------------------------------------- figures

def check_ann(where: str, fig: dict) -> None:
    seen = set()
    for p in fig.get("pins", []):
        if not (0 <= p["x"] <= 100 and 0 <= p["y"] <= 100):
            err(f"{where}: pin {p.get('n')} at {p['x']}, {p['y']} is outside the image")
        if p.get("n") in seen:
            err(f"{where}: pin number {p.get('n')} used twice")
        seen.add(p.get("n"))
    for b in fig.get("boxes", []):
        if b["x"] < 0 or b["y"] < 0 or b["x"] + b["w"] > 100.05 or b["y"] + b["h"] > 100.05:
            err(f"{where}: box {b} is outside the image")


def pending(fig: dict) -> str:
    return (f'<div class="pending"><b>{esc(fig.get("shot", "?"))}</b>'
            f'{md(fig.get("pending") or fig.get("caption") or "Screenshot to come.")}</div>')


# images at least this many times wider than tall, and wider than the room beside a legend (1080
# content - 280 legend - 24 gap), get their legend under them (figure()); a narrower strip fits beside
WIDE_RATIO = 3
ASIDE_MAX_W = 776


def pin_features(p: dict, where: str) -> list:
    """The features a pin names: `feature` / `features` (setting keys) or `anchor` (a string or a list)."""
    slug = p.get("mod")
    if not slug or slug not in MODS:
        return []
    keys = p.get("features") or ([p["feature"]] if p.get("feature") else [])
    anchors = p.get("anchor") or []
    anchors = [anchors] if isinstance(anchors, str) else anchors
    found = []
    for k in keys:
        f = next((f for f in MODS[slug].features if f.key == k), None)
        if f is None:
            err(f"{where}: pin {p.get('n')} names unknown feature {slug}.{k}")
        else:
            found.append(f)
    for a in anchors:
        f = next((f for f in MODS[slug].features if f.anchor == a), None)
        if f is None:
            err(f"{where}: pin {p.get('n')} names unknown anchor {slug}#{a}")
        else:
            found.append(f)
    return found


def figure(fig: dict, folder: str, drafts: bool, where: str, height_share: float = 1.0) -> str:
    img = IMAGES.find(folder, fig["shot"])
    if not img:
        if drafts:
            return pending(fig)
        err(f"{where}: screenshot {folder}/{fig['shot']} is missing")
        return ""
    pins = fig.get("pins", [])
    pins = [p for p in pins if not p.get("mod") or p["mod"] in Ctx.visible]
    check_ann(where, fig)
    boxes = fig.get("boxes", [])
    frame = ["shot-frame"] + (["dimmed"] if fig.get("dim") and boxes else [])
    parts = [f'<div class="{" ".join(frame)}">',
             f'<img src="{esc(Ctx.prefix + img["src"])}" width="{img["w"]}" height="{img["h"]}" '
             f'alt="{esc(fig.get("alt", ""))}" loading="lazy" decoding="async"'
             + (f' style="--hk:{height_share:.4f}"' if height_share < 1 else "") + '>']
    for b in boxes:
        parts.append(f'<div class="ann-box" style="left:{b["x"]}%;top:{b["y"]}%;width:{b["w"]}%;height:{b["h"]}%"></div>')
    # A figure whose every pin names a mod ("Find it in the game"): each mod a number in order of its
    # first pin, each of its pins a letter (1A, 1B, 2A, ...), and the legend grouped under the mods
    # (user, 2026-11-26)
    groups: list[tuple[str, list]] = []
    labels: dict[int, str] = {}
    if pins and all(p.get("mod") for p in pins):
        numbers: dict[str, int] = {}
        for p in sorted(pins, key=lambda q: q["n"]):
            if p["mod"] not in numbers:
                numbers[p["mod"]] = len(numbers) + 1
                groups.append((p["mod"], []))
            members = groups[numbers[p["mod"]] - 1][1]
            labels[id(p)] = f"{numbers[p['mod']]}{chr(ord('A') + len(members))}"
            members.append(p)

    def label(p: dict) -> str:
        return str(labels.get(id(p), p["n"]))

    # A pin's `area` is the part of the picture it is about, outlined while the pin or its legend line is
    # pointed at (user, 2026-11-26: highlight the areas)
    for p in pins:
        a = p.get("area")
        if a:
            if a["x"] < 0 or a["y"] < 0 or a["x"] + a["w"] > 100.05 or a["y"] + a["h"] > 100.05:
                err(f"{where}: pin {p.get('n')}'s area is outside the image")
            parts.append(f'<div class="ann-area" data-n="{label(p)}" style="left:{a["x"]}%;top:{a["y"]}%;width:{a["w"]}%;height:{a["h"]}%"></div>')
    for p in pins:
        parts.append(f'<span class="pin" data-n="{label(p)}" style="left:{p["x"]}%;top:{p["y"]}%" aria-hidden="true">{label(p)}</span>')
    parts.append("</div>")
    # Every figure the same way (user, 2026-11-25): the image, then beside it its caption and the
    # numbered legend, so a pin can be looked up without scrolling; stacked where the figure's box is
    # narrow (site.css, a container query on .shot-box).
    aside = []
    if fig.get("caption"):
        aside.append(f"<figcaption>{md(fig['caption'])}</figcaption>")
    if groups:
        aside.append('<ol class="legend grouped">')
        for number, (slug, members) in enumerate(groups, 1):
            name = MODS[slug].name
            href = mod_href(f"mod:{slug}")
            link = f'<a href="{esc(href)}">{esc(name)}</a>' if href else esc(name)
            aside.append(f'<li class="legend-mod"><span class="n">{number}</span><span>{link}</span></li>')
            for p in members:
                titles = []
                for feature in pin_features(p, where):
                    fhref = mod_href(f"mod:{slug}#{feature.anchor}")
                    titles.append(f'<a href="{esc(fhref)}">{esc(feature.title)}</a>' if fhref else esc(feature.title))
                feat = f'<span class="feat">{" · ".join(titles)}</span>' if titles else ""
                aside.append(f'<li data-n="{label(p)}"><span class="n">{label(p)}</span><span>{feat}{md(p["text"])}</span></li>')
        aside.append("</ol>")
    elif pins:
        aside.append('<ol class="legend">')
        for p in pins:
            mod = ""
            if p.get("mod"):
                label = p.get("mod_name") or MODS[p["mod"]].name
                href = mod_href(f"mod:{p['mod']}" + (f"#{p['anchor']}" if p.get("anchor") else ""))
                mod = f'<span class="mod">{f"<a href={chr(34)}{esc(href)}{chr(34)}>{esc(label)}</a>" if href else esc(label)}</span>'
            aside.append(f'<li data-n="{p["n"]}"><span class="n">{p["n"]}</span><span>{mod}{md(p["text"])}</span></li>')
        aside.append("</ol>")
    if aside:
        parts.append('<div class="shot-aside">' + "".join(aside) + "</div>")
    # a wide strip (a table row band, the game bar) keeps the full width, with the legend straight under
    # it in columns: beside it, the strip would shrink to a sliver
    # (`legend = "below"` asks for the same: a statistics half, readable only at the full width)
    wide = (img["w"] >= WIDE_RATIO * img["h"] and img["w"] > ASIDE_MAX_W) or fig.get("legend") == "below"
    cls = "shot" + (" has-aside" if aside else "") + (" wide" if aside and wide else "")
    return f'<div class="shot-box"><figure class="{cls}">' + "".join(parts) + "</figure></div>"


def figures(figs: list, folder: str, drafts: bool, where: str) -> str:
    out = []
    for i, fig in enumerate(figs):
        w = f"{where} figure {i + 1}"
        if "before" in fig:
            # the shorter half's height cap shrinks with it (site.css --hk), so a capped pair keeps one
            # scale and switching doesn't look like a zoom (user, 2026-11-25: LE-16-window)
            ia, ib = IMAGES.find(folder, fig["before"]["shot"]), IMAGES.find(folder, fig["after"]["shot"])
            tall = max(ia["h"] if ia else 1, ib["h"] if ib else 1)
            a = figure(fig["before"], folder, drafts, w + " (before)", (ia["h"] / tall) if ia else 1.0)
            b = figure(fig["after"], folder, drafts, w + " (after)", (ib["h"] / tall) if ib else 1.0)
            # the two shots one above the other, each with its legend beside it; the shared caption first.
            # Without labels of its own a pair is the stock game against the mod: tagged and edged grey /
            # blue so the viewer always knows which UI they look at (user, 2026-11-25); labelled pairs
            # compare two views with the mod and get neutral tags.
            #
            # A switch above the pair shows one half at a time in the same place, so the two can be
            # compared without scrolling (user, 2026-11-25): the mod's half first for a stock pair, the
            # first view otherwise. Both halves share one grid cell, so the box keeps the taller one's
            # height and nothing below moves. Without JavaScript the switch is hidden and the halves
            # stack, each with its label (annotate.js sets html.js and runs the switch).
            cap = f'<p class="pair-caption">{md(fig["caption"])}</p>' if fig.get("caption") else ""
            stock = "before_label" not in fig and "after_label" not in fig
            kinds = ("stock", "mod") if stock else ("view", "view")
            labels = (fig.get("before_label", "Stock Game UI"), fig.get("after_label", "UI with Mod"))
            shown = 1 if stock else 0
            Ctx.pairs += 1
            pid = f"pair-{Ctx.pairs}"
            tabs = "".join(
                f'<button type="button" class="seg {kinds[i]}" role="tab" id="{pid}-tab{i}" aria-controls="{pid}-view{i}" '
                f'aria-selected="{"true" if i == shown else "false"}" tabindex="{0 if i == shown else -1}">{esc(labels[i])}</button>'
                for i in (0, 1))
            halves = "".join(
                f'<div class="pair-half {kinds[i]}{" active" if i == shown else ""}" role="tabpanel" id="{pid}-view{i}" '
                f'aria-labelledby="{pid}-tab{i}"><span class="label">{esc(labels[i])}</span>{(a, b)[i]}</div>'
                for i in (0, 1))
            out.append(f'<div class="pair">{cap}<div class="pair-switch" role="tablist" aria-label="Compare">{tabs}</div>'
                       f'<div class="pair-views">{halves}</div></div>')
        else:
            out.append(figure(fig, folder, drafts, w))
    return "".join(out)


# ---------------------------------------------------------------- content

class Feature:
    def __init__(self, key: str, data: dict, param: dict | None):
        self.key = key
        self.data = data
        self.param = param
        self.title = data.get("title") or (param or {}).get("name") or key
        self.anchor = data.get("anchor") or slugify(self.title)
        self.what = data.get("what") or clean((param or {}).get("tooltip", ""))
        self.where = data.get("where", [])
        self.short = data.get("short") or self.what.strip().split(". ")[0].rstrip(".") + "."


class Mod:
    def __init__(self, path: pathlib.Path):
        self.slug = path.stem
        self.data = tomllib.loads(path.read_text(encoding="utf-8"))
        snap_path = HERE / "mods" / f"{self.slug}.json"
        if not snap_path.exists():
            err(f"{self.slug}: no settings snapshot; run sync_mods.py")
            self.snap = {"name": self.slug, "summary": "", "params": []}
        else:
            self.snap = json.loads(snap_path.read_text(encoding="utf-8"))
        d = self.data
        self.name = d.get("name") or self.snap.get("name") or self.slug
        self.group = d.get("group", "enhancements")
        self.order = d.get("order", 99)
        self.status = d.get("status", "soon")
        if self.status not in STATUS:
            err(f"{self.slug}: unknown status {self.status!r}")
            self.status = "soon"
        self.publish = bool(d.get("publish"))
        self.lead = d.get("lead") or self.snap.get("summary", "")
        self.card = d.get("card") or self.lead
        self.params = {p["key"]: p for p in self.snap.get("params", [])}
        keys = d.get("features") or [k for k in self.params if k != "logging"]
        fdata = d.get("feature", {})
        for k in fdata:
            if k not in keys:
                err(f"{self.slug}: [feature.{k}] isn't in the features list")
        self.features = []
        for k in keys:
            f = fdata.get(k, {})
            setting = f.get("setting", k)
            param = self.params.get(setting)
            if param is None and not f.get("title"):
                err(f"{self.slug}: feature {k} has no setting {setting!r} and no title")
            self.features.append(Feature(k, f, param))
        sections = d.get("section", [])
        listed = [k for s in sections for k in s.get("features", [])]
        if sections and sorted(listed) != sorted(keys):
            err(f"{self.slug}: [[section]] lists {sorted(listed)}, features are {sorted(keys)}")
        self.sections = sections

    def feature(self, key: str) -> Feature:
        return next(f for f in self.features if f.key == key)


MODS: dict[str, Mod] = {}


# ---------------------------------------------------------------- page shell

def badge(status: str, modio: str = "") -> str:
    cls, label = STATUS[status]
    # a live mod's badge links to its mod.io page (user, 2026-11-27)
    if status == "live" and modio:
        return f'<a class="badge {cls}" href="{esc(modio)}">{label}</a>'
    return f'<span class="badge {cls}">{label}</span>'


def page(*, title: str, description: str, crumbs: list, body: str, canonical: str,
         og_image: str | None = None, current: str = "", draft: bool = False, built: str = "") -> str:
    p = Ctx.prefix
    crumb_html = " › ".join(f'<a href="{esc(h)}">{esc(t)}</a>' if h else f"<span>{esc(t)}</span>" for t, h in crumbs)
    nav = [("Find it", f"{p}#where", "where"), ("Mods", f"{p}#mods", "mods"),
           ("Research", f"{p}#research", "research"), ("Install", f"{p}install/", "install")]
    nav_html = "".join(f'<a href="{esc(h)}"{" aria-current=" + chr(34) + "page" + chr(34) if k == current else ""}>{t}</a>'
                       for t, h, k in nav)
    og = [f'<meta property="og:title" content="{esc(title)}">',
          f'<meta property="og:description" content="{esc(description)}">',
          f'<meta property="og:url" content="{esc(canonical)}">',
          '<meta property="og:type" content="website">']
    if og_image:
        og.append(f'<meta property="og:image" content="{esc(TF3_URL + og_image)}">')
        og.append('<meta name="twitter:card" content="summary_large_image">')
    note = '<div class="wrap"><div class="draft-note">Draft: this page is only in the local preview, not on the public site yet.</div></div>' if draft else ""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<link rel="canonical" href="{esc(canonical)}">
{chr(10).join(og)}
<meta name="theme-color" content="#171b1f">
<link rel="preload" href="{p}assets/fonts/lato-regular.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="{p}assets/site.css?v={asset_version("site.css")}">
<script>document.documentElement.classList.add("js")</script>
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="site-head">
  <div class="wrap">
    <a class="brand" href="{p or './'}"><span class="brand-mark" aria-hidden="true">T</span>tuatara · TF3 mods</a>
    <nav class="crumbs" aria-label="Breadcrumb">{crumb_html}</nav>
    <nav class="head-nav" aria-label="Site">{nav_html}</nav>
  </div>
</header>
{note}
<main id="main">
{body}
</main>
<footer class="site-foot">
  <div class="wrap"><div>Fan-made mods by tuatara. Not affiliated with or endorsed by Urban Games; Transport Fever is their trademark. Screenshots are from the author's own games. Text set in Lato (SIL Open Font License). No cookies, no tracking.{f" Updated {built}." if built else ""}</div></div>
</footer>
<script src="{p}assets/annotate.js?v={asset_version("annotate.js")}" defer></script>
</body>
</html>
"""


def write(path: pathlib.Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


# ---------------------------------------------------------------- landing

def mod_card(m: Mod, drafts: bool) -> str:
    img = None
    ref = m.data.get("card_image") or m.data.get("hero")
    if ref:
        img = IMAGES.find(m.slug, ref)
        if not img:
            (warn if drafts or not m.publish else err)(f"{m.slug}: card image {ref} is missing")
    img_html = (f'<div class="card-img"><img src="{esc(Ctx.prefix + img["src"])}" alt="" loading="lazy" decoding="async"></div>'
                if img else "")
    n = len(m.features)
    count = f"<span>{n} features</span>" if n > 1 else ""
    modio = m.data.get("modio", "")
    if m.slug in Ctx.visible:
        # The card's name is its link, stretched over the whole card (site.css .card-main), so the On
        # mod.io badge can be a link of its own: links can't nest
        name = f'<a class="card-main" href="mods/{m.slug}/">{esc(m.name)}</a>'
        cls = "card linked"
    else:
        name, cls = esc(m.name), "card off"
    body = (f'<div class="card-body"><h3>{name}</h3><p>{md(m.card)}</p>'
            f'<div class="card-meta">{badge(m.status, modio)}{count}</div></div>')
    return f'<div class="{cls}">{img_html}{body}</div>'


def landing(site: dict, mods: list[Mod], drafts: bool, built: str) -> str:
    Ctx.prefix = ""
    total_features = sum(len(m.features) for m in mods)
    hero = site["hero"]
    facts = (f'<span class="fact"><b>{len(mods)}</b> mods</span>'
             f'<span class="fact"><b>{total_features}</b> features, each with its own switch</span>'
             f'<span class="fact">Tested on game build <b>{esc(site["build"])}</b></span>')
    hero_img = ""
    if hero.get("shot"):
        im = IMAGES.find("site", hero["shot"])
        if im:
            hero_img = f'<div><img class="hero-shot" src="{esc(im["src"])}" width="{im["w"]}" height="{im["h"]}" alt="{esc(hero.get("alt", ""))}"></div>'
    body = [f'<section class="hero"><div class="wrap{" hero-grid" if hero_img else ""}"><div>'
            f'<h1>{esc(hero["title"])}</h1><p class="lead">{md(hero["lead"])}</p><div class="facts">{facts}</div></div>{hero_img}</div></section>',
            '<div class="wrap">']

    steps = "".join(f'<div class="step"><b>{esc(s["title"])}</b><p>{md(s["text"])}</p></div>' for s in site.get("how", []))
    body.append(f'<section class="window" id="how"><div class="window-title"><h2>How the mods work</h2>'
                f'<p>Every mod follows the same rules.</p></div><div class="steps">{steps}</div></section>')

    # Find it first (user, 2026-11-27): its links lead on to the mod pages, so it comes before the grid
    body.append(find_it(site, mods, drafts))
    grid = ['<section class="window" id="mods"><div class="window-title"><h2>The mods</h2></div>']
    for key, title, sub in GROUPS:
        group = sorted((m for m in mods if m.group == key), key=lambda m: m.order)
        if group:
            grid.append(f'<h3 class="decor">{title}</h3><p class="muted group-sub">{sub}</p>'
                        f'<div class="cards menu">{"".join(mod_card(m, drafts) for m in group)}</div>')
    grid.append("</section>")
    body.append("".join(grid))


    cards = []
    for r in site.get("research", []):
        links = []
        for l in r.get("links", []):
            if "mod" in l:
                href = mod_href(f"mod:{l['mod']}")
                if href:
                    links.append(f'<a href="{esc(href)}">{esc(l["label"])}</a>')
                elif l.get("url"):
                    links.append(f'<a href="{esc(l["url"])}">{esc(l["label"])}</a>')
            else:
                links.append(f'<a href="{esc(l["url"])}">{esc(l["label"])}</a>')
        cards.append(f'<div class="card"><div class="card-body"><h3>{esc(r["title"])}</h3><p>{md(r["text"])}</p>'
                     f'<div class="card-links">{" ".join(links)}</div></div></div>')
    body.append(f'<section class="window" id="research"><div class="window-title"><h2>Research</h2>'
                f'<p>{md(site.get("research_lead", ""))}</p></div><div class="cards">{"".join(cards)}</div></section>')
    body.append("</div>")
    return page(title=site["title"], description=site["description"],
                crumbs=[("tuatara.ca", "../../../../"), ("personal", "../../../"), ("shawn", "../../"), ("gaming", "../"), ("TF3", None)],
                body="".join(body), canonical=TF3_URL, og_image=site.get("og_image"), built=built)


def find_it(site: dict, mods: list[Mod], drafts: bool) -> str:
    windows = []
    for w in site.get("window", []):
        feats = [(m, f) for m in sorted(mods, key=lambda m: (GROUPS.index(next(g for g in GROUPS if g[0] == m.group)), m.order))
                 for f in m.features if w["key"] in f.where and m.slug in Ctx.visible]
        if feats:
            windows.append((w, feats))
    if not windows:
        return ""
    buttons, panes = [], []
    for i, (w, feats) in enumerate(windows):
        n_mods = len({m.slug for m, _ in feats})
        buttons.append(f'<li><button type="button" data-show="{esc(w["key"])}" aria-pressed="{"true" if i == 0 else "false"}">'
                       f'{esc(w["name"])} <span>{n_mods} mod{"s" if n_mods > 1 else ""}</span></button></li>')
        # A window's screens (user, 2026-11-26): tabs over the pane, one picture each (or a statistics table
        # in two halves, one under the other), every feature pinned where it shows. The old flat list of the
        # window's features is gone; a feature no picture shows is named under the pictures.
        views = [v for v in w.get("view", [])
                 if any(not p.get("mod") or p["mod"] in Ctx.visible for f in (v.get("figure") or [v]) for p in f.get("pins", []))]
        pinned: set[int] = set()
        tabs, bodies = [], []
        for k, v in enumerate(views):
            figs = v.get("figure") or [v]
            html = []
            for j, f in enumerate(figs):
                wh = f"window {w['key']} view {v['tab']}" + (f" figure {j + 1}" if len(figs) > 1 else "")
                html.append(figure(f, "site", drafts, wh))
                for p in f.get("pins", []):
                    if not p.get("mod") or p["mod"] in Ctx.visible:
                        pinned.update(id(x) for x in pin_features(p, wh))
            vid = f"view-{w['key']}-{k}"
            cap = f'<p class="view-caption">{md(v["view_caption"])}</p>' if v.get("view_caption") else ""
            tabs.append(f'<button type="button" class="view-tab" role="tab" id="{vid}-tab" aria-controls="{vid}" '
                        f'aria-selected="{"true" if k == 0 else "false"}" tabindex="{0 if k == 0 else -1}">{esc(v["tab"])}</button>')
            bodies.append(f'<div class="view{" active" if k == 0 else ""}" role="tabpanel" id="{vid}" aria-labelledby="{vid}-tab">'
                          f'<h3 class="view-label">{esc(v["tab"])}</h3>{cap}{"".join(html)}</div>')
        bar = (f'<div class="view-tabs" role="tablist" aria-label="{esc(w["name"])} screens">{"".join(tabs)}</div>'
               if len(views) > 1 else "")
        rest = [(m, f) for m, f in feats if id(f) not in pinned]
        if views and rest:
            for m, f in rest:
                warn(f"find it: {w['key']}: {m.slug}.{f.key} is pinned in none of its pictures")
        rows = ""
        if rest:
            head = '<p class="not-pictured">Also here, not in a picture:</p>' if views else ""
            rows = head + '<ul class="feature-list">' + "".join(
                f'<li><a href="mods/{m.slug}/#{f.anchor}"><b>{esc(f.title)}</b></a> '
                f'<span class="muted">· {esc(m.name)}</span><br><span class="small">{md(f.short)}</span></li>'
                for m, f in rest) + "</ul>"
        panes.append(f'<div data-pane="{esc(w["key"])}"{" hidden" if i else ""}>{bar}{"".join(bodies)}{rows}</div>')
    return (f'<section class="window" id="where"><div class="window-title"><h2>Find it in the game</h2>'
            f'<p>Open a window, see what the mods add there.</p></div><div class="where">'
            f'<ul class="where-list">{"".join(buttons)}</ul><div>{"".join(panes)}</div></div></section>')


# ---------------------------------------------------------------- mod page

def feature_section(m: Mod, f: Feature, drafts: bool) -> str:
    d = f.data
    figs = figures(d.get("figure", []), m.slug, drafts, f"{m.slug} {f.key}")
    text = []
    if d.get("why"):
        text.append(f"<h3>Why</h3>{paras(d['why'])}")
    if f.what:
        text.append(f"<h3>What it does</h3>{paras(f.what)}")
    if d.get("how"):
        text.append(f"<h3>How to use</h3>{items(d['how'], ordered=True)}")
    if d.get("good"):
        text.append(f"<h3>Good to know</h3>{items(d['good'])}")
    if d.get("also"):
        text.append(f"<h3>Also in</h3>{paras(d['also'])}")
    setting = ""
    if f.param:
        default = f.param["default"]
        setting = f'<span class="setting">Setting: <b>{esc(f.param["name"])}</b> · {esc(default)} by default</span>'
    # Screenshots first at full width, then the text in columns below them (user, 2026-11-24:
    # text beside the figures looked out of proportion).
    text_html = f'<div class="feature-text cols">{"".join(text)}</div>'
    inner = f'<div class="feature-figs">{figs}</div>{text_html}' if figs else text_html
    return (f'<section class="window feature" id="{esc(f.anchor)}"><div class="feature-head"><h2>{esc(f.title)}</h2>{setting}</div>'
            f"{inner}</section>")


def mod_page(m: Mod, drafts: bool, built: str) -> str:
    Ctx.prefix = "../../"
    d = m.data
    hero_html, og = "", None
    if d.get("hero"):
        im = IMAGES.find(m.slug, d["hero"])
        if im:
            og = im["src"]
            hero_html = (f'<div><img class="hero-shot zoom" src="{esc(Ctx.prefix + im["src"])}" width="{im["w"]}" height="{im["h"]}" '
                         f'alt="{esc(d.get("hero_alt", ""))}"></div>')
        else:
            (warn if drafts else err)(f"{m.slug}: hero {d['hero']} is missing")
    facts = [badge(m.status, d.get("modio", "")), f'<span class="fact">Version <b>{esc(d.get("version", "?"))}</b></span>',
             f'<span class="fact">Game build <b>{esc(d.get("build", SITE["build"]))}</b></span>']
    if len(m.features) > 1:
        facts.append(f'<span class="fact"><b>{len(m.features)}</b> features</span>')
    if m.status == "live" and d.get("modio"):
        button = f'<a class="btn primary" href="{esc(d["modio"])}">Get it on mod.io</a>'
    else:
        button = '<span class="btn primary" aria-disabled="true">Coming soon to mod.io</span>'
    chips = ""
    if len(m.features) > 1:
        chips = '<div class="chips">' + "".join(
            f'<a class="chip" href="#{esc(f.anchor)}">{esc(f.title)}'
            f'{" <small>" + esc(" · ".join(where_name(w) for w in f.where)) + "</small>" if f.where else ""}</a>'
            for f in m.features) + "</div>"
    head = (f'<section class="mod-head"><div class="{"hero-grid" if hero_html else ""}"><div>'
            f'<div class="badges">{"".join(facts)}</div><h1>{esc(m.name)}</h1>{paras(m.lead, "lead")}'
            f'<p class="buttons">{button} <a class="btn" href="#settings">Settings</a></p></div>{hero_html}</div>{chips}</section>')
    if d.get("intro"):
        head += f'<section class="window intro">{paras(d["intro"])}</section>'

    body = [head]
    if m.sections:
        for s in m.sections:
            body.append(f'<h2 class="section-title" id="{esc(slugify(s["title"]))}">{esc(s["title"])}</h2>')
            body += [feature_section(m, m.feature(k), drafts) for k in s["features"]]
    else:
        body += [feature_section(m, f, drafts) for f in m.features]

    rows = []
    for p in m.params.values():
        default = p["default"]
        cls = "on-off" + (" off" if default == "Off" else "") if default in ("On", "Off") else "value"
        choices = "" if sorted(p["values"]) == ["Off", "On"] else f' <span class="muted">Choices: {esc(", ".join(p["values"]))}.</span>'
        rows.append(f'<tr><td>{esc(p["name"])}</td><td><span class="{cls}">{esc(default)}</span></td>'
                    f'<td>{esc(clean(p["tooltip"]))}{choices}</td></tr>')
    body.append(f'<section class="window" id="settings"><h2>Settings</h2>'
                f'<p class="muted">Choosing a save\'s mods: the gear next to {esc(m.name)} → Settings. Each save keeps its own choice. '
                f'Off turns a feature off completely.</p><div class="table-scroll"><table class="settings">'
                f'<thead><tr><th>Setting</th><th>Default</th><th>What it does</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div></section>')

    more = []
    if d.get("compat"):
        more.append(f'<h3 class="decor">Compatibility</h3>{paras(d["compat"], "muted")}')
    if d.get("issues"):
        more.append(f'<h3 class="decor">Known issues</h3><div class="muted">{items(d["issues"])}</div>')
    changes = d.get("change", [])
    if changes:
        first, rest = changes[0], changes[1:]
        lis = "".join(f"<li><b>{esc(c['version'])}</b>: {md(c['text'])}</li>" for c in rest)
        more.append(f'<h3 class="decor">Changes</h3><p><b>{esc(first["version"])}</b>: {md(first["text"])}</p>'
                    + (f'<details class="tf-card"><summary>Earlier versions</summary><div class="tf-card-body"><ul class="muted">{lis}</ul></div></details>' if rest else ""))
    if more:
        body.append(f'<section class="window" id="more"><h2>More</h2>{"".join(more)}</section>')

    return page(title=f"{m.name} · Transport Fever 3 mod by tuatara", description=clean(d.get("description") or m.lead),
                crumbs=[("TF3", "../../"), ("Mods", "../../#mods"), (m.name, None)],
                body='<div class="wrap">' + "".join(body) + "</div>", canonical=f"{TF3_URL}mods/{m.slug}/",
                og_image=og, current="mods", draft=drafts and not m.publish, built=built)


def where_name(key: str) -> str:
    for w in SITE.get("window", []):
        if w["key"] == key:
            return w.get("short", w["name"])
    err(f"unknown where tag {key!r}")
    return key


# ---------------------------------------------------------------- other pages

def install_page(site: dict, built: str) -> str:
    Ctx.prefix = "../"
    inst = site["install"]
    secs = "".join(f'<section class="window"><h2>{esc(s["title"])}</h2>{paras(s.get("text", ""))}'
                   f'{items(s["steps"], ordered=True) if s.get("steps") else ""}{paras(s.get("after", ""), "muted")}'
                   f'{figure(s["figure"], "site", False, "install " + s["title"]) if s.get("figure") else ""}</section>'
                   for s in inst["section"])
    body = (f'<div class="wrap"><section class="mod-head"><h1>{esc(inst["title"])}</h1>{paras(inst["lead"], "lead")}</section>'
            f'<div class="prose">{secs}</div></div>')
    return page(title=f"{inst['title']} · TF3 mods by tuatara", description=inst["lead"],
                crumbs=[("TF3", "../"), (inst["title"], None)], body=body,
                canonical=f"{TF3_URL}install/", current="install", built=built)


def crumb_page(depth_to_tf3: str, title: str, links: list, canonical: str) -> str:
    Ctx.prefix = depth_to_tf3
    lis = "".join(f'<li><a href="{esc(h)}">{esc(t)}</a></li>' for t, h in links)
    body = f'<div class="wrap"><section class="mod-head"><h1>{esc(title)}</h1></section><section class="window"><ul class="link-list">{lis}</ul></section></div>'
    return page(title=f"{title} · tuatara.ca", description=f"{title} on tuatara.ca", crumbs=[("tuatara.ca", "/"), (title, None)],
                body=body, canonical=canonical)


# ---------------------------------------------------------------- main

SITE: dict = {}


def main() -> int:
    ap = argparse.ArgumentParser(description="Build the TF3 mods site.")
    ap.add_argument("--drafts", action="store_true", help="build every mod (drafts marked) into build-preview/")
    ap.add_argument("--out", type=pathlib.Path, help="output folder (default site/, or build-preview/ with --drafts)")
    args = ap.parse_args()
    out = args.out or (REPO / ("build-preview" if args.drafts else "site"))
    built = datetime.date.today().isoformat()

    SITE.update(tomllib.loads((HERE / "content" / "site.toml").read_text(encoding="utf-8")))
    for path in sorted((HERE / "content" / "mods").glob("*.toml")):
        MODS[path.stem] = Mod(path)
    mods = list(MODS.values())
    Ctx.visible = {m.slug for m in mods if m.publish or args.drafts}
    for m in mods:
        if m.publish and m.status == "live" and not m.data.get("modio"):
            err(f"{m.slug}: live but no modio link")
        for f in m.features:
            for w in f.where:
                where_name(w)

    pages: dict[str, str] = {}
    IMAGES.find("site", "bg-world")
    pages["index.html"] = landing(SITE, mods, args.drafts, built)
    for m in mods:
        if m.slug in Ctx.visible:
            pages[f"mods/{m.slug}/index.html"] = mod_page(m, args.drafts, built)
    pages["install/index.html"] = install_page(SITE, built)

    for w in warnings:
        print(f"warning: {w}")
    if errors:
        for e in errors:
            print(f"error: {e}", file=sys.stderr)
        print(f"{len(errors)} error(s); nothing written.", file=sys.stderr)
        return 1

    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for f in ROOT_SRC.iterdir():
        shutil.copyfile(f, out / f.name)
    tf3 = out / TF3_PATH
    for rel, text in pages.items():
        write(tf3 / rel, text)
    write(out / "personal/index.html", crumb_page("shawn/gaming/tf3/", "personal", [("shawn", "shawn/")], SITE_URL + "personal/"))
    write(out / "personal/shawn/index.html", crumb_page("gaming/tf3/", "shawn", [("gaming", "gaming/")], SITE_URL + "personal/shawn/"))
    write(out / "personal/shawn/gaming/index.html",
          crumb_page("tf3/", "gaming", [("Transport Fever 3 mods", "tf3/")], SITE_URL + "personal/shawn/gaming/"))
    shutil.copytree(HERE / "assets", tf3 / "assets")
    IMAGES.write(tf3)
    if errors:
        for e in errors:
            print(f"error: {e}", file=sys.stderr)
        return 1
    n_img = len(IMAGES.used)
    print(f"{out.relative_to(REPO) if out.is_relative_to(REPO) else out}: {len(pages)} TF3 pages ({len(Ctx.visible)} mod pages), {n_img} images")
    return 0


if __name__ == "__main__":
    sys.exit(main())
