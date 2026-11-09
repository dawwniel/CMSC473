# CIX texture holdout

Fifteen visually reviewed CIX effects were reserved, three from each of five families. The IDs were selected with seed 473 before scoring. Their emitter rows are excluded from the current training JSONL and labeled `review` in Studio. The 15 query prompts in [cix_texture_holdout.json](../data/cix_texture_holdout.json) are different wording from their image descriptions. The original generic and visually reviewed descriptions are in [cix_prompt_before_review.json](../data/cix_prompt_before_review.json) and [cix_prompt_review.json](../data/cix_prompt_review.json).

The original experiment used a catalog of 60 reviewed CIX textures, including the 15 reserved IDs. This tests whether a prompt can **select an available texture from a described catalog**. It does not test whether the parameter model can invent an unknown asset ID. A classifier trained without one of these IDs cannot output it, while a catalog can make it selectable without fitting model weights on that effect.

| Catalog method | Exact top 1 | Exact top 3 | Correct within same family |
| --- | ---: | ---: | ---: |
| Original generic descriptions, MiniLM | 4/15 | 10/15 | 4/15 |
| Visually reviewed descriptions, MiniLM | 12/15 | 15/15 | 12/15 |
| Frozen CLIP against texture images | 3/15 | 6/15 | 4/15 |

The three misses with reviewed descriptions were `N355` (four-point star), `N172` (spiral slash), and `N174` (thin crescent slash). All three targets were ranked second or third. The [visual comparison sheets](images/cix_holdout_page_1.png) show the target next to the closest alternatives; [page 2](images/cix_holdout_page_2.png) and [page 3](images/cix_holdout_page_3.png) cover the rest. `N355` shares a four-point shape with several soft glints, and its query omits the target's jagged metallic edge. The two slash queries give more detail, but the text encoder ranks similar arcs ahead of the target. These are visual observations, not a blinded human-acceptability score.

## Plugin selection rule

The plugin compares the prompt to the CIX description catalog and to its ordinary training-prompt bank. It chooses the CIX texture only when its catalog similarity is at least **0.65** and is no lower than the best training-prompt similarity. That rule was checked on the 15 CIX queries and on 140 older development prompts: it selected the correct CIX ID for **12/15** and overrode **0/140** older prompts. In a final read-only check it also overrode **0/211** familiar-base test prompts and **0/260** original held-out-base prompts. Those original scores therefore remain 82.9% and 33.8% with the active texture fallback.

This is a small controlled check. The query paraphrases were written after viewing the images, and the catalog descriptions are human-written. The 12/15 result shows a workable path for a curated texture library, but it is not a blind estimate for arbitrary user prompts or the other 345 CIX review textures. The next verification should have another person write prompts without seeing the catalog descriptions, then rate the returned images for visual fit as well as exact ID.

To reproduce locally after caching the image assets and the MiniLM and CLIP weights:

```powershell
.\.venv\Scripts\python.exe scripts\evaluate_cix_texture_holdout.py
.\.venv\Scripts\python.exe scripts\render_cix_holdout_review.py
.\.venv\Scripts\python.exe scripts\evaluate_cix_gate.py
```

The complete ranks are written to ignored `checkpoints/cix_texture_holdout_evaluation.json`.

The runtime catalog now has 124 descriptions: the original 60, a second visual
pass over 40 effects in eight additional families, and 24 effects reserved for
new independently written prompts. Adding these descriptions left the original
15-query result at 12/15 and changed zero of the 211 familiar or 260 held-out
base predictions. The 24-query result is pending independent prompt writing;
see [texture_evaluation.md](texture_evaluation.md). These extra effects remain
outside the training JSONL.
