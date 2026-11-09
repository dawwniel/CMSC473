"""Build the CIX expansion manifest and its Studio builder from the catalog."""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
ROBLOX = ROOT / "roblox"

PALETTES = {
    "Fire": [(255, 151, 58, "orange"), (255, 202, 86, "golden"), (99, 190, 255, "blue"), (255, 95, 69, "red-orange")],
    "Smoke": [(188, 193, 199, "gray"), (227, 226, 218, "pale"), (145, 151, 163, "slate gray"), (183, 167, 146, "dusty brown")],
    "Shadow": [(95, 106, 125, "dark blue-gray"), (144, 151, 166, "smoky gray"), (99, 83, 120, "deep plum")],
    "Water": [(139, 220, 255, "pale blue"), (71, 173, 232, "blue"), (103, 226, 216, "aqua")],
    "Ice": [(207, 239, 255, "icy white"), (154, 214, 252, "frost blue")],
    "Electric": [(116, 204, 255, "electric blue"), (238, 229, 122, "yellow"), (128, 231, 226, "cyan")],
    "Magic": [(119, 202, 255, "blue"), (242, 189, 103, "golden"), (122, 231, 195, "teal"), (198, 159, 255, "violet")],
    "Cosmic": [(182, 225, 255, "blue-white"), (255, 221, 164, "warm white"), (171, 169, 245, "lavender")],
    "Combat": [(232, 239, 249, "white"), (255, 178, 115, "orange"), (135, 213, 255, "blue")],
    "Earth": [(186, 171, 143, "tan"), (139, 149, 157, "gray"), (206, 153, 104, "rust-colored")],
    "Nature": [(235, 164, 78, "orange"), (121, 195, 108, "green"), (222, 185, 97, "golden")],
    "Healing": [(255, 150, 183, "pink"), (141, 235, 179, "mint green"), (255, 211, 138, "warm gold")],
    "Poison": [(139, 224, 89, "green"), (209, 231, 85, "yellow-green"), (96, 196, 138, "sea green")],
    "Ambient": [(234, 238, 248, "pale white"), (166, 210, 247, "soft blue"), (252, 213, 162, "warm gold")],
    "Wildlife": [(234, 238, 248, "pale white"), (194, 224, 255, "light blue"), (247, 196, 125, "golden")],
}


def classify(kind: str, name: str) -> tuple[str, str, str, str]:
    stem = re.sub(r"\d+$", "", name).lower()
    if "blacklightning" in stem:
        return "Shadow", "ShadowEffects", "lightning", "lightning arc"
    if "blackdust" in stem:
        return "Shadow", "ShadowEffects", "debris", "soot fleck"
    if "blackfire" in stem or "darkflame" in stem:
        return "Shadow", "ShadowEffects", "flame", "flame"
    if "blackhole" in stem:
        return "Cosmic", "CosmicVortices", "vortex", "accretion ring" if name == "BlackHole1" else "vortex ring"
    if any(word in stem for word in ("ghost", "skull", "monsterface")):
        label = "ghost" if "ghost" in stem else "skull" if "skull" in stem else "monster face"
        return "Shadow", "ShadowEffects", "symbol", label
    if any(word in stem for word in ("darkenergy", "cursedenergy")):
        return "Shadow", "ShadowEffects", "shadow", "shadow shape"
    if "fish" in stem or "dolphin" in stem:
        return "Water", "AquaticCreatures", "creature", "fish" if "fish" in stem else "dolphin"
    if any(word in stem for word in ("buturfly", "butterfly", "dove", "bat", "dragon")):
        label = "butterfly" if "buturfly" in stem or "butterfly" in stem else "dove" if "dove" in stem else "bat" if "bat" in stem else "dragon silhouette"
        return "Wildlife", "FloatingCreatures", "creature", label
    if "blood" in stem:
        return "Combat", "BleedSplatter", "blood", "blood splatter"
    if any(word in stem for word in ("fire", "flame")):
        return "Fire", "FireFlicker", "flame", "flame"
    if any(word in stem for word in ("cartoonsmoke", "smoke", "cloudfade", "cloud")):
        recipe = "cloud" if "cloud" in stem else "smoke"
        return "Smoke", "CloudDrift" if recipe == "cloud" else "SmokePuffs", recipe, "cloud" if recipe == "cloud" else "smoke puff"
    if any(word in stem for word in ("dust", "powder")):
        return "Earth", "DustClouds", "dust", "dust cloud"
    if any(word in stem for word in ("bubble", "bublbe")):
        return "Water", "WaterBubbles", "bubble", "bubble"
    if "waterball" in stem:
        return "Water", "WaterBubbles", "orb", "water orb"
    if "leaf" in stem or "shamrock" in stem:
        return "Nature", "FallingLeaves", "leaf", "leaf shape" if "leaf" in stem else "shamrock"
    if any(word in stem for word in ("rock", "debris", "shard")):
        return "Earth", "DebrisBurst", "debris", "stone fragment" if "rock" in stem or "debris" in stem else "shard"
    if "snow" in stem:
        return "Ice", "SnowFlurry", "snow", "snow puff" if kind == "Particle" and name == "Snowflake1" else "snowflake"
    if "lightning" in stem:
        return "Electric", "LightningSparks", "lightning", "lightning arc"
    if any(word in stem for word in ("spark", "star", "point")):
        return "Cosmic", "CosmicSparks", "spark", "star" if "star" in stem else "glimmer streak" if "sparkle" in stem else "spark"
    if any(word in stem for word in ("slash", "crescent", "sword")):
        return "Combat", "SwordSlashes", "slash", "crescent slash" if "crescent" in stem else "slash"
    if any(word in stem for word in ("impact", "crack", "ditch")):
        return "Combat", "ImpactFlashes", "impact", "impact mark" if "crack" in stem or "ditch" in stem else "impact flash"
    if "explosion" in stem:
        return "Fire", "ExplosionBursts", "impact", "explosion flash"
    if any(word in stem for word in ("ripple", "wavecircle")):
        return "Water", "WaterRipples", "ripple", "circular ripple"
    if stem == "wave" or "wave" in stem:
        return "Water", "WaterRipples", "ripple", "water wave"
    if any(word in stem for word in ("splash", "water")):
        return "Water", "WaterSplashes", "splash", "water splash"
    if any(word in stem for word in ("gear", "compas", "radar", "grid", "scope", "atom")):
        return "Magic", "MagicCircles", "sigil", "rotating gear" if "gear" in stem else "circular sigil"
    if any(word in stem for word in ("shockwave", "circle", "rosette", "radar", "grid", "scope", "atom", "gear", "compas")):
        if "magic" in stem or "pixelized" in stem:
            return "Magic", "MagicCircles", "sigil", "magic circle"
        if "shockwave" in stem:
            return "Electric", "Shockwaves", "ring", "shockwave ring"
        return "Magic", "MagicCircles", "ring", "circular sigil"
    if any(word in stem for word in ("ray", "beam", "line")):
        return "Electric", "ElectricSurges", "beam", "energy streak"
    if any(word in stem for word in ("swirl", "spin", "distortion")):
        return "Magic", "MagicAuras", "vortex", "spiral"
    if "heart" in stem:
        return "Healing", "HealingGlow", "heart", "heart"
    if "shield" in stem or "crucifix" in stem or stem == "cross":
        return "Healing", "ShieldPulse", "shield", "shield" if "shield" in stem else "protective cross"
    if any(word in stem for word in ("toxic", "acid")):
        return "Poison", "PoisonBurst", "symbol", "toxic symbol"
    if any(word in stem for word in ("flare", "ball", "aura", "particle", "energy", "explosion")):
        return "Magic", "MagicBursts", "orb", "glowing orb" if "ball" in stem else "energy flare"
    if any(word in stem for word in ("alphabet", "number", "kanji", "hieroglyph", "spell", "rune")):
        label = "letter glyph" if "alphabet" in stem else "number glyph" if "number" in stem else "rune symbol"
        return "Magic", "Runes", "glyph", label
    if any(word in stem for word in ("musicnote", "arrow", "cursor", "triangle", "eye", "moon", "egg", "teeth", "thinkers", "geomostry")):
        label = re.sub(r"(?<!^)(?=[A-Z])", " ", re.sub(r"\d+$", "", name)).lower().replace("buturfly", "butterfly").replace("geomostry", "geometry")
        if "thinkers" in stem:
            label = "thought mark"
        return "Ambient", "AmbientSymbols", "symbol", label
    return "Ambient", "AmbientSymbols", "symbol", "abstract symbol"


ACTION = {
    "shadow": "drifts upward and fades",
    "blood": "spreads quickly from an impact",
    "flame": "flickers upward",
    "smoke": "billows upward and thins out",
    "cloud": "drifts slowly across the air",
    "dust": "bursts outward and settles",
    "bubble": "rises gently and fades",
    "leaf": "tumbles downward in a breeze",
    "debris": "scatters outward and falls",
    "snow": "falls slowly and turns",
    "lightning": "flashes and branches outward",
    "spark": "scatters and twinkles",
    "slash": "flashes across the view once",
    "impact": "appears in a sharp burst and vanishes",
    "ripple": "expands in one smooth pulse",
    "splash": "bursts outward and falls",
    "ring": "expands and fades",
    "sigil": "turns slowly before fading",
    "beam": "shoots upward and fades",
    "vortex": "spins and fades",
    "heart": "floats upward and fades",
    "symbol": "appears, drifts upward, and fades",
    "orb": "glows and drifts upward",
    "glyph": "glows briefly and fades",
    "creature": "glides across the air and fades",
    "shield": "pulses once and fades",
}

# Frame grids checked on the CIX review board in Studio. The other sheets use 4x4.
TWO_BY_TWO = {
    "Bat1", "Buturfly1", "Buturfly2", "CartoonSmoke1", "Circle3", "Eye1",
    "Impact12", "Impact13", "Lightning3", "Lightning4", "Lightning5", "Rock1",
    "Smoke18", "Smoke24", "Smoke27", "Smoke28", "Smoke29", "Water5",
}
EIGHT_BY_EIGHT = {
    "Alphabet1", "BlackDust1", "BlackLightning3", "Blood1", "Fire7", "Fire13",
    "Heart1", "Heart2", "Kanji2", "Lightning2", "Lightning8", "Lightning14",
    "Lightning16", "Lightning17", "Number1", "Shockwave1", "Shockwave6",
    "Slash12", "Smoke2", "Smoke15", "Smoke22", "Smoke23", "Smoke25",
    "Smoke26", "SnowFlakes2",
}


def existing_textures() -> set[str]:
    used = set()
    for path in (ROOT / "src/data").glob("*/particles_*.jsonl"):
        for line in path.read_text(encoding="utf-8").splitlines():
            used.add(json.loads(line)["emitter"]["properties"]["Texture"])
    pilot = json.loads((DATA / "cix_pilot_review.json").read_text(encoding="utf-8"))["effects"]
    used.update(item["texture"] for item in pilot)
    previous = DATA / "cix_expansion_manifest.json"
    if previous.exists():
        expansion = json.loads(previous.read_text(encoding="utf-8"))["effects"]
        used.difference_update(item["texture"] for item in expansion)
    return used


def make_manifest() -> list[dict]:
    catalog = json.loads((DATA / "cix_catalog.json").read_text(encoding="utf-8"))["entries"]
    prompt_overrides = json.loads((DATA / "cix_prompt_review.json").read_text(encoding="utf-8"))
    holdout_ids = set(json.loads((DATA / "cix_texture_holdout.json").read_text(encoding="utf-8"))["queries"])
    assert holdout_ids <= prompt_overrides.keys()
    seen = existing_textures()
    trained_prompts = set()
    used_overrides = set()
    entries = sorted(catalog, key=lambda x: (x["kind"], x["name"], x["galleryImage"]))
    manifest = []
    for card in entries:
        texture = card["galleryImage"]
        if texture in seen:
            continue
        seen.add(texture)
        category, family, recipe, label = classify(card["kind"], card["name"])
        rgb = PALETTES[category][len(manifest) % len(PALETTES[category])]
        color = "red" if recipe == "blood" else rgb[3]
        if recipe == "blood":
            rgb = (204, 44, 55, color)
        if "chromatic" in card["name"].lower():
            rgb = (255, 255, 255, "rainbow")
            color = "rainbow"
        if card["name"].lower().startswith("black") and not card["name"].lower().startswith("blackhole"):
            rgb = (255, 255, 255, "inky black")
            color = "inky black"
        if card["name"] == "BlackHole1":
            rgb = (255, 255, 255, "blue-white")
            color = "blue-white"
        elif card["name"] == "BlackHole2":
            rgb = (255, 255, 255, "icy blue")
            color = "icy blue"
        if recipe == "creature" and category == "Water":
            action = "swims past and fades"
        else:
            action = ACTION[recipe]
        if card["kind"] == "Particle" and card["name"] == "Snowflake1":
            action = "drifts downward and fades"
        if "sparkle" in card["name"].lower():
            action = "flashes and twinkles as it drifts upward"
        article = "An" if color[0].lower() in "aeiou" else "A"
        prompt = f"{article} {color} {label} {action}."
        if card["kind"] == "FlipBook" and recipe in {"flame", "smoke", "cloud", "lightning", "spark", "splash", "orb"}:
            prompt = f"An animated {color} {label} {action}."
        effect_id = f"N{len(manifest) + 48:03d}"
        if effect_id in prompt_overrides:
            prompt = prompt_overrides[effect_id]
            assert prompt.strip() == prompt and 0 < len(prompt) <= 500, effect_id
            used_overrides.add(effect_id)
        wording = " ".join(prompt.casefold().split())
        if effect_id in used_overrides:
            assert wording not in trained_prompts, f"duplicate reviewed prompt: {effect_id}"
        split = "review" if effect_id in holdout_ids or wording in trained_prompts else "train"
        trained_prompts.add(wording)
        index = len(manifest)
        manifest.append({
            "id": effect_id,
            "kind": card["kind"], "card": card["name"], "texture": texture,
            "family": family, "category": category, "recipe": recipe,
            "color": list(rgb[:3]), "prompt": prompt, "split": split,
            "layout": "Grid2x2" if card["kind"] == "FlipBook" and card["name"] in TWO_BY_TWO else "Grid8x8" if card["kind"] == "FlipBook" and card["name"] in EIGHT_BY_EIGHT else "Grid4x4" if card["kind"] == "FlipBook" else "None",
            "column": index % 22, "row": index // 22,
        })
    assert used_overrides == prompt_overrides.keys(), prompt_overrides.keys() - used_overrides
    return manifest


def main() -> None:
    manifest = make_manifest()
    assert len(manifest) == 574, len(manifest)
    (DATA / "cix_expansion_manifest.json").write_text(
        json.dumps({"effects": manifest}, indent=2) + "\n", encoding="utf-8"
    )
    template = (ROBLOX / "cix_expansion.template.lua").read_text(encoding="utf-8")
    def lua_value(value):
        if isinstance(value, list):
            return "{" + ", ".join(map(lua_value, value)) + "}"
        if isinstance(value, str):
            return json.dumps(value, ensure_ascii=False)
        return str(value)

    lines = []
    for effect in manifest:
        fields = ", ".join(f"{key} = {lua_value(value)}" for key, value in effect.items())
        lines.append("\t{" + fields + "},")
    source = template.replace("__MANIFEST_LUA__", "\n".join(lines))
    (ROBLOX / "cix_expansion.lua").write_text(source, encoding="utf-8")
    print(f"Wrote {len(manifest)} CIX effects, N048–N{len(manifest) + 47:03d}")


if __name__ == "__main__":
    main()
