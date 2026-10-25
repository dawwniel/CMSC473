# Particle record, version 1

The Roblox exporter writes one JSON object per `ParticleEmitter`, one object per
line. `formatVersion` is `1`. The emitter is the model target; the attachment
and prompt GUI are kept so the original Studio effect can be rebuilt.

## Record

| Field | Meaning |
| --- | --- |
| `formatVersion` | Always `1` |
| `id` | `/`-joined names in `path` |
| `path` | Folder names, then attachment name, then emitter name, relative to `Dataset` |
| `split` | `train`, `validation`, `test`, or `generalization_test` |
| `prompt` | Text paired with the emitter |
| `attachment` | Serialized parent node, including its properties and attributes |
| `emitter` | Serialized `ParticleEmitter` node |
| `prompt_gui` | Serialized prompt billboard, when present |
| `playback_mode` | `burst` when `EmitCount > 0`, otherwise `continuous` |
| `row_hash` | 16 lowercase hex digits; hash of the JSON row without this field |

The exporter also writes `family`, `feature_id`, `feature_no`, `variant_no`, and
`variant_name` when the names can be parsed. These fields describe the sample;
the importer does not use them to build the emitter.

A node has `class`, `name`, and optional `properties`, `attributes`, and
`children` fields. `properties` and `attributes` are objects keyed by Roblox
name; `children` is a list of nodes. `EmitCount` is stored at
`emitter.attributes.EmitCount`. It is a nonnegative integer: zero uses `Rate`,
and a positive value is the count passed to `ParticleEmitter:Emit()`.

## Emitter properties

All 32 properties below are required in an exported training row. `EmitCount`
is required in addition to these properties.

| Type | Properties |
| --- | --- |
| Number | `Brightness`, `Drag`, `LightEmission`, `LightInfluence`, `Rate`, `ShapePartial`, `TimeScale`, `VelocityInheritance`, `ZOffset` |
| Boolean | `Enabled`, `FlipbookStartRandom`, `LockedToPart`, `WindAffectsDrag` |
| String | `Texture` |
| `Vector3` | `Acceleration` |
| `Vector2` | `SpreadAngle` |
| `NumberRange` | `FlipbookFramerate`, `Lifetime`, `Rotation`, `RotSpeed`, `Speed` |
| `NumberSequence` | `Size`, `Squash`, `Transparency` |
| `ColorSequence` | `Color` |
| Enum | `EmissionDirection` (`NormalId`), `FlipbookLayout` (`ParticleFlipbookLayout`), `FlipbookMode` (`ParticleFlipbookMode`), `Orientation` (`ParticleOrientation`), `Shape` (`ParticleEmitterShape`), `ShapeInOut` (`ParticleEmitterShapeInOut`), `ShapeStyle` (`ParticleEmitterShapeStyle`) |

Roblox values use tagged JSON objects. The same tags are used in the Lua
exporter, Lua importer, and Python validator:

```json
{"_type":"NumberRange","value":[0.5,1.0]}
{"_type":"Vector3","value":[0,2,0]}
{"_type":"Enum","enum":"ParticleEmitterShape","value":"Sphere"}
{"_type":"NumberSequence","keypoints":[[0,0,0],[1,1,0]]}
{"_type":"ColorSequence","keypoints":[[0,1,0,0],[1,0,0,1]]}
```

`NumberSequence` points are `[time, value, envelope]`.
`ColorSequence` points are `[time, red, green, blue]`, with channels from 0 to
1. Point times run from 0 to 1 and may repeat at the same time, as they do in
some exported Roblox sequences. Other tags used for attachment and GUI data
are `Color3`, `UDim`, `UDim2`, `Rect`, `CFrame`, `Font`, `BrickColor`, `Content`,
and `JSONString` (for JSON stored in a string attribute).

The saved curves keep their original keypoints rather than resampling them.
Values are stored to the exporter's six-decimal precision. A fixed number of
curve samples for a model head can be derived later; it is not part of the
version 1 JSONL record.

The exporter sorts object keys and rounds numbers to six decimal places before
writing JSONL. It calculates `row_hash` over that row without `row_hash` using
its two-lane 32-bit hash in `roblox/exporter.lua`. The Python loader verifies
the hash against the line it reads.

In Luau, `Importer.deserialize(record)` returns a detached attachment with the
emitter and prompt GUI. `Importer.deserializeEmitter(record)` returns only a
detached `ParticleEmitter`. Both use the values in the record; neither changes
the open place.

## Python loader

```python
from src.data.dataset import ParticleDataset

train = ParticleDataset("train")
sample = train[0]
prompt = sample["prompt"]
properties = sample["emitter"]["properties"]
emit_count = sample["emitter"]["attributes"]["EmitCount"]
```

The loader checks the schema, split label, duplicate IDs, and row hash. It
reports the file and line for a bad row. It does not mix splits or calculate
normalization statistics; those must be fitted on `train` only.

The saved files currently have 987 train, 212 validation, 211 test, and 260
generalization test rows. The last split holds out 26 complete base effects.
The loader reads these assignments as written and never reshuffles them.

## Model tensors

`python scripts/prepare_data.py` fits a `Normalizer` on `train`, saves it to
`data/processed/normalizer.json`, and caches MiniLM prompt embeddings in
`data/processed/embeddings/<split>.pt`. Validation, test, and
generalization test rows are only transformed with the saved train
statistics. The embedding caches are rebuilt when the model name or a split's
prompts change.

`ParticleTensorDataset` returns one item per prompt. Train uses the main
prompt and both `PromptAlternates` (2,961 items); the other splits use only
the main prompt, so each effect is scored once. Each item has:

| Key | Shape | Type | Meaning |
| --- | --- | --- | --- |
| `embedding` | 384 | float32 | Unit-length `all-MiniLM-L6-v2` prompt embedding |
| `continuous` | 96 | float32 | Train-standardized values, in `Normalizer.continuous` order |
| `continuous_mask` | 96 | float32 | 0 for a column that doesn't apply; its value is then 0 |
| `categories` | 8 | int64 | Class index per field, in `Normalizer.categories` order; 0 is `<UNK>` |
| `flags` | 3 | float32 | `FlipbookStartRandom`, `LockedToPart`, `Burst` |

Continuous columns are the numbers, both ends of each `NumberRange`, vector
axes, and each curve resampled at 8 even times (`Size`, `Squash`, and
`Transparency` value and envelope; `Color` red, green, and blue). Skewed
values use `log1p`, or a signed `log1p` when they can be negative, before
standardizing. `Rate` is masked for burst emitters and `EmitCount` for
continuous ones. Fields with one value in train, such as `Enabled`, are
stored as constants and aren't model targets.

The category heads are `EmissionDirection`, `FlipbookLayout`, `FlipbookMode`,
`Orientation`, `Shape`, `ShapeInOut`, `ShapeStyle`, and `Texture`. A label not
seen in train maps to `<UNK>` and decodes to the most common train value; the
generalization test has 10 such textures. `Normalizer.inverse_transform`
turns a prediction back into an emitter that `validate_emitter` accepts.

A few columns are almost always zero in train, such as `Acceleration.x` and
`Transparency.envelope.0`, so their rare non-zero values standardize to about
|z| = 12. The targets are left unclipped so they decode exactly; training
should use a masked Huber (SmoothL1) loss rather than plain MSE so these
columns don't dominate.
