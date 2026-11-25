"""Write a downscaled copy of a screenshot master with a labelled 10 % grid, for placing pins.

    python src/tf3/grid_preview.py <slug>/<shot> [--width 1100] [--out DIR]

Pins and boxes in content/mods/*.toml are percentages of the image, so read them straight off the grid
(labels every 10 %, faint lines every 5 %).
"""
import argparse
import pathlib
import struct
import subprocess

HERE = pathlib.Path(__file__).resolve().parent
FONT = r"C\:/Windows/Fonts/arial.ttf"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("shots", nargs="+", help="<slug>/<shot id>")
    ap.add_argument("--width", type=int, default=1100)
    ap.add_argument("--out", type=pathlib.Path, default=pathlib.Path("."))
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    for ref in a.shots:
        src = HERE / "shots" / (ref + ".png")
        dst = a.out / (ref.replace("/", "__") + ".png")
        w, h = struct.unpack(">II", src.read_bytes()[16:24])
        k = min(a.width / max(w, h * 1.6), 3.0)  # long side about --width; small strips scaled up
        f = [f"scale={round(w * k / 2) * 2}:{round(h * k / 2) * 2}",
             "drawgrid=w=iw/20:h=ih/20:t=1:c=cyan@0.25",
             "drawgrid=w=iw/10:h=ih/10:t=1:c=magenta@0.7"]
        for i in range(1, 10):
            for axis in ("x", "y"):
                pos = (f"x=w*{i}/10+2:y=2" if axis == "x" else f"x=2:y=h*{i}/10+2")
                f.append(f"drawtext=fontfile='{FONT}':text='{i}0':{pos}:fontsize=13:fontcolor=yellow:box=1:boxcolor=black@0.7")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-vf", ",".join(f), str(dst)], check=True)
        print(dst)


if __name__ == "__main__":
    main()
