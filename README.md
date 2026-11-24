# AbsentMotion Community

Things people made with [AbsentMotion](https://github.com/Comett1225/AbsentMotion): project bundles, layer presets and effects.

**Share your own: [send it with the Community form](https://forms.gle/Xyn4TiKNJ9kUPQ7x8).** Upload the file to any file hosting website (an anonymous one, Google Drive or MEGA) and paste the link in the form.

## Using items

In AbsentMotion 5.2 or later, open **Home > Community**, tap an item, and tap **Add**.

You can also download an item file from GitHub and import it yourself:

- On a phone, open the downloaded file with AbsentMotion.
- On a computer, drag the file onto the AbsentMotion window.

A preset goes into **My Presets** instead of opening as a project. An effect goes into **Effects > Added**.

## Sharing your own

Only the maintainer adds items to this repository. Everything is checked by a person before it goes up.

- For a project bundle, open your project in AbsentMotion, go to **Export**, tap the arrow next to **Project Bundle**, and choose **Community bundle**.
- For a preset, go to **Home > Templates > My Presets**, open the preset's menu, and tap **Share to Community**. This saves a preset bundle: an `.absproj` file with the preset on its placeholder picture or video.
- Upload the `.absproj` file to any file hosting website: an anonymous one works, and so do Google Drive and MEGA. Anyone with the link must be able to download it.
- Paste the link in the [Community form](https://forms.gle/Xyn4TiKNJ9kUPQ7x8) (also at the top of the Community tab in the app) and choose Project, Preset or Effect.
- To make an effect, read [effects/README.md](effects/README.md): it explains the effect file, its settings and its shader, with an example.

## Rules

- Bundles must be 20 MB or smaller.
- Preset bundles must be 20 MB or smaller. Older `.xml` presets must be 1 MB or smaller.
- Effect files (`.json` or `.abmfx` packs) must be 512 KB or smaller. No effects taken or converted from another app's files.
- Edits can use clips from shows, anime, films and music videos. If you share someone else's edit, project, preset or art, credit them in the description. Paid assets are not allowed.
- If something you made was shared here and you want it taken down, contact **comett1225** on Discord.
- Items are shared under CC BY 4.0 per [LICENSE-ITEMS.md](LICENSE-ITEMS.md). Clips from shows, anime and films in an edit stay with their owners and are not part of that licence.

## Pictures

Every picture in the Community tab shows the item itself.

- A bundle's picture is a frame of its own project. The creator picks the moment and the square when exporting the Community bundle, and `scripts/community.py` copies that picture out of the bundle.
- A preset has no picture file. The app draws the preset itself on its placeholder and shows its most visible moment.
- An effect has no picture file either. The app draws the effect on a sample picture.

## Layout

```
README.md                       overview, usage, and rules
LICENSE-ITEMS.md                item licence (CC BY 4.0)
index.json                      generated index of all items
bundles/README.md               what goes in bundles/
bundles/<name>/<name>.absproj   Community bundle (at most 20 MB)
bundles/<name>/thumb.webp       bundle picture, copied out of the bundle
bundles/<name>/item.json        bundle details
presets/README.md               what goes in presets/
presets/<name>/<name>.absproj   preset bundle (at most 20 MB)
presets/<name>/<name>.xml       older layer preset (at most 1 MB)
presets/<name>/item.json        preset details
effects/README.md               how to make and share effects
effects/<name>/<name>.json      one effect (at most 512 KB)
effects/<name>/<name>.abmfx      effect pack, a ZIP of .json effects (at most 512 KB)
effects/<name>/item.json        effect details
scripts/community.py            maintainer script
.github/workflows/check.yml     CI workflow
```

## For the maintainer

```
python3 scripts/community.py add FILE...
python3 scripts/community.py index
python3 scripts/community.py check
python3 scripts/community.py selftest
```

- `add` adds `.absproj` files or `.xml` presets and updates `index.json`. A project bundle goes in `bundles/` and a preset bundle in `presets/`. A preset bundle must have one layer in a preset scene and no picture. `.xml` presets also accept `--creator`, `--description`, and `--tags`; preset bundles carry their own details. `.abmfx` and `.json` effects go in `effects/`; they take `--creator` (default: the effect's author), `--description`, `--tags`, and `--title` (needed for a pack whose file name is not a good title).
- `index` rebuilds `index.json` from every `item.json`.
- `check` verifies files, sizes, SHA-256 hashes, paths, limits, READMEs, and `index.json`, checks that every preset has one layer, re-checks every effect file (ids, names, settings, shader size and pack limits), and rejects a preset or effect folder with a `thumb.webp` or a `thumbnail` in its `item.json`.
- `selftest` runs built-in tests in temporary folders.
