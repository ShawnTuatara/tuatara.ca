# tuatara.ca

Source of https://tuatara.ca/, published with GitHub Pages.

- `site/` is what gets published: the GitHub Actions workflow in `.github/workflows/pages.yml` uploads this folder on every push to `main`. It is generated; don't edit it by hand.
- The custom domain is set in the repository's Pages settings, so there is no `CNAME` file.

## Layout

| Path | What |
|---|---|
| `src/root/` | The domain's own pages (`tuatara.ca/`, the 404 page), copied as they are |
| `src/tf3/build.py` | Builds the Transport Fever 3 mods site into `site/personal/shawn/gaming/tf3/` |
| `src/tf3/sync_mods.py` | Snapshots each mod's name, texts and settings from the game's mods folder into `src/tf3/mods/<slug>.json` |
| `src/tf3/content/site.toml` | Landing page, research cards, "find it in the game" windows, install page |
| `src/tf3/content/mods/<slug>.toml` | One page per mod: status, texts, features, figures and their pins |
| `src/tf3/shots/<folder>/<id>.png` | Screenshot masters; the build writes them as WebP |
| `src/tf3/assets/` | `site.css`, `annotate.js`, the Lato fonts (cut to Latin, WOFF2, with their licence) |

## Building

```
python src/tf3/build.py            # public pages -> site/ (commit and push this)
python src/tf3/build.py --drafts   # every mod, drafts marked -> build-preview/ (local only)
python -m http.server 8792 --directory build-preview
```

The build uses only Python's standard library, plus `ffmpeg` for new or changed screenshots (converted WebP files are cached in `src/tf3/.cache/`). It stops without writing anything when a public page names a missing screenshot, a pin lies outside its image, or a feature names an unknown setting.

A mod's page goes public when its content file says `publish = true`. Until then it is only in the preview, and the landing page shows it as a card without a link.

## Content files

```toml
modid = "tuatara_industry_enhancements"
group = "enhancements"            # enhancements | tools | bugfixes
order = 3                         # place within the group
status = "soon"                   # live (On mod.io) | soon | test
publish = false
modio = ""                        # mod.io page, for live mods
version = "0.7.11"
card = "One line for the landing page's card."
lead = "A paragraph under the mod's name."
hero = "BF-CQ-00"                 # screenshot id in shots/<slug>/, or "site/<name>"

[feature.inactiveWorkers]         # a setting's key from the mod's mod.json
where = ["industry-window"]       # window keys from site.toml
why = "What the game shows or lacks."
# what = "..."                    # defaults to the setting's in-game tooltip
how = ["Step one.", "Step two."]
good = ["A limit or an interplay worth knowing."]

[[feature.inactiveWorkers.figure]]
shot = "IE-03"
caption = "..."
alt = "..."
dim = true                        # darken everything outside the boxes
boxes = [ { x = 3.9, y = 9.1, w = 86.3, h = 22 } ]          # % of the image
pins  = [ { n = 1, x = 29.5, y = 19.9, text = "..." } ]
```

A figure with `[feature.x.figure.before]` and `[feature.x.figure.after]` tables is a Game / With the mod pair. Texts take `` `code` ``, `**bold**` and `[text](url)`; `mod:<slug>#anchor` links to another mod's page. Add `?edit` to a page's URL to read pin coordinates off a figure: moving shows the cursor's x / y in %, a click copies a pin line.
