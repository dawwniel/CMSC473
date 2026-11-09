"""Score blinded Studio texture ratings without changing exact-ID metrics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RATINGS = {"texture_fit", "texture_usable", "texture_wrong", "texture_skip"}
ACCEPTED = {"texture_fit", "texture_usable"}


def score(path: Path, prompts_path: Path) -> dict:
    prompts = json.loads(prompts_path.read_text(encoding="utf-8"))
    expected = [entry["prompt"] for entry in prompts]
    if len(expected) != len(set(expected)):
        raise ValueError("visual evaluation prompts must be unique")
    expected_set = set(expected)
    by_reviewer = {}
    ignored = 0
    duplicates = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        entry = json.loads(line)
        if entry.get("rating") not in RATINGS:
            continue
        prompt = entry["record"]["prompt"]
        if prompt not in expected_set:
            ignored += 1
            continue
        reviewer = entry["reviewer"]
        group = by_reviewer.setdefault(reviewer, {"model_ids": set(), "ratings": {}})
        group["model_ids"].add(entry.get("model_id", "unknown"))
        if prompt in group["ratings"]:
            duplicates += 1
            continue  # The first rating is fixed; reruns cannot improve the score.
        group["ratings"][prompt] = entry["rating"]

    if not by_reviewer:
        raise ValueError("no texture ratings found for the scheduled prompts")
    model_ids = set()
    results = {"scheduled_prompts": len(expected), "ignored_unscheduled": ignored,
               "ignored_duplicates": duplicates, "reviewers": {}}
    for reviewer, group in sorted(by_reviewer.items()):
        if len(group["model_ids"]) != 1:
            raise ValueError(f"reviewer {reviewer} rated more than one model version")
        model_ids.update(group["model_ids"])
        counts = {rating: sum(value == rating for value in group["ratings"].values())
                  for rating in RATINGS}
        missing = len(expected) - len(group["ratings"])
        results["reviewers"][reviewer] = {
            "model_id": next(iter(group["model_ids"])),
            "complete": missing == 0,
            "missing": missing,
            "counts": counts,
            "strict_fit": counts["texture_fit"] / len(expected),
            "acceptable": (counts["texture_fit"] + counts["texture_usable"]) / len(expected),
        }
    if len(model_ids) != 1:
        raise ValueError("reviewers rated different model versions")
    if len(by_reviewer) >= 2:
        common = set.intersection(*(set(group["ratings"]) for group in by_reviewer.values()))
        unanimous = sum(prompt in common and all(group["ratings"][prompt] in ACCEPTED
                                                for group in by_reviewer.values())
                        for prompt in expected)
        results["shared_ratings"] = len(common)
        results["unanimous_acceptable"] = unanimous / len(expected)
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feedback", type=Path,
                        default=ROOT / "checkpoints/visual_feedback.jsonl")
    parser.add_argument("--prompts", type=Path,
                        default=ROOT / "data/visual_eval_prompts.json")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "checkpoints/visual_feedback_report.json")
    args = parser.parse_args()
    result = score(args.feedback, args.prompts)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    for reviewer, values in result["reviewers"].items():
        print(f"{reviewer}: fits={values['strict_fit']:.1%} "
              f"acceptable={values['acceptable']:.1%} missing={values['missing']}")
    if "unanimous_acceptable" in result:
        print(f"all reviewers accept={result['unanimous_acceptable']:.1%}")
    print(f"saved {args.output}")


if __name__ == "__main__":
    main()
