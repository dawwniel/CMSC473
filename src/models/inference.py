"""Load the trained full model once and predict importer-ready records."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import torch

from ..data.normalize import Normalizer
from ..data.dataset import load_split
from .color import color_cue, emitter_color_matches, requested_color, tint_emitter_color
from .encoder import TextEncoder, split_embeddings
from .full import ParticleFull, decode_full
from .full_color import ParticleFullColor
from .levels import chosen_biases
from .model import particle_record
from .nearest_neighbor import build_bank, nearest
from .texture_layout import align_flipbook_layouts, texture_layout_index
from .v2 import ParticleV2


CIX_TEXTURE_THRESHOLD = 0.65


def model_from_checkpoint(saved: dict, normalizer: Normalizer) -> ParticleFull:
    if saved.get("architecture") == "color_v1":
        model = ParticleFullColor(normalizer, saved["embedding_dim"], saved["hidden_dim"])
    elif saved.get("architecture") == "v2":
        model = ParticleV2(
            normalizer,
            saved["group_names"],
            saved["model"]["texture_mask"],
            saved["embedding_dim"],
            saved["hidden_dim"],
            saved["texture_bias"],
        )
    else:
        model = ParticleFull(normalizer, saved["embedding_dim"], saved["hidden_dim"])
    model.load_state_dict(saved["model"])
    model.eval()
    return model


def apply_neighbor_textures(emitters: list[dict], confidence: torch.Tensor,
                            neighbors: list[dict], threshold: float) -> None:
    """Replace uncertain texture IDs while preserving all other emitter settings."""
    if len(emitters) != len(neighbors) or len(emitters) != confidence.numel():
        raise ValueError("emitter, confidence, and neighbor counts differ")
    if not 0 <= threshold <= 1:
        raise ValueError("texture confidence threshold must be between 0 and 1")
    for emitter, probability, neighbor in zip(emitters, confidence.tolist(), neighbors):
        if probability < threshold:
            emitter["properties"]["Texture"] = neighbor["properties"]["Texture"]


def exact_texture_index(records: list[dict]) -> dict[str, str]:
    """Keep unambiguous main prompts for exact texture lookup."""
    textures = {}
    for record in records:
        prompt = " ".join(record["prompt"].casefold().split())
        texture = record["emitter"]["properties"]["Texture"]
        if prompt in textures and textures[prompt] != texture:
            raise ValueError(f"training prompts disagree on texture: {record['prompt']}")
        textures[prompt] = texture
    return textures


def apply_catalog_textures(emitters: list[dict], scores: torch.Tensor,
                           nearest_scores: torch.Tensor, textures: list[str],
                           threshold: float = CIX_TEXTURE_THRESHOLD) -> None:
    """Use a described texture when its match beats the training-prompt lookup."""
    if scores.shape != (len(emitters), len(textures)) or len(nearest_scores) != len(emitters):
        raise ValueError("catalog scores do not match the emitters")
    values, choices = scores.max(dim=1)
    for emitter, score, nearest_score, choice in zip(
            emitters, values.tolist(), nearest_scores.tolist(), choices.tolist()):
        if score >= threshold and score >= nearest_score:
            emitter["properties"]["Texture"] = textures[choice]


class FullPredictor:
    def __init__(self, checkpoint: Path, neighbor_texture_threshold: float | None = None,
                 base_bias: float | None = None, light_bias: float | None = None):
        """`base_bias`/`light_bias` override the checkpoint's LightEmission biases."""
        torch.set_num_threads(min(4, torch.get_num_threads()))
        saved = torch.load(checkpoint, map_location="cpu", weights_only=True)
        normalizer = Normalizer.from_dict(saved["normalizer"])
        model = model_from_checkpoint(saved, normalizer)
        self.normalizer = normalizer
        self.model = model
        self.base_bias, self.light_bias = chosen_biases(saved)
        if base_bias is not None:
            self.base_bias = base_bias
        if light_bias is not None:
            self.light_bias = light_bias
        self.encoder = TextEncoder(saved["encoder_name"], device="cpu")
        self.neighbor_texture_threshold = neighbor_texture_threshold
        self.train_records = load_split("train")
        root = Path(__file__).resolve().parents[2]
        manifest = json.loads((root / "data/cix_expansion_manifest.json").read_text(encoding="utf-8"))
        self.texture_layouts = texture_layout_index(self.train_records, manifest["effects"])
        if neighbor_texture_threshold is not None:
            if not 0 <= neighbor_texture_threshold <= 1:
                raise ValueError("texture confidence threshold must be between 0 and 1")
            fingerprint = hashlib.sha256("\n".join(
                row["row_hash"] for row in self.train_records
            ).encode()).hexdigest()
            bank_fingerprint = saved.get("neighbor_bank_fingerprint", saved["train_fingerprint"])
            if fingerprint != bank_fingerprint:
                raise ValueError("texture lookup data changed after the checkpoint was prepared")
            embeddings = split_embeddings("train", model_name=saved["encoder_name"])
            self.bank, self.owners = build_bank(self.train_records, embeddings)
            self.exact_textures = exact_texture_index(self.train_records)
            descriptions = {}
            for path in ("cix_prompt_review.json", "cix_second_prompt_review.json",
                         "cix_new_holdout_catalog.json"):
                more = json.loads((root / "data" / path).read_text(encoding="utf-8"))
                if set(descriptions) & set(more):
                    raise ValueError("CIX description files contain duplicate effect IDs")
                descriptions.update(more)
            by_id = {item["id"]: item for item in manifest["effects"]}
            self.cix_textures = [by_id[effect_id]["texture"] for effect_id in descriptions]
            self.cix_bank = self.encoder.encode(list(descriptions.values()))

    def predict(self, prompt: str) -> dict:
        return self.predict_many([prompt])[0]

    def predict_many(self, prompts: list[str]) -> list[dict]:
        prompts = [prompt.strip() for prompt in prompts]
        if not prompts or any(not prompt or len(prompt) > 500 for prompt in prompts):
            raise ValueError("prompts must be between 1 and 500 characters")
        with torch.no_grad():
            vectors = self.encoder.encode(prompts)
            if isinstance(self.model, ParticleFullColor):
                cues = torch.tensor([color_cue(prompt) for prompt in prompts], dtype=vectors.dtype)
                output = self.model(vectors, cues)
            else:
                output = self.model(vectors)
        emitters = [
            decode_full(self.normalizer, output, index, prompt, self.base_bias, self.light_bias)
            for index, prompt in enumerate(prompts)
        ]
        for prompt, emitter in zip(prompts, emitters):
            request = requested_color(prompt)
            if request is not None and not emitter_color_matches(emitter, request.rgb):
                emitter["properties"]["Color"] = tint_emitter_color(emitter, request.rgb)["properties"]["Color"]
        if self.neighbor_texture_threshold is not None:
            confidence = output["categories"]["Texture"].softmax(dim=1).max(dim=1).values
            indices, similarities = nearest(vectors, self.bank)
            neighbors = [self.train_records[self.owners[index][0]]["emitter"]
                         for index in indices.tolist()]
            apply_neighbor_textures(emitters, confidence, neighbors,
                                    self.neighbor_texture_threshold)
            apply_catalog_textures(emitters, vectors @ self.cix_bank.T,
                                   similarities, self.cix_textures)
            for prompt, emitter in zip(prompts, emitters):
                texture = self.exact_textures.get(" ".join(prompt.casefold().split()))
                if texture is not None:
                    emitter["properties"]["Texture"] = texture
        align_flipbook_layouts(emitters, self.texture_layouts)
        return [
            particle_record(prompt, emitter)
            for prompt, emitter in zip(prompts, emitters)
        ]
