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

## Project Structure

```text
CMSC473/
├── data/
├── roblox/
├── scripts/
├── src/
├── tests/
├── requirements.txt
└── README.md