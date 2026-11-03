# Model development after the first full checkpoint

The first full model predicts valid emitters, but a valid emitter can still
look wrong. Texture accuracy is 83.9% on familiar-base test variants and 27.3%
on whole bases absent from training. This is the largest visible gap.

## Development check

`data/dev_base_ids.json` reserves 20 whole base effects from the training
split. Its 140 variants are used only to compare new approaches. The other
847 training effects fit the model and its normalization. The official
validation, test, and generalization splits are unchanged. Fourteen of the
140 development effects use a texture absent from the fitted subset, so their
texture cannot be predicted by its classifier.

| Development method | Texture accuracy | Burst accuracy | Size MAE | Color MAE |
| --- | ---: | ---: | ---: | ---: |
| Nearest neighbor | 13.6% | 83.6% | 2.151 | 0.196 |
| Plain full model | 23.6% | 89.3% | 2.138 | 0.189 |
| Category-aware, weighted loss | 15.7% | 89.3% | 2.188 | 0.197 |
| Category-aware, no texture bias | 20.0% | 89.3% | 2.174 | 0.199 |
| Plain model, 128 hidden units | 17.1% | 89.3% | 2.066 | 0.189 |
| Plain model, dropout 0.5 | 22.1% | 89.3% | 2.153 | 0.191 |
| Plain model, 42 extra prompt wordings | 22.9% | 89.3% | 2.149 | 0.196 |

The category-aware loss and small prompt augmentation did not improve this
check. They remain experiments. The Studio server uses `particle_full.pt` for
every property and a train-only nearest-neighbor texture fallback when the
model's texture confidence is below 0.6926. The extra wordings are drafts in
`data/extra_train_prompts.json`, not human visual labels. More of them should
not be treated as evidence that the model understands more effects.

Selecting after about 12 epochs on this held-out-base check and fitting the
full training split produced 35.4% texture accuracy on
`generalization_test`, versus 27.3% for the existing checkpoint. It also
reduced familiar-base test texture accuracy from 83.9% to 40.8%, and increased
test color MAE from 0.057 to 0.164. It is not the default checkpoint. Later
texture-only and confidence experiments also inspected the official splits.
Those splits are no longer pristine blind estimates. Collect a new untouched
set of whole base effects for a final generalization claim.

A separate texture classifier improved development texture accuracy but fell
from 83.9% to 29.9% on familiar-base test and from 27.3% to 20.0% on the
generalization split. It was not deployed. Taking only the nearest neighbor's
texture below a confidence threshold gave 82.9% familiar-base and 34.2%
generalization texture accuracy. Speed, color, curves, and burst predictions
stay with the full model. The complete comparison is in
[`evaluation_results.md`](evaluation_results.md).

## Controlled prompts and visual review

`scripts/evaluate_controls.py` compares 12 low/high wording pairs for speed,
size, density, lifetime, spread, and brightness. The current checkpoint passes
5 of 12 chosen thresholds. The early-stopped checkpoint passes only 1 of 12.
These checks reveal wording failures, but the
thresholds are project checks, not physical ground truth for arbitrary text.

The plugin's **Next test** and rating buttons support visual review. Review
the predictions in Studio, group errors by texture and motion, then correct
ambiguous or poor training labels before another training run. Keep ratings
outside the official test data. A useful next model experiment is a texture
retrieval head or a jointly trained text encoder, chosen on the development
split before one final held-out evaluation.

## Reproduce

From the `CMSC473` directory:

```powershell
.\.venv\Scripts\python.exe scripts\make_dev_split.py
.\.venv\Scripts\python.exe scripts\train_v2.py --mode plain --dev
.\.venv\Scripts\python.exe scripts\train_v2.py --mode v2 --dev
.\.venv\Scripts\python.exe scripts\evaluate_dev.py
.\.venv\Scripts\python.exe scripts\evaluate_controls.py
```

The checkpoints and reports are under `checkpoints/` and are ignored by Git.
