"""Snapshot each mod's name, texts and settings into src/tf3/mods/<slug>.json.

The site's settings tables and feature fallbacks come from these snapshots, so the
build needs only this repo. Run it after a mod's options or texts change:

    python src/tf3/sync_mods.py [--mods DIR]

DIR defaults to the game's local mods folder. Each content file
(content/mods/<slug>.toml) names its mod with `modid`.
"""
import argparse
import json
import pathlib
import sys
import tomllib

HERE = pathlib.Path(__file__).resolve().parent
DEFAULT_MODS = pathlib.Path(r"C:\Games\Steam\userdata\57981291\3493540\local\mods")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--mods", type=pathlib.Path, default=DEFAULT_MODS, help="folder holding the mod folders")
    args = ap.parse_args()

    out_dir = HERE / "mods"
    out_dir.mkdir(exist_ok=True)
    failed = 0
    for content in sorted((HERE / "content" / "mods").glob("*.toml")):
        slug = content.stem
        modid = tomllib.loads(content.read_text(encoding="utf-8"))["modid"]
        folder = args.mods / modid
        try:
            mod = json.loads((folder / "mod.json").read_text(encoding="utf-8"))
            info = json.loads((folder / "_metadata" / "modinfo.json").read_text(encoding="utf-8"))
        except OSError as e:
            print(f"{slug}: {e}", file=sys.stderr)
            failed += 1
            continue
        params = []
        for p in mod.get("params") or []:
            values = list(p.get("values") or [])
            params.append({
                "key": p["key"],
                "name": p.get("name", p["key"]),
                "tooltip": p.get("tooltip", ""),
                "values": values,
                "default": values[p.get("defaultIndex", 0)] if values else "",
            })
        snap = {
            "modid": modid,
            "name": info.get("name", ""),
            "summary": info.get("summary", ""),
            "description": info.get("description", ""),
            "params": params,
        }
        path = out_dir / f"{slug}.json"
        text = json.dumps(snap, ensure_ascii=False, indent=2) + "\n"
        changed = not path.exists() or path.read_text(encoding="utf-8") != text
        path.write_text(text, encoding="utf-8", newline="\n")
        print(f"{slug}: {len(params)} settings{' (changed)' if changed else ''}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
