"""Build the two "Find it in the game" pictures that put existing shots side by side (Subsidies, Pop-ups).

    python src/tf3/make_window_composites.py

Writes shots/site/where-subsidies.png (the offer window next to the reward window) and
shots/site/where-popups.png (the offer card, the reward card and the ring strip, one above the other)
from masters in shots/subsidy-enhancements/. The padding is transparent. Pins for both are in
content/site.toml; if a master changes size, recompute them.
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

# offer card 490 x 230, reward card 490 x 170, ring strip 280 x 80, 20 px apart
run([SUB / "SU-01a.png", SUB / "SU-02b.png", SUB / "SU-03d.png"],
    "[0]format=rgba,pad=490:520:0:0:color=0x00000000[a];"
    "[1]format=rgba[b];[2]format=rgba[c];"
    "[a][b]overlay=0:250[ab];[ab][c]overlay=0:440[out]",
    OUT / "where-popups.png")

# Track and bulldoze tools: the Shift + bulldoze frame (3440 x 1369) with the path signal tool's Settings
# panel, cropped from the signal tool frame, in a band under it (the two never show at once in the game)
SIG = SHOTS / "signal-enhancements"
run([SIG / "SG-03d.png", SIG / "SG-01-full.png"],
    "[0]format=rgba,pad=3440:1594:0:0:color=0x00000000[a];"
    "[1]format=rgba,crop=540:205:2900:725[b];[a][b]overlay=1450:1389[out]",
    OUT / "where-build-tools.png")
