"""Check the local HTTP contract used by the Studio plugin."""

from __future__ import annotations

import json
import tempfile
import threading
import unittest
from http.server import HTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from scripts.serve_full import handler_for


class FakePredictor:
    def predict(self, prompt):
        if not prompt.strip():
            raise ValueError("prompt is blank")
        return {"formatVersion": 1, "prompt": prompt}


class LocalServerTests(unittest.TestCase):
    def test_health_prediction_and_bad_prompt(self):
        temp = tempfile.TemporaryDirectory()
        feedback = Path(temp.name) / "feedback.jsonl"
        server = HTTPServer(("127.0.0.1", 0), handler_for(FakePredictor(), feedback))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            with urlopen(base + "/health") as response:
                self.assertEqual(json.load(response), {"status": "ok"})
            with urlopen(base + "/next_prompt") as response:
                sample = json.load(response)
                self.assertTrue(sample["prompt"])
                self.assertEqual(sample["number"], 1)
            request = Request(
                base + "/predict", data=b'{"prompt":"blue sparks"}',
                headers={"Content-Type": "application/json"}, method="POST",
            )
            with urlopen(request) as response:
                prediction = json.load(response)
                self.assertEqual(prediction["record"]["prompt"], "blue sparks")
            review = Request(
                base + "/feedback",
                data=json.dumps({"request_id": prediction["request_id"], "rating": "texture"}).encode(),
                method="POST",
            )
            with urlopen(review) as response:
                self.assertEqual(json.load(response), {"saved": True})
            self.assertEqual(json.loads(feedback.read_text())["rating"], "texture")
            bad = Request(base + "/predict", data=b'{"prompt":""}', method="POST")
            with self.assertRaises(HTTPError) as caught:
                urlopen(bad)
            self.assertEqual(caught.exception.code, 400)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
            temp.cleanup()


if __name__ == "__main__":
    unittest.main()
