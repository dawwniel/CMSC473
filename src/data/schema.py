"""Validation for version 1 particle records exported by Roblox Studio."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from typing import Any


FORMAT_VERSION = 1
SPLITS = frozenset({"train", "validation", "test", "generalization_test"})

# Keep this list in sync with Exporter.PROPERTIES.ParticleEmitter in roblox/exporter.lua.
PARTICLE_PROPERTIES = {
    "Acceleration": "Vector3",
    "Brightness": "number",
    "Color": "ColorSequence",
    "Drag": "number",
    "EmissionDirection": "NormalId",
    "Enabled": "boolean",
    "FlipbookFramerate": "NumberRange",
    "FlipbookLayout": "ParticleFlipbookLayout",
    "FlipbookMode": "ParticleFlipbookMode",
    "FlipbookStartRandom": "boolean",
    "Lifetime": "NumberRange",
    "LightEmission": "number",
    "LightInfluence": "number",
    "LockedToPart": "boolean",
    "Orientation": "ParticleOrientation",
    "Rate": "number",
    "RotSpeed": "NumberRange",
    "Rotation": "NumberRange",
    "Shape": "ParticleEmitterShape",
    "ShapeInOut": "ParticleEmitterShapeInOut",
    "ShapePartial": "number",
    "ShapeStyle": "ParticleEmitterShapeStyle",
    "Size": "NumberSequence",
    "Speed": "NumberRange",
    "SpreadAngle": "Vector2",
    "Squash": "NumberSequence",
    "Texture": "string",
    "TimeScale": "number",
    "Transparency": "NumberSequence",
    "VelocityInheritance": "number",
    "WindAffectsDrag": "boolean",
    "ZOffset": "number",
}

_VECTOR_WIDTHS = {
    "Vector2": 2,
    "Vector3": 3,
    "Color3": 3,
    "UDim": 2,
    "UDim2": 4,
    "Rect": 4,
    "CFrame": 12,
    "NumberRange": 2,
}
_ENUM_TYPES = frozenset({
    "NormalId", "ParticleFlipbookLayout", "ParticleFlipbookMode",
    "ParticleOrientation", "ParticleEmitterShape", "ParticleEmitterShapeInOut",
    "ParticleEmitterShapeStyle",
})
_HASH_RE = re.compile(r"[0-9a-f]{16}\Z")


class SchemaError(ValueError):
    pass


def _error(where: str, message: str) -> None:
    raise SchemaError(f"{where}: {message}")


def _object(value: Any, where: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        _error(where, "expected an object")
    return value


def _text(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _error(where, "expected a non-empty string")
    return value


def _number(value: Any, where: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        _error(where, "expected a finite number")
    return value


def _number_list(value: Any, width: int, where: str) -> list[Any]:
    if not isinstance(value, list) or len(value) != width:
        _error(where, f"expected {width} numbers")
    for i, item in enumerate(value):
        _number(item, f"{where}[{i}]")
    return value


def _json_value(value: Any, where: str) -> None:
    if value is None or isinstance(value, (str, bool)):
        return
    if isinstance(value, (int, float)):
        _number(value, where)
    elif isinstance(value, list):
        for i, item in enumerate(value):
            _json_value(item, f"{where}[{i}]")
    elif isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                _error(where, "object keys must be strings")
            _json_value(item, f"{where}.{key}")
    else:
        _error(where, "not a JSON value")


def _sequence(value: Any, kind: str, where: str) -> None:
    points = value.get("keypoints")
    if not isinstance(points, list) or len(points) < 2:
        _error(where, "expected at least two keypoints")
    width = 4 if kind == "ColorSequence" else 3
    last_time = -1.0
    for i, point in enumerate(points):
        _number_list(point, width, f"{where}.keypoints[{i}]")
        time = point[0]
        if not 0 <= time <= 1 or time < last_time:
            _error(f"{where}.keypoints[{i}][0]", "times must run from 0 to 1")
        if kind == "ColorSequence" and any(not 0 <= channel <= 1 for channel in point[1:]):
            _error(f"{where}.keypoints[{i}]", "color channels must be between 0 and 1")
        last_time = time
    if points[0][0] != 0 or points[-1][0] != 1:
        _error(where, "first and last keypoint times must be 0 and 1")


def _value(value: Any, expected: str | None, where: str) -> None:
    if expected == "string":
        if not isinstance(value, str):
            _error(where, "expected a string")
        return
    if expected == "boolean":
        if not isinstance(value, bool):
            _error(where, "expected a boolean")
        return
    if expected == "number":
        _number(value, where)
        return
    if isinstance(value, (str, bool)) and expected is None:
        return
    if isinstance(value, (int, float)) and expected is None:
        _number(value, where)
        return

    tagged = _object(value, where)
    kind = _text(tagged.get("_type"), f"{where}._type")
    if expected is not None and kind != ("Enum" if expected in _ENUM_TYPES else expected):
        _error(where, f"expected {expected}, got {kind}")
    if kind in _VECTOR_WIDTHS:
        values = _number_list(tagged.get("value"), _VECTOR_WIDTHS[kind], f"{where}.value")
        if kind == "NumberRange" and values[0] > values[1]:
            _error(where, "range minimum exceeds maximum")
        if kind == "Color3" and any(not 0 <= channel <= 1 for channel in values):
            _error(where, "color channels must be between 0 and 1")
    elif kind in {"NumberSequence", "ColorSequence"}:
        _sequence(tagged, kind, where)
    elif kind == "Enum":
        enum = _text(tagged.get("enum"), f"{where}.enum")
        _text(tagged.get("value"), f"{where}.value")
        if expected in _ENUM_TYPES and enum != expected:
            _error(where, f"expected Enum.{expected}, got Enum.{enum}")
    elif kind == "Font":
        for key in ("family", "weight", "style"):
            _text(tagged.get(key), f"{where}.{key}")
    elif kind in {"BrickColor", "Content"}:
        _text(tagged.get("value" if kind == "BrickColor" else "uri"), where)
    elif kind == "JSONString":
        if "value" not in tagged:
            _error(where, "missing JSONString value")
        _json_value(tagged["value"], f"{where}.value")
    else:
        _error(where, f"unknown Roblox value type {kind}")


def _node(value: Any, where: str) -> Mapping[str, Any]:
    node = _object(value, where)
    _text(node.get("class"), f"{where}.class")
    _text(node.get("name"), f"{where}.name")
    for field in ("properties", "attributes"):
        items = _object(node.get(field, {}), f"{where}.{field}")
        for name, item in items.items():
            _text(name, f"{where}.{field} key")
            _value(item, None, f"{where}.{field}.{name}")
    children = node.get("children", [])
    if not isinstance(children, list):
        _error(f"{where}.children", "expected a list")
    for i, child in enumerate(children):
        _node(child, f"{where}.children[{i}]")
    return node


def validate_emitter(value: Any) -> Mapping[str, Any]:
    """Check the model target: 32 properties and the EmitCount attribute."""
    emitter = _node(value, "emitter")
    if emitter["class"] != "ParticleEmitter":
        _error("emitter.class", "expected ParticleEmitter")
    properties = emitter.get("properties", {})
    missing = PARTICLE_PROPERTIES.keys() - properties.keys()
    extra = properties.keys() - PARTICLE_PROPERTIES.keys()
    if missing or extra:
        _error("emitter.properties", f"missing {sorted(missing)}, unsupported {sorted(extra)}")
    for name, expected in PARTICLE_PROPERTIES.items():
        _value(properties[name], expected, f"emitter.properties.{name}")
    attributes = emitter.get("attributes", {})
    count = attributes.get("EmitCount")
    if type(count) is not int or count < 0:
        _error("emitter.attributes.EmitCount", "expected a nonnegative integer")
    return emitter


def validate_record(value: Any, expected_split: str | None = None) -> Mapping[str, Any]:
    """Check a complete JSONL row. Raises SchemaError on the first problem."""
    record = _object(value, "record")
    if type(record.get("formatVersion")) is not int or record["formatVersion"] != FORMAT_VERSION:
        _error("formatVersion", f"expected {FORMAT_VERSION}")
    split = record.get("split")
    if not isinstance(split, str) or split not in SPLITS:
        _error("split", f"expected one of {', '.join(sorted(SPLITS))}")
    if expected_split is not None and split != expected_split:
        _error("split", f"expected {expected_split}, got {split}")
    _text(record.get("prompt"), "prompt")
    path = record.get("path")
    if not isinstance(path, list) or len(path) < 2:
        _error("path", "expected at least an attachment and emitter name")
    for i, name in enumerate(path):
        _text(name, f"path[{i}]")
        if "/" in name:
            _error(f"path[{i}]", "names cannot contain /")
    if record.get("id") != "/".join(path):
        _error("id", "does not match path")
    attachment = _node(record.get("attachment"), "attachment")
    emitter = validate_emitter(record.get("emitter"))
    if attachment["name"] != path[-2] or emitter["name"] != path[-1]:
        _error("path", "attachment or emitter name does not match")
    if attachment.get("attributes", {}).get("Split") != split:
        _error("attachment.attributes.Split", "does not match split")
    if "prompt_gui" in record:
        prompt_gui = _node(record["prompt_gui"], "prompt_gui")
        if prompt_gui["class"] != "BillboardGui":
            _error("prompt_gui.class", "expected BillboardGui")
        labels = [
            child for child in prompt_gui.get("children", [])
            if child["class"] == "TextLabel"
        ]
        if not labels or labels[0].get("properties", {}).get("Text") != record["prompt"]:
            _error("prompt_gui", "TextLabel text does not match prompt")
    mode = "burst" if emitter["attributes"]["EmitCount"] > 0 else "continuous"
    if record.get("playback_mode") != mode:
        _error("playback_mode", f"expected {mode}")
    if not isinstance(record.get("row_hash"), str) or not _HASH_RE.fullmatch(record["row_hash"]):
        _error("row_hash", "expected 16 lowercase hex digits")
    if "family" in record and record["family"] != path[0]:
        _error("family", "does not match path")
    return record
