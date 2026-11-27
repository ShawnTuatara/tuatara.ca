"""Build the "Find it in the game" pictures made from existing shots: side by side, stacked or cropped.

    python src/tf3/make_window_composites.py

Writes into shots/site/: where-subsidies.png (the offer window next to the reward window),
where-notifications.png (the ring strip above the offer and reward cards), and the
crops (where-<window>-<part>.png): the statistics tables cut into a left and a right half so each is
readable at the page's width, the town window's Supplies view and the game bar's counters. The padding is
transparent. Pins for all of them are in content/site.toml; if a master changes size or a crop moves,
recompute them.
"""
import pathlib
import subprocess

SHOTS = pathlib.Path(__file__).resolve().parent / "shots"
SUB = SHOTS / "subsidy-enhancements"
OUT = SHOTS / "site"


def run(inputs, graph, dst):
    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    for p in inputs:
        cmd += ["-i", str(p)]
    cmd += ["-filter_complex", graph, "-map", "[out]", str(dst)]
    subprocess.run(cmd, check=True)
    print(dst)


# offer window 580 x 845 at the left, reward window 580 x 530 at the top right
run([SUB / "SU-01b.png", SUB / "SU-02.png"],
    "[0]format=rgba,pad=1184:845:0:0:color=0x00000000[a];"
    "[1]format=rgba[b];[a][b]overlay=604:0[out]",
    OUT / "where-subsidies.png")

# Notifications (user, 2026-11-26: the strip first, the two cards it opens below it): ring strip 280 x 80,
# offer card 490 x 230, reward card 490 x 170, 20 px apart
run([SUB / "SU-03d.png", SUB / "SU-01a.png", SUB / "SU-02b.png"],
    "[0]format=rgba,pad=490:520:0:0:color=0x00000000[a];"
    "[1]format=rgba[b];[2]format=rgba[c];"
    "[a][b]overlay=0:100[ab];[ab][c]overlay=0:350[out]",
    OUT / "where-notifications.png")

# Crops: (output, master, w, h, x, y). A statistics table at the page's width is too small to read
# (user, 2026-11-26), so each is cut at a column boundary into a left and a right half.
CROPS = [
    ("where-stats-industries-left", OUT / "where-statistics.png", 1500, 1000, 150, 0),
    ("where-stats-industries-right", OUT / "where-statistics.png", 1250, 1000, 1650, 0),
    ("where-stats-towns-left", SHOTS / "statistics-enhancements" / "SE-03d.png", 1575, 620, 0, 0),
    ("where-stats-towns-right", SHOTS / "statistics-enhancements" / "SE-03d.png", 1180, 620, 1560, 0),
    ("where-stats-lines-right", SHOTS / "line-enhancements" / "LE-17d.png", 1478, 620, 1262, 0),
    ("where-stats-stations-left", SHOTS / "statistics-enhancements" / "SE-07c.png", 1290, 600, 0, 0),
    ("where-stats-stations-right", SHOTS / "statistics-enhancements" / "SE-07c.png", 1450, 600, 1290, 0),
    ("where-stats-vehicles-left", SHOTS / "statistics-enhancements" / "SE-06e.png", 1340, 420, 0, 0),
    ("where-stats-vehicles-right", SHOTS / "statistics-enhancements" / "SE-06e.png", 1400, 420, 1340, 0),
    ("where-stats-warehouses-left", SHOTS / "warehouse-enhancements" / "WE-01d.png", 1340, 620, 0, 0),
    ("where-stats-warehouses-right", SHOTS / "warehouse-enhancements" / "WE-01d.png", 1400, 620, 1340, 0),
    # the town window of Cargo Enhancements' Wellington frame, machines picked
    ("where-town-supplies", SHOTS / "cargo-enhancements" / "CE-05b-machines.png", 580, 1150, 2826, 14),
    # the game bar's counters, no tooltip over them (user, 2026-11-26)
    ("where-game-bar-counters", OUT / "GEN-03.png", 1130, 107, 100, 0),
]
for name, master, w, h, x, y in CROPS:
    run([master], f"[0]crop={w}:{h}:{x}:{y}[out]", OUT / f"{name}.png")
