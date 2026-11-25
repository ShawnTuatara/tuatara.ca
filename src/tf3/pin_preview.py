"""Draw each figure's pins on its screenshot at the size the site shows it, to check that no pin covers
what it points at.

    python src/tf3/pin_preview.py <slug> [<slug> ...] [--out DIR] [--grid]

<slug> is a content/mods/<slug>.toml name, or "site" for content/site.toml. Each figure (each half of a
before / after pair) becomes <out>/<slug>__<shot>.png: the image scaled as a desktop browser shows it
(site.css: beside its legend at most 776 px wide, a 3:1 strip up to 1080 px, no taller than 860 px)
with each pin as the site's 28 px yellow disc. --grid adds the 10 % grid labels of grid_preview.py.
It also prints each figure's place in the TOML and its pins, to edit x / y there.
"""
import argparse
import pathlib
import struct
import subprocess
import sys
import tomllib

HERE = pathlib.Path(__file__).resolve().parent
FONT = r"C\:/Windows/Fonts/arialbd.ttf"
PIN = 28            # site.css .pin, CSS px
ASIDE_MAX_W = 776   # 1080 content - 280 legend - 24 gap
WIDE_MAX_W = 1080
PANE_MAX_W = 516    # the landing page's "find it" panes
MAX_H = 860         # a 1000 px tall window minus 140 (site.css)
WIDE_RATIO = 3      # build.py


def shot_path(folder: str, shot: str) -> pathlib.Path:
    """as build.py: a shot named "<folder>/<id>" is in that folder"""
    if "/" in shot:
        folder, shot = shot.split("/", 1)
    return HERE / "shots" / folder / (shot + ".png")


def shot_size(folder: str, shot: str) -> tuple[int, int]:
    src = shot_path(folder, shot)
    w, h = struct.unpack(">II", src.read_bytes()[16:24])
    return w, h


def figures(data: dict, folder_of) -> list[tuple[str, str, dict]]:
    """(place in the TOML, image folder, figure) for every figure with a shot"""
    out = []

    def add(place, fig, folder):
        if "before" in fig:
            out.append((place + " before", folder, fig["before"]))
            out.append((place + " after", folder, fig["after"]))
        elif "shot" in fig:
            out.append((place, folder, fig))

    for key, feat in data.get("feature", {}).items():
        for i, fig in enumerate(feat.get("figure", [])):
            add(f"[[feature.{key}.figure]] #{i + 1}", fig, folder_of("feature"))
    for w in data.get("window", []):
        if w.get("figure"):
            add(f"[[window]] {w['key']} figure", w["figure"], "site")
    for s in data.get("install", {}).get("section", []):
        if s.get("figure"):
            add(f"[[install.section]] {s['title']!r} figure", s["figure"], "site")
    return out


def render(folder: str, fig: dict, dst: pathlib.Path, grid: bool, pane: bool) -> float:
    w, h = shot_size(folder, fig["shot"])
    pins = fig.get("pins", [])
    aside = bool(pins or fig.get("caption"))
    if aside and w >= WIDE_RATIO * h and w > ASIDE_MAX_W:
        k = min(1.0, WIDE_MAX_W / w)
    else:
        k = min(1.0, (PANE_MAX_W if pane else ASIDE_MAX_W if aside else WIDE_MAX_W) / w, MAX_H / h)
    sw, sh = max(2, round(w * k / 2) * 2), max(2, round(h * k / 2) * 2)
    f = [f"scale={sw}:{sh}"]
    if grid:
        f += ["drawgrid=w=iw/10:h=ih/10:t=1:c=magenta@0.45"]
        for i in range(1, 10):
            f.append(f"drawtext=fontfile='{FONT}':text='{i}0':x=w*{i}/10+2:y=2:fontsize=11:fontcolor=magenta")
            f.append(f"drawtext=fontfile='{FONT}':text='{i}0':x=2:y=h*{i}/10+2:fontsize=11:fontcolor=magenta")
    for p in pins:
        cx, cy = p["x"] / 100 * sw, p["y"] / 100 * sh
        x0, y0 = round(cx - PIN / 2), round(cy - PIN / 2)
        f.append(f"drawbox=x={x0}:y={y0}:w={PIN}:h={PIN}:color=black@0.9:t=fill")
        f.append(f"drawbox=x={x0 + 2}:y={y0 + 2}:w={PIN - 4}:h={PIN - 4}:color=yellow@1:t=fill")
        f.append(f"drawtext=fontfile='{FONT}':text='{p['n']}':fontsize=14:fontcolor=black:"
                 f"x={round(cx)}-tw/2:y={round(cy)}-th/2")
    src = shot_path(folder, fig["shot"])
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-vf", ",".join(f), str(dst)], check=True)
    return k


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("slugs", nargs="+")
    ap.add_argument("--out", type=pathlib.Path, default=pathlib.Path("."))
    ap.add_argument("--grid", action="store_true")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    for slug in a.slugs:
        path = HERE / "content" / ("site.toml" if slug == "site" else f"mods/{slug}.toml")
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        for place, folder, fig in figures(data, lambda kind: "site" if slug == "site" else slug):
            dst = a.out / f"{slug}__{fig['shot'].replace('/', '__')}.png"
            k = render(folder, fig, dst, a.grid, pane=place.startswith("[[window]]"))
            print(f"{dst}  ({path.name} {place}, shown at {k:.2f}x)")
            for p in fig.get("pins", []):
                print(f"    pin {p['n']}: x = {p['x']}, y = {p['y']}  {p['text'][:70]}")


if __name__ == "__main__":
    main()
