import argparse
import hashlib
import json
import re
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile
import zlib
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUNDLE_LIMIT = 20 * 1024 * 1024
PRESET_LIMIT = 1 * 1024 * 1024
EFFECT_LIMIT = 512 * 1024
EFFECT_SKSL_LIMIT = 64 * 1024
EFFECT_PARAM_LIMIT = 32
EFFECT_PACK_LIMIT = 20
EFFECT_CATEGORIES = frozenset({"color", "blur", "distort", "stylize", "noise", "repeat", "key", "move", "beat", "3d", "text", "other"})
EFFECT_PARAM_TYPES = frozenset({"float", "angle", "point", "color", "switch", "choice", "text"})
MANIFEST_LIMIT = 1 * 1024 * 1024
THUMB_LIMIT = 4 * 1024 * 1024
ENTRY_COUNT_LIMIT = 2000
UNPACKED_LIMIT = 2 * 1024 * 1024 * 1024
ZIP_ERRORS = (zipfile.BadZipFile, zipfile.LargeZipFile, RuntimeError, NotImplementedError, OSError, EOFError, zlib.error)
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
    "effects": "effect",
}
REQUIRED_READMES = (
    "README.md",
    "bundles/README.md",
    "presets/README.md",
    "effects/README.md",
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
PRESET_DETAILS = (
    "title",
    "description",
    "tags",
    "creator",
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
EFFECT_ID_PATTERN = re.compile(r"^[a-z0-9-]{1,40}$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2}Z)?$")


class Rejected(Exception):
    pass


def is_non_bool_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


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


def is_webp(data):
    return len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"


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
    try:
        with bundle:
            return read_bundle_entries(path, bundle, size)
    except ZIP_ERRORS as error:
        raise Rejected(f"{path.name} is damaged: {error}")


def read_bundle_entries(path, bundle, size):
    entries = bundle.infolist()
    names = {entry.filename for entry in entries}
    if "manifest.json" not in names or "project.xml" not in names:
        raise Rejected(f"{path.name} is not an AbsentMotion project file")
    if len(entries) > ENTRY_COUNT_LIMIT:
        raise Rejected(f"{path.name} has more than {ENTRY_COUNT_LIMIT} files")
    if sum(entry.file_size for entry in entries) > UNPACKED_LIMIT:
        raise Rejected(f"{path.name} unpacks to more than 2 GB")
    if bundle.getinfo("manifest.json").file_size > MANIFEST_LIMIT:
        raise Rejected(f"{path.name} has a damaged manifest")
    damaged = bundle.testzip()
    if damaged is not None:
        raise Rejected(f"{path.name} is damaged: {damaged} does not match its checksum")
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
    kind = community.get("kind")
    if kind not in (None, "project", "preset"):
        raise Rejected(f"{path.name} has an unknown kind {kind!r}")
    if kind == "preset":
        if "thumbnail" in community or "community/thumb.webp" in names:
            raise Rejected(f"{path.name} is a preset with a thumbnail; presets take no picture, the app draws the preset")
        if bundle.getinfo("project.xml").file_size > BUNDLE_LIMIT:
            raise Rejected(f"{path.name} scene is larger than 20 MB")
        if read_preset_scene(path.name, bundle.read("project.xml")).attrib.get("type") != "preset":
            raise Rejected(f"{path.name} is not a preset: its scene type is not preset")
        thumb_bytes = None
    else:
        thumbnail = community.get("thumbnail")
        if not isinstance(thumbnail, str) or not thumbnail or thumbnail not in names:
            raise Rejected(f"{path.name} has no thumbnail")
        if bundle.getinfo(thumbnail).file_size > THUMB_LIMIT:
            raise Rejected(f"{path.name} thumbnail is larger than 4 MB")
        thumb_bytes = bundle.read(thumbnail)
        if not thumb_bytes:
            raise Rejected(f"{path.name} has an empty thumbnail")
        if not is_webp(thumb_bytes):
            raise Rejected(f"{path.name} thumbnail is not a WebP picture")
    raw_title = community.get("title")
    if raw_title is None:
        raw_title = manifest.get("title")
    title = str(raw_title or "").strip()
    if not title:
        raise Rejected(f"{path.name} has no title")
    if len(title) > TITLE_LIMIT:
        raise Rejected(f"{path.name} title is longer than {TITLE_LIMIT} characters")

    details = {"title": title}
    for key in PRESET_DETAILS if kind == "preset" else BUNDLE_DETAILS:
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
    return ("preset" if kind == "preset" else "bundle"), details, thumb_bytes, size, sha256


def read_preset_scene(file_name, raw_bytes):
    try:
        root = ET.fromstring(raw_bytes)
    except ET.ParseError:
        raise Rejected(f"{file_name} is not valid XML")
    if root.tag != "scene":
        raise Rejected(f"{file_name} is not a layer preset: root tag must be <scene>")
    layers = sum(child.tag in LAYER_TAGS for child in root)
    if layers == 0:
        raise Rejected(f"{file_name} is not a layer preset: <scene> has no layer element")
    if layers > 1:
        raise Rejected(f"{file_name} is not a layer preset: <scene> has {layers} layers, a preset has one")
    return root


def read_preset(path):
    if not path.is_file():
        raise Rejected(f"{path} is not a file")
    size = path.stat().st_size
    if size > PRESET_LIMIT:
        raise Rejected(f"{path.name} is {size / 1048576:.1f} MB; the limit is 1 MB")
    raw_bytes = path.read_bytes()
    root = read_preset_scene(path.name, raw_bytes)
    title = (root.attrib.get("title") or "").strip()
    if not title:
        raise Rejected(f"{path.name} has no title attribute on <scene>")
    if len(title) > TITLE_LIMIT:
        raise Rejected(f"{path.name} title is longer than {TITLE_LIMIT} characters")

    sha256 = hashlib.sha256(raw_bytes).hexdigest()
    return title, raw_bytes, size, sha256


def check_effect(source, effect):
    if not isinstance(effect, dict):
        raise Rejected(f"{source} is not an effect object")
    effect_id = effect.get("id")
    if not isinstance(effect_id, str) or not EFFECT_ID_PATTERN.fullmatch(effect_id):
        raise Rejected(f"{source}: id must be 1 to 40 lowercase letters, digits or dashes")
    name = effect.get("name")
    if not isinstance(name, str) or not name.strip() or len(name) > TITLE_LIMIT:
        raise Rejected(f"{source}: name must be a non-empty string of at most {TITLE_LIMIT} characters")
    if not isinstance(effect.get("category"), str):
        raise Rejected(f"{source}: category must be a string")
    sksl = effect.get("sksl")
    if not isinstance(sksl, str) or "main(" not in sksl:
        raise Rejected(f"{source}: sksl must be a shader with a main function")
    if len(sksl.encode("utf-8")) > EFFECT_SKSL_LIMIT:
        raise Rejected(f"{source}: sksl is larger than 64 KB")
    params = effect.get("params")
    if not isinstance(params, list) or len(params) > EFFECT_PARAM_LIMIT:
        raise Rejected(f"{source}: params must be a list of at most {EFFECT_PARAM_LIMIT} settings")
    seen = set()
    for param in params:
        if not isinstance(param, dict) or not isinstance(param.get("id"), str) or param.get("type") not in EFFECT_PARAM_TYPES:
            raise Rejected(f"{source}: every setting needs an id and a type ({', '.join(sorted(EFFECT_PARAM_TYPES))})")
        if param["id"] in seen:
            raise Rejected(f"{source}: setting {param['id']!r} appears twice")
        seen.add(param["id"])
        if param["type"] == "choice":
            options = param.get("options")
            if not isinstance(options, list) or not options or not is_non_bool_int(param.get("default")) or not 0 <= param["default"] < len(options):
                raise Rejected(f"{source}: choice {param['id']!r} needs options and a default index")
    if "version" in effect and (not is_non_bool_int(effect["version"]) or effect["version"] < 1):
        raise Rejected(f"{source}: version must be a positive integer")
    return effect


def read_effects(path):
    if not path.is_file():
        raise Rejected(f"{path} is not a file")
    size = path.stat().st_size
    if size > EFFECT_LIMIT:
        raise Rejected(f"{path.name} is {size / 1024:.0f} KB; the limit is 512 KB")
    raw_bytes = path.read_bytes()
    suffix = path.suffix.lower()
    effects = []
    if suffix == ".json":
        try:
            effects.append(check_effect(path.name, json.loads(raw_bytes.decode("utf-8"))))
        except (ValueError, UnicodeDecodeError) as error:
            raise Rejected(f"{path.name} is not valid JSON ({error})")
    elif suffix == ".amfx":
        try:
            with zipfile.ZipFile(path) as pack:
                entries = [info for info in pack.infolist() if not info.is_dir() and "/" not in info.filename and info.filename.lower().endswith(".json")]
                if len(pack.infolist()) > ENTRY_COUNT_LIMIT or sum(info.file_size for info in entries) > 4 * EFFECT_LIMIT:
                    raise Rejected(f"{path.name} unpacks too large")
                if not entries:
                    raise Rejected(f"{path.name} has no effect .json files at its top level")
                if len(entries) > EFFECT_PACK_LIMIT:
                    raise Rejected(f"{path.name} has {len(entries)} effects; the limit is {EFFECT_PACK_LIMIT}")
                for info in entries:
                    try:
                        effects.append(check_effect(f"{path.name}/{info.filename}", json.loads(pack.read(info).decode("utf-8"))))
                    except (ValueError, UnicodeDecodeError) as error:
                        raise Rejected(f"{path.name}/{info.filename} is not valid JSON ({error})")
        except ZIP_ERRORS as error:
            raise Rejected(f"{path.name} is not a readable .amfx pack ({error})")
    else:
        raise Rejected(f"{path.name}: effects are .amfx packs or .json files")
    ids = [effect["id"] for effect in effects]
    if len(set(ids)) != len(ids):
        raise Rejected(f"{path.name} has two effects with the same id")
    return effects, raw_bytes, size, hashlib.sha256(raw_bytes).hexdigest()


def add_effect(path, root=ROOT, creator=None, description=None, tags=None, title=None):
    effects, raw_bytes, size, sha256 = read_effects(path)
    first = effects[0]
    clean_title = (title or (first["name"] if len(effects) == 1 else path.stem.replace("_", " ").replace("-", " "))).strip()
    if not clean_title or len(clean_title) > TITLE_LIMIT:
        raise Rejected(f"{path.name}: title must be 1 to {TITLE_LIMIT} characters (use --title for packs)")
    clean_creator = (creator if creator is not None else first.get("author") or "").strip()
    if len(clean_creator) > CREATOR_LIMIT:
        raise Rejected(f"creator is longer than {CREATOR_LIMIT} characters")
    clean_description = (description if description is not None else (first.get("description") or "" if len(effects) == 1 else "")).strip()
    if len(clean_description) > DESCRIPTION_LIMIT:
        raise Rejected(f"description is longer than {DESCRIPTION_LIMIT} characters")
    clean_tags = parse_tags_argument(tags)

    effects_dir = root / "effects"
    effects_dir.mkdir(parents=True, exist_ok=True)
    name = unique_slug(effects_dir, clean_title)
    folder = effects_dir / name
    folder.mkdir(parents=True)
    item_rel = f"effects/{name}/{name}{path.suffix.lower()}"
    (root / item_rel).write_bytes(raw_bytes)

    info = {"kind": "effect", "name": name, "title": clean_title}
    if clean_creator:
        info["creator"] = clean_creator
    if clean_description:
        info["description"] = clean_description
    if clean_tags:
        info["tags"] = clean_tags
    info["added"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    info["file"] = item_rel
    info["bytes"] = size
    info["sha256"] = sha256
    info["effects"] = [effect["name"] for effect in effects]
    (folder / "item.json").write_text(json.dumps(info, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    rebuild_index(root)
    return f"effects/{name}"


def add_bundle(path, root=ROOT):
    kind, details, thumb_bytes, size, sha256 = read_bundle(path)
    kind_dir_name = "presets" if kind == "preset" else "bundles"
    kind_dir = root / kind_dir_name
    kind_dir.mkdir(parents=True, exist_ok=True)
    name = unique_slug(kind_dir, details["title"])
    folder = kind_dir / name
    folder.mkdir(parents=True)

    item_rel = f"{kind_dir_name}/{name}/{name}.absproj"
    shutil.copyfile(path, root / item_rel)

    info = {
        "kind": kind,
        "name": name,
    }
    for key in BUNDLE_DETAILS:
        if key in details and details[key] is not None:
            info[key] = details[key]
    info["added"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    info["file"] = item_rel
    info["bytes"] = size
    info["sha256"] = sha256
    if thumb_bytes is not None:
        thumb_rel = f"bundles/{name}/thumb.webp"
        (root / thumb_rel).write_bytes(thumb_bytes)
        info["thumbnail"] = thumb_rel

    (folder / "item.json").write_text(json.dumps(info, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    rebuild_index(root)
    return f"{kind_dir_name}/{name}"


def add_preset(path, root=ROOT, creator=None, description=None, tags=None):
    clean_creator = creator.strip() if creator is not None else None
    if clean_creator is not None and len(clean_creator) > CREATOR_LIMIT:
        raise Rejected(f"creator is longer than {CREATOR_LIMIT} characters")
    clean_description = description.strip() if description is not None else None
    if clean_description is not None and len(clean_description) > DESCRIPTION_LIMIT:
        raise Rejected(f"description is longer than {DESCRIPTION_LIMIT} characters")
    clean_tags = parse_tags_argument(tags)

    title, xml_bytes, size, sha256 = read_preset(path)
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
    info["added"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    info["file"] = item_rel
    info["bytes"] = size
    info["sha256"] = sha256

    (folder / "item.json").write_text(json.dumps(info, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    rebuild_index(root)
    return f"presets/{name}"


def add_item(path, root=ROOT, creator=None, description=None, tags=None, title=None):
    suffix = path.suffix.lower()
    if suffix == ".absproj":
        if creator is not None or description is not None or tags is not None or title is not None:
            raise Rejected(f"{path.name}: --creator, --description, --tags and --title only apply to .xml presets and effects")
        return add_bundle(path, root)
    if suffix == ".xml":
        if title is not None:
            raise Rejected(f"{path.name}: --title only applies to effects")
        return add_preset(path, root, creator=creator, description=description, tags=tags)
    if suffix in (".amfx", ".json"):
        return add_effect(path, root, creator=creator, description=description, tags=tags, title=title)
    raise Rejected(f"{path.name}: expected a .absproj bundle, an .xml preset, or an .amfx or .json effect")


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
        problems.append(f"{folder_prefix}item.json: added must be YYYY-MM-DD or YYYY-MM-DDTHH:MM:SSZ")
    else:
        try:
            datetime.strptime(added, "%Y-%m-%dT%H:%M:%SZ" if "T" in added else "%Y-%m-%d")
        except ValueError:
            problems.append(f"{folder_prefix}item.json: added is not a valid calendar date: {added!r}")

    if "minVersion" in info:
        min_version = info["minVersion"]
        if not is_non_bool_int(min_version) or min_version < 1:
            problems.append(f"{folder_prefix}item.json: minVersion must be a positive integer")

    if expected_kind in ("preset", "effect"):
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

    file_rel = info.get("file")
    preset_bundle = expected_kind == "preset" and isinstance(file_rel, str) and file_rel.endswith(".absproj")
    limit = EFFECT_LIMIT if expected_kind == "effect" else PRESET_LIMIT if expected_kind == "preset" and not preset_bundle else BUNDLE_LIMIT

    recorded_bytes = info.get("bytes")
    if not is_non_bool_int(recorded_bytes) or recorded_bytes < 0:
        problems.append(f"{folder_prefix}item.json: bytes must be a non-negative integer")
        recorded_bytes = None
    elif recorded_bytes > limit:
        problems.append(f"{folder_prefix}item.json: bytes exceeds {f'{limit >> 20} MB' if limit >= 1 << 20 else f'{limit >> 10} KB'} limit")

    recorded_sha = info.get("sha256")
    if not isinstance(recorded_sha, str) or not SHA256_PATTERN.fullmatch(recorded_sha):
        problems.append(f"{folder_prefix}item.json: sha256 must be 64 lowercase hex characters")
        recorded_sha = None

    item_file_name = None
    path_error = validate_repo_path(file_rel, folder_prefix)
    if path_error:
        problems.append(f"{folder_prefix}item.json: invalid file path ({path_error})")
    else:
        if expected_kind == "bundle" and file_rel != f"{folder_prefix}{name}.absproj":
            problems.append(f"{folder_prefix}item.json: bundle file must be {folder_prefix}{name}.absproj")
        elif expected_kind == "preset" and file_rel not in (f"{folder_prefix}{name}.xml", f"{folder_prefix}{name}.absproj"):
            problems.append(
                f"{folder_prefix}item.json: preset file must be {folder_prefix}{name}.xml or {folder_prefix}{name}.absproj"
            )
        elif expected_kind == "effect" and file_rel not in (f"{folder_prefix}{name}.amfx", f"{folder_prefix}{name}.json"):
            problems.append(f"{folder_prefix}item.json: effect file must be {folder_prefix}{name}.amfx or {folder_prefix}{name}.json")

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
            if actual_bytes > limit:
                problems.append(f"{folder_prefix}: {file_rel} exceeds {f'{limit >> 20} MB' if limit >= 1 << 20 else f'{limit >> 10} KB'} limit ({actual_bytes} bytes)")
            actual_sha = hashlib.sha256(target_file.read_bytes()).hexdigest()
            if recorded_sha is not None and actual_sha != recorded_sha:
                problems.append(f"{folder_prefix}: sha256 mismatch for {file_rel}")
            if expected_kind == "preset":
                try:
                    if not preset_bundle:
                        read_preset(target_file)
                    elif read_bundle(target_file)[0] != "preset":
                        problems.append(f"{folder_prefix}: {file_rel} is a project bundle, not a preset")
                except Rejected as rejected:
                    problems.append(f"{folder_prefix}: {rejected}")
            if expected_kind == "effect":
                try:
                    read_effects(target_file)
                except Rejected as rejected:
                    problems.append(f"{folder_prefix}: {rejected}")

    thumb_rel = info.get("thumbnail")
    has_valid_thumb = False
    if expected_kind == "bundle" and thumb_rel is None:
        problems.append(f"{folder_prefix}item.json: bundles must have a thumbnail")
    if expected_kind in ("preset", "effect"):
        if thumb_rel is not None:
            problems.append(f"{folder_prefix}item.json: {expected_kind}s have no thumbnail; the app draws the picture itself")
        if (folder / "thumb.webp").exists():
            problems.append(f"{folder_prefix}: {expected_kind}s have no thumb.webp; the app draws the picture itself")
    elif thumb_rel is not None:
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
            elif thumb_file.stat().st_size > THUMB_LIMIT:
                problems.append(f"{folder_prefix}: {thumb_rel} is larger than 4 MB")
            else:
                with thumb_file.open("rb") as thumb:
                    if not is_webp(thumb.read(12)):
                        problems.append(f"{folder_prefix}: {thumb_rel} is not a WebP picture")

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


def create_fake_bundle(path, community=None, padding=0, thumb=b"RIFF0000WEBP", scene='<scene title="Glow intro"/>', media=None):
    with zipfile.ZipFile(path, "w") as bundle:
        bundle.writestr("project.xml", scene)
        manifest = {
            "format": "absentmotion-package",
            "version": 1,
            "title": "Glow intro",
            "project": "project.xml",
            "media": [],
            "fonts": [],
        }
        if media is not None:
            bundle.writestr(media, b"RIFF0000WEBP")
            manifest["media"].append({"uri": f"amproj:{media}", "file": media.split("_", 1)[1], "entry": media})
        if community is not None:
            manifest["community"] = community
            if thumb is not None:
                bundle.writestr("community/thumb.webp", thumb)
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
        assert add_item(
            good_preset,
            root,
            creator="PresetMaker",
            description="Smooth fade",
            tags="Shape, Fade",
        ) == "presets/fade-in"
        assert add_item(good_preset, root) == "presets/fade-in-2"

        preset_item = json.loads((root / "presets/fade-in/item.json").read_text(encoding="utf-8"))
        assert preset_item["kind"] == "preset"
        assert preset_item["file"] == "presets/fade-in/fade-in.xml"
        assert "thumbnail" not in preset_item
        assert preset_item["tags"] == ["Shape", "Fade"]
        assert sorted(child.name for child in (root / "presets/fade-in").iterdir()) == ["fade-in.xml", "item.json"]
        preset_two = json.loads((root / "presets/fade-in-2/item.json").read_text(encoding="utf-8"))
        assert "thumbnail" not in preset_two

        index = json.loads((root / "index.json").read_text(encoding="utf-8"))
        assert index["format"] == INDEX_FORMAT
        assert index["version"] == INDEX_VERSION
        assert sorted(entry["name"] for entry in index["items"]) == ["fade-in", "fade-in-2", "glow-intro", "glow-intro-2"]
        added_order = [(entry["added"], entry["name"]) for entry in index["items"]]
        assert added_order == sorted(added_order, reverse=True), added_order
        assert all(re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", entry["added"]) for entry in index["items"])
        assert all("path" not in entry for entry in index["items"])
        assert check_repo(root) == []

        plain_bundle = root / "plain.absproj"
        create_fake_bundle(plain_bundle)
        expect_rejected(lambda: add_item(plain_bundle, root), "not a Community bundle")

        png_thumb = root / "png-thumb.absproj"
        create_fake_bundle(png_thumb, details, thumb=b"\x89PNG\r\n\x1a\n0000")
        expect_rejected(lambda: add_item(png_thumb, root), "not a WebP picture")

        huge_thumb = root / "huge-thumb.absproj"
        create_fake_bundle(huge_thumb, details, thumb=b"RIFF0000WEBP" + b"\0" * THUMB_LIMIT)
        expect_rejected(lambda: add_item(huge_thumb, root), "larger than 4 MB")

        damaged_bundle = root / "damaged.absproj"
        create_fake_bundle(damaged_bundle, details, padding=1000)
        damaged_bytes = bytearray(damaged_bundle.read_bytes())
        damaged_bytes[damaged_bytes.index(b"\0" * 1000) + 500] = 1
        damaged_bundle.write_bytes(bytes(damaged_bytes))
        expect_rejected(lambda: add_item(damaged_bundle, root), "is damaged")

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

        two_layers = root / "two-layers.xml"
        create_fake_preset(two_layers, '<scene title="Two"><shape/><text/></scene>')
        expect_rejected(lambda: add_item(two_layers, root), "a preset has one")

        no_title = root / "no-title.xml"
        create_fake_preset(no_title, "<scene><text/></scene>")
        expect_rejected(lambda: add_item(no_title, root), "no title attribute")

        expect_rejected(lambda: add_item(good_bundle, root, creator="Someone"), "only apply to .xml presets")
        _, unknown = build_parser().parse_known_args(["add", str(good_preset), "--thumb", "picture.webp"])
        assert "--thumb" in unknown, unknown

        preset_folder = root / "presets/fade-in"
        stray_thumb = preset_folder / "thumb.webp"
        stray_thumb.write_bytes(b"RIFF0000WEBP")
        thumb_problems = check_repo(root)
        assert any("presets have no thumb.webp" in problem for problem in thumb_problems), thumb_problems
        stray_thumb.unlink()
        assert check_repo(root) == []

        preset_json = preset_folder / "item.json"
        saved_json = preset_json.read_text(encoding="utf-8")
        with_thumb = json.loads(saved_json)
        with_thumb["thumbnail"] = "presets/fade-in/thumb.webp"
        preset_json.write_text(json.dumps(with_thumb, indent=1) + "\n", encoding="utf-8")
        rebuild_index(root)
        field_problems = check_repo(root)
        assert any("presets have no thumbnail" in problem for problem in field_problems), field_problems
        preset_json.write_text(saved_json, encoding="utf-8")
        rebuild_index(root)
        assert check_repo(root) == []

        thumb_target = root / "bundles/glow-intro/thumb.webp"
        saved_thumb = thumb_target.read_bytes()
        thumb_target.write_bytes(b"\x89PNG\r\n\x1a\n0000")
        webp_problems = check_repo(root)
        assert any("not a WebP picture" in problem for problem in webp_problems), webp_problems
        thumb_target.write_bytes(saved_thumb)
        assert check_repo(root) == []

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

        preset_readme = root / "presets/README.md"
        saved_readme = preset_readme.read_text(encoding="utf-8")
        preset_readme.unlink()
        readme_problems = check_repo(root)
        assert any("presets/README.md" in problem for problem in readme_problems), readme_problems
        preset_readme.write_text(saved_readme, encoding="utf-8")
        assert check_repo(root) == []

        preset_details = {
            "kind": "preset",
            "title": "Soft Glow",
            "description": "A soft glow for pictures",
            "tags": ["Glow", "Picture"],
            "creator": "PresetMaker",
            "licence": "CC BY 4.0",
            "madeWith": "5.2.0",
        }
        layer = '<shape id="{}" fillType="media" fillImage="amproj:media/1_placeholder.webp"/>'
        one_layer = f'<scene title="Soft Glow" type="preset">{layer.format(1)}</scene>'
        placeholder = "media/1_placeholder.webp"

        preset_bundle = root / "soft-glow.absproj"
        create_fake_bundle(preset_bundle, preset_details, thumb=None, scene=one_layer, media=placeholder)
        assert add_item(preset_bundle, root) == "presets/soft-glow"
        bundle_preset = json.loads((root / "presets/soft-glow/item.json").read_text(encoding="utf-8"))
        assert sorted(bundle_preset) == ["added", "bytes", "creator", "description", "file", "kind", "name", "sha256", "tags", "title"]
        assert bundle_preset["kind"] == "preset" and bundle_preset["title"] == "Soft Glow"
        assert bundle_preset["file"] == "presets/soft-glow/soft-glow.absproj"
        assert bundle_preset["tags"] == ["Glow", "Picture"]
        assert bundle_preset["bytes"] == preset_bundle.stat().st_size
        assert bundle_preset["sha256"] == hashlib.sha256(preset_bundle.read_bytes()).hexdigest()
        assert sorted(child.name for child in (root / "presets/soft-glow").iterdir()) == ["item.json", "soft-glow.absproj"]
        index_entry = next(entry for entry in json.loads((root / "index.json").read_text(encoding="utf-8"))["items"] if entry["name"] == "soft-glow")
        assert index_entry == {key: bundle_preset[key] for key in INDEX_FIELDS if key in bundle_preset}
        assert check_repo(root) == []

        project_kind = root / "project-kind.absproj"
        create_fake_bundle(project_kind, dict(details, kind="project"))
        assert add_item(project_kind, root).startswith("bundles/glow-intro-")

        two_layer_bundle = root / "two-layer.absproj"
        two_layer_scene = f'<scene title="Soft Glow" type="preset">{layer.format(1)}{layer.format(2)}</scene>'
        create_fake_bundle(two_layer_bundle, preset_details, thumb=None, scene=two_layer_scene, media=placeholder)
        expect_rejected(lambda: add_item(two_layer_bundle, root), "a preset has one")

        over_preset_bundle = root / "big-preset.absproj"
        create_fake_bundle(over_preset_bundle, preset_details, padding=BUNDLE_LIMIT + 1, thumb=None, scene=one_layer, media=placeholder)
        expect_rejected(lambda: add_item(over_preset_bundle, root), "the limit is 20 MB")

        thumb_field = root / "thumb-field.absproj"
        create_fake_bundle(thumb_field, dict(preset_details, thumbnail="community/thumb.webp"), thumb=None, scene=one_layer, media=placeholder)
        expect_rejected(lambda: add_item(thumb_field, root), "presets take no picture")
        thumb_file = root / "thumb-file.absproj"
        create_fake_bundle(thumb_file, preset_details, scene=one_layer, media=placeholder)
        expect_rejected(lambda: add_item(thumb_file, root), "presets take no picture")

        project_scene = root / "project-scene.absproj"
        create_fake_bundle(project_scene, preset_details, thumb=None, scene=f'<scene title="Soft Glow">{layer.format(1)}</scene>')
        expect_rejected(lambda: add_item(project_scene, root), "scene type is not preset")

        unknown_kind = root / "unknown-kind.absproj"
        create_fake_bundle(unknown_kind, dict(details, kind="tool"))
        expect_rejected(lambda: add_item(unknown_kind, root), "unknown kind")

        preset_bundle_folder = root / "presets/soft-glow"
        (preset_bundle_folder / "thumb.webp").write_bytes(b"RIFF0000WEBP")
        bundle_thumb_problems = check_repo(root)
        assert any("presets have no thumb.webp" in problem for problem in bundle_thumb_problems), bundle_thumb_problems
        (preset_bundle_folder / "thumb.webp").unlink()

        preset_bundle_json = preset_bundle_folder / "item.json"
        saved_bundle_json = preset_bundle_json.read_text(encoding="utf-8")
        preset_bundle_file = preset_bundle_folder / "soft-glow.absproj"
        saved_bundle_bytes = preset_bundle_file.read_bytes()
        preset_bundle_file.write_bytes(good_bundle.read_bytes())
        swapped = dict(json.loads(saved_bundle_json), bytes=good_bundle.stat().st_size, sha256=hashlib.sha256(good_bundle.read_bytes()).hexdigest())
        preset_bundle_json.write_text(json.dumps(swapped, indent=1) + "\n", encoding="utf-8")
        rebuild_index(root)
        swapped_problems = check_repo(root)
        assert any("is a project bundle, not a preset" in problem for problem in swapped_problems), swapped_problems
        preset_bundle_file.write_bytes(saved_bundle_bytes)
        preset_bundle_json.write_text(saved_bundle_json, encoding="utf-8")
        rebuild_index(root)
        assert check_repo(root) == []

        saved_index = (root / "index.json").read_text(encoding="utf-8")
        (root / "index.json").write_text('{\n "format": "absentmotion-community",\n "version": 2,\n "items": []\n}\n', encoding="utf-8")
        stale_problems = check_repo(root)
        assert any("index.json does not match" in problem for problem in stale_problems), stale_problems
        (root / "index.json").write_text(saved_index, encoding="utf-8")
        assert check_repo(root) == []

        effect = {"id": "simple-duotone", "name": "Simple Duotone", "category": "color", "author": "Someone", "description": "Two colors", "version": 1,
                  "params": [{"id": "amount", "type": "float", "default": 1, "min": 0, "max": 1}], "sksl": "uniform shader image;\nhalf4 main(float2 p) { return image.eval(p); }\n"}
        effect_json = root / "duotone.json"
        effect_json.write_text(json.dumps(effect), encoding="utf-8")
        assert add_item(effect_json, root, tags="Color") == "effects/simple-duotone"
        effect_item = json.loads((root / "effects/simple-duotone/item.json").read_text(encoding="utf-8"))
        assert effect_item["kind"] == "effect" and effect_item["creator"] == "Someone" and effect_item["effects"] == ["Simple Duotone"]
        pack = root / "Glow_Pack.amfx"
        with zipfile.ZipFile(pack, "w") as archive:
            archive.writestr("one.json", json.dumps(dict(effect, id="one", name="One")))
            archive.writestr("two.json", json.dumps(dict(effect, id="two", name="Two")))
            archive.writestr("notes.txt", "ignored")
        assert add_item(pack, root) == "effects/glow-pack"
        assert check_repo(root) == []
        assert any(entry["kind"] == "effect" for entry in json.loads((root / "index.json").read_text(encoding="utf-8"))["items"])
        for bad, reason in ((dict(effect, id="Bad Id"), "id must be"), (dict(effect, sksl="x" * (EFFECT_SKSL_LIMIT + 1) + "main("), "larger than 64 KB"),
                            (dict(effect, params=[{"id": "a", "type": "slider"}]), "every setting needs"), (dict(effect, sksl="no shader"), "main function")):
            effect_json.write_text(json.dumps(bad), encoding="utf-8")
            try:
                add_item(effect_json, root)
                raise AssertionError(f"accepted {reason}")
            except Rejected as rejected:
                assert reason in str(rejected), rejected
        big = root / "big.amfx"
        with zipfile.ZipFile(big, "w") as archive:
            for number in range(EFFECT_PACK_LIMIT + 1):
                archive.writestr(f"e{number}.json", json.dumps(dict(effect, id=f"e{number}")))
        try:
            add_item(big, root, title="Big")
            raise AssertionError("accepted a pack with too many effects")
        except Rejected as rejected:
            assert "the limit is" in str(rejected), rejected
        assert check_repo(root) == []

    print("selftest passed")


def build_parser():
    parser = argparse.ArgumentParser(
        prog="community.py",
        description="Manage AbsentMotion Community bundles, presets, and index.json.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser("add", help="add .absproj project or preset bundles, .xml presets, or .amfx and .json effects")
    add_parser.add_argument("files", nargs="+", type=Path, metavar="FILE", help="project or preset bundle (.absproj), preset (.xml), or effect (.amfx pack or .json) files to add")
    add_parser.add_argument("--creator", help="creator name for .xml presets and effects (at most 80 characters; effects default to their author)")
    add_parser.add_argument("--description", help="description for .xml presets and effects (at most 500 characters)")
    add_parser.add_argument("--tags", help="comma-separated tags for .xml presets and effects (up to 8 tags, 30 characters each)")
    add_parser.add_argument("--title", help="title for an effect pack (a single effect uses its name)")

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
        failed = 0
        for file in args.files:
            try:
                added_folder = add_item(
                    file,
                    root=ROOT,
                    creator=args.creator,
                    description=args.description,
                    tags=args.tags,
                    title=args.title,
                )
                print(f"added {added_folder}")
            except Rejected as rejected:
                print(f"rejected: {rejected}", file=sys.stderr)
                failed += 1
            except (OSError, ValueError, UnicodeDecodeError) as error:
                print(f"error: {file.name}: {error}", file=sys.stderr)
                failed += 1
        return 1 if failed else 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
