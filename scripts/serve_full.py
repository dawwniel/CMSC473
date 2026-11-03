"""Serve the full particle model to the local Roblox Studio plugin."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import secrets
import sys
import traceback
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.models.inference import FullPredictor


ROOT = Path(__file__).resolve().parents[1]


def handler_for(predictor, feedback_path: Path | None = None):
    feedback_path = feedback_path or ROOT / "checkpoints/visual_feedback.jsonl"
    recent = {}
    test_prompts = json.loads((ROOT / "data/visual_eval_prompts.json").read_text(encoding="utf-8"))
    prompt_cursor = [0]

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
            if self.path == "/health":
                self.send_json(200, {"status": "ok"})
            elif self.path == "/next_prompt":
                index = prompt_cursor[0] % len(test_prompts)
                prompt_cursor[0] += 1
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
                    if (not isinstance(request_id, str) or request_id not in recent
                            or rating not in ("good", "texture", "motion", "other")):
                        raise ValueError("unknown prediction or rating")
                    entry = {
                        "time_utc": datetime.now(timezone.utc).isoformat(),
                        "rating": rating,
                        "request_id": request_id,
                        "record": recent[request_id],
                    }
                    feedback_path.parent.mkdir(parents=True, exist_ok=True)
                    with feedback_path.open("a", encoding="utf-8") as stream:
                        stream.write(json.dumps(entry, separators=(",", ":")) + "\n")
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
    server = HTTPServer(("127.0.0.1", args.port), handler_for(predictor))
    print(f"Prompt2Particles ready at http://127.0.0.1:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
