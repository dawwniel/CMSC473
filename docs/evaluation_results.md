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
| Texture fallback | 92.3% | 34.2% | 2.108 | 0.158 | 260/260 |
| Full model | 92.3% | 27.3% | 2.108 | 0.158 | 260/260 |
| Nearest neighbor | 93.8% | 35.4% | 3.025 | 0.187 | 260/260 |
| Seven-value model | 90.4% | 0.0% | 3.386 | 0.290 | 260/260 |
| Train constant | 76.9% | 0.0% | 3.386 | 0.290 | 260/260 |

### Numeric MAE

Rate and EmitCount below are averaged across all effects. The active
values following the table only score continuous Rate or burst
EmitCount when that setting applies.

| Property | Texture fallback | Full model | Nearest neighbor | Seven-value model | Train constant |
| --- | --- | --- | --- | --- | --- |
| Brightness | 5.564 | 5.564 | 6.297 | 5.712 | 5.749 |
| Rate | 5.448 | 5.448 | 7.762 | 5.905 | 9.350 |
| EmitCount | 1.900 | 1.900 | 2.031 | 2.285 | 2.688 |
| Lifetime.min | 0.307 | 0.307 | 0.375 | 0.271 | 0.415 |
| Lifetime.max | 0.409 | 0.409 | 0.451 | 0.359 | 0.573 |
| Speed.min | 3.790 | 3.790 | 5.428 | 3.903 | 4.797 |
| Speed.max | 4.851 | 4.851 | 5.768 | 4.710 | 6.397 |

| Active property | Texture fallback | Full model | Nearest neighbor | Seven-value model | Train constant |
| --- | --- | --- | --- | --- | --- |
| Rate | 6.304 | 6.304 | 8.918 | 6.531 | 8.767 |
| EmitCount | 8.233 | 8.233 | 8.650 | 9.900 | 11.650 |

### Sequence MAE

| Curve | Texture fallback | Full model | Nearest neighbor | Seven-value model | Train constant |
| --- | --- | --- | --- | --- | --- |
| Size.value | 2.108 | 2.108 | 3.025 | 3.386 | 3.386 |
| Size.envelope | 0.397 | 0.397 | 0.795 | 0.543 | 0.543 |
| Squash.value | 0.235 | 0.235 | 0.166 | 0.179 | 0.179 |
| Squash.envelope | 0.013 | 0.013 | 0.015 | 0.037 | 0.037 |
| Transparency.value | 0.148 | 0.148 | 0.140 | 0.208 | 0.208 |
| Transparency.envelope | 0.003 | 0.003 | 0.004 | 0.001 | 0.001 |
| Color | 0.158 | 0.158 | 0.187 | 0.290 | 0.290 |

### Categorical accuracy

| Property | Texture fallback | Full model | Nearest neighbor | Seven-value model | Train constant |
| --- | --- | --- | --- | --- | --- |
| Texture | 34.2% | 27.3% | 35.4% | 0.0% | 0.0% |
| EmissionDirection | 83.8% | 83.8% | 81.2% | 84.6% | 84.6% |
| FlipbookLayout | 72.3% | 72.3% | 68.5% | 38.5% | 38.5% |
| FlipbookMode | 61.9% | 61.9% | 73.5% | 61.5% | 61.5% |
| Orientation | 85.4% | 85.4% | 84.6% | 100.0% | 100.0% |
| Shape | 82.7% | 82.7% | 81.2% | 88.5% | 88.5% |
| ShapeInOut | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| ShapeStyle | 90.0% | 90.0% | 93.5% | 100.0% | 100.0% |

## Interpretation

The texture fallback improves held-out-base texture accuracy from 27.3%
to 34.2%, while familiar-base texture accuracy changes from 83.9%
to 82.9%. All other emitter predictions and their errors are unchanged.
On the held-out-base split, the fallback is used for 106 of 260 effects:
it corrects 22 prior mistakes and changes 4 previously correct IDs.
On familiar-base test, it is used for 24 of 211 effects, correcting 2
and changing 4 previously correct IDs.
Nearest neighbor reaches 35.4% texture accuracy on held-out bases, but
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
.\.venv\Scripts\python.exe scripts\evaluate_full.py --neighbor-texture-threshold 0.6926 --output checkpoints\neighbor_hybrid_evaluation.json
.\.venv\Scripts\python.exe scripts\write_results_report.py
```

The raw report is `checkpoints/neighbor_hybrid_evaluation.json`.
