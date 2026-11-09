# CIX texture prompt review

Sixty effects from the CIX `review` split were checked against their image sheets in Studio. The batch covers circles, smoke, slashes, stars, and fire. [cix_prompt_review.json](../data/cix_prompt_review.json) holds the replacement prompts. They describe visible outlines, patterns, and animation frames instead of repeating the same generic family description. The prompt still includes the emitter's color and behavior.

All 60 effects were first promoted to train with canonical rows in [particles_train.jsonl](../src/data/train/particles_train.jsonl). The local promotion used [promote_cix_review.py](../scripts/promote_cix_review.py) with the earlier all-CIX exporter output as `--source`. All 60 new row hashes matched a fresh Studio exporter serialization. Fifteen were then reserved for the [CIX texture holdout](cix_texture_holdout.md) and moved back to `review`; the other 45 remain in train. The prompt audit found no conflicting wording involving train or validation, and no held-out main prompt equal to a train prompt. The live place now has 1,231 train effects and 371 review effects; validation, test, and generalization labels did not change.

## Image retrieval check

This first development check was run before reserving the 15 CIX effects. It reserved 20 whole base effects (140 variants) from train. The text lookup bank was built from the other training effects. Both methods ranked the same 375 texture candidates available in that bank. Fourteen development variants had a texture absent from the candidate bank, so neither method could score an exact hit on those variants.

[fetch_texture_images.py](../scripts/fetch_texture_images.py) cached the Roblox asset images, using public thumbnails where direct asset delivery denied access. One of 378 numeric asset IDs had a blocked thumbnail. For animated flipbooks, [benchmark_texture_retrieval.py](../scripts/benchmark_texture_retrieval.py) presents the frame with the most visible pixels to the frozen [CLIP ViT-B/32 model](https://huggingface.co/openai/clip-vit-base-patch32). Static images are shown on a dark background. The text lookup uses the project's frozen MiniLM embeddings and the same candidate textures. Neither method was fitted on the 20 development bases.

| Texture selector | Exact top 1 | Exact top 3 |
| --- | ---: | ---: |
| MiniLM text lookup | 26/140 (18.6%) | 39/140 (27.9%) |
| Frozen CLIP image retrieval | 2/140 (1.4%) | 4/140 (2.9%) |

The first CLIP run using full flipbook sheets scored 0/140 exact; selecting a representative frame raised it to 2/140. This zero-shot image model is not suitable as the plugin's texture selector in its current form. Exact ID scoring also hides some visually similar alternatives. [render_texture_review.py](../scripts/render_texture_review.py) makes four local contact sheets under `checkpoints/texture_review_page_*.png` for human rating; no visual-acceptability percentage is claimed from those sheets.

## Full-model check

The full model was retrained on all 1,246 training effects before the separate CIX holdout was selected. It ran for 240 epochs, with validation selecting epoch 239. It reached 86.3% raw texture accuracy on the familiar-base test, compared with 83.9% for the earlier model. On the 260 held-out-base effects, raw texture accuracy stayed at 27.3%, burst accuracy fell from 92.3% to 88.5%, and color-curve MAE rose from 0.158 to 0.162. This candidate is saved locally as `checkpoints/particle_full_cix_review.pt`; it did not replace the active model or take part in the CIX holdout check. The active model uses the earlier particle-property checkpoint with the current 1,231-row text lookup and retains 33.8% texture accuracy and 92.3% burst accuracy on the official held-out bases.

The active plugin also checks for an exact, unambiguous training prompt before choosing its final texture. Before the CIX holdout was selected, this returned the saved texture for all 60 reviewed prompts (60/60 in a training-prompt smoke check). That was a lookup for known wording, not a generalization score. The current CIX holdout uses different query wording and excludes its 15 effects from train.

The earlier official test sets have been inspected during development. These figures describe this project iteration; a fresh untouched set of whole base effects is needed for a final generalization claim. The remaining 345 CIX review effects should stay out of training until their prompts are checked visually. The next model experiment should use texture-specific positive and hard-negative descriptions on development bases, with human visual ratings alongside exact ID accuracy.
