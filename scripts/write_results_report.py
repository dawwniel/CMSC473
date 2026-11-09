"""Turn the saved evaluation JSON into report-ready Markdown tables."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
METHODS = [
    ("neighbor_texture_hybrid", "Texture fallback"),
    ("full_model", "Full model"),
    ("nearest_neighbor", "Nearest neighbor"),
    ("seven_value_model", "Seven-value model"),
    ("train_constant", "Train constant"),
]
NUMERIC = ("Brightness", "Rate", "EmitCount", "Lifetime.min", "Lifetime.max",
           "Speed.min", "Speed.max")
CURVES = ("Size.value", "Size.envelope", "Squash.value", "Squash.envelope",
          "Transparency.value", "Transparency.envelope", "Color")
CATEGORIES = ("Texture", "EmissionDirection", "FlipbookLayout", "FlipbookMode",
              "Orientation", "Shape", "ShapeInOut", "ShapeStyle")


def percent(value):
    return f"{value * 100:.1f}%"


def number(value):
    return "—" if value is None else f"{value:.3f}"


def table(headers, rows):
    return "\n".join([
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
        *("| " + " | ".join(map(str, row)) + " |" for row in rows),
    ])


def method_rows(split):
    rows = []
    for key, label in METHODS:
        row = split[key]
        rows.append((label, percent(row["seven_value_metrics"]["burst_accuracy"]),
                     percent(row["category_accuracy"]["Texture"]),
                     number(row["curve_mae"]["Size.value"]),
                     number(row["curve_mae"]["Color"]),
                     f"{row['valid_emitters']}/{row['samples']}"))
    return rows


def property_rows(split, group, names, format_value):
    rows = []
    for name in names:
        row = [name]
        for key, _ in METHODS:
            value = split[key][group][name]
            row.append(format_value(value))
        rows.append(row)
    return rows


def render(results, changes, evaluation_file="neighbor_hybrid_evaluation.json"):
    familiar = results["test"]
    new_base = results["generalization_test"]
    familiar_full = percent(familiar["full_model"]["category_accuracy"]["Texture"])
    familiar_fallback = percent(familiar["neighbor_texture_hybrid"]["category_accuracy"]["Texture"])
    new_full = percent(new_base["full_model"]["category_accuracy"]["Texture"])
    new_fallback = percent(new_base["neighbor_texture_hybrid"]["category_accuracy"]["Texture"])
    new_neighbor = percent(new_base["nearest_neighbor"]["category_accuracy"]["Texture"])
    lines = [
        "# Particle model evaluation",
        "",
        "The full model predicts one Roblox `ParticleEmitter` from a prompt. The",
        "texture fallback keeps every full-model setting except `Texture`. When",
        "the model assigns its top texture less than 0.6926 probability, it uses",
        "the texture from the nearest training prompt. That threshold was selected",
        "using validation effects and 20 base effects reserved from the training",
        "split. The nearest-neighbor bank contains training prompts only.",
        "",
        "Higher accuracy is better. Mean absolute error (MAE) is the average",
        "absolute difference from the saved emitter value, so lower is better.",
        "Texture accuracy requires the exact asset ID. Color MAE is averaged",
        "over sampled red, green, and blue channels on a 0–1 scale. Validity means",
        "the decoded emitter passed schema validation, not that it looks good.",
        "",
    ]
    for name, title in (("test", "Familiar-base test"),
                        ("generalization_test", "Held-out-base generalization test")):
        split = results[name]
        lines.extend([
            f"## {title} (n={split['full_model']['samples']})", "",
            table(("Method", "Burst accuracy", "Texture accuracy", "Size MAE",
                   "Color MAE", "Valid"), method_rows(split)), "",
            "### Numeric MAE", "",
            "Rate and EmitCount below are averaged across all effects. The active",
            "values following the table only score continuous Rate or burst",
            "EmitCount when that setting applies.", "",
            table(("Property", *(label for _, label in METHODS)), [
                (field, *(number(split[key]["seven_value_metrics"]["mae"][field])
                          for key, _ in METHODS)) for field in NUMERIC
            ]), "",
            table(("Active property", *(label for _, label in METHODS)), [
                (field, *(number(split[key]["seven_value_metrics"]["active_mae"][field])
                          for key, _ in METHODS)) for field in ("Rate", "EmitCount")
            ]), "",
            "### Sequence MAE", "",
            table(("Curve", *(label for _, label in METHODS)),
                  property_rows(split, "curve_mae", CURVES, number)), "",
            "### Categorical accuracy", "",
            table(("Property", *(label for _, label in METHODS)),
                  property_rows(split, "category_accuracy", CATEGORIES, percent)), "",
        ])
    lines.extend([
        "## Interpretation", "",
        f"The texture fallback improves held-out-base texture accuracy from {new_full}",
        f"to {new_fallback}, while familiar-base texture accuracy changes from {familiar_full}",
        f"to {familiar_fallback}. All other emitter predictions and their errors are unchanged.",
        f"On the held-out-base split, the fallback is used for {changes['generalization_test']['used']} of 260 effects:",
        f"it corrects {changes['generalization_test']['fixed']} prior mistakes and changes {changes['generalization_test']['broken']} previously correct IDs.",
        f"On familiar-base test, it is used for {changes['test']['used']} of 211 effects, correcting {changes['test']['fixed']}",
        f"and changing {changes['test']['broken']} previously correct IDs.",
        f"Nearest neighbor reaches {new_neighbor} texture accuracy on held-out bases, but",
        "copies the whole emitter, leading to larger errors on several numeric",
        "and curve properties. The texture fallback uses only its texture.",
        "",
        f"{new_base['full_model']['texture_unseen_in_train']} generalization effects use textures absent from training; no method",
        "restricted to training texture IDs can predict those exact IDs. Exact",
        "asset-ID accuracy also does not tell us whether a different texture",
        "looks acceptable. The plugin's visual ratings are needed for that.",
        "The current full model passes 5 of 12 controlled wording checks.",
        "",
        "These official splits have been inspected during development, so this",
        "is a descriptive project comparison rather than a pristine blind final",
        "estimate. A new, never-inspected set of whole base effects should be",
        "collected for a final claim about generalization.",
        "",
        "Reproduce from `CMSC473`:", "",
        "```powershell",
        f".\\.venv\\Scripts\\python.exe scripts\\evaluate_full.py --neighbor-texture-threshold 0.6926 --output checkpoints\\{evaluation_file}",
        f".\\.venv\\Scripts\\python.exe scripts\\write_results_report.py --input checkpoints\\{evaluation_file}",
        "```", "",
        f"The raw report is `checkpoints/{evaluation_file}`.",
    ])
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path,
                        default=ROOT / "checkpoints/neighbor_hybrid_evaluation.json")
    parser.add_argument("--output", type=Path, default=ROOT / "docs/evaluation_results.md")
    args = parser.parse_args()
    results = json.loads(args.input.read_text(encoding="utf-8"))
    for split in ("test", "generalization_test"):
        if "neighbor_texture_hybrid" not in results[split]:
            parser.error(f"{split} has no texture fallback result")
    changes = {}
    for split in ("test", "generalization_test"):
        detail_path = args.input.with_name(f"{args.input.stem}_errors_{split}.jsonl")
        details = [json.loads(line) for line in detail_path.read_text(encoding="utf-8").splitlines()]
        changes[split] = {
            "used": sum(row["fallback_used"] for row in details),
            "fixed": sum(row["predicted_texture"] != row["actual_texture"]
                         and row["fallback_texture_correct"] for row in details),
            "broken": sum(row["predicted_texture"] == row["actual_texture"]
                          and not row["fallback_texture_correct"] for row in details),
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(results, changes, args.input.name), encoding="utf-8")
    print(f"saved {args.output}")


if __name__ == "__main__":
    main()
