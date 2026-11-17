# Asset access and flipbook layout audit — November 16, 2026

Studio reported two CIX images as **not approved for this requester**:
`rbxassetid://9295449811` (N063, Bubble8) and
`rbxassetid://18636212277` (N117, Geomostry3). They are listed in
`data/unavailable_textures.json` and excluded from the generated CIX manifest,
the corresponding Studio effects, and the training export. N117 was the only
one in the train split. The resulting split counts are 1,230 train, 212
validation, 211 test, 260 generalization test, and 370 review effects. The
other CIX IDs and effect definitions remain unchanged. Of the catalog's 610
distinct image IDs, 608 are covered and two are unavailable.

The other pasted Start Page 403 and 500 messages come from Roblox's built-in
discovery requests for unrelated universes. They do not identify a failure in
the local particle model or exporter.

## Frame-grid correction

The cached sheets for BlackDust1 (N052), Heart2 (N119), and Smoke15 (N186)
visibly contain 4 by 4 frames, although the manifest and train export had
marked them 8 by 8. Their source labels, generated Luau, Studio emitters, and
training rows now use `Grid4x4`. The other cached 8 by 8 exceptions inspected
in this pass retained their labels. This inspection does not prove that every
uncached CIX image has been labeled correctly.

Inference now checks the **final** selected texture after model prediction,
nearest-neighbor fallback, catalog lookup, and exact-prompt lookup. It sets
`FlipbookLayout` to the layout recorded for that texture in the training export
or CIX manifest. This prevents a texture replacement from leaving, for
example, an 8 by 8 grid on a 4 by 4 sheet. The active checkpoint's hybrid
predictions required three such repairs on the familiar test and 46 on the
held-out-base split. A repair makes the predicted texture and layout
consistent; it does not imply the predicted texture matches the reference.

## Light emission

Roblox defines `LightEmission = 1` as additive blending and `0` as normal
blending. It does not control particle transparency or light the surrounding
scene. In the saved 1,914 labeled effects before this cleanup, 1,004 had a
value of exactly 1. The others include dark smoke and shadow effects that
would become faint or change color if forced to 1. The model therefore keeps
predicting this property rather than setting a universal constant. Alpha and
`Transparency` remain separate controls.

## Retraining check

The full model was retrained after excluding N117 and correcting the three
grid labels. The candidate was selected on validation loss at epoch 236 of
240. The table reports the texture-fallback output; all 211 test and 260
generalization predictions passed schema validation. These evaluation splits
have been inspected during development, so these are descriptive comparisons,
not a new blind estimate.

| Metric | Active model | Retrained candidate |
| --- | ---: | ---: |
| Test exact texture ID, 211 effects | 82.9% | 85.3% |
| Held-out-base exact texture ID, 260 effects | 33.8% | 34.6% |
| Held-out-base burst accuracy | 92.3% | 88.5% |
| Held-out-base color MAE, 0–1 scale | 0.158 | 0.155 |

The candidate improves texture accuracy slightly but loses 3.8 percentage
points of held-out burst accuracy. The active model weights remain in use; its
training-only texture lookup bank was refreshed for the cleaned 1,230-row
split. The retrained checkpoint is retained for analysis rather than used by
the Studio plugin.
