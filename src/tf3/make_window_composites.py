"""Build the "Find it in the game" pictures made from existing shots: side by side, stacked or cropped.

    python src/tf3/make_window_composites.py

Writes into shots/site/: where-subsidies.png (the offer window next to the reward window),
where-notifications.png (the ring strip above the offer and reward cards), and the
crops (where-<window>-<part>.png): the statistics tabs, each cut into a left and a right half so it is
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
    # the statistics window, expanded, one capture per tab (where-stats-<tab>.png, 2770 x 1012 in the
    # 3440 x 1369 game window, 2026-11-27); 998 high leaves out the game bar's buttons below it. The left
    # half keeps the tab bar, the right half the filter bar.
    ("where-stats-industries-left", OUT / "where-stats-industries.png", 1510, 998, 0, 0),
    ("where-stats-industries-right", OUT / "where-stats-industries.png", 1260, 998, 1510, 0),
    ("where-stats-towns-left", OUT / "where-stats-towns.png", 1560, 998, 0, 0),
    ("where-stats-towns-right", OUT / "where-stats-towns.png", 1210, 998, 1560, 0),
    ("where-stats-lines-left", OUT / "where-stats-lines.png", 1280, 998, 0, 0),
    ("where-stats-lines-right", OUT / "where-stats-lines.png", 1490, 998, 1280, 0),
    ("where-stats-stations-left", OUT / "where-stats-stations.png", 1180, 998, 0, 0),
    ("where-stats-stations-right", OUT / "where-stats-stations.png", 1590, 998, 1180, 0),
    ("where-stats-vehicles-left", OUT / "where-stats-vehicles.png", 1356, 998, 0, 0),
    ("where-stats-vehicles-right", OUT / "where-stats-vehicles.png", 1414, 998, 1356, 0),
    ("where-stats-warehouses-left", OUT / "where-stats-warehouses.png", 1385, 998, 0, 0),
    ("where-stats-warehouses-right", OUT / "where-stats-warehouses.png", 1385, 998, 1385, 0),
    # the town window of Cargo Enhancements' Wellington frame, machines picked
    ("where-town-supplies", SHOTS / "cargo-enhancements" / "CE-05b-machines.png", 580, 1150, 2826, 14),
    # the game bar's counters, no tooltip over them (user, 2026-11-26)
    ("where-game-bar-counters", OUT / "GEN-03.png", 1130, 107, 100, 0),
]
for name, master, w, h, x, y in CROPS:
    run([master], f"[0]crop={w}:{h}:{x}:{y}[out]", OUT / f"{name}.png")
