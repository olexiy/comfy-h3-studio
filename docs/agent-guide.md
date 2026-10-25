# AGENT GUIDE — home ComfyUI studio (Krea 2 · Qwen-Image-Edit · MiniMax H3 · LTX-2.5) + RunPod

```yaml
doc: agent-guide
audience: autonomous coding/ops agents driving ComfyUI and cloud GPUs (not humans)
version: 2026-10-25
evidence_tags: {MEASURED: "run by us, numbers from our logs", SOURCE: "official template / docs / community, not re-measured", RULE: "derived decision rule"}
baseline_box: {gpu: "RTX 5070 Ti 16 GB (Blackwell)", ram: "62 GB", os: "Windows 11", comfyui: "0.42.x", torch: "2.12+cu130", python: "3.13"}
cloud_box: {provider: RunPod, gpu: "RTX PRO 6000 Blackwell Server Edition 96 GB", price_usd_h: 2.49, cloud: SECURE, region: IE}
content_policy: "all examples SFW, depicted adults stated 25+"
```

## 0. How to use this file
- Sections are independent; each bullet = one fact or rule. Prefer MEASURED over SOURCE when they conflict.
- File names below are exact (copy them). Node names are ComfyUI class_type names.
- Numbers are for the baseline box unless a section says `cloud_box`.

## 1. Driving ComfyUI headless (API)
- Run a second headless instance next to the desktop app: `main.py --listen 127.0.0.1 --port 8189 --extra-model-paths-config <yaml> --input-directory <dir> --output-directory <dir> --disable-auto-launch --reserve-vram 1.5`. Never run two H3 jobs on two instances at once — free RAM falls to ~3 GB and both runs double in time. [MEASURED] Check `GET :8188/queue` before queueing.
- API cycle: `POST /prompt {"prompt": api_graph, "client_id": id}` → poll `GET /history/<prompt_id>` → outputs; `GET /object_info` for node specs; `POST /free {"unload_models":true,"free_memory":true}` to release VRAM.
- **Cache object_info but refetch when a class is missing** — after installing a custom node the cache lacks it (our symptom: `TypeError: 'NoneType' object is not iterable` while building the graph). [MEASURED]
- **Validation walks every input of every reachable node, including the switched-off side of `ComfySwitchNode`.** A graph with an off branch that references a missing custom node or model file is rejected on a bare install. Fix before submitting: drop `on_true`/`on_false` of the dead side, then drop nodes unreachable from the output node. [MEASURED]
- `ComfySwitchNode` is lazy at execution: the off branch never runs (use it for optional passes: upscale, 48 fps, sound). An unconnected `on_false` returns None → `CreateVideo` writes no audio track. [MEASURED]
- ComfyUI caches node outputs: re-running a graph where only a downstream widget changed re-executes only that tail (H3 clip re-cut with `Video Slice`: 3.3 s instead of 6 min). Exploit it for post knobs. [MEASURED]
- UI-json → API conversion pitfalls: subgraphs must be expanded; some widget lists shift (LTX `LTXVEmptyLatentAudio` batch_size became 25 → tensor mismatch; force 1). Verify a built workflow with the real frontend: load page, `app.loadGraphData(wf)` → `app.graphToPrompt()` (no execution). [MEASURED]
- `extra_model_paths.yaml` must list every folder a template uses: diffusion_models, text_encoders, vae, loras, upscale_models, latent_upscale_models, clip_vision, model_patches, controlnet, audio_encoders, style_models, frame_interpolation, ultralytics. [MEASURED]
- User-facing workflow style that a human liked: main canvas = note + Load Image + ONE subgraph node exposing only the knobs (prompt, size MP, frames, seed, shift, toggles) + Save; optional parts = BOOLEAN toggles on lazy switches; build workflows by script, never hand-edit JSON. [RULE]

## 2. Model recipes (exact settings)
```yaml
krea2_turbo:            # photoreal default, best prompt fidelity + physics (hands really use tools)
  files: {unet: krea2_turbo_int8_convrot.safetensors, clip: qwen3vl_4b_fp8_scaled.safetensors (type krea2), vae: qwen_image_vae.safetensors}
  sampler: {steps: 8, sampler: euler, scheduler: beta, cfg: 1.0}   # cfg 0 in Krea's own tools == cfg 1 on KSampler
  size: "2 MP native (1280x1600); 1 MP loses pore/freckle detail"  # MEASURED
  speed: "≈ 14 s at 2 MP, ≈ 6 s at 1 MP (5070 Ti)"
  prompt: "30-80 words prose; subject → setting → camera → light → texture; no (word:1.3) weights; negatives useless at cfg 1"
  quirks: ["seed diversity ≈ 0 for one prompt → iterate the prompt, not seeds", "realism LoRAs make faces 5-10 y younger"]
  realism_loras: {realism_engine_krea2_v3.1: 0.5, RealisticSnapshotKrea2V2: 0.9}   # 0.7+ = glossy 'AI face'
krea2_raw: {use: "LoRA training base, variety", sampler: "≈ 30-50 steps, cfg 3.5-4"}   # SOURCE
qwen_image_edit_2511:   # edit / restage a person into new scenes, turnarounds
  files: {unet: qwen_image_edit_2511_int8_convrot.safetensors, clip: qwen_2.5_vl_7b_fp8_scaled.safetensors (type qwen_image), vae: qwen_image_vae.safetensors}
  chain: "LoadImage → FluxKontextImageScale → TextEncodeQwenImageEditPlus(pos & empty neg, image1) → FluxKontextMultiReferenceLatentMethod(index_timestep_zero) → ModelSamplingAuraFlow(3.1) → CFGNorm(1.0) → KSampler"
  sampler: {steps: 40, cfg: 4.0, sampler: euler, scheduler: simple}
  speed: "≈ 110 s per 1 MP edit (16 GB, int8)"
  quirks: ["obeys scene/outfit/light/expression strongly", "ages faces (forehead/eye wrinkles) on strong expressions", "misplaces small marks", "framing words weak ('close-up' ignored)"]
  angles_lora: {file: qwen-image-edit-2511-multiple-angles-lora.safetensors, prompt: "<sks> front-left quarter view eye-level shot medium shot"}   # 'close-up' → macro crop
krea2_identity_edit_v2:  # BEST persona restaging engine (needs custom node comfyui-krea2edit >= 2.0)
  files: {lora: krea2_identity_edit_v2_r128.safetensors on krea2_turbo, clip: qwen3vl_4b (type krea2), vae: qwen_image_vae}
  nodes: "Krea2EditModelPatch(model, source_latent=VAEEncode(img), vae, source_image, target_latent=EmptySD3LatentImage, ref_boost, fit_mode=fit, ref_position) + 2x Krea2EditGroundedEncode(clip, prompt, image) as pos/neg (neg prompt '')"
  sampler: {steps: 10, cfg: 1.0, sampler: euler, scheduler: simple, size: "1024x1280 (≤ 2 MP)"}
  best: {ref_position: "aligned (trained)", ref_boost: 2}     # MEASURED; boost 4 ≈ copies the reference
  speed: "≈ 28 s"
  person_into_scene: "first ref = scene image (source_latent/image, ref_position_a aligned), second ref = person (source_latent_b/image_b, ref_position beside); prompt 'Replace the woman in the first image with the woman from the second image. Keep pose, framing, outfit, background and light of the first image'"
  licence: non-commercial
minimax_h3:              # #1 open image→video with audio
  files: {unet: minimax_h3_fl2va_pruned_int8_convrot.safetensors (21 GB), clip: qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors (type minimax), vae_video: minimax_h3_video_vae_fp16, vae_audio: minimax_h3_audio_vae_fp32}
  quality_recipe: {turbo_lora: 0, steps: 30, sampler: res_multistep, scheduler: simple, shift_video: 12, shift_audio: 3, size: "0.70 MP no-crop (768x960)", fps: 24}   # MEASURED best hands/fabric
  speed: "5 s ≈ 300-360 s, 9 s ≈ 12.5 min with SageAttention (MiniMaxH3MemoryEfficientSageAttentionPatch, ×2)"
  limits: {frames: "17k+5 (124=5 s, 226=9 s, 294=12 s)", local_max: "≈ 12 s (RAM ≤ 59 GB); longer → chain 5-8 s hops with MiniMaxH3AddGuide (22 anchor frames + audio)", native_cap: "≈ 1 MP"}
  ram: "5 s ≈ 27 GB over background; 9 s peaks 60-62 GB — RAM, not VRAM, is the ceiling (32B text encoder)"
  precision_test: "fl2va_bf16 unpruned (66 GB) + TE bf16 (51.5 GB) vs pruned_int8 + TE nvfp4, same seed, cloud_box, no Sage: calm 5 s pixel diff 2-5/255, hard 9 s (fast hands, phone, passing bus) same beats and fingers → quantised weights are NOT the quality ceiling; don't pay for full precision"   # MEASURED
  above_native: "1.31 MP (1088x1280) = 2.2x time, no extra detail, more identity wander → stay ≈ 1 MP; get detail from a post upscaler"   # MEASURED
  cloud_box_speed: "no Sage: 5 s ≈ 225 s (int8) / 280 s (bf16); 9 s ≈ 493 s / 595 s"
ltx_2_5:                 # fast video path
  speed: "9 s 1024x1280 in ≈ 3 min with H3-level sharpness (H3 12.5 min); weaker identity on head turns"
  prompt: "timed lines, one action per 2-3 s, state hand + object in every line, explicit object count; keep appearance/background lock lines"   # MEASURED beats the docs' 'one flowing paragraph'
others:
  z_image_turbo: "8 steps cfg 1 shift 3 res_multistep; wants 100-180-word paragraphs; seeds look alike"
  qwen_image_2_1_turbo: "fastest (3-4 s/MP), stock look, drops small details"
  flux3_klein: "rawest phone-photo realism, faces older; up to 10 reference images"
  moss_image: "cfg 3, 25 steps; airy illustration, high seed diversity, weak physics (people pose, tools touch nothing)"
  anima: "anime/2.5D; er_sde, never DPM/Karras, cfg 4-5"
  sdxl_juggernaut: "77-token CLIP limit → short tag prompts; glossy beauty look"
  wan_2_2_i2v_a14b: "75 min per 9 s at 768x960 on 16 GB, no audio, loose shot list → not worth it on this class of box"
```

## 3. Prompting rules (tested)
- Character consistency: split every prompt into an **identity layer** (age, face, hair, skin, permanent marks; short, verbatim every time) and a **shot layer** (outfit, pose, action, gaze, place, light, camera; rewritten fully — prompts are stateless, never "still/again/same"). [SOURCE + MEASURED]
- Age: anchor with structure words ("adult woman in her late twenties, defined cheekbones, mature composed look") not "youthful"; "no retouching" / "fine lines" + 45° side light = deep asymmetric mouth folds (+10 years). [MEASURED]
- Small permanent marks (mole, scar) appear on Krea only with realism LoRAs; the model mirrors the requested side — accept the rendered side as canon and describe it consistently afterwards. [MEASURED]
- Turnarounds with edit models: "rotate left/right" turns the head toward the marks both times. For the far side say: "her face points toward the right edge of the image; we see her right cheek and ear; her left cheek with the mole is turned away and not visible". [MEASURED]
- Restage prompts that keep identity best: medium/close framing, face toward the camera, closed-lip expression → 18/20 frames with ArcFace ≥ 0.53. [MEASURED]
- H3 shot-list template (works):
```text
[Shot 1] <Picture 1> is the first frame. Whole clip is 5 seconds. Live-action. <who, age, where — as framed in <Picture 1>>.
Appearance lock: <identity layer words>. Keep face, marks, outfit and proportions exactly as in <Picture 1>.
Background lock: the background of <Picture 1> stays still apart from natural light flicker.
Lighting lock: exposure, white balance and light exactly as in <Picture 1>.
[Shot 2] 0s-2s: <one action>. [Shot 3] 2s-4s: <one action, hands named>. [Shot 4] 4s-5s: <calm hold>.
camera: locked-off tripod, static, no zoom, no cuts.
overall_soundscape: <diegetic sounds>.   non_diegetic_music: None.
negative: morphing face, identity drift, wide toothy grin, extra fingers, warped hands, flicker, text, subtitles, watermark, music.
```
- H3: no mood words (warm, dim, cosy) anywhere incl. the music line → colour drift; hand-body contact mid-clip, calm hold at the end (finger melt happens in the last second); "smiles softly with closed lips" avoids big teeth. [MEASURED]

## 4. First frame for image→video (H3)
- Never crop the still: `ImageScaleToTotalPixels(lanczos, megapixels 0.70, resolution_steps 32)` → `GetImageSize` → H3 width/height. Cropping/resizing mismatch made H3 repaint the background in the first second. [MEASURED]
- Drop output frame 0 (`ImageFromBatch` batch_index 1) — it is the input still and pops. [MEASURED]
- Frame 0 must show the face frontal or ≤ 3/4 with every mark visible; starting turned away → H3 invents the hidden side (ArcFace 0.38 vs 0.59-0.69). Background lock must describe exactly what the still shows. Hands near the face are fine if fully in frame. [MEASURED]
- Start "pop": face sharpness falls 135 → 56 in the first 0.5 s before any motion. Remedy: shot-list beat `0s-0.5s: holds completely still, settling` + core `Video Slice(start_time 0.5)` (cuts frames and audio). [MEASURED]
- Light drift (darker/warmer over 3 s): KJNodes `ColorMatch(mkl)` of every frame to the scaled first frame; turn OFF when a big new object enters (bus) — it greys skin. [MEASURED]

## 5. Persona pipeline (one fictional face → LoRA)
1. Hero still: Krea 2 Turbo 2 MP + realism LoRAs + identity layer, frontal butterfly light. Reverse-image check that it is not a real person (human step).
2. Restage 50-80 SFW scenes: **Krea Identity Edit V2 aligned b2** for frontal / 3/4 / medium; Qwen-Edit for strong expressions, profiles, high angles; full-body = Qwen full-body scene + Identity Edit person-into-scene (Krea aligned alone never gives full body — layout is pinned to the reference). [MEASURED]
3. Curate: ArcFace ≥ 0.5 vs hero + eye check of mark side on a face-crop sheet (edit engines flip the side in some frames). Dataset norms: 40-60 images, ~35/35/30 % close/medium/full, outfits ≤ 15 % each, rooms ≤ 10 %. [SOURCE + MEASURED]
4. Captions: `<trigger>, a woman. <scene text>` — trigger first, prose (LLM text encoder), never describe face/marks/hair colour. [SOURCE]
5. Train (ai-toolkit, Krea 2 Raw) — config below; evaluate on **Turbo** (the real inference), not on training samples.
6. Expect: identity first (copper hair/freckles ≈ step 1000 at lr 1e-4), small marks last (only at the final 2500 steps).
7. **Leak check is mandatory**: include a no-trigger prompt of a different woman. Without countermeasures the marks and eye colour leaked into every "woman" (they attached to the class word — every caption said "a woman"). A regularisation set (`is_reg: true`) cut the leak 0.48 → 0.24 **but ai-toolkit alternates steps with it** (`batch_step % 2 == 0` → reg batch, BaseSDTrainProcess ≈ l. 2578, commit ea3afb4): the subject got only half of the 2500 steps and the small marks never formed. Use **Differential Output Preservation** instead (train: `diff_output_preservation: true`, `diff_output_preservation_class: woman`, `diff_output_preservation_multiplier: 1.0`, process-level `trigger_word` required, no `train_text_encoder`; works with `cache_text_embeddings: true`), no reg folder — what creators do. [MEASURED code + SOURCE]
- Unknown-word triggers can be rendered as text (book cover printed "mrnholt") — the LLM text encoder reads them as words. [MEASURED]
- No generative finishing on persona images: whole-frame img2img 0.12-0.3 and FaceDetailer 0.3-0.45 wipe the mole/scar every time; with realism LoRAs FaceDetailer even made the face teen-looking. Realism must come from the generator; finishing = pixel-only (grain/grade/CA). [MEASURED]

```yaml
# ai-toolkit (ostris) Krea 2 character LoRA — run 1 settings (worked; for the leak use DOP, not the reg dataset line below — see step 7)
job: extension
config:
  name: persona_krea2
  process:
    - type: sd_trainer
      training_folder: /workspace/output
      device: cuda:0
      network: {type: lora, linear: 32, linear_alpha: 32}
      save: {dtype: bf16, save_every: 250, max_step_saves_to_keep: 10}
      datasets:
        - {folder_path: /workspace/data/persona, caption_ext: txt, caption_dropout_rate: 0.05, shuffle_tokens: false, cache_latents_to_disk: true, resolution: [512, 1024]}   # no 768: Krea 2 not pretrained on it
        - {folder_path: /workspace/data/reg, caption_ext: txt, is_reg: true, caption_dropout_rate: 0.05, cache_latents_to_disk: true, resolution: [512, 1024]}
      train: {batch_size: 1, cache_text_embeddings: true, steps: 2500, gradient_accumulation: 1, train_unet: true, train_text_encoder: false, gradient_checkpointing: true, noise_scheduler: flowmatch, optimizer: adamw8bit, lr: 1e-4, reg_weight: 1.0, dtype: bf16}
      model: {name_or_path: /workspace/models/krea2_raw_bf16.safetensors, arch: krea2, quantize: false}   # 96 GB card; on 24-32 GB: quantize: true, qtype: qfloat8
      sample: {sampler: flowmatch, sample_every: 250, width: 1024, height: 1280, guidance_scale: 4, sample_steps: 30, seed: 42, prompts: ["<trigger>, a woman. Close-up portrait ...", "A woman with dark curly hair ... (leak check, no trigger)"]}
```
- Weights without an HF token: `Comfy-Org/Krea-2` → `diffusion_models/krea2_raw_bf16.safetensors` (26.3 GB, not gated; its 430 keys match ai-toolkit's SingleStreamDiT exactly). `krea/Krea-2-Raw` is gated. Text encoder `Qwen/Qwen3-VL-4B-Instruct` and VAE `Qwen/Qwen-Image` download automatically. [MEASURED]
- Speed `cloud_box`: ≈ 0.8 s/step at 512, ≈ 2.4 s/step at 1024, ≈ 55 min per 2500 steps + ≈ 2.7 min per sample round (5 images); VRAM 31.6 GB. ai-toolkit Krea 2 LoRAs load in ComfyUI `LoraLoaderModelOnly` unchanged. [MEASURED]
- Inference: Turbo, strength 0.8 (1.0-1.2 raises identity but also the leak). [MEASURED]

## 6. Evaluation harness (what metrics mean)
- Identity: insightface buffalo_l ArcFace cosine of the largest face vs the reference. ≥ 0.6 ≈ same person; 0.5-0.6 usable; < 0.3 different. Blind to profiles (≈ 0) and fooled by animal faces (picked a dog). Faces < 100 px are unreliable. [MEASURED]
- Taste: LAION aesthetic v2 reproduced a human's per-image ranking; sharpness (Laplacian) and CLIP prompt-adherence did not. Physics/hand-object interaction is invisible to all metrics → eye check. [MEASURED]
- Video: per-frame Laplacian of the face box for start pops / mid-clip blur; corner diff for background repaint; luma mean for colour drift. [MEASURED]
- Show humans: stacked full-res crop sheets (same regions, same moments per variant) + side-by-side mp4; blind A/B with a shuffled-letter key for subjective choices. [RULE]
- Judge speed tricks on a HARD scene (≥ 9 s, fast hands, held object, passing vehicle): a broken turbo recipe ranked first on a calm 5 s clip by metrics. [MEASURED]

## 7. RunPod procedure (runpodctl 2.x)
```bash
runpodctl gpu list                       # ids, VRAM, stock level (no prices)
runpodctl template search "ai toolkit"   # official ostris template id 0fqzfjy6f3, image ostris/aitoolkit:latest (ai-toolkit + torch 2.13 cu130)
runpodctl pod create --template-id 0fqzfjy6f3 --gpu-id "NVIDIA RTX PRO 6000 Blackwell Server Edition" \
  --cloud-type SECURE --container-disk-in-gb 150 --volume-in-gb 0 --ports "22/tcp" \
  --env '{"AI_TOOLKIT_AUTH":"<random>"}' --name <name> --terminate-after <UTC ISO time>
runpodctl ssh info <pod_id>              # ip, port, key path
runpodctl pod list ; runpodctl pod delete <pod_id> ; runpodctl me   # verify nothing bills; balance
```
- Security: the ostris template exposes UI port 8675 with password `password` by default → expose only `22/tcp` and set `AI_TOOLKIT_AUTH`. Always set `--terminate-after` as a safety net. [MEASURED]
- Community cloud often has no stock for big cards ("no longer any instances available") → fall back to SECURE. [MEASURED]
- SSH: use the key `runpodctl doctor` created (`~/.runpod/ssh/runpodctl-ssh-key`); a separately registered ed25519 key was refused. [MEASURED]
- `/workspace` may not exist when `--volume-in-gb 0` → `mkdir -p` first. [MEASURED]
- In-datacenter HF downloads are extremely fast: 26 GB in < 1 min, 135 GB in a few minutes (`hf download`, Xet). `HF_HUB_ENABLE_HF_TRANSFER` is deprecated → `HF_XET_HIGH_PERFORMANCE=1`. Pass globs with `--include`. [MEASURED]
- System Python is PEP 668-locked: use a venv for tools (insightface 2.1 installs from wheels), or `pip install --break-system-packages` only inside the throw-away container (ComfyUI requirements did not disturb ai-toolkit's torch). [MEASURED]
- ComfyUI on a pod in 2 min: `git clone ComfyUI; pip install --break-system-packages -r requirements.txt; hf download Comfy-Org/<model repo> <files> --local-dir /workspace/hfc; ln -s` into `models/*`; run on 127.0.0.1:8188; drive it from the local machine through `ssh -N -L 8190:127.0.0.1:8188 -p <port> root@<ip>` with the same API scripts. Training and a ComfyUI can share one 96 GB card. [MEASURED]
- Background jobs over ssh: `setsid nohup cmd < /dev/null > log 2>&1 &` (plain `nohup … &` keeps the ssh session open). A Windows-made tar extracts with "Cannot change ownership" (exit 1) → `--no-same-owner`, don't chain with `&&`. [MEASURED]
- Cost reference: LoRA run (setup + 2500 steps + eval) ≈ 1.7 h ≈ $4.2 on PRO 6000 SECURE. [MEASURED]
- Decision rule: if a local job takes hours and the cloud does it for a few dollars, use the cloud — especially for daytime experiments a human is waiting on; overnight batches can stay local. "Local hardware can't do better" may only be claimed after the same input was rendered on full-precision weights in the cloud. [RULE]

## 7b. Replicating a Civitai post (trend loop)
- Metadata without login: `GET https://civitai.com/api/v1/images?imageId=<id>&withMeta=true&nsfw=X` → `meta` (may be nested once more as `meta.meta`): prompt, negativePrompt, sampler, scheduler, steps, cfgScale, seed, `civitaiResources` [{modelVersionId, weight, type}], sometimes the full ComfyUI API graph as a JSON string in `meta.comfy`. Resolve each version: `GET /api/v1/model-versions/<id>` → trainedWords (triggers), files[].downloadUrl, sizeKB, baseModel. [MEASURED]
- `/api/trpc/image.getGenerationData` returns 401 without a browser login (worked logged-in on 2026-10-24). [MEASURED]
- Downloads: `GET /api/download/models/<versionId>` answers 307 → file (anonymous) or 307 → `/login?reason=download-auth` (creator requires an account — most style LoRAs and finetunes). Use an API key (`Authorization: Bearer <key>`) or the human's browser. HEAD the URL first; following the redirect blindly saves a login page as the "model". [MEASURED]
- Posts made in ComfyUI list LoRAs by file name only (`meta.additionalResources`); find the version with `GET /api/v1/models?query=<name>`; some (private/renamed) cannot be found. [MEASURED]
- The `prompt` field is one text node; trace `ComfySwitchNode`/`StringConcatenate` inputs in `meta.comfy` to get the effective conditioning text (hidden style suffixes, LLM prompt expanders that may be on or off). [MEASURED]
- Posts from the Civitai on-site generator (meta keys `workflow`, `ecosystem`) do not reproduce pixel-exact with the same seed in ComfyUI — compare style, not pixels. [MEASURED]
- Page format: 1 closest copy + 2 own-subject renders in the same aesthetic (keep style sentences, LoRAs, sampler; swap the subject). [USER RULE]
- Diagnosis: right subject + wrong medium in the no-LoRA render = the look is a style LoRA (adding ta86_myw4y made post 146084006 near-identical); don't rewrite the prompt. [MEASURED]
- Krea 2 Turbo two-pass used by half of top graphs (8 steps ≈ 1 MP → `LatentUpscaleBy` ×1.5 nearest-exact → 4 steps euler/simple denoise 0.4): same quality as one pass at 1280×1600, 18 % faster, one pass cleaner on small text — a speed knob, not a quality gain. [MEASURED]
- Expected outcome (6 posts, 2026-10-25): prompt-only artist-style posts and posts whose model + LoRAs are already local replicate on the first render (14–40 s per image on a 16 GB card); posts whose look comes from a creator LoRA/finetune need that file — the no-LoRA render is still useful as a "what the LoRA adds" baseline. Cap size at ≈ 2.4 MP keeping aspect; published sizes are often upscaled. [MEASURED]

## 8. Operating pitfalls for agents on Windows hosts
- `python` not `python3`; console is cp1252 → avoid printing non-ASCII (→, …) from scripts or set `PYTHONIOENCODING=utf-8`. [MEASURED]
- Bash heredocs in Git Bash eat backslashes in Windows paths and `\n` escapes → write scripts with a file-write tool, not heredocs. [MEASURED]
- Killing Git-Bash-launched processes: PowerShell `Get-CimInstance Win32_Process | Where CommandLine -match …` + `Stop-Process`; `pkill -f` does not work. [MEASURED]
- Custom-node installs and similar code-integration steps may be blocked by the agent's permission classifier; a human's explicit, specific chat authorisation unblocked it. List such steps and get them done **before** an unattended stretch. [MEASURED]
- One downloader per file (two writers on one `.part` corrupted a 7 GB file); verify HF LFS sha256. [MEASURED]
- Builders that regenerate all workflows when called without arguments will overwrite a human's edited files — build one target per call. [MEASURED]

## 9. Open questions (not yet measured)
- Resolved 2026-10-25: regularisation set (47 same-scene images of other women, `is_reg: true`, reg_weight 1.0) cut the no-trigger leak from 0.48 to 0.24 ArcFace and removed leaked marks, at equal identity (0.60) — but at 2500 steps the persona's small marks disappeared too (reg slows learning). Open: how many steps / which lr bring the marks back with reg on (try 4000 steps or lr 2e-4).
- 9:16 vs 4:5 first frames; H3 Ref2V with persona references; H3 LoRA from still images; H3 15-30 s clips on a 96 GB card.
- Resolved 2026-10-25: H3 full precision vs quantised → no visible gap (section 2, minimax_h3.precision_test).
