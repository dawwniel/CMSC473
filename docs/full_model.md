# Full particle model

The current plugin also uses a train-only nearest-neighbor texture fallback
when the model's texture confidence is low. Its comparison with this original
checkpoint and all baselines is in [`evaluation_results.md`](evaluation_results.md).

The model takes a prompt through the frozen MiniLM encoder, then predicts the
variable fields of one Roblox `ParticleEmitter`. Its heads cover 96 numeric
targets (including sampled Size, Squash, Transparency, and Color curves), 8
categorical fields, and 3 variable flags. The normalizer fills fields that
never change in training. `EmitCount` is predicted for burst effects; `Rate`
is predicted for continuous effects.

Training uses 987 effects with three prompt wordings each. The 212 validation
effects select the checkpoint. Neither test split is used to fit the model or
normalization values. The test split has 211 familiar-base variants; the
generalization split has 260 effects from held-out bases.

## Results

These results are from the saved prompt revisions and seed 473. MAE is measured
after decoding, in Roblox property units. Lower MAE is better; higher accuracy
is better.

| Split | Method | Burst accuracy | Texture accuracy | Color curve MAE | Brightness MAE |
| --- | --- | ---: | ---: | ---: | ---: |
| test | Full model | 100.0% | 83.9% | 0.057 | 1.75 |
| test | Seven-value model | 100.0% | 6.2% | 0.290 | 1.99 |
| test | Nearest neighbor | 98.1% | 77.3% | 0.063 | 2.16 |
| generalization_test | Full model | 92.3% | 27.3% | 0.158 | 5.56 |
| generalization_test | Seven-value model | 90.4% | 0.0% | 0.290 | 5.71 |
| generalization_test | Nearest neighbor | 93.8% | 35.4% | 0.187 | 6.30 |

All 471 full-model outputs passed the emitter schema check. On test, Rate MAE
was 2.84 and EmitCount MAE was 0.95 across all effects. On generalization_test,
those values were 5.45 and 1.90. Restricting the calculation to effects where
each property is active gives Rate/EmitCount MAE of 3.86/3.53 on test and
6.30/8.23 on generalization_test. A burst-mode mistake contributes to error.

Texture accuracy on generalization_test is weak, and nearest neighbor does
better there. Ten effects use textures absent from training, which the model's
texture classifier cannot output. Several numeric and sequence errors also
rise on held-out bases. The decoded emitters are valid Roblox data, but that
does not establish that every effect looks good. Review the saved predictions
in Studio before using them as final visual examples.

The prompt audit found 75 identical wordings paired with different emitter
settings after the revisions, all within the untouched test and
generalization splits. There are no exact main-prompt matches between train
and either held-out split. This checks exact wording only; related phrasing and
families still occur across splits.

## Reproduce

From `CMSC473`, with dependencies installed:

```sh
python scripts/audit_prompts.py
python scripts/train_full.py
python scripts/train.py
python scripts/evaluate_full.py
python -m unittest discover -s tests -v
```

`checkpoints/full_evaluation.json` contains every reported property metric.
`checkpoints/full_evaluation_errors_*.jsonl` contains per-effect errors and
`checkpoints/full_evaluation_review_*.jsonl` contains importer-ready review
predictions. Checkpoints and generated reports are ignored by Git, so rerun
these commands after cloning the repository.
