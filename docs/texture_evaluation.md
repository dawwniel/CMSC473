# Texture evaluation

Exact asset-ID accuracy remains the automatic benchmark. It is 82.9% on the
211 familiar-base test effects and 33.8% on the 260 held-out-base effects for
the current plugin. A different image may still be suitable for the same
prompt, so the Studio review measures that separately. Do not call the visual
score exact-ID accuracy.

## Blind visual-fit review

The 40 prompts in `data/visual_eval_prompts.json` are fixed before rating.
Each reviewer sees the prompt and the generated effect in Studio, but no
expected texture ID. Use different reviewer initials, such as `A` and `B`.
Do not show one reviewer the other's ratings until both finish.

1. Restart the Python server from `CMSC473` with
   `.\.venv\Scripts\python.exe scripts\serve_full.py`.
2. Reload the saved local Studio plugin after updating it from
   `roblox/studio_plugin.lua`. Enter reviewer initials in its panel.
3. Click **Next test**, then **Create emitter**. Use **Focus** or **Emit** to
   inspect it. Judge the texture's visible shape, pattern, color, and material
   against the prompt. Judge motion separately; this rating is for texture.
4. Click exactly one texture rating:
   - **Fits:** the texture clearly depicts what the prompt asks for.
   - **Usable:** it is a different but reasonable texture for that prompt.
   - **Wrong:** the texture depicts the wrong kind of thing or has a visibly
     unsuitable pattern or color.
   - **Skip:** Studio did not show enough to judge. Skips remain in the score's
     denominator.
5. Repeat until all 40 prompts are rated. The server keeps a separate prompt
   cursor for each reviewer. Keep it running during a review session.

Run `.\.venv\Scripts\python.exe scripts\score_visual_feedback.py` afterward.
It reads `checkpoints/visual_feedback.jsonl`. The **strict fit** score counts
only Fits; **acceptable** counts Fits and Usable. Both divide by all 40
scheduled prompts, including skipped or unanswered ones. If two people rate,
the report also shows the fraction both accepted. An 80% visual-acceptability
result means at least 32 of 40 prompts accepted under the stated rule. Report
the reviewer counts and exact-ID results alongside it. If a prompt is rated
twice, the first rating counts and the duplicate is reported. The script
rejects mixed model versions.

The current 40 prompts are a usability pilot. They do not replace a new blind
whole-effect test because they were prepared during development.

## New whole-effect check

The 24 IDs in `data/cix_new_holdout_ids.json` were selected before their images
were described. They remain in Studio's `review` split and outside model
training. Their image descriptions are now frozen in
`data/cix_new_holdout_catalog.json` so the catalog can select those assets.
This measures retrieval from an available image catalog, not the classifier's
ability to invent an unseen Roblox asset ID.

A person who has **not read the catalog descriptions or seen model predictions**
should view each of the 24 effects in Studio and write one new prompt about its
visible appearance. The `CIXBlindPromptReview` module focuses each target and
hides its saved prompt billboard. Run this in Studio's Command Bar once per
effect; it prints the ID to fill in the template:

```lua
local id = require(game.ServerStorage.Prompt2Particles.CIXBlindPromptReview).next()
print(id)
```

Copy `data/cix_new_holdout_prompts.template.json` to
`data/cix_new_holdout_prompts.json` and replace each empty string with that
person's prompt. The module restores the prior billboard on each step. After
the last effect, run
`require(game.ServerStorage.Prompt2Particles.CIXBlindPromptReview).reset()`
to restore the current one. Then run
`.\.venv\Scripts\python.exe scripts\evaluate_new_cix_holdout.py`. It
checks all 24 IDs, confirms none entered training, and reports catalog top-one,
top-three, and the plugin's gated catalog choice. The queries must be written
before this score is run. Do not tune the selection threshold on those 24
results and then report the same set as blind.
