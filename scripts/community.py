import argparse
import hashlib
import json
import re
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUNDLE_LIMIT = 20 * 1024 * 1024
PRESET_LIMIT = 1 * 1024 * 1024
THUMB_LIMIT = 512 * 1024
TITLE_LIMIT = 80
CREATOR_LIMIT = 80
DESCRIPTION_LIMIT = 500
MAX_TAGS = 8
TAG_LIMIT = 30
SLUG_LIMIT = 48

INDEX_FORMAT = "absentmotion-community"
INDEX_VERSION = 2

KIND_FOLDERS = {
    "bundles": "bundle",
    "presets": "preset",
    "tools": "tool",
}
REQUIRED_READMES = (
    "README.md",
    "bundles/README.md",
    "presets/README.md",
    "tools/README.md",
)
LAYER_TAGS = frozenset({
    "shape",
    "text",
    "drawing",
    "embedScene",
    "camera",
    "audio",
    "nullobj",
    "model",
    "light",
})
BUNDLE_DETAILS = (
    "title",
    "description",
    "tags",
    "creator",
    "madeWith",
    "width",
    "height",
    "fps",
    "lengthMs",
    "thumbnailMs",
    "effects",
    "licence",
)
INDEX_FIELDS = (
    "kind",
    "name",
    "title",
    "creator",
    "description",
    "tags",
    "added",
    "file",
    "bytes",
    "sha256",
    "thumbnail",
    "width",
    "height",
    "lengthMs",
    "minVersion",
)

REPO_PATH_PATTERN = re.compile(r"^[A-Za-z0-9._/-]+$")
SLUG_PATTERN = re.compile(r"^[a-z0-9-]{1,48}$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class Rejected(Exception):
    pass


def is_non_bool_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def is_webp(data):
    return len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"


def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:SLUG_LIMIT].strip("-") or "item"


def unique_slug(parent_dir, title):
    base = slugify(title)
    if not (parent_dir / base).exists():
        return base
    number = 2
    while True:
        suffix = f"-{number}"
        prefix = base[: SLUG_LIMIT - len(suffix)].rstrip("-") or "item"
        candidate = f"{prefix}{suffix}"
        if not (parent_dir / candidate).exists():
            return candidate
        number += 1


def parse_tags_argument(raw_tags):
    if raw_tags is None:
        return None
    tags = [part.strip() for part in raw_tags.split(",") if part.strip()]
    if not tags:
        return None
    if len(tags) > MAX_TAGS:
        raise Rejected(f"too many tags ({len(tags)}); the limit is {MAX_TAGS}")
    for tag in tags:
        if len(tag) > TAG_LIMIT:
            raise Rejected(f"tag {tag!r} is longer than {TAG_LIMIT} characters")
    return tags


def validate_repo_path(value, expected_prefix):
    if not isinstance(value, str) or not value:
        return "must be a non-empty string"
    if not REPO_PATH_PATTERN.fullmatch(value):
        return f"contains invalid characters: {value!r}"
    if value.startswith("/") or value.endswith("/"):
        return f"must not start or end with '/': {value!r}"
    if "//" in value:
        return f"must not contain '//': {value!r}"
    segments = value.split("/")
    if any(segment in ("", ".", "..") for segment in segments):
        return f"contains invalid path segment: {value!r}"
    if not value.startswith(expected_prefix):
        return f"must start with {expected_prefix!r}: {value!r}"
    return None


def read_bundle(path):
    if not path.is_file():
        raise Rejected(f"{path} is not a file")
    size = path.stat().st_size
    if size > BUNDLE_LIMIT:
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
        except (ValueError, UnicodeDecodeError):
            raise Rejected(f"{path.name} has a damaged manifest")
        if not isinstance(manifest, dict) or manifest.get("format") != "absentmotion-package":
            raise Rejected(f"{path.name} is not an AbsentMotion project file")
        community = manifest.get("community")
        if not isinstance(community, dict):
            raise Rejected(
                f"{path.name} is not a Community bundle: export it with Export > Project Bundle > Community bundle"
            )
        thumbnail = community.get("thumbnail")
        if not isinstance(thumbnail, str) or not thumbnail or thumbnail not in names:
            raise Rejected(f"{path.name} has no thumbnail")
        thumb_bytes = bundle.read(thumbnail)
        if not thumb_bytes:
            raise Rejected(f"{path.name} has an empty thumbnail")
        raw_title = community.get("title")
        if raw_title is None:
            raw_title = manifest.get("title")
        title = str(raw_title or "").strip()
        if not title:
            raise Rejected(f"{path.name} has no title")
        if len(title) > TITLE_LIMIT:
            raise Rejected(f"{path.name} title is longer than {TITLE_LIMIT} characters")

        details = {"title": title}
        for key in BUNDLE_DETAILS:
            if key == "title":
                continue
            value = community.get(key)
            if value is None:
                continue
            if key == "creator":
                if not isinstance(value, str):
                    raise Rejected(f"{path.name} creator must be a string")
                cleaned = value.strip()
                if len(cleaned) > CREATOR_LIMIT:
                    raise Rejected(f"{path.name} creator is longer than {CREATOR_LIMIT} characters")
                if cleaned:
                    details[key] = cleaned
            elif key == "description":
                if not isinstance(value, str):
                    raise Rejected(f"{path.name} description must be a string")
                cleaned = value.strip()
                if len(cleaned) > DESCRIPTION_LIMIT:
                    raise Rejected(f"{path.name} description is longer than {DESCRIPTION_LIMIT} characters")
                if cleaned:
                    details[key] = cleaned
            elif key == "tags":
                if not isinstance(value, list) or not all(isinstance(tag, str) for tag in value):
                    raise Rejected(f"{path.name} tags must be a list of strings")
                cleaned_tags = [tag.strip() for tag in value if tag.strip()]
                if len(cleaned_tags) > MAX_TAGS:
                    raise Rejected(f"{path.name} has more than {MAX_TAGS} tags")
                for tag in cleaned_tags:
                    if len(tag) > TAG_LIMIT:
                        raise Rejected(f"{path.name} tag {tag!r} is longer than {TAG_LIMIT} characters")
                if cleaned_tags:
                    details[key] = cleaned_tags
            elif key in ("width", "height", "lengthMs"):
                if not is_non_bool_int(value) or value < 0:
                    raise Rejected(f"{path.name} {key} must be a non-negative integer")
                details[key] = value
            else:
                details[key] = value

    sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    return details, thumb_bytes, size, sha256


def read_preset(path, thumb_path=None):
    if not path.is_file():
        raise Rejected(f"{path} is not a file")
    size = path.stat().st_size
    if size > PRESET_LIMIT:
        raise Rejected(f"{path.name} is {size / 1048576:.1f} MB; the limit is 1 MB")
    raw_bytes = path.read_bytes()
    try:
        root = ET.fromstring(raw_bytes)
    except ET.ParseError:
        raise Rejected(f"{path.name} is not valid XML")
    if root.tag != "scene":
        raise Rejected(f"{path.name} is not a layer preset: root tag must be <scene>")
    if not any(child.tag in LAYER_TAGS for child in root):
        raise Rejected(f"{path.name} is not a layer preset: <scene> has no layer element")
    title = (root.attrib.get("title") or "").strip()
    if not title:
        raise Rejected(f"{path.name} has no title attribute on <scene>")
    if len(title) > TITLE_LIMIT:
        raise Rejected(f"{path.name} title is longer than {TITLE_LIMIT} characters")

    thumb_bytes = None
    if thumb_path is not None:
        if not thumb_path.is_file():
            raise Rejected(f"{thumb_path} is not a file")
        thumb_size = thumb_path.stat().st_size
        if thumb_size > THUMB_LIMIT:
            raise Rejected(f"{thumb_path.name} is {thumb_size / 1024:.0f} KB; the thumbnail limit is 512 KB")
        thumb_bytes = thumb_path.read_bytes()
        if not is_webp(thumb_bytes):
            raise Rejected(f"{thumb_path.name} is not a WebP image")

    sha256 = hashlib.sha256(raw_bytes).hexdigest()
    return title, raw_bytes, thumb_bytes, size, sha256


def add_bundle(path, root=ROOT):
    details, thumb_bytes, size, sha256 = read_bundle(path)
    bundles_dir = root / "bundles"
    bundles_dir.mkdir(parents=True, exist_ok=True)
    name = unique_slug(bundles_dir, details["title"])
    folder = bundles_dir / name
    folder.mkdir(parents=True)

    item_rel = f"bundles/{name}/{name}.absproj"
    thumb_rel = f"bundles/{name}/thumb.webp"
    shutil.copyfile(path, root / item_rel)
    (root / thumb_rel).write_bytes(thumb_bytes)

    info = {
        "kind": "bundle",
        "name": name,
    }
    for key in BUNDLE_DETAILS:
        if key in details and details[key] is not None:
            info[key] = details[key]
    info["added"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    info["file"] = item_rel
    info["bytes"] = size
    info["sha256"] = sha256
    info["thumbnail"] = thumb_rel

    (folder / "item.json").write_text(json.dumps(info, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    rebuild_index(root)
    return f"bundles/{name}"


def add_preset(path, root=ROOT, thumb_path=None, creator=None, description=None, tags=None):
    clean_creator = creator.strip() if creator is not None else None
    if clean_creator is not None and len(clean_creator) > CREATOR_LIMIT:
        raise Rejected(f"creator is longer than {CREATOR_LIMIT} characters")
    clean_description = description.strip() if description is not None else None
    if clean_description is not None and len(clean_description) > DESCRIPTION_LIMIT:
        raise Rejected(f"description is longer than {DESCRIPTION_LIMIT} characters")
    clean_tags = parse_tags_argument(tags)

    title, xml_bytes, thumb_bytes, size, sha256 = read_preset(path, thumb_path)
    presets_dir = root / "presets"
    presets_dir.mkdir(parents=True, exist_ok=True)
    name = unique_slug(presets_dir, title)
    folder = presets_dir / name
    folder.mkdir(parents=True)

    item_rel = f"presets/{name}/{name}.xml"
    (root / item_rel).write_bytes(xml_bytes)

    info = {
        "kind": "preset",
        "name": name,
        "title": title,
    }
    if clean_creator:
        info["creator"] = clean_creator
    if clean_description:
        info["description"] = clean_description
    if clean_tags:
        info["tags"] = clean_tags
    info["added"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    info["file"] = item_rel
    info["bytes"] = size
    info["sha256"] = sha256
    if thumb_bytes is not None:
        thumb_rel = f"presets/{name}/thumb.webp"
        (root / thumb_rel).write_bytes(thumb_bytes)
        info["thumbnail"] = thumb_rel

    (folder / "item.json").write_text(json.dumps(info, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    rebuild_index(root)
    return f"presets/{name}"


def add_item(path, root=ROOT, thumb_path=None, creator=None, description=None, tags=None):
    suffix = path.suffix.lower()
    if suffix == ".absproj":
        if thumb_path is not None or creator is not None or description is not None or tags is not None:
            raise Rejected(f"{path.name}: --thumb, --creator, --description, and --tags only apply to .xml presets")
        return add_bundle(path, root)
    if suffix == ".xml":
        return add_preset(path, root, thumb_path=thumb_path, creator=creator, description=description, tags=tags)
    raise Rejected(f"{path.name}: expected a .absproj bundle or .xml preset")


def build_index_data(root=ROOT):
    entries = []
    for kind_dir_name, expected_kind in KIND_FOLDERS.items():
        kind_dir = root / kind_dir_name
        if not kind_dir.is_dir():
            continue
        for item_dir in sorted(kind_dir.iterdir()):
            if not item_dir.is_dir():
                continue
            item_json = item_dir / "item.json"
            if not item_json.is_file():
                continue
            info = json.loads(item_json.read_text(encoding="utf-8"))
            if not isinstance(info, dict):
                raise ValueError(f"{kind_dir_name}/{item_dir.name}/item.json must be a JSON object")
            entry = {key: info[key] for key in INDEX_FIELDS if key in info}
            if "kind" not in entry:
                entry["kind"] = expected_kind
            if "name" not in entry:
                entry["name"] = item_dir.name
            entries.append(entry)
    entries.sort(key=lambda entry: (entry.get("added", ""), entry.get("name", ""), entry.get("kind", "")), reverse=True)
    return {
        "format": INDEX_FORMAT,
        "version": INDEX_VERSION,
        "items": entries,
    }


def render_index(root=ROOT):
    return json.dumps(build_index_data(root), indent=1, ensure_ascii=False) + "\n"


def rebuild_index(root=ROOT):
    (root / "index.json").write_text(render_index(root), encoding="utf-8")


def check_item_metadata(info, expected_kind, folder_prefix, problems):
    if info.get("kind") != expected_kind:
        problems.append(f"{folder_prefix}item.json: kind must be {expected_kind!r}")
    name = folder_prefix.rstrip("/").split("/")[-1]
    if info.get("name") != name:
        problems.append(f"{folder_prefix}item.json: name must be {name!r}")

    title = info.get("title")
    if not isinstance(title, str) or not title.strip():
        problems.append(f"{folder_prefix}item.json: title must be a non-empty string")
    elif len(title) > TITLE_LIMIT:
        problems.append(f"{folder_prefix}item.json: title exceeds {TITLE_LIMIT} characters")

    if "creator" in info:
        creator = info["creator"]
        if not isinstance(creator, str):
            problems.append(f"{folder_prefix}item.json: creator must be a string")
        elif len(creator) > CREATOR_LIMIT:
            problems.append(f"{folder_prefix}item.json: creator exceeds {CREATOR_LIMIT} characters")

    if "description" in info:
        description = info["description"]
        if not isinstance(description, str):
            problems.append(f"{folder_prefix}item.json: description must be a string")
        elif len(description) > DESCRIPTION_LIMIT:
            problems.append(f"{folder_prefix}item.json: description exceeds {DESCRIPTION_LIMIT} characters")

    if "tags" in info:
        tags = info["tags"]
        if not isinstance(tags, list):
            problems.append(f"{folder_prefix}item.json: tags must be a list")
        else:
            if len(tags) > MAX_TAGS:
                problems.append(f"{folder_prefix}item.json: tags exceeds {MAX_TAGS} items")
            for tag in tags:
                if not isinstance(tag, str) or not tag.strip():
                    problems.append(f"{folder_prefix}item.json: every tag must be a non-empty string")
                elif len(tag) > TAG_LIMIT:
                    problems.append(f"{folder_prefix}item.json: tag {tag!r} exceeds {TAG_LIMIT} characters")

    added = info.get("added")
    if not isinstance(added, str) or not DATE_PATTERN.fullmatch(added):
        problems.append(f"{folder_prefix}item.json: added must be YYYY-MM-DD")
    else:
        try:
            datetime.strptime(added, "%Y-%m-%d")
        except ValueError:
            problems.append(f"{folder_prefix}item.json: added is not a valid calendar date: {added!r}")

    if "minVersion" in info:
        min_version = info["minVersion"]
        if not is_non_bool_int(min_version) or min_version < 1:
            problems.append(f"{folder_prefix}item.json: minVersion must be a positive integer")

    if expected_kind == "preset":
        for key in ("width", "height", "lengthMs"):
            if key in info:
                problems.append(f"{folder_prefix}item.json: {key} is only allowed for bundles")
    elif expected_kind == "bundle":
        for key in ("width", "height", "lengthMs"):
            if key in info and (not is_non_bool_int(info[key]) or info[key] < 0):
                problems.append(f"{folder_prefix}item.json: {key} must be a non-negative integer")


def check_item_folder(root, kind_dir_name, expected_kind, folder, problems):
    name = folder.name
    folder_prefix = f"{kind_dir_name}/{name}/"
    if not SLUG_PATTERN.fullmatch(name) or name.startswith("-") or name.endswith("-"):
        problems.append(f"{folder_prefix}: folder name must be lowercase [a-z0-9-] slug up to {SLUG_LIMIT} characters")

    item_json_path = folder / "item.json"
    if not item_json_path.is_file():
        problems.append(f"{folder_prefix}: missing item.json")
        return

    try:
        info = json.loads(item_json_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError) as error:
        problems.append(f"{folder_prefix}item.json: invalid JSON ({error})")
        return
    if not isinstance(info, dict):
        problems.append(f"{folder_prefix}item.json: must be a JSON object")
        return

    check_item_metadata(info, expected_kind, folder_prefix, problems)

    recorded_bytes = info.get("bytes")
    if not is_non_bool_int(recorded_bytes) or recorded_bytes < 0:
        problems.append(f"{folder_prefix}item.json: bytes must be a non-negative integer")
        recorded_bytes = None
    elif expected_kind == "bundle" and recorded_bytes > BUNDLE_LIMIT:
        problems.append(f"{folder_prefix}item.json: bytes exceeds 20 MB limit")
    elif expected_kind == "preset" and recorded_bytes > PRESET_LIMIT:
        problems.append(f"{folder_prefix}item.json: bytes exceeds 1 MB limit")

    recorded_sha = info.get("sha256")
    if not isinstance(recorded_sha, str) or not SHA256_PATTERN.fullmatch(recorded_sha):
        problems.append(f"{folder_prefix}item.json: sha256 must be 64 lowercase hex characters")
        recorded_sha = None

    file_rel = info.get("file")
    item_file_name = None
    path_error = validate_repo_path(file_rel, folder_prefix)
    if path_error:
        problems.append(f"{folder_prefix}item.json: invalid file path ({path_error})")
    else:
        if expected_kind == "bundle" and file_rel != f"{folder_prefix}{name}.absproj":
            problems.append(f"{folder_prefix}item.json: bundle file must be {folder_prefix}{name}.absproj")
        elif expected_kind == "preset" and file_rel != f"{folder_prefix}{name}.xml":
            problems.append(f"{folder_prefix}item.json: preset file must be {folder_prefix}{name}.xml")

        target_file = root / file_rel
        if target_file.parent == folder:
            item_file_name = target_file.name
        else:
            problems.append(f"{folder_prefix}item.json: file must be directly inside {folder_prefix}")

        if not target_file.is_file():
            problems.append(f"{folder_prefix}: missing item file {file_rel}")
        else:
            actual_bytes = target_file.stat().st_size
            if recorded_bytes is not None and actual_bytes != recorded_bytes:
                problems.append(
                    f"{folder_prefix}: size mismatch for {file_rel} (item.json has {recorded_bytes}, file has {actual_bytes})"
                )
            if expected_kind == "bundle" and actual_bytes > BUNDLE_LIMIT:
                problems.append(f"{folder_prefix}: {file_rel} exceeds 20 MB limit ({actual_bytes} bytes)")
            elif expected_kind == "preset" and actual_bytes > PRESET_LIMIT:
                problems.append(f"{folder_prefix}: {file_rel} exceeds 1 MB limit ({actual_bytes} bytes)")
            actual_sha = hashlib.sha256(target_file.read_bytes()).hexdigest()
            if recorded_sha is not None and actual_sha != recorded_sha:
                problems.append(f"{folder_prefix}: sha256 mismatch for {file_rel}")

    thumb_rel = info.get("thumbnail")
    has_valid_thumb = False
    if expected_kind == "bundle" and thumb_rel is None:
        problems.append(f"{folder_prefix}item.json: bundles must have a thumbnail")
    if thumb_rel is not None:
        thumb_error = validate_repo_path(thumb_rel, folder_prefix)
        if thumb_error:
            problems.append(f"{folder_prefix}item.json: invalid thumbnail path ({thumb_error})")
        elif thumb_rel != f"{folder_prefix}thumb.webp":
            problems.append(f"{folder_prefix}item.json: thumbnail must be {folder_prefix}thumb.webp")
        else:
            has_valid_thumb = True
            thumb_file = root / thumb_rel
            if not thumb_file.is_file():
                problems.append(f"{folder_prefix}: missing thumbnail {thumb_rel}")
            elif expected_kind == "preset" and thumb_file.stat().st_size > THUMB_LIMIT:
                problems.append(f"{folder_prefix}: {thumb_rel} exceeds 512 KB thumbnail limit")

    allowed_names = {"item.json"}
    if item_file_name is not None:
        allowed_names.add(item_file_name)
    if has_valid_thumb:
        allowed_names.add("thumb.webp")
    for child in sorted(folder.iterdir()):
        if child.is_dir() or child.name not in allowed_names:
            problems.append(f"{folder_prefix}: stray entry {child.name}")


def check_repo(root=ROOT):
    problems = []

    for rel_readme in REQUIRED_READMES:
        readme_path = root / rel_readme
        if not readme_path.is_file():
            problems.append(f"missing required README: {rel_readme}")
        elif not readme_path.read_text(encoding="utf-8").strip():
            problems.append(f"empty required README: {rel_readme}")

    for kind_dir_name, expected_kind in KIND_FOLDERS.items():
        kind_dir = root / kind_dir_name
        if not kind_dir.is_dir():
            problems.append(f"missing folder: {kind_dir_name}/")
            continue
        for entry in sorted(kind_dir.iterdir()):
            if not entry.is_dir():
                if entry.name != "README.md":
                    problems.append(f"stray file in {kind_dir_name}/: {entry.name}")
                continue
            check_item_folder(root, kind_dir_name, expected_kind, entry, problems)

    try:
        expected_index = render_index(root)
    except (OSError, ValueError, UnicodeDecodeError) as error:
        problems.append(f"cannot build index.json: {error}")
    else:
        index_path = root / "index.json"
        if not index_path.is_file():
            problems.append("missing index.json")
        else:
            try:
                actual_index = index_path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as error:
                problems.append(f"cannot read index.json: {error}")
            else:
                if actual_index != expected_index:
                    problems.append("index.json does not match what 'index' would write")

    return problems


def create_fake_bundle(path, community=None, padding=0):
    with zipfile.ZipFile(path, "w") as bundle:
        bundle.writestr("project.xml", '<scene title="Glow intro"/>')
        manifest = {
            "format": "absentmotion-package",
            "version": 1,
            "title": "Glow intro",
            "project": "project.xml",
            "media": [],
            "fonts": [],
        }
        if community is not None:
            manifest["community"] = community
            bundle.writestr("community/thumb.webp", b"RIFF0000WEBP")
        if padding:
            bundle.writestr("media/1_big.bin", b"\0" * padding, compress_type=zipfile.ZIP_STORED)
        bundle.writestr("manifest.json", json.dumps(manifest))


def create_fake_preset(path, xml_text):
    path.write_text(xml_text, encoding="utf-8")


def expect_rejected(action, expected_fragment):
    try:
        action()
    except Rejected as rejected:
        if expected_fragment not in str(rejected):
            raise AssertionError(f"expected {expected_fragment!r} in {str(rejected)!r}")
        return
    raise AssertionError(f"expected rejection containing {expected_fragment!r}")


def selftest():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        for rel_readme in REQUIRED_READMES:
            readme_path = root / rel_readme
            readme_path.parent.mkdir(parents=True, exist_ok=True)
            readme_path.write_text("# Test\n\nPlaceholder.\n", encoding="utf-8")
        rebuild_index(root)
        assert check_repo(root) == []

        details = {
            "title": "Glow Intro!",
            "description": "A glowing title",
            "tags": ["Text", "Glow"],
            "creator": "Someone",
            "thumbnail": "community/thumb.webp",
            "width": 1080,
            "height": 1920,
            "lengthMs": 4000,
            "thumbnailMs": 1200,
            "fps": 60,
        }
        good_bundle = root / "good.absproj"
        create_fake_bundle(good_bundle, details)
        assert add_item(good_bundle, root) == "bundles/glow-intro"
        assert add_item(good_bundle, root) == "bundles/glow-intro-2"

        bundle_item = json.loads((root / "bundles/glow-intro/item.json").read_text(encoding="utf-8"))
        assert bundle_item["kind"] == "bundle"
        assert bundle_item["file"] == "bundles/glow-intro/glow-intro.absproj"
        assert bundle_item["thumbnail"] == "bundles/glow-intro/thumb.webp"
        assert bundle_item["fps"] == 60
        assert (root / "bundles/glow-intro/thumb.webp").read_bytes() == b"RIFF0000WEBP"

        good_preset = root / "fade.xml"
        create_fake_preset(good_preset, '<scene title="Fade In"><shape id="1"/></scene>')
        preset_thumb = root / "picture.webp"
        preset_thumb.write_bytes(b"RIFF0000WEBP")
        assert add_item(
            good_preset,
            root,
            thumb_path=preset_thumb,
            creator="PresetMaker",
            description="Smooth fade",
            tags="Shape, Fade",
        ) == "presets/fade-in"
        assert add_item(good_preset, root) == "presets/fade-in-2"

        preset_item = json.loads((root / "presets/fade-in/item.json").read_text(encoding="utf-8"))
        assert preset_item["kind"] == "preset"
        assert preset_item["file"] == "presets/fade-in/fade-in.xml"
        assert preset_item["thumbnail"] == "presets/fade-in/thumb.webp"
        assert preset_item["tags"] == ["Shape", "Fade"]
        preset_two = json.loads((root / "presets/fade-in-2/item.json").read_text(encoding="utf-8"))
        assert "thumbnail" not in preset_two

        index = json.loads((root / "index.json").read_text(encoding="utf-8"))
        assert index["format"] == INDEX_FORMAT
        assert index["version"] == INDEX_VERSION
        assert [entry["name"] for entry in index["items"]] == [
            "glow-intro-2",
            "glow-intro",
            "fade-in-2",
            "fade-in",
        ]
        assert all("path" not in entry for entry in index["items"])
        assert check_repo(root) == []

        plain_bundle = root / "plain.absproj"
        create_fake_bundle(plain_bundle)
        expect_rejected(lambda: add_item(plain_bundle, root), "not a Community bundle")

        over_bundle = root / "big.absproj"
        create_fake_bundle(over_bundle, details, padding=BUNDLE_LIMIT + 1)
        expect_rejected(lambda: add_item(over_bundle, root), "the limit is 20 MB")

        over_preset = root / "big.xml"
        create_fake_preset(
            over_preset,
            f'<scene title="Big"><shape note="{"a" * PRESET_LIMIT}"/></scene>',
        )
        expect_rejected(lambda: add_item(over_preset, root), "the limit is 1 MB")

        bad_xml = root / "broken.xml"
        create_fake_preset(bad_xml, "<scene><shape/>")
        expect_rejected(lambda: add_item(bad_xml, root), "not valid XML")

        wrong_root = root / "wrong-root.xml"
        create_fake_preset(wrong_root, '<project title="X"><shape/></project>')
        expect_rejected(lambda: add_item(wrong_root, root), "root tag must be <scene>")

        no_layer = root / "no-layer.xml"
        create_fake_preset(no_layer, '<scene title="X"><metadata/></scene>')
        expect_rejected(lambda: add_item(no_layer, root), "no layer element")

        no_title = root / "no-title.xml"
        create_fake_preset(no_title, "<scene><text/></scene>")
        expect_rejected(lambda: add_item(no_title, root), "no title attribute")

        bad_thumb = root / "bad.png"
        bad_thumb.write_bytes(b"PNG000000000")
        expect_rejected(lambda: add_item(good_preset, root, thumb_path=bad_thumb), "not a WebP image")

        big_thumb = root / "big.webp"
        big_thumb.write_bytes(b"RIFF0000WEBP" + (b"\0" * THUMB_LIMIT))
        expect_rejected(lambda: add_item(good_preset, root, thumb_path=big_thumb), "512 KB")

        bundle_target = root / "bundles/glow-intro/glow-intro.absproj"
        original_bytes = bundle_target.read_bytes()
        bundle_target.write_bytes(original_bytes + b"X")
        changed_problems = check_repo(root)
        assert any("size mismatch" in problem for problem in changed_problems), changed_problems
        flipped_byte = bytes([original_bytes[-1] ^ 0xFF])
        bundle_target.write_bytes(original_bytes[:-1] + flipped_byte)
        hash_problems = check_repo(root)
        assert any("sha256 mismatch" in problem for problem in hash_problems), hash_problems
        bundle_target.write_bytes(original_bytes)
        assert check_repo(root) == []

        long_preset = root / "long.xml"
        create_fake_preset(long_preset, f'<scene title="{"a" * 60}"><text/></scene>')
        first_long = add_item(long_preset, root)
        second_long = add_item(long_preset, root)
        assert len(first_long.split("/")[1]) == SLUG_LIMIT
        assert len(second_long.split("/")[1]) == SLUG_LIMIT and second_long.endswith("-2")
        assert check_repo(root) == []

        stray_file = root / "presets/fade-in/extra.txt"
        stray_file.write_text("stray", encoding="utf-8")
        stray_problems = check_repo(root)
        assert any("stray entry extra.txt" in problem for problem in stray_problems), stray_problems
        stray_file.unlink()
        assert check_repo(root) == []

        preset_json_path = root / "presets/fade-in/item.json"
        saved_preset_json = preset_json_path.read_text(encoding="utf-8")
        bad_preset_data = json.loads(saved_preset_json)
        bad_preset_data["file"] = "../fade-in.xml"
        preset_json_path.write_text(json.dumps(bad_preset_data) + "\n", encoding="utf-8")
        path_problems = check_repo(root)
        assert any("invalid file path" in problem for problem in path_problems), path_problems
        preset_json_path.write_text(saved_preset_json, encoding="utf-8")
        assert check_repo(root) == []

        tools_readme = root / "tools/README.md"
        saved_readme = tools_readme.read_text(encoding="utf-8")
        tools_readme.unlink()
        readme_problems = check_repo(root)
        assert any("tools/README.md" in problem for problem in readme_problems), readme_problems
        tools_readme.write_text(saved_readme, encoding="utf-8")
        assert check_repo(root) == []

        saved_index = (root / "index.json").read_text(encoding="utf-8")
        (root / "index.json").write_text('{\n "format": "absentmotion-community",\n "version": 2,\n "items": []\n}\n', encoding="utf-8")
        stale_problems = check_repo(root)
        assert any("index.json does not match" in problem for problem in stale_problems), stale_problems
        (root / "index.json").write_text(saved_index, encoding="utf-8")
        assert check_repo(root) == []

    print("selftest passed")


def build_parser():
    parser = argparse.ArgumentParser(
        prog="community.py",
        description="Manage AbsentMotion Community bundles, presets, and index.json.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser("add", help="add .absproj bundles or .xml presets")
    add_parser.add_argument("files", nargs="+", type=Path, metavar="FILE", help="bundle (.absproj) or preset (.xml) files to add")
    add_parser.add_argument("--thumb", type=Path, metavar="WEBP", help="optional WebP thumbnail for a preset (at most 512 KB)")
    add_parser.add_argument("--creator", help="creator name for presets (at most 80 characters)")
    add_parser.add_argument("--description", help="description for presets (at most 500 characters)")
    add_parser.add_argument("--tags", help="comma-separated tags for presets (up to 8 tags, 30 characters each)")

    subparsers.add_parser("index", help="rebuild index.json from all item.json files")
    subparsers.add_parser("check", help="verify item files, metadata, paths, READMEs, and index.json")
    subparsers.add_parser("selftest", help="run built-in self-tests in temporary folders")
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "selftest":
        selftest()
        return 0

    if args.command == "index":
        try:
            rebuild_index(ROOT)
        except (OSError, ValueError, UnicodeDecodeError) as error:
            print(f"error: {error}", file=sys.stderr)
            return 1
        print("index.json rebuilt")
        return 0

    if args.command == "check":
        problems = check_repo(ROOT)
        if problems:
            for problem in problems:
                print(problem, file=sys.stderr)
            return 1
        print("check passed")
        return 0

    if args.command == "add":
        if args.thumb is not None and len(args.files) != 1:
            print("rejected: --thumb can only be used when adding one preset file", file=sys.stderr)
            return 1
        failed = 0
        for file in args.files:
            try:
                added_folder = add_item(
                    file,
                    root=ROOT,
                    thumb_path=args.thumb,
                    creator=args.creator,
                    description=args.description,
                    tags=args.tags,
                )
                print(f"added {added_folder}")
            except Rejected as rejected:
                print(f"rejected: {rejected}", file=sys.stderr)
                failed += 1
        return 1 if failed else 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
