# Particle model evaluation

The full model predicts one Roblox `ParticleEmitter` from a prompt. The
texture fallback keeps every full-model setting except `Texture`. When
the model assigns its top texture less than 0.6926 probability, it uses
the texture from the nearest training prompt. That threshold was selected
using validation effects and 20 base effects reserved from the training
split. The nearest-neighbor bank contains training prompts only.

Higher accuracy is better. Mean absolute error (MAE) is the average
absolute difference from the saved emitter value, so lower is better.
Texture accuracy requires the exact asset ID. Color MAE is averaged
over sampled red, green, and blue channels on a 0–1 scale. Validity means
the decoded emitter passed schema validation, not that it looks good.

## Familiar-base test (n=211)

| Method | Burst accuracy | Texture accuracy | Size MAE | Color MAE | Valid |
| --- | --- | --- | --- | --- | --- |
| Texture fallback | 100.0% | 82.9% | 1.174 | 0.057 | 211/211 |
| Full model | 100.0% | 83.9% | 1.174 | 0.057 | 211/211 |
| Nearest neighbor | 98.1% | 77.3% | 1.507 | 0.063 | 211/211 |
| Seven-value model | 100.0% | 6.2% | 2.533 | 0.290 | 211/211 |
| Train constant | 73.0% | 6.2% | 2.533 | 0.290 | 211/211 |

### Numeric MAE

Rate and EmitCount below are averaged across all effects. The active
values following the table only score continuous Rate or burst
EmitCount when that setting applies.

| Property | Texture fallback | Full model | Nearest neighbor | Seven-value model | Train constant |
| --- | --- | --- | --- | --- | --- |
| Brightness | 1.745 | 1.745 | 2.155 | 1.988 | 2.813 |
| Rate | 2.843 | 2.843 | 3.621 | 2.798 | 9.773 |
| EmitCount | 0.953 | 0.953 | 1.270 | 1.341 | 2.720 |
| Lifetime.min | 0.164 | 0.164 | 0.160 | 0.183 | 0.353 |
| Lifetime.max | 0.178 | 0.178 | 0.184 | 0.215 | 0.472 |
| Speed.min | 1.789 | 1.789 | 1.261 | 1.736 | 4.022 |
| Speed.max | 2.405 | 2.405 | 1.417 | 2.428 | 5.942 |

| Active property | Texture fallback | Full model | Nearest neighbor | Seven-value model | Train constant |
| --- | --- | --- | --- | --- | --- |
| Rate | 3.856 | 3.856 | 4.896 | 3.795 | 9.250 |
| EmitCount | 3.526 | 3.526 | 4.579 | 4.965 | 10.070 |

### Sequence MAE

| Curve | Texture fallback | Full model | Nearest neighbor | Seven-value model | Train constant |
| --- | --- | --- | --- | --- | --- |
| Size.value | 1.174 | 1.174 | 1.507 | 2.533 | 2.533 |
| Size.envelope | 0.353 | 0.353 | 0.325 | 0.654 | 0.654 |
| Squash.value | 0.080 | 0.080 | 0.042 | 0.112 | 0.112 |
| Squash.envelope | 0.007 | 0.007 | 0.005 | 0.040 | 0.040 |
| Transparency.value | 0.080 | 0.080 | 0.047 | 0.235 | 0.235 |
| Transparency.envelope | 0.001 | 0.001 | 0.000 | 0.003 | 0.003 |
| Color | 0.057 | 0.057 | 0.063 | 0.290 | 0.290 |

### Categorical accuracy

| Property | Texture fallback | Full model | Nearest neighbor | Seven-value model | Train constant |
| --- | --- | --- | --- | --- | --- |
| Texture | 82.9% | 83.9% | 77.3% | 6.2% | 6.2% |
| EmissionDirection | 98.6% | 98.6% | 97.2% | 87.7% | 87.7% |
| FlipbookLayout | 93.4% | 93.4% | 88.2% | 48.8% | 48.8% |
| FlipbookMode | 94.3% | 94.3% | 92.9% | 68.2% | 68.2% |
| Orientation | 96.2% | 96.2% | 96.7% | 88.6% | 88.6% |
| Shape | 96.7% | 96.7% | 96.2% | 80.6% | 80.6% |
| ShapeInOut | 100.0% | 100.0% | 99.5% | 98.1% | 98.1% |
| ShapeStyle | 98.1% | 98.1% | 97.6% | 93.8% | 93.8% |

## Held-out-base generalization test (n=260)

| Method | Burst accuracy | Texture accuracy | Size MAE | Color MAE | Valid |
| --- | --- | --- | --- | --- | --- |
| Texture fallback | 92.3% | 33.8% | 2.108 | 0.158 | 260/260 |
| Full model | 92.3% | 27.3% | 2.108 | 0.158 | 260/260 |
| Nearest neighbor | 93.5% | 35.0% | 3.026 | 0.187 | 260/260 |
| Seven-value model | 90.4% | 0.0% | 3.386 | 0.290 | 260/260 |
| Train constant | 76.9% | 0.0% | 3.386 | 0.290 | 260/260 |

### Numeric MAE

Rate and EmitCount below are averaged across all effects. The active
values following the table only score continuous Rate or burst
EmitCount when that setting applies.

| Property | Texture fallback | Full model | Nearest neighbor | Seven-value model | Train constant |
| --- | --- | --- | --- | --- | --- |
| Brightness | 5.564 | 5.564 | 6.293 | 5.712 | 5.749 |
| Rate | 5.448 | 5.448 | 7.765 | 5.905 | 9.350 |
| EmitCount | 1.900 | 1.900 | 2.035 | 2.285 | 2.688 |
| Lifetime.min | 0.307 | 0.307 | 0.376 | 0.271 | 0.415 |
| Lifetime.max | 0.409 | 0.409 | 0.450 | 0.359 | 0.573 |
| Speed.min | 3.790 | 3.790 | 5.428 | 3.903 | 4.797 |
| Speed.max | 4.851 | 4.851 | 5.768 | 4.710 | 6.397 |

| Active property | Texture fallback | Full model | Nearest neighbor | Seven-value model | Train constant |
| --- | --- | --- | --- | --- | --- |
| Rate | 6.304 | 6.304 | 8.922 | 6.531 | 8.767 |
| EmitCount | 8.233 | 8.233 | 8.650 | 9.900 | 11.650 |

### Sequence MAE

| Curve | Texture fallback | Full model | Nearest neighbor | Seven-value model | Train constant |
| --- | --- | --- | --- | --- | --- |
| Size.value | 2.108 | 2.108 | 3.026 | 3.386 | 3.386 |
| Size.envelope | 0.397 | 0.397 | 0.795 | 0.543 | 0.543 |
| Squash.value | 0.235 | 0.235 | 0.166 | 0.179 | 0.179 |
| Squash.envelope | 0.013 | 0.013 | 0.015 | 0.037 | 0.037 |
| Transparency.value | 0.148 | 0.148 | 0.140 | 0.208 | 0.208 |
| Transparency.envelope | 0.003 | 0.003 | 0.004 | 0.001 | 0.001 |
| Color | 0.158 | 0.158 | 0.187 | 0.290 | 0.290 |

### Categorical accuracy

| Property | Texture fallback | Full model | Nearest neighbor | Seven-value model | Train constant |
| --- | --- | --- | --- | --- | --- |
| Texture | 33.8% | 27.3% | 35.0% | 0.0% | 0.0% |
| EmissionDirection | 83.8% | 83.8% | 81.2% | 84.6% | 84.6% |
| FlipbookLayout | 72.3% | 72.3% | 68.5% | 38.5% | 38.5% |
| FlipbookMode | 61.9% | 61.9% | 73.5% | 61.5% | 61.5% |
| Orientation | 85.4% | 85.4% | 84.6% | 100.0% | 100.0% |
| Shape | 82.7% | 82.7% | 80.8% | 88.5% | 88.5% |
| ShapeInOut | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| ShapeStyle | 90.0% | 90.0% | 93.5% | 100.0% | 100.0% |

## Interpretation

The active checkpoint remains the version reported in the tables above.

### Retraining after the CIX texture review (November 8)

Studio and the exported dataset agree on 1,231 train effects, 212 validation,
211 test, 260 generalization test, and 371 effects still under review. The
review effects are excluded from fitting. Fifteen CIX effects were deliberately
reserved from training for the separate catalog check described in
[cix_texture_holdout.md](cix_texture_holdout.md).

I retrained the full model on the current 1,231 train effects and selected its
checkpoint by validation loss (best epoch 230). I also tried a linear texture
head and a category-aware model. The table reports **exact asset ID** accuracy;
the denominator includes textures not present in training.

| Method | Familiar test (211) | Held-out bases (260) |
| --- | ---: | ---: |
| Active model with texture fallback | 175/211 (82.9%) | 88/260 (33.8%) |
| Retrained full model | 177/211 (83.9%) | 71/260 (27.3%) |
| Retrained model with texture fallback | 174/211 (82.5%) | 89/260 (34.2%) |
| Retrained texture-only linear head | 74/211 (35.1%) | 60/260 (23.1%) |
| Nearest training prompt | 163/211 (77.3%) | 91/260 (35.0%) |

The new fallback gains one held-out effect but loses one familiar effect
relative to the active checkpoint. Its held-out burst accuracy also falls from
92.3% to 89.6%. It has **not** replaced the active model. The texture-only head
was selected after reaching 50/140 on 20 reserved training bases, but that
small development result did not carry over to the official sets. The
category-aware model reached only 25/140 on those reserved bases.

Only 10 of the 260 held-out effects use an asset ID absent from training.
Among the 364 texture IDs in training, 243 occur in just one effect. Many of
the remaining misses have similar prompts within a family but different
textures. More epochs or a larger output head cannot reliably resolve an
image distinction that the prompt does not describe. The next data pass
should add visually specific, independently written descriptions for reused
textures and test on newly reserved whole base effects. Keep the existing
test and generalization sets fixed for reporting.

The candidate checkpoint and per-effect errors are in ignored `checkpoints/`
files. Reproduce the experiment with `scripts/train_full.py`,
`scripts/evaluate_full.py`, `scripts/train_texture.py`, and
`scripts/evaluate_texture_head.py`.

A later image-aware retrieval experiment aligned prompt embeddings to cached
texture images. It reached 36.4% exact top-one on the 140 reserved development
effects, but only 26.2% on the 260 held-out-base effects, so it was not added
to inference. The active model's top three texture IDs contain the recorded ID
for 44.6% of held-out effects; the three closest distinct training-prompt
textures contain it for 47.3%. A three-choice picker alone therefore does not
meet an 80% exact-ID target. The separate human visual-fit protocol is in
[`texture_evaluation.md`](texture_evaluation.md).

### Active checkpoint details

The texture fallback improves held-out-base texture accuracy from 27.3%
to 33.8%, while familiar-base texture accuracy changes from 83.9%
to 82.9%. All other emitter predictions and their errors are unchanged.
On the held-out-base split, the fallback is used for 106 of 260 effects:
it corrects 21 prior mistakes and changes 4 previously correct IDs.
On familiar-base test, it is used for 24 of 211 effects, correcting 2
and changing 4 previously correct IDs.
Nearest neighbor reaches 35.0% texture accuracy on held-out bases, but
copies the whole emitter, leading to larger errors on several numeric
and curve properties. The texture fallback uses only its texture.

10 generalization effects use textures absent from training; no method
restricted to training texture IDs can predict those exact IDs. Exact
asset-ID accuracy also does not tell us whether a different texture
looks acceptable. The plugin's visual ratings are needed for that.
The current full model passes 5 of 12 controlled wording checks.

These official splits have been inspected during development, so this
is a descriptive project comparison rather than a pristine blind final
estimate. A new, never-inspected set of whole base effects should be
collected for a final claim about generalization.

Reproduce from `CMSC473`:

```powershell
.\.venv\Scripts\python.exe scripts\evaluate_full.py --neighbor-texture-threshold 0.6926 --output checkpoints\cix_holdout_hybrid_evaluation.json
.\.venv\Scripts\python.exe scripts\write_results_report.py --input checkpoints\cix_holdout_hybrid_evaluation.json
```

The raw report is `checkpoints/cix_holdout_hybrid_evaluation.json`.
