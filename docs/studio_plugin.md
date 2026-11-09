# Studio prompt panel

The plugin sends one prompt to a Python server on your own computer. The server
loads `checkpoints/particle_full.pt` once and returns an importer record. For
uncertain texture predictions, it takes the texture from the closest training
prompt while keeping the model's other settings.
An exact match to an unambiguous training prompt uses that prompt's saved
texture. New wording still goes through the model and nearest-neighbor lookup.
For CIX textures with reviewed descriptions, the server also checks the CIX
catalog. It uses a catalog texture only when that description matches the
prompt more closely than any training prompt and clears a minimum similarity.
The [CIX holdout check](cix_texture_holdout.md) reports the measured result.
The plugin uses `ServerStorage.Prompt2Particles.Importer` to build the emitter and
places it in `Workspace.Prompt2ParticlesGenerated`, away from the dataset.

## One-time setup

1. Open the particle place in Studio. In Explorer, confirm that
   `ServerStorage > Prompt2Particles` contains `Importer` and `StudioPlugin`.
2. Select `StudioPlugin`. In Studio's **Plugins** tab, choose **Save as Local
   Plugin** and save it as `Prompt2Particles`. The source Script stays in
   ServerStorage so the project retains a copy. It does not run during play.
3. Start the local server by double-clicking `scripts/run_server.cmd`, or from
   the `CMSC473` directory run:

   ```powershell
   .\.venv\Scripts\python.exe scripts\serve_full.py
   ```

   Leave that window open while using the plugin. It should print
   `Prompt2Particles ready at http://127.0.0.1:8765`.
   Restart the server after changing the training JSONL file or checkpoint.

## Use

Click **Prompt2Particles** in Studio's Plugins toolbar, type a description,
and click **Create emitter**. A transparent anchor containing the predicted
emitter and prompt billboard appears on the clear back area of the Baseplate.
The plugin selects it and moves the Studio camera to it. **Focus** returns to
the latest effect. **Emit** plays its `EmitCount` burst again; for a continuous
effect, it emits about one second of particles as a quick preview. Its saved
`Rate` stays the same. Each click makes one new anchor in
`Workspace.Prompt2ParticlesGenerated`.

Enter reviewer initials before using **Next test**. Each reviewer gets their
own cycle through the 40 prompts in `data/visual_eval_prompts.json`. After
looking at a generated effect, click **Fits**, **Usable**, **Wrong**, or **Skip**
to rate its texture. The local server writes the prompt, prediction, reviewer,
model version, and rating to `checkpoints/visual_feedback.jsonl`. These ratings
do not retrain the model automatically. The scoring rubric and command are in
[`texture_evaluation.md`](texture_evaluation.md). Save the place if you want to
keep generated effects.

The first HTTP request might ask you to allow this plugin to contact
`127.0.0.1`. If Studio says HTTP requests are disabled, enable **Allow HTTP
Requests** in Experience Settings > Security. The server listens only on
`127.0.0.1`; it does not publish an internet endpoint. [Roblox's HTTP
documentation](https://create.roblox.com/docs/cloud-services/http-service)
describes localhost plugin requests and the permission prompt.

If you edit `roblox/studio_plugin.lua`, copy it into the `StudioPlugin` Script,
save the place, then use **Save as Local Plugin** again and reload the plugin. Editing the
place's Script does not update an already installed local plugin. If you edit `roblox/importer.lua`, update the
`Importer` ModuleScript in the place and reopen the place or reload the plugin.
The plugin source is kept in `roblox/studio_plugin.lua`; the Python endpoint is
in `scripts/serve_full.py`.
