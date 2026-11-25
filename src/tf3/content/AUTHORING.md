# Writing a mod page

One TOML file per mod in `content/mods/<slug>.toml`; `build.py` turns it into `mods/<slug>/`. Screenshot masters are in `shots/<slug>/<ID>.png`; the storyboard (`knowledge/website/tf3-screenshot-storyboard.md` in the game folder, §4) says what each shot shows and which callouts it was taken for.

Models: `bug-fix-crosswalk-queue.toml` (a live page, finished) and `industry-enhancements.toml` (sections, a figure with pins and boxes).

## Top-level fields

| Field | |
|---|---|
| `modid`, `group`, `order`, `status`, `version`, `modio` | Keep as they are. `status` is `live` only once the mod is on mod.io. |
| `publish` | `true` builds the page on the public site. |
| `card` | One line for the landing page card (what the mod gives you). |
| `card_image` | Optional `site/<file>` for the card. |
| `lead` | Two or three sentences under the title: the problem and what the mod adds. |
| `description` | Meta description: "<Name> for Transport Fever 3: …" in one sentence. |
| `hero`, `hero_alt` | Optional shot beside the lead (a wide, striking one). |
| `intro` | Optional paragraphs after the head. |
| `compat` | Compatibility: mods it works with or shares windows with. |
| `issues` | Optional list of known issues. |
| `features` | Optional order of feature keys; default: the settings in `mods/<slug>.json` minus `logging`. Every key is a setting key there (or has its own `title`). |
| `[[section]]` | Optional groups: `title`, `features = [...]`; together they must list every feature once. |
| `[[change]]` | Optional `version`, `text`, newest first. |

## A feature: `[feature.<key>]`

| Field | |
|---|---|
| `where` | Keys of the windows it shows in: `line-manager`, `line-window`, `station-window`, `industry-window`, `town-window`, `warehouse-window`, `vehicle-window`, `vehicle-store`, `statistics`, `subsidies`, `game-bar`, `mod-buttons`, `map`, `build-tools`, `popups`, `background`. |
| `why` | The problem in the game, from the player's side. One short paragraph (two at most). |
| `what` | What the feature does. Defaults to the setting's tooltip; write it when the tooltip is too terse. |
| `how` | Optional numbered steps, when it isn't obvious where to click. |
| `good` | Optional "Good to know" bullets: limits, rules of thumb, what stays as it was. |
| `also` | Optional: where else it shows. |
| `title`, `short`, `anchor` | Defaults from the setting's name and `what`; rarely needed. |

Text takes `code`, **bold**, [text](url) and `[text](mod:<slug>#anchor)` links. Triple-quoted strings for paragraphs; a blank line starts a new paragraph.

## Figures: `[[feature.<key>.figure]]`

```toml
[[feature.stocksCard.figure]]
shot = "WE-02"
alt = "What the image shows, for screen readers"
caption = "One or two sentences: which save, what to look at."
pins = [
  { n = 1, x = 30.5, y = 18, text = "What this part shows and what it means." },
]
boxes = [ { x = 4, y = 10, w = 90, h = 20 } ]   # optional frames, % of the image
dim = true                                       # optional: darken outside the boxes
layout = "side"                                  # optional: a narrow window beside its legend

# before / after: two shots of one save, the game alone vs with the mod
[[feature.recipeFigures.figure]]
caption = "…"
[feature.recipeFigures.figure.before]
shot = "IE-01-stock"
alt = "…"
pins = [ … ]
[feature.recipeFigures.figure.after]
shot = "IE-01"
alt = "…"
pins = [ … ]
```

- **Pins** sit on the thing they explain: `x` / `y` in % of the image (0–100, decimals fine), numbered from 1 in reading order, 1–5 per image. To read positions, write a gridded copy and look at it:
  `python -I src/tf3/grid_preview.py <slug>/<ID> [<slug>/<ID> …] --out <scratch dir>` (labels every 10 %, faint lines every 5 %). Put a pin beside small text rather than on it when it would hide the figure the text explains.
- **Pin text**: one sentence, at most two; say what is there and what it tells the player ("Next Full: the cargo to act on first, here Grain in 41 days.").
- A narrow window (portrait crop) reads best with `layout = "side"`.
- Use a before / after pair only where the game itself shows the figure differently; the `-stock` shots exist for that. Labels default to "Game" and "With the mod" (`before_label`, `after_label`).
- Every `shot` must exist (no `pending` on a published page). Not every shot has to be used: pick the ones that explain the feature best; a feature without a fitting shot keeps only its text.

## Style

- Plain, short sentences in present tense, addressed to the player ("your lines"). No marketing words ("powerful", "seamless", "ultimate"), no exclamation marks.
- British spelling, as the game: colour, kerb, centre, travelled.
- The game's own names, capitalised as in the game: Line Manager, Production card, Boosters card, statistics window's Industries tab, Mod Hub.
- Figures and claims come from the mod's settings snapshot (`mods/<slug>.json`: description and tooltips) and its doc (`knowledge/mods/<modid>.md` in the game folder). Don't promise what the doc marks untested or ❓ unless the snapshot says so too.
- No internal names: no script, recipe or API names, version histories, test notes or save names beyond what a caption needs.

## Check

`python src/tf3/build.py --drafts --out <scratch dir>` must end without errors. `build-preview/` (`--drafts` without `--out`) is the local preview on port 8792.

## Publish

The Pages workflow uploads `site/` as committed; it doesn't build. After changing a TOML or a shot, run `python src/tf3/build.py` (no flags: writes `site/`) and commit `site/` with the sources, or the live pages keep the old text and images.
