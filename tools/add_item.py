#!/usr/bin/env python3
import argparse
import hashlib
import json
import re
import shutil
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIMIT = 20 * 1024 * 1024
DETAILS = ("title", "description", "tags", "creator", "madeWith", "width", "height", "fps", "lengthMs", "thumbnailMs", "effects", "licence")
LISTED = ("name", "title", "creator", "tags", "added", "bytes", "file", "thumbnail", "width", "height", "lengthMs")


class Rejected(Exception):
    pass


def read_bundle(path):
    size = path.stat().st_size
    if size > LIMIT:
        raise Rejected(f"{path.name} is {size / 1048576:.1f} MB; the limit is 20 MB")
    try:
        bundle = zipfile.ZipFile(path)
    except zipfile.BadZipFile:
        raise Rejected(f"{path.name} is not an AbsentMotion project file")
    with bundle:
        names = set(bundle.namelist())
        if "manifest.json" not in names or "project.xml" not in names:
            raise Rejected(f"{path.name} is not an AbsentMotion project file")
        try:
            manifest = json.loads(bundle.read("manifest.json"))
        except ValueError:
            raise Rejected(f"{path.name} has a damaged manifest")
        if manifest.get("format") != "absentmotion-package":
            raise Rejected(f"{path.name} is not an AbsentMotion project file")
        community = manifest.get("community")
        if not isinstance(community, dict):
            raise Rejected(f"{path.name} is not a Community bundle: export it with Export > Project Bundle > Community bundle")
        thumbnail = community.get("thumbnail")
        if not thumbnail or thumbnail not in names:
            raise Rejected(f"{path.name} has no thumbnail")
        title = str(community.get("title") or manifest.get("title") or "").strip()
        if not title:
            raise Rejected(f"{path.name} has no title")
        return dict(community, title=title), bundle.read(thumbnail), size


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:48].strip("-") or "item"


def add(path, root=ROOT):
    community, thumbnail, size = read_bundle(path)
    items = root / "items"
    base = slug(community["title"])
    name, number = base, 2
    while (items / name).exists():
        name, number = f"{base}-{number}", number + 1
    folder = items / name
    folder.mkdir(parents=True)
    shutil.copyfile(path, folder / f"{name}.absproj")
    (folder / "thumb.webp").write_bytes(thumbnail)
    info = {key: community[key] for key in DETAILS if community.get(key) is not None}
    info.update(name=name, file=f"{name}.absproj", thumbnail="thumb.webp", bytes=size,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(), added=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    (folder / "item.json").write_text(json.dumps(info, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    rebuild(root)
    return name


def rebuild(root=ROOT):
    entries = []
    for file in sorted((root / "items").glob("*/item.json")):
        info = json.loads(file.read_text(encoding="utf-8"))
        entry = {key: info[key] for key in LISTED if key in info}
        entry["path"] = f"items/{info['name']}"
        entries.append(entry)
    entries.sort(key=lambda e: (e.get("added", ""), e["name"]), reverse=True)
    index = {"format": "absentmotion-community", "version": 1, "items": entries}
    (root / "index.json").write_text(json.dumps(index, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def fake_bundle(path, community=None, padding=0):
    with zipfile.ZipFile(path, "w") as bundle:
        bundle.writestr("project.xml", "<scene title=\"Glow intro\"/>")
        manifest = {"format": "absentmotion-package", "version": 1, "title": "Glow intro", "project": "project.xml", "media": [], "fonts": []}
        if community is not None:
            manifest["community"] = community
            bundle.writestr("community/thumb.webp", b"RIFF0000WEBP")
        if padding:
            bundle.writestr("media/1_big.bin", b"\0" * padding, compress_type=zipfile.ZIP_STORED)
        bundle.writestr("manifest.json", json.dumps(manifest))


def selftest():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        (root / "items").mkdir()
        details = {"title": "Glow Intro!", "description": "A glowing title", "tags": ["Text", "Glow"], "creator": "Someone", "thumbnail": "community/thumb.webp", "thumbnailMs": 1200}
        good = root / "good.absproj"
        fake_bundle(good, details)
        assert add(good, root) == "glow-intro"
        assert add(good, root) == "glow-intro-2"
        item = json.loads((root / "items/glow-intro/item.json").read_text())
        assert item["creator"] == "Someone" and item["tags"] == ["Text", "Glow"] and (root / "items/glow-intro/thumb.webp").read_bytes() == b"RIFF0000WEBP"
        index = json.loads((root / "index.json").read_text())
        assert [e["name"] for e in index["items"]] == ["glow-intro-2", "glow-intro"]
        plain = root / "plain.absproj"
        fake_bundle(plain)
        big = root / "big.absproj"
        fake_bundle(big, details, padding=LIMIT + 1)
        for bad, why in ((plain, "not a Community bundle"), (big, "the limit is 20 MB")):
            try:
                add(bad, root)
                raise AssertionError(f"{bad.name} was accepted")
            except Rejected as rejected:
                assert why in str(rejected), rejected
        assert len(list((root / "items").iterdir())) == 2
    print("selftest passed")


def main():
    parser = argparse.ArgumentParser(description="Adds Community bundles to this repository and rebuilds index.json.")
    parser.add_argument("files", nargs="*", type=Path, help="Community bundles (.absproj) to add")
    parser.add_argument("--rebuild", action="store_true", help="only rebuild index.json")
    parser.add_argument("--selftest", action="store_true", help="check this script")
    args = parser.parse_args()
    if args.selftest:
        selftest()
        return 0
    if args.rebuild or not args.files:
        rebuild()
        print("index.json rebuilt")
        return 0
    failed = 0
    for file in args.files:
        try:
            print(f"added items/{add(file)}")
        except Rejected as rejected:
            print(f"rejected: {rejected}", file=sys.stderr)
            failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
