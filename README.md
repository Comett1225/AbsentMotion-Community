# AbsentMotion Community

Edits, presets and templates made with [AbsentMotion](https://github.com/Comett1225/AbsentMotion) and shared by the
community. Each item is a **Community bundle**: an AbsentMotion project file (`.absproj`) that also carries a title, a
thumbnail taken from the project itself, a description, tags and the creator's name.

## Using an item

1. Open the item's folder in `items/`.
2. Download the `.absproj` file.
3. Open it in AbsentMotion 5.1 or later (on a phone: Import on the Home screen; on a computer: drag it onto the window).

## Sharing your own

Only the maintainer adds items to this repository. To share something:

1. In AbsentMotion, open your project, go to **Export**, open the arrow next to **Project Bundle** and pick
   **Community bundle**.
2. Fill in the title, pick the thumbnail moment, and add a description, tags and your name.
3. Send the `.absproj` file to the maintainer (Discord or the feedback form linked in the app's About page).

Rules:

- The file must be **20 MB or smaller**, media and fonts included.
- It must be a **Community bundle** (made with the Community bundle option, so it has its thumbnail and details).
- You made it, or you have the right to share everything in it.
- Items are shared under the terms in [LICENSE-ITEMS.md](LICENSE-ITEMS.md).

## Layout

```
index.json                    the list of every item, made by tools/add_item.py
items/<name>/<name>.absproj   the Community bundle
items/<name>/thumb.webp       its thumbnail
items/<name>/item.json        its details
tools/add_item.py             adds a bundle and rebuilds index.json
```

## For the maintainer

```
python3 tools/add_item.py path/to/Item.absproj
```

The script checks the file (size, Community bundle details, thumbnail), makes the item folder and rebuilds `index.json`.
`python3 tools/add_item.py --rebuild` only rebuilds `index.json`, and `python3 tools/add_item.py --selftest` checks the
script itself.
