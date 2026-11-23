# Explicit prompt colors

The previous full checkpoint predicted an orange Color sequence for “Create
dense green flame embers that rise upward and fade quickly.” Its chosen texture
is a mostly white flipbook, so the wrong hue came from Color, not the texture.

`src/models/color.py` reads one unambiguous color word from the prompt. The
frozen MiniLM still produces the same 384-value embedding. The new
`ParticleFullColor` checkpoint retains the old backbone and every non-color
head. A small color head receives the 128-value hidden vector plus the
four-value RGB/presence cue. It learns brightness through the particle's life.
The requested hue is applied when the original Color output conflicts with
the prompt. An already matching shade stays unchanged. A final check after
decoding catches any remaining mismatch before texture/layout alignment and
schema validation.

`scripts/train_full_color.py` trains this head on 1,894 existing color-explicit
training prompts and 1,206 color-swapped prompts from effects with nearly
grayscale textures. The other model weights are frozen. The checkpoint is
`checkpoints/particle_full_color.pt`. Run the training script after generating
`particle_full.pt`; checkpoints are ignored by Git.

`scripts/evaluate_color_control.py` compares the prior and new checkpoints on
the same prompts. RGB MAE uses Color channels on a 0–1 scale. These are
color-explicit prompts only, and the other heads were identical for each
prompt in the comparison.

| Split | Prompts | Prior RGB MAE | Color model RGB MAE |
| --- | ---: | ---: | ---: |
| validation | 131 | 0.0465 | 0.0453 |
| test | 122 | 0.0534 | 0.0523 |
| generalization_test | 165 | 0.1062 | 0.1041 |

The three controlled versions of the flame prompt—red, green, and blue—now
produce the requested hue with the same texture. The [green Studio preview](figures/green_flame_embers_fixed_studio.jpg),
[old orange preview](figures/green_flame_embers_before_color_studio.jpg), and
[updated transparent diagram](figures/model_flow_transparent.svg) are kept with
this document. The complete intermediate values are in the local
`presentation/green_flame_embers_trace.json` file.

This change addresses a stated single color. Prompts naming several colors
remain with the full model's output. A texture with color baked into its image
may still alter the final appearance, and the present fix does not improve
motion, density, or texture selection.
