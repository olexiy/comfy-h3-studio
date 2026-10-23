# comfy-h3-studio

A local ComfyUI pipeline for photoreal image-to-video on a single 16 GB consumer GPU:

**Krea 2 Turbo still → MiniMax H3 image-to-video (with sound) → RIFE ×2 / lanczos ×2 upscale → 1536×1920 @ 48 fps.**

Ready-to-drop ComfyUI workflows, the Python tooling used to generate and benchmark them, and the measured
results of the first experiment series.

- **Learning page (Russian, with videos and comparison sheets):** https://olexiy.github.io/comfy-h3-studio/
- **Workflows:** [`workflows/`](workflows/) · **Tools:** [`tools/`](tools/) · **Shot-list prompts:** [`prompts/`](prompts/)

> **Model licence first.** This repo ships no weights. MiniMax H3's open-weights licence
> [excludes the EU, the UK, South Korea and the US](https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/docs/QA-about-License.md)
> (formal licence on request), adds a revenue cap and attribution rules. Krea 2, MOSS and the community LoRAs have
> their own terms. Read each model card and check what applies where you live before you download or use anything.
> The workflows here document a private research setup.

## Tested hardware

| | |
|---|---|
| GPU | RTX 5070 Ti 16 GB (Blackwell) |
| RAM | 62 GB — **the real limit**: H3's 32 B text encoder keeps system RAM at 54–60 GB |
| ComfyUI | Desktop app, core v0.42.4, torch 2.12.1+cu130, Python 3.13 |
| Custom nodes | [KJNodes](https://github.com/kijai/ComfyUI-KJNodes), [UltimateSDUpscale](https://github.com/ssitu/ComfyUI_UltimateSDUpscale), [Impact Pack](https://github.com/ltdrdata/ComfyUI-Impact-Pack) + [Subpack](https://github.com/ltdrdata/ComfyUI-Impact-Subpack), [Frame-Interpolation](https://github.com/Fannovel16/ComfyUI-Frame-Interpolation) (RIFE), [VideoHelperSuite](https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite) |

No Triton / SageAttention needed.

## Workflows

All five use the same layout: on the canvas only the input (image / video), **one subgraph node with the
fields you actually change plus on/off toggles**, and the save node. The technical graph lives inside the
subgraph (double-click its title; the breadcrumb brings you back). Toggles drive lazy `ComfySwitchNode`s, so a
switched-off branch never runs.

| File | What it does | Fields · toggles | Measured time (RTX 5070 Ti 16 GB) |
|---|---|---|---|
| `01_image_krea2_realism` | Krea 2 Turbo + Realism Engine 0.5 + Realistic Snapshot 0.9, 2 passes, ColorMatch, face detailer, Ultimate SD Upscale ×1.9 | prompt, width/height (896×1120 for video), seed, realism strength · **face detail**, **upscale ×1.9** | 896×1120 → 2552×3192: **54–57 s** · 1000×1600 → 2856×4560: 88–106 s |
| `01b_image_krea2_simple` | Krea 2 Turbo, one pass, 8 steps euler/beta — the most natural "phone photo" look | prompt, size, seed · **realism LoRAs** (glossier) | 1000×1600: **13–14 s** warm |
| `03_video_h3_i2v` | MiniMax H3 i2v, turbo LoRA 8 steps, shift 8, timed shot-list, audio. First frame scaled to a pixel budget (`ImageScaleToTotalPixels` 0.70 MP, steps of 32 → `GetImageSize`), **never cropped**; output frame 0 (= the input still) and 1 frame of audio are cut | prompt, size (MP), frames, seed, shift · **Eros Max**, **keep first-frame light**, **sound** + volume (dB), **48 fps** | 768×960 · 5 s: **160–184 s** · 9 s 434 s · 12 s 694 s |
| `03c_video_h3_chain` | Continue a clip: last 22 frames + audio of the previous clip as anchor (`MiniMaxH3AddGuide`), +5 s, joined into one mp4; size taken from the clip | same as 03 | **233 s** per +5 s |
| `04_post_upscale_rife` | lanczos ×2 → 1536×1920, RIFE 4.7 → 48 fps, audio passed through | RIFE multiplier, fps (= 24 × multiplier) · **upscale ×2**, **RIFE** | **27 s** (×3 / 72 fps: 39 s, RAM 61 GB) |

Toggles in the video workflows:
- **Eros Max** — off = official H3 + turbo LoRA (sharper); on = community finetune Eros Max beta5 + VBVR LoRA 0.25
  (158–171 s, same time, ≈ 30 % softer, drifts darker). Only the selected branch loads.
- **keep first-frame light** — ColorMatch (mkl) of every frame against the first frame; removes H3's darkening /
  warming drift (−9 to −31 % brightness over a clip). Switch off when the light is meant to change.
- **sound** + **volume** — off = video without an audio track; volume in dB (−6 = half as loud).
- **48 fps** — RIFE ×2 on the result (+15–25 s, +3–5 GB RAM).

Peak VRAM is 15.2–15.9 GB everywhere. Raw numbers: [`tools/timings.json`](tools/timings.json).

## Models

All Hugging Face files are mirrored in ComfyUI folder layout; `scripts/download_models.sh` fetches them
(`COMFY_MODELS=/path/to/ComfyUI/models bash scripts/download_models.sh all`).

| Folder | File | Source |
|---|---|---|
| diffusion_models | `krea2_turbo_int8_convrot` | [Comfy-Org/Krea-2](https://huggingface.co/Comfy-Org/Krea-2) |
| text_encoders | `qwen3vl_4b_fp8_scaled` | Comfy-Org/Krea-2 |
| vae | `qwen_image_vae`, `wan_2.1_vae` | Comfy-Org/Krea-2, [Comfy-Org/Wan_2.1_ComfyUI_repackaged](https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged) |
| diffusion_models | `minimax_h3_fl2va_pruned_int8_convrot` | [Comfy-Org/MiniMax-H3](https://huggingface.co/Comfy-Org/MiniMax-H3) |
| text_encoders | `qwen3vl_32b_minimax_h3_nvfp4_awq` | Comfy-Org/MiniMax-H3 |
| vae | `minimax_h3_video_vae_fp16`, `minimax_h3_audio_vae_fp32` | Comfy-Org/MiniMax-H3 |
| loras | `minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16` | Comfy-Org/MiniMax-H3 |
| vae_approx | `taeh3` (optional live preview) | [Kijai/MiniMax-H3-TAE](https://huggingface.co/Kijai/MiniMax-H3-TAE) |
| ultralytics/bbox | `face_yolov8m.pt` | [Bingsu/adetailer](https://huggingface.co/Bingsu/adetailer) |
| upscale_models | `OmniSR_X4_DIV2K` | [Acly/Omni-SR](https://huggingface.co/Acly/Omni-SR) |
| (auto) | `rife47.pth` | downloaded by ComfyUI-Frame-Interpolation on first run |
| loras | `realism_engine_krea2_v3.1`, `RealisticSnapshotKrea2V2` (01, 01b toggle) | Civitai community LoRAs — [search](https://civitai.com/search/models?query=realism%20engine%20krea2) |
| diffusion_models | `h3ErosMax_beta5` (Eros Max toggle in 03/03c, int8, ≈ 20 GB) | Civitai community finetune — [search](https://civitai.com/search/models?query=H3%20Eros%20Max) |
| loras | `H3_VBVR_Pro_attn_only` (Eros Max toggle) | Civitai — [search](https://civitai.com/search/models?query=H3%20VBVR) |

The Eros Max files are only needed if you switch that toggle on; the off branch never loads them.

Links only; no weights are redistributed here. Civitai downloads need a login.

## Quick start

1. Install ComfyUI (Desktop or git, core ≥ 0.42) and the custom nodes listed above.
2. Download the models (table above). Impact Pack looks for `ultralytics/bbox/face_yolov8m.pt` inside the
   *core* `models/` folder — copy it there if you use a shared models directory.
3. Drag a JSON from `workflows/` into the ComfyUI window. The note on the canvas explains every field and
   toggle and lists the measured timings.
4. Typical run: `01` (or `01b`) → first frame for `03` → `04` (or just the 48 fps toggle in `03`).
   Longer clips: raise *frames* in `03` up to 294 (12 s), beyond that chain with `03c`.
5. Write video prompts as a **timed shot-list** — see [`prompts/`](prompts/) (`prompt_5s.txt`, `len_*.txt`).

Close other ComfyUI instances before H3: two H3 processes at once leave ≈ 3 GB free RAM and double the run time.

## Key findings (series 0)

- **H3 sweet spot: 768×960 + shift 8 + turbo LoRA 8 steps + timed shot-list.** Resolution matters more than
  steps: 768 with turbo beats 640 at 20 steps. A short plain prompt makes the face drift and drops actions —
  always include *appearance lock* and *background lock* blocks.
- **H3 sizes must be multiples of 32** (576×720 crashes; 640×800, 768×960, 896×1120 work); frame counts are
  17k+5 (73 = 3 s, 124 = 5 s, 226 = 9 s, 294 = 12 s).
- **Local length limit ≈ 12 s.** 12 s (294 f) takes 694 s and keeps every beat; 15 s runs but the end goes soft
  and the background drifts. 9 s is the best quality/time trade-off.
- **Chaining beats long single clips:** `03c` 5 s + 5 s = 397 s vs 434 s for one 9 s clip, invisible seam,
  sharper middle (892 vs 724 Laplacian). Rule: ≤ 9 s single clip, > 12 s chain 5–8 s hops.
- **First-frame pop fix:** frame 0 of H3's output is the input still itself (sharper, slightly different
  colour), so the clip visibly "jumps" after it. Drop it with `ImageFromBatch` (batch_index 1) after decode
  (and trim one frame of audio) — done in `03` / `03c`.
- **Never crop the first frame.** Cropping a 5:8 still to 4:5 while the *background lock* lists objects that
  are no longer in the frame makes H3 repaint the whole background within 0.75–1.5 s. Scale to a pixel budget
  instead (megapixels, aspect kept, snapped to /32 — 0.70 MP ≈ 768×960 for 4:5, 672×1088 for 5:8) and lock
  "the room exactly as in &lt;Picture 1&gt;, nothing added". Verified by a render: 5:8 → 672×1088, background stable.
- **Mood words move the light.** "warm", "dim" and similar — even in the music line — shift brightness and
  colour over the clip; H3 (and Eros Max more so) also drifts darker / yellower by itself (−9 to −31 %).
  Keep mood words out of the shot-list and use the *keep first-frame light* toggle.
- **Krea 2 Turbo needs strong body wording.** At cfg 1 the distilled model ignores soft adjectives about build;
  concrete, strong tag words (plus describing how the body relates to the pose) work on the first seed. Scene
  context pulls the figure towards its stereotype (yoga → athletic). Repeat the same words in the video
  shot-list's appearance lock, or H3 slims the figure over the clip.
- **Tags work as well as prose** for Krea 2 stills: quality tags + `photo \(medium\)` + short comma-separated
  subject / pose / wardrobe / location tags. "instagram photograph" = glossy, "amateur phone photo" = raw.
- **"AI face" fix (01):** Realism Engine 0.7 → 0.5, upscale denoise 0.1 → 0.22, and prompt words for mature
  features, uneven skin tone and hard side light.
- **RAM, not VRAM, is the ceiling** on 62 GB: H3 sits at 58–60 GB; RIFE ×3 at 1536×1920 × 124 frames hits 61 GB → use ×2.
- **MOSS-Image** (tested, dropped from the repo) renders pure noise with `ModelSamplingSD3` (multiplier 1000);
  use `ModelSamplingAuraFlow` shift 5. Its stills make soft H3 video — not a good first-frame model here.
- **Eros Max vs official H3** on the same clothed scene: same time, ≈ 30 % softer; shift 8 recovers about a
  third. For ordinary scenes keep the toggle off.

## Tools

Python helpers that generate the workflows and drive a headless ComfyUI over its HTTP API. Paths come from
environment variables ([`tools/paths.py`](tools/paths.py)):

| Variable | Meaning | Default |
|---|---|---|
| `COMFY_URL` | ComfyUI server | `http://127.0.0.1:8189` |
| `COMFY_WF_DIR` | where `build_*.py` write and runners read workflows | `<repo>/workflows` |
| `COMFY_DATA` | ComfyUI folder holding `input/` and `output/` | — (base for relative paths in `sheet.py` / `lenstats.py`) |

| Script | Purpose |
|---|---|
| `build_v2.py` | builds all five workflows in `workflows/` (subgraph + promoted fields + lazy toggles) |
| `subgraph.py` | generic "wrap a flat graph into one subgraph node with promoted widgets" helper (format of the official `video_minimax_h3_i2v` template) |
| `comfytool.py` | UI ⇄ API converter driven by `/object_info` (expands subgraphs), `check`, `queue` with timing + peak VRAM/RAM logging to `results.json` |
| `build_workflows.py`, `build_long.py` | earlier flat-graph generators; now used as libraries (default SFW prompts, seed, chain prompt) |
| `eros_cmp.py` | queue `03` with the Eros Max toggle off/on on the same frame / seed / shot-list (`--shift`, `--len`, `--seed`) |
| `lenstats.py`, `sheet.py` | per-clip sharpness / temporal diff / face drift + frame grids; image contact sheets (need numpy + Pillow, ffmpeg) |

```bash
cd tools
python comfytool.py refresh          # cache /object_info from the running server (needed once)
python build_v2.py                   # regenerate ../workflows
python comfytool.py check ../workflows/03_video_h3_i2v.json
```

## Content policy

Everything in this repo — workflows, prompts, page media — is SFW: fictional, clearly adult, clothed people
only. The workflows are content-neutral tools; you are responsible for what you generate with them and for
following each model's licence and acceptable-use terms.

## Licence

Code and documentation: [MIT](LICENSE). Models are not part of this repo and keep their own licences.
