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
