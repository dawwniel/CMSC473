# Prompt2Particles

Prompt2Particles is a CMSC473 project that explores whether a supervised NLP model can translate natural language descriptions of visual effects into structured Roblox particle-system parameters.

For example, a prompt such as:

> "fast blue magical sparks that fade quickly"

would be converted into values such as particle speed, lifetime, emission rate, color, size, transparency, shape, and other ParticleEmitter properties.

## Project Goal

The goal of this project is to learn a direct mapping from natural language VFX descriptions to structured particle configurations instead of using a general-purpose language model to generate Roblox code.

The planned model pipeline is:

`Prompt -> Text Encoder -> Embedding -> Shared MLP -> Output Heads -> Particle Parameters`

The initial text encoder will use MiniLM / Sentence-BERT embeddings, followed by a neural network that predicts continuous and categorical particle properties.

## Dataset

Because there is no existing dataset that directly pairs natural language descriptions with Roblox ParticleEmitter configurations, we will create our own dataset.

Each example will contain:

- A natural language description
- The corresponding Roblox particle configuration
- Continuous properties such as speed, lifetime, rate, and brightness
- Categorical properties such as shape and orientation
- Sequence properties such as color, size, and transparency

The target dataset size is approximately 1,000 to 6,000 prompt/effect pairs created from 100-200 base particle effects.

## Current Development

The project is currently focused on:

- Defining the particle configuration format
- Exporting ParticleEmitter properties from Roblox
- Reconstructing ParticleEmitters from exported data
- Loading and validating particle data in Python
- Testing MiniLM sentence embeddings
- Preparing the training pipeline

## Testing the Roblox roundtrip

The JSONL fields and supported emitter properties are listed in
[`docs/particle_schema.md`](docs/particle_schema.md). Python code can read a
split with `ParticleDataset("train")` from `src.data.dataset`.
Run `python -m unittest discover -s tests -v` to validate the saved JSONL files.

`EmitCount` is stored as a `ParticleEmitter` attribute. In the JSONL file it is
`emitter.attributes.EmitCount`. Zero means continuous emission; a positive
integer is the burst count.

The tensor layout is in
[`docs/particle_schema.md`](docs/particle_schema.md#model-tensors). Set
`RUN_SLOW=1` to include the MiniLM tests.

With the dataset place open in Studio, run this from the `CMSC473` directory:

```sh
python scripts/build_roundtrip_command.py --suite both
```

Paste the generated `roblox/tests/roundtrip_command.lua` into Studio's Command
Bar. The results appear in Output. The test exports each emitter, imports it
into a temporary folder, compares its properties and attributes, and checks
that exporting it again produces the same JSONL row and hash. It also checks
which records the batch exporter includes. The test does not change the place.

Use `--limit 100` to check a smaller batch, or add `--offset 100 --limit 100`
for the next batch. Rebuild the command after changing the exporter, importer,
or tests.

## First model

`python scripts/train.py` trains a small MLP on frozen MiniLM embeddings. It
predicts burst mode, `EmitCount` or `Rate`, `Speed`, `Lifetime`, and `Brightness`.
Other emitter fields use train-only defaults. The script uses `train` for
fitting and `validation` for early stopping; it does not load `test` or
`generalization_test`. It saves a checkpoint and six validation examples under
`checkpoints/`.

After training, run `python scripts/predict.py "fast blue magical sparks"` to
write an importer-compatible record to `checkpoints/prediction.jsonl`. This is
an initial baseline; texture, color, and curve prediction are later work.
To check the six validation previews in Studio, run
`python scripts/build_prediction_check.py` and paste the generated
`checkpoints/import_check.lua` into the Command Bar. The check creates and
destroys detached emitters; it does not change the place.
Use `--input checkpoints/prediction.jsonl` to check a custom prompt instead.

To see one prediction in Studio, run `python scripts/build_prediction_preview.py`
after `predict.py`. Copy `checkpoints/preview_command.lua` into Studio's Command
Bar. It puts a temporary preview 25 studs in front of the camera, and fires
burst effects three times. Delete `Workspace.Prompt2ParticlesPreview` when
finished. The command does not modify the dataset.

Run `python scripts/evaluate.py` to score the saved checkpoint on `test` and
`generalization_test`. It writes `checkpoints/evaluation.json` and compares
the model with a constant emitter built from train statistics. MAE uses the
decoded emitter values in Roblox units. `active_mae` reports `Rate` on
continuous effects and `EmitCount` on burst effects; mode mistakes still count.

## Project Structure

```text
CMSC473/
├── data/
├── docs/
├── roblox/
├── scripts/
├── src/
├── tests/
├── requirements.txt
└── README.md
