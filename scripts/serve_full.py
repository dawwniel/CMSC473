"""Serve the full particle model to the local Roblox Studio plugin."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import secrets
import sys
import traceback
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.models.inference import FullPredictor


ROOT = Path(__file__).resolve().parents[1]


def handler_for(predictor, feedback_path: Path | None = None, model_id: str = "unknown"):
    feedback_path = feedback_path or ROOT / "checkpoints/visual_feedback.jsonl"
    recent = {}
    test_prompts = json.loads((ROOT / "data/visual_eval_prompts.json").read_text(encoding="utf-8"))
    prompt_cursor = {}
    rated = set()

    class Handler(BaseHTTPRequestHandler):
        def send_json(self, status: int, value: dict) -> None:
            body = json.dumps(value, separators=(",", ":")).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            url = urlsplit(self.path)
            if url.path == "/health":
                self.send_json(200, {"status": "ok"})
            elif url.path == "/next_prompt":
                reviewer = parse_qs(url.query).get("reviewer", ["default"])[0]
                if not isinstance(reviewer, str) or not 1 <= len(reviewer) <= 32:
                    self.send_json(400, {"error": "reviewer must be 1-32 characters"})
                    return
                index = prompt_cursor.get(reviewer, 0) % len(test_prompts)
                prompt_cursor[reviewer] = index + 1
                self.send_json(200, {**test_prompts[index], "number": index + 1, "total": len(test_prompts)})
            else:
                self.send_json(404, {"error": "not found"})

        def do_POST(self) -> None:
            if self.path not in ("/predict", "/feedback"):
                self.send_json(404, {"error": "not found"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            if length <= 0 or length > 4096:
                self.send_json(400, {"error": "request body must be 1-4096 bytes"})
                return
            try:
                payload = json.loads(self.rfile.read(length))
                if not isinstance(payload, dict):
                    raise ValueError("send a JSON object")
                if self.path == "/feedback":
                    request_id = payload.get("request_id")
                    rating = payload.get("rating")
                    reviewer = payload.get("reviewer")
                    if (not isinstance(request_id, str) or request_id not in recent
                            or rating not in ("good", "texture", "motion", "other",
                                              "texture_fit", "texture_usable", "texture_wrong", "texture_skip")):
                        raise ValueError("unknown prediction or rating")
                    if rating.startswith("texture_"):
                        if (not isinstance(reviewer, str) or not 1 <= len(reviewer.strip()) <= 32
                                or not all(character.isalnum() or character in "-_" for character in reviewer)):
                            raise ValueError("reviewer must be 1-32 letters, digits, - or _")
                        if (request_id, reviewer) in rated:
                            raise ValueError("prediction already rated by this reviewer")
                    entry = {
                        "time_utc": datetime.now(timezone.utc).isoformat(),
                        "rating": rating,
                        "request_id": request_id,
                        "model_id": model_id,
                        "record": recent[request_id],
                    }
                    if rating.startswith("texture_"):
                        entry["reviewer"] = reviewer
                    feedback_path.parent.mkdir(parents=True, exist_ok=True)
                    with feedback_path.open("a", encoding="utf-8") as stream:
                        stream.write(json.dumps(entry, separators=(",", ":")) + "\n")
                    if rating.startswith("texture_"):
                        rated.add((request_id, reviewer))
                    self.send_json(200, {"saved": True})
                    return
                if not isinstance(payload.get("prompt"), str):
                    raise ValueError("send a prompt string")
                record = predictor.predict(payload["prompt"])
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                self.send_json(400, {"error": str(exc)})
                return
            except Exception:
                traceback.print_exc()
                self.send_json(500, {"error": "prediction failed; check the server window"})
                return
            request_id = secrets.token_hex(8)
            recent[request_id] = record
            if len(recent) > 100:
                recent.pop(next(iter(recent)))
            self.send_json(200, {"record": record, "request_id": request_id})

        def log_message(self, format: str, *args) -> None:
            print("Studio: " + format % args)

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, default=ROOT / "checkpoints/particle_full.pt")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--neighbor-texture-threshold", type=float, default=0.6926)
    parser.add_argument("--no-neighbor-texture", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")
    predictor = FullPredictor(
        args.checkpoint,
        None if args.no_neighbor_texture else args.neighbor_texture_threshold,
    )
    version = hashlib.sha256()
    for path in (args.checkpoint, ROOT / "src/models/inference.py",
                 ROOT / "src/data/train/particles_train.jsonl",
                 ROOT / "data/cix_prompt_review.json",
                 ROOT / "data/cix_second_prompt_review.json",
                 ROOT / "data/cix_new_holdout_catalog.json"):
        version.update(path.read_bytes())
    model_id = version.hexdigest()[:16]
    server = HTTPServer(("127.0.0.1", args.port), handler_for(predictor, model_id=model_id))
    print(f"Prompt2Particles ready at http://127.0.0.1:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
