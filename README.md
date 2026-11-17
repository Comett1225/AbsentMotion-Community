# AbsentMotion Community

Things people made with [AbsentMotion](https://github.com/Comett1225/AbsentMotion): project bundles and layer presets.

## Using items

In AbsentMotion 5.2 or later, open **Home > Community**, tap an item, and tap **Add**.

You can also download an item file from GitHub and import it yourself:

- On a phone, open the downloaded file with AbsentMotion.
- On a computer, drag the file onto the AbsentMotion window.

## Sharing your own

Only the maintainer adds items to this repository.

- For a project bundle, open your project in AbsentMotion, go to **Export**, tap the arrow next to **Project Bundle**, and choose **Community bundle**.
- Sharing your own layer presets from the app is coming in a later update. Until then, only the maintainer adds presets.
- Send your file on [Discord](https://discord.gg/xXEHj8Sx8X) or through the report form linked in the app's About screen.

## Rules

- Bundles must be 20 MB or smaller.
- Presets must be 1 MB or smaller.
- You made the item, or you have the right to share everything in it.
- Items are shared under CC BY 4.0 per [LICENSE-ITEMS.md](LICENSE-ITEMS.md).

## Pictures

Every picture in the Community tab shows the item itself.

- A bundle's picture is a frame of its own project. The creator picks the moment and the square when exporting the Community bundle, and `scripts/community.py` copies that picture out of the bundle.
- A preset has no picture file. The app draws the preset itself and shows its most visible moment.

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
presets/<name>/<name>.xml       layer preset (at most 1 MB)
presets/<name>/item.json        preset details
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

- `add` adds `.absproj` bundles or `.xml` presets and updates `index.json`. Presets also accept `--creator`, `--description`, and `--tags`. Presets take no picture.
- `index` rebuilds `index.json` from every `item.json`.
- `check` verifies files, sizes, SHA-256 hashes, paths, limits, READMEs, and `index.json`, and rejects a preset folder with a `thumb.webp` or a `thumbnail` in its `item.json`.
- `selftest` runs built-in tests in temporary folders.
