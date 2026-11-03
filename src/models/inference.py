"""Load the trained full model once and predict importer-ready records."""

from __future__ import annotations

import hashlib
from pathlib import Path

import torch

from ..data.normalize import Normalizer
from ..data.dataset import load_split
from .encoder import TextEncoder, split_embeddings
from .full import ParticleFull, decode_full
from .model import particle_record
from .nearest_neighbor import build_bank, nearest
from .v2 import ParticleV2


def model_from_checkpoint(saved: dict, normalizer: Normalizer) -> ParticleFull:
    if saved.get("architecture") == "v2":
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


class FullPredictor:
    def __init__(self, checkpoint: Path, neighbor_texture_threshold: float | None = None):
        torch.set_num_threads(min(4, torch.get_num_threads()))
        saved = torch.load(checkpoint, map_location="cpu", weights_only=True)
        normalizer = Normalizer.from_dict(saved["normalizer"])
        model = model_from_checkpoint(saved, normalizer)
        self.normalizer = normalizer
        self.model = model
        self.encoder = TextEncoder(saved["encoder_name"], device="cpu")
        self.neighbor_texture_threshold = neighbor_texture_threshold
        if neighbor_texture_threshold is not None:
            if not 0 <= neighbor_texture_threshold <= 1:
                raise ValueError("texture confidence threshold must be between 0 and 1")
            self.train_records = load_split("train")
            fingerprint = hashlib.sha256("\n".join(
                row["row_hash"] for row in self.train_records
            ).encode()).hexdigest()
            if fingerprint != saved["train_fingerprint"]:
                raise ValueError("training data changed after the model checkpoint")
            embeddings = split_embeddings("train", model_name=saved["encoder_name"])
            self.bank, self.owners = build_bank(self.train_records, embeddings)

    def predict(self, prompt: str) -> dict:
        return self.predict_many([prompt])[0]

    def predict_many(self, prompts: list[str]) -> list[dict]:
        prompts = [prompt.strip() for prompt in prompts]
        if not prompts or any(not prompt or len(prompt) > 500 for prompt in prompts):
            raise ValueError("prompts must be between 1 and 500 characters")
        with torch.no_grad():
            vectors = self.encoder.encode(prompts)
            output = self.model(vectors)
        emitters = [decode_full(self.normalizer, output, index) for index in range(len(prompts))]
        if self.neighbor_texture_threshold is not None:
            confidence = output["categories"]["Texture"].softmax(dim=1).max(dim=1).values
            indices, _ = nearest(vectors, self.bank)
            neighbors = [self.train_records[self.owners[index][0]]["emitter"]
                         for index in indices.tolist()]
            apply_neighbor_textures(emitters, confidence, neighbors,
                                    self.neighbor_texture_threshold)
        return [
            particle_record(prompt, emitter)
            for prompt, emitter in zip(prompts, emitters)
        ]
