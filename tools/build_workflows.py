"""Build the H3-test UI workflows. python build_workflows.py [outdir]  (default: $COMFY_WF_DIR or <repo>/workflows)"""
import json, os, sys, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comfytool import Graph, check_overlaps, ui_to_api
import paths

OUT = sys.argv[1] if len(sys.argv) > 1 else paths.WF_DIR
TIMINGS = json.load(open(os.path.join(os.path.dirname(__file__), 'timings.json'), encoding='utf-8')) \
    if os.path.exists(os.path.join(os.path.dirname(__file__), 'timings.json')) else {}
SEED = 20261023

PROMPT_IMG = (
    "Amateur digicam photo of a fictional 28-year-old woman with a mature adult face, defined cheekbones and jawline, "
    "long wavy copper-red hair with a side part, fair skin with natural freckles across her nose and cheeks, light "
    "everyday makeup, soft closed-lip smile, green-hazel eyes looking at the camera. She sits on a black perforated metal mesh bench inside a glass "
    "bus shelter, knees together, hands resting in her lap. She wears an untucked white linen blouse with rolled-up "
    "sleeves, dark-blue high-waisted jeans, a small silver pendant on a thin "
    "chain and small silver hoop earrings. A black leather shoulder bag lies on the bench beside her. Behind the "
    "shelter glass: a red brick shop front with a red-and-white striped awning, a yellow painted curb along the "
    "street, parked bicycles, ordinary city daylight with soft overcast sun and faint reflections on the glass. "
    "Shot on a cheap compact digital camera from about three meters at eye level, slightly off-center framing, "
    "mild wide-angle distortion, slight sensor noise, JPEG compression, auto white balance a little cool, natural "
    "unretouched skin texture with visible pores and fine flyaway hairs, everyday candid snapshot, casual adult "
    "everyday outfit.")

PROMPT_SIMPLE = (
    "Photograph of a late-20s adult woman with long, wavy copper-red hair and fair skin with "
    "freckles, sitting on a black metal bench in a glass bus shelter on a sunny day. She has green eyes, a small "
    "nose and light natural makeup, and smiles softly. She wears an untucked white linen blouse with rolled sleeves, "
    "dark-blue high-waisted jeans, a small silver pendant and silver hoop earrings; a black bag lies next to her. "
    "Behind her is a red brick shop with a striped awning and a yellow curb. Natural daylight, amateur phone photo.")

PROMPT_VIDEO = """integrated_multimodal_description: [Shot 1] <Picture 1> is the first frame. Whole clip is 3 seconds. Live-action. Static medium shot of a fictional 28-year-old woman sitting on a black metal mesh bench inside a glass bus shelter in daylight.
Appearance lock: long wavy copper-red hair, freckles, mature adult face, light everyday makeup, untucked white linen blouse with rolled sleeves, dark-blue high-waisted jeans, small silver pendant, silver hoop earrings, black bag on the bench. Keep face, outfit and proportions exactly as in <Picture 1>.
Background lock: red brick shop with striped awning, yellow curb, glass shelter panels with soft reflections; background stays still apart from natural light flicker.
[Shot 2] 0s-1.5s: she lifts her right hand and tucks a strand of hair behind her ear, then smiles warmly at the camera; small natural breathing and blinking.
[Shot 3] 1.5s-3s: she glances briefly to her left toward the street, looks back at the camera and gives a small playful wink, hands return to her lap.
camera: handheld phone feel, almost static, very slight natural sway, no zoom, no cuts.
overall_soundscape: quiet city street ambience, distant traffic, a soft breeze, faint footsteps on the pavement.
non_diegetic_music: None.
negative: nudity, revealing clothing, morphing face, identity drift, extra fingers, warped hands, flicker, jitter, text, subtitles, watermark, music, talking."""

PROMPT_VIDEO_5S = """integrated_multimodal_description: [Shot 1] <Picture 1> is the first frame. Whole clip is 5 seconds. Live-action. Static medium shot of a fictional 28-year-old woman sitting on a black metal mesh bench inside a glass bus shelter in daylight.
Appearance lock: long wavy copper-red hair, freckles, mature adult face, light everyday makeup, untucked white linen blouse with rolled sleeves, dark-blue high-waisted jeans, small silver pendant, silver hoop earrings, black bag on the bench. Keep face, outfit and proportions exactly as in <Picture 1>.
Background lock: red brick shop with striped awning, yellow curb, glass shelter panels with soft reflections; background stays still apart from natural light flicker.
[Shot 2] 0s-2.5s: she lifts her right hand and tucks a strand of hair behind her ear, then smiles warmly at the camera; small natural breathing and blinking.
[Shot 3] 2.5s-5s: she glances briefly to her left toward the street, looks back at the camera and gives a small playful wink, then relaxes, hands return to her lap and she keeps smiling softly.
camera: handheld phone feel, almost static, very slight natural sway, no zoom, no cuts.
overall_soundscape: quiet city street ambience, distant traffic, a soft breeze, faint footsteps on the pavement.
non_diegetic_music: None.
negative: nudity, revealing clothing, morphing face, identity drift, extra fingers, warped hands, flicker, jitter, text, subtitles, watermark, music, talking."""

NEG_MOSS = "nsfw, worst quality, bad anatomy, watermark, jpeg artifact"


def t(key, default='_pending — filled in phase 2_'):
    return TIMINGS.get(key, default)


def save(g, name):
    ui = g.to_ui()
    ov = check_overlaps(ui)
    if ov: print('  OVERLAPS', name, ov)
    os.makedirs(OUT, exist_ok=True)
    p = os.path.join(OUT, name)
    json.dump(ui, open(p, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    warn = []
    api = ui_to_api(ui, warn)
    print(f'  {name}: {len(ui["nodes"])} ui nodes, {len(api)} api nodes, warnings={warn or "none"}')
    return p


# ------------------------------------------------------------------ shared image tail (hi-res, face, upscale, save)
def image_tail(g, model, clip, vae, pos, neg, lat1, img1, base_w, base_h, sampler2, sched2, face_sampler, face_sched,
               face_steps=4, prefix='H3test/img', hires_steps=4, hires_denoise=0.54):
    g.group('4 · Hi-res pass', 'hires')
    g.note(f"""### 4 · Hi-res pass (latent ×1.5)
Latent upscale (bicubic ×1.5) → second sampler at **denoise {hires_denoise}**, {hires_steps} steps, cfg 1, {sampler2}/{sched2}.
Adds real detail instead of interpolated blur.

**ColorMatch** (KJNodes, `hm-mkl-hm`, strength **0.22**): pulls pass-2 colours back toward the pass-1 decode —
the hi-res pass tends to drift saturation/contrast. Higher strength = closer to pass 1.

- denoise 0.45–0.6: higher = more new detail but more drift from pass 1
- {base_w}×{base_h} → {int(base_w*1.5)}×{int(base_h*1.5)}""", w=380)
    up = g.add('LatentUpscaleBy', col=1, samples=lat1, upscale_method='bicubic', scale_by=1.5)
    ks2 = g.add('KSampler', 'KSampler · hi-res', col=1, model=model, positive=pos, negative=neg, latent_image=up,
                seed=SEED, steps=hires_steps, cfg=1.0, sampler_name=sampler2, scheduler=sched2, denoise=hires_denoise)
    dec2 = g.add('VAEDecode', 'VAE Decode · hi-res', col=2, samples=ks2, vae=vae)
    cm = g.add('ColorMatch', 'ColorMatch → pass 1', col=2, image_ref=img1, image_target=dec2, method='hm-mkl-hm',
               strength=0.22, multithread=True)

    g.group('5 · Face detailer', 'face')
    g.note("""### 5 · Face detailer (Impact)
YOLO face bbox (`face_yolov8m.pt`) → crop → re-sample at **guide/max size 1440** → paste back.
4 steps, cfg 1, `dpmpp_2m_sde` / `sgm_uniform`, **denoise 0.5**.

- denoise 0.35–0.5: lower keeps the face identity, higher fixes more
- bbox_crop_factor 3 = context around the face
- No SAM model — bbox mask is enough at this size""", w=380)
    det = g.add('UltralyticsDetectorProvider', col=0, model_name='bbox/face_yolov8m.pt')
    fd = g.add('FaceDetailer', 'FaceDetailer', col=1, w=360, image=cm, model=model, clip=clip, vae=vae,
               positive=pos, negative=neg, bbox_detector=det['BBOX_DETECTOR'],
               guide_size=1440, guide_size_for=True, max_size=1440, seed=SEED, steps=face_steps, cfg=1.0,
               sampler_name=face_sampler, scheduler=face_sched, denoise=0.5, feather=5, noise_mask=True,
               force_inpaint=True, bbox_threshold=0.5, bbox_dilation=10, bbox_crop_factor=3.0,
               sam_detection_hint='center-1', drop_size=10, cycle=1)

    hw, hh = int(base_w * 1.5), int(base_h * 1.5)
    tw = int(round((hw * 1.9 + 192) / 2 / 8) * 8)
    th = int(round((hh * 1.9 + 192) / 2 / 8) * 8)
    g.group('6 · Upscale', 'upscale')
    g.note(f"""### 6 · Ultimate SD Upscale ×1.9
`OmniSR_X4_DIV2K` model upscale, then tiled re-sampling: **2 steps, euler/simple, denoise 0.1**
(only sharpens; does not repaint). mask_blur 64, tile_padding 96, Linear mode.

Tiles ≈ (W·1.9 + 192)/2 → **{tw}×{th}** for {hw}×{hh} (= 2×2 tiles). Change the tile size if you change the base resolution.

Author also blends a `1xSkinContrast` upscale at 5 % — not available, skipped.
Output ≈ {int(hw*1.9)}×{int(hh*1.9)} — for the video still use the hi-res/face output instead.""", w=380)
    um = g.add('UpscaleModelLoader', col=0, model_name='OmniSR_X4_DIV2K.safetensors')
    us = g.add('UltimateSDUpscale', 'Ultimate SD Upscale ×1.9', col=1, w=360, image=fd['image'], model=model,
               positive=pos, negative=neg, vae=vae, upscale_model=um, upscale_by=1.9, seed=SEED, steps=2, cfg=1.0,
               sampler_name='euler', scheduler='simple', denoise=0.1, mode_type='Linear', tile_width=tw,
               tile_height=th, mask_blur=64, tile_padding=96, seam_fix_mode='None', seam_fix_denoise=1.0,
               seam_fix_width=64, seam_fix_mask_blur=8, seam_fix_padding=16, force_uniform_tiles=True,
               tiled_decode=False, batch_size=1)

    g.group('7 · Save', 'save')
    g.note("""### 7 · Save
- **final** — after upscale (big, for viewing)
- **face** — after face detailer at hi-res size: use this one as the video first frame (03)
Files land in `ComfyUI-Shared/output/H3test/`.""", w=380)
    g.add('SaveImage', 'Save · face (video still)', col=0, w=380, h=420, images=fd['image'], filename_prefix=prefix + '_face')
    g.add('SaveImage', 'Save · final', col=1, w=420, h=600, images=us, filename_prefix=prefix + '_final')


# ------------------------------------------------------------------ 01 Krea 2 realism (author recipe B)
def wf01():
    g = Graph('01_image_krea2_realism')
    W, H = 1000, 1600
    g.group('0 · About', 'about')
    g.note(f"""# 01 · Krea 2 Turbo — realism recipe (B)
Reverse-engineered from Civitai **just_a_prompt_guy**, image 146288534
(Krea 2 Turbo + Realism Engine + Realistic Snapshot, 2-pass + face detailer + USDU).
Base graph: Comfy-Org template `image_krea2_turbo_t2i_int8`.

**Flow:** 1 Models → 2 Prompt → 3 Pass 1 → 4 Hi-res → 5 Face → 6 Upscale → 7 Save

**Machine:** RTX 5070 Ti 16 GB · 62 GB RAM · ComfyUI 0.37.4
**Timings:** {t('01')}

Subject is a fictional adult; SFW only. Fixed seed `{SEED}` for A/B — set the sampler seeds to *randomize* to explore.
Baseline A (single pass, euler/beta) = `01b_image_krea2_simple.json`.""", w=460)

    g.group('1 · Models', 'models')
    g.note("""### 1 · Models
- **UNet** `krea2_turbo_int8_convrot` (int8, ~fits 16 GB with LoRAs)
- **Text encoder** `qwen3vl_4b_fp8_scaled`, type **krea2**
- **VAE**: author uses `wan_2.1_vae`; the Comfy template uses `qwen_image_vae`.
  Toggle the **VAE switch** (false = wan 2.1, true = qwen_image). Only the selected loader runs (lazy switch).
- **LoRAs** (model + clip): Realism Engine **0.7**, Realistic Snapshot **0.9**.
  Lower Snapshot (0.6–0.8) if the image looks too "phone-flash".""", w=400)
    unet = g.add('UNETLoader', col=1, w=400, unet_name='krea2_turbo_int8_convrot.safetensors', weight_dtype='default')
    clip = g.add('CLIPLoader', col=1, w=400, clip_name='qwen3vl_4b_fp8_scaled.safetensors', type='krea2', device='default')
    vae_w = g.add('VAELoader', 'VAE · wan 2.1 (author)', col=1, w=400, vae_name='wan_2.1_vae.safetensors')
    vae_q = g.add('VAELoader', 'VAE · qwen_image (template)', col=1, w=400, vae_name='qwen_image_vae.safetensors')
    vae = g.add('ComfySwitchNode', 'VAE switch (false = wan 2.1 · true = qwen_image)', col=2, w=360,
                switch=False, on_false=vae_w, on_true=vae_q)
    l1 = g.add('LoraLoader', 'LoRA · Realism Engine Krea2 @0.7', col=2, w=360, model=unet, clip=clip,
               lora_name='realism_engine_krea2_v3.1.safetensors', strength_model=0.7, strength_clip=0.7)
    l2 = g.add('LoraLoader', 'LoRA · Realistic Snapshot Krea2 @0.9', col=2, w=360, model=l1[0], clip=l1[1],
               lora_name='RealisticSnapshotKrea2V2.safetensors', strength_model=0.9, strength_clip=0.9)
    model, clipm = l2[0], l2[1]

    g.group('2 · Prompt', 'prompt')
    g.note("""### 2 · Prompt
Author style: *"Amateur digicam photo of a fictional 21-year-old adult …"* — one dense natural-language paragraph:
subject → pose → wardrobe → location → light → camera artefacts.
Krea 2 Turbo runs at **cfg 1**, so the negative is just **ConditioningZeroOut** (no negative prompt).""", w=420)
    pos = g.add('CLIPTextEncode', 'Positive prompt', col=0, w=420, h=440, clip=clipm, text=PROMPT_IMG)
    neg = g.add('ConditioningZeroOut', 'Negative = zero (cfg 1)', col=0, w=420, conditioning=pos)

    g.group('3 · Pass 1', 'pass1')
    g.note(f"""### 3 · Pass 1 — base image
**{W}×{H}** (author). For the video aspect use **896×1120** (4:5).
KSamplerAdvanced: **8 steps, cfg 1, euler_ancestral, sgm_uniform**.
Ancestral sampling adds the grain/texture the author's look relies on.""", w=380)
    lat = g.add('EmptyLatentImage', 'Empty Latent · base size', col=1, width=W, height=H, batch_size=1)
    ks1 = g.add('KSamplerAdvanced', 'KSampler · pass 1', col=1, model=model, positive=pos, negative=neg,
                latent_image=lat, add_noise='enable', noise_seed=SEED, steps=8, cfg=1.0,
                sampler_name='euler_ancestral', scheduler='sgm_uniform', start_at_step=0, end_at_step=10000,
                return_with_leftover_noise='disable')
    dec1 = g.add('VAEDecode', 'VAE Decode · pass 1', col=2, samples=ks1, vae=vae)
    g.add('PreviewImage', 'Preview · pass 1', col=2, h=380, images=dec1)

    image_tail(g, model, clipm, vae, pos, neg, ks1, dec1, W, H, 'euler', 'simple', 'dpmpp_2m_sde', 'sgm_uniform',
               prefix='H3test/krea2')
    return save(g, '01_image_krea2_realism.json')


# ------------------------------------------------------------------ 01b Krea 2 simple baseline (A)
def wf01b():
    g = Graph('01b_image_krea2_simple')
    g.group('0 · About', 'about')
    g.note(f"""# 01b · Krea 2 — simple baseline (A)
Mirrors Civitai image **145959733** (13-node graph): one pass, **KSampler 8 steps, cfg 1, euler / beta**,
`qwen3vl_4b_fp8_scaled` + `qwen_image_vae`. The author used the community checkpoint *DesireX INT8*;
here the official `krea2_turbo_int8_convrot` is used instead.
Plain descriptive prompt (*"Photograph of a young woman with …"*).

Purpose: A/B against the multi-pass recipe **01 (B)** — what do hi-res + face + upscale actually buy?
The two realism LoRAs are present but **bypassed** (purple) — un-bypass (Ctrl+B) to test "A + LoRAs".

**Timings:** {t('01b')}""", w=440)
    g.group('1 · Models', 'models')
    unet = g.add('UNETLoader', col=0, w=400, unet_name='krea2_turbo_int8_convrot.safetensors', weight_dtype='default')
    clip = g.add('CLIPLoader', col=0, w=400, clip_name='qwen3vl_4b_fp8_scaled.safetensors', type='krea2', device='default')
    vae = g.add('VAELoader', col=0, w=400, vae_name='qwen_image_vae.safetensors')
    l1 = g.add('LoraLoader', 'LoRA · Realism Engine @0.7 (bypassed)', col=1, w=360, mode=4, model=unet, clip=clip,
               lora_name='realism_engine_krea2_v3.1.safetensors', strength_model=0.7, strength_clip=0.7)
    l2 = g.add('LoraLoader', 'LoRA · Realistic Snapshot @0.9 (bypassed)', col=1, w=360, mode=4, model=l1[0], clip=l1[1],
               lora_name='RealisticSnapshotKrea2V2.safetensors', strength_model=0.9, strength_clip=0.9)
    g.group('2 · Prompt', 'prompt')
    pos = g.add('CLIPTextEncode', 'Positive prompt', col=0, w=420, h=300, clip=l2[1], text=PROMPT_SIMPLE)
    neg = g.add('ConditioningZeroOut', 'Negative = zero (cfg 1)', col=0, w=420, conditioning=pos)
    g.group('3 · Sample', 'pass1')
    lat = g.add('EmptyLatentImage', 'Empty Latent', col=0, width=1000, height=1600, batch_size=1)
    ks = g.add('KSampler', 'KSampler · 8 steps euler/beta', col=0, model=l2[0], positive=pos, negative=neg,
               latent_image=lat, seed=SEED, steps=8, cfg=1.0, sampler_name='euler', scheduler='beta', denoise=1.0)
    dec = g.add('VAEDecode', col=1, samples=ks, vae=vae)
    g.group('4 · Save', 'save')
    g.add('SaveImage', 'Save · simple', col=0, w=420, h=600, images=dec, filename_prefix='H3test/krea2_simple')
    return save(g, '01b_image_krea2_simple.json')


# ------------------------------------------------------------------ 02 MOSS-Image
def wf02():
    g = Graph('02_image_moss')
    W, H = 1024, 1280
    g.group('0 · About', 'about')
    g.note(f"""# 02 · MOSS-Image SFT — A/B vs Krea 2
Same subject/prompt as 01. LoRA stack mirrors Civitai image **146220084**
(MOSS SFT + nicegirls 0.4 + lenovo 0.5 + DMD 8-step turbo 1.0 + hi8 "2000s Analog Core" 0.4).

⚠ **Needs ComfyUI ≥ v0.42.0** (core MOSS support, PR #17095 by Kijai, merged 2026-10-16).
The installed core **0.37.4 cannot load MOSS** (no `moss_image` CLIP type, no model detection) — update ComfyUI Desktop first.

**Settings sources:** comfyui-wiki news 2026-10-16; Neural Dreamer video (YouTube 9GGOv7sxSoY):
SFT is built for **50 steps, cfg 3, shift 5**, scheduler **simple** (beta is noisier); 1–2 MP best, ≤4 MP stable, >6 MP breaks
composition. With a turbo/DMD LoRA: **8–10 steps, cfg 1**. Put `nsfw` in the negative when running non-turbo.

**Timings:** {t('02')}""", w=480)

    g.group('1 · Models + LoRA stack', 'models')
    g.note("""### 1 · Models
- **DiT** `moss_image_sft_bf16` (10.2 GB; `…_int8_convrot` 5.4 GB is the low-VRAM option)
- **Text encoder** `qwen3.5_9b_int8_convrot`, CLIPLoader type **moss_image**
- **VAE** `flux2-vae` (MOSS works in the FLUX.2 latent space)
- **ModelSamplingAuraFlow shift 5** (= model default). Do NOT use ModelSamplingSD3: it sets multiplier 1000, MOSS needs 1.0 → pure noise.

### LoRA chain (model-only)
nicegirls 0.4 → lenovo 0.5 (trigger **l3n0v0**, already in the prompt) → **DMD 8-step 1.0** → hi8 0.4.

### No-turbo variant
Bypass the **DMD** LoRA (Ctrl+B), set the sampler to **50 steps, cfg 3**, and un-bypass
**Skip layer 22 (negative only)** — negative-branch layer skip at 22 (24/26 also work).""", w=420)
    unet = g.add('UNETLoader', col=1, w=400, unet_name='moss_image_sft_bf16.safetensors', weight_dtype='default')
    clip = g.add('CLIPLoader', col=1, w=400, clip_name='qwen3.5_9b_int8_convrot.safetensors', type='moss_image', device='default')
    vae = g.add('VAELoader', col=1, w=400, vae_name='flux2-vae.safetensors')
    l1 = g.add('LoraLoaderModelOnly', 'LoRA · nicegirls v2 @0.4', col=2, w=380, model=unet,
               lora_name='nicegirls_v2_moss.safetensors', strength_model=0.4)
    l2 = g.add('LoraLoaderModelOnly', 'LoRA · lenovo @0.5 (trigger l3n0v0)', col=2, w=380, model=l1,
               lora_name='lenovo_moss.safetensors', strength_model=0.5)
    l3 = g.add('LoraLoaderModelOnly', 'LoRA · DMD 8-step turbo @1.0', col=2, w=380, model=l2,
               lora_name='MOSS_Image_SFT_8_steps_dmd_v0.1.safetensors', strength_model=1.0)
    l4 = g.add('LoraLoaderModelOnly', 'LoRA · hi8 v2 "2000s Analog Core" @0.4', col=2, w=380, model=l3,
               lora_name='hi8_v2_moss.safetensors', strength_model=0.4)
    ms = g.add('ModelSamplingAuraFlow', 'ModelSampling (AuraFlow) · shift 5', col=3, model=l4, shift=5.0, sampling='flow')
    slg = g.add('SkipLayerGuidanceDiTSimple', 'Skip layer 22 (negative only) · no-turbo', col=3, mode=4, model=ms,
                double_layers='', single_layers='22', start_percent=0.0, end_percent=1.0)
    model = slg

    g.group('2 · Prompt', 'prompt')
    g.note("""### 2 · Prompt
Same scene text as 01, prefixed with the lenovo trigger `l3n0v0`.
MOSS uses stock Qwen3.5-9B — long natural-language prompts work well.
Negative (only active at cfg > 1): `nsfw, worst quality, bad anatomy, watermark, jpeg artifact`.""", w=420)
    pos = g.add('CLIPTextEncode', 'Positive prompt', col=0, w=420, h=440, clip=clip, text='l3n0v0, ' + PROMPT_IMG)
    neg = g.add('CLIPTextEncode', 'Negative prompt (cfg > 1 only)', col=0, w=420, h=200, clip=clip, text=NEG_MOSS)

    g.group('3 · Pass 1', 'pass1')
    g.note(f"""### 3 · Pass 1
**{W}×{H}** (1.3 MP, 4:5, multiples of 16) — Flux2 empty latent.
Turbo (DMD): **8 steps, cfg 1, euler / simple**. Try `lcm` if DMD looks soft.
No-turbo: 50 steps, cfg 3.""", w=380)
    lat = g.add('EmptyFlux2LatentImage', 'Empty Flux2 Latent · base size', col=1, width=W, height=H, batch_size=1)
    ks1 = g.add('KSampler', 'KSampler · pass 1', col=1, model=model, positive=pos, negative=neg, latent_image=lat,
                seed=SEED, steps=8, cfg=1.0, sampler_name='euler', scheduler='simple', denoise=1.0)
    dec1 = g.add('VAEDecode', 'VAE Decode · pass 1', col=2, samples=ks1, vae=vae)
    g.add('PreviewImage', 'Preview · pass 1', col=2, h=380, images=dec1)

    image_tail(g, model, clip, vae, pos, neg, ks1, dec1, W, H, 'euler', 'simple', 'euler', 'simple',
               prefix='H3test/moss', hires_denoise=0.5)
    return save(g, '02_image_moss.json')


# ------------------------------------------------------------------ 03 MiniMax H3 i2v
def wf03():
    g = Graph('03_video_h3_i2v')
    VW, VH, LEN = 768, 960, 124
    g.group('0 · About', 'about')
    g.note(f"""# 03 · MiniMax H3 — image → video (5 s, with audio)
Based on the Comfy-Org template `video_minimax_h3_i2v` (flattened, no subgraph), mirroring the Civitai reference video
**143911899**: H3 FL2VA pruned int8 + **turbo 8-step LoRA**, BasicGuider (no CFG), structured shot-list prompt.

**Input:** the face-detailed still from 01/02 (`H3test/*_face_*.png` — copy it to `ComfyUI-Shared/input`).
**Output:** `output/video/H3test_*.mp4`, 24 fps, H.264 crf 16, with generated audio.

**Timings:** {t('03')}""", w=460)

    g.group('1 · Models', 'models')
    g.note("""### 1 · Models
- **UNet** `minimax_h3_fl2va_pruned_int8_convrot` (video + audio DiT)
- **LoRA** `minimax_h3_fl2v_turbo_8step_v1.0` @1.0 → 8 steps without CFG.
  Bypass it for the full model (template: 20 steps).
- **Text encoder** `qwen3vl_32b_minimax_h3_nvfp4_awq`, type **minimax** (also encodes the first frame)
- **VAEs**: video `minimax_h3_video_vae_fp16`, audio `minimax_h3_audio_vae_fp32`
- **ModelSamplingMiniMaxH3 shift_video 8** (model default 12; 8 = sharper + actions still played; tested 8/12/16)""", w=420)
    unet = g.add('UNETLoader', col=1, w=440, unet_name='minimax_h3_fl2va_pruned_int8_convrot.safetensors', weight_dtype='default')
    lora = g.add('LoraLoaderModelOnly', 'LoRA · H3 turbo 8-step @1.0', col=1, w=440, model=unet,
                 lora_name='minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors', strength_model=1.0)
    clip = g.add('CLIPLoader', col=1, w=440, clip_name='qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors', type='minimax', device='default')
    vvae = g.add('VAELoader', 'VAE · video', col=1, w=440, vae_name='minimax_h3_video_vae_fp16.safetensors')
    avae = g.add('VAELoader', 'VAE · audio', col=1, w=440, vae_name='minimax_h3_audio_vae_fp32.safetensors')

    g.group('2 · First frame', 'input')
    g.note(f"""### 2 · First frame
Load the still and scale it with **lanczos** to the video size (crop = center keeps 4:5).
Width/height must be **multiples of 32** (node step).

- **{VW}×{VH}** = 0.74 MP (portrait 4:5) — best detail/time trade-off in tests
- 640×800 (≈ 65 s for 3 s) for quick drafts · 896×1120 (reference size) works too
- 576×720 fails — 720 is not a multiple of 32
- set the same size in the H3 node (section 3)""", w=380)
    img = g.add('LoadImage', 'Load first frame', col=1, w=360, h=420, image='h3_first_frame.png')
    sc = g.add('ImageScale', 'Scale to video size (lanczos)', col=1, image=img[0], upscale_method='lanczos',
               width=VW, height=VH, crop='center')

    g.group('3 · Conditioning', 'prompt')
    g.note(f"""### 3 · H3 conditioning
`MiniMaxH3ImageToVideo` encodes prompt + first frame and creates the joint video/audio latent.

- **length = {LEN} frames** ≈ 5 s @ 24 fps (73 = 3 s). Valid lengths are **5 + 17·k: 5, 22, 39, 56, 73, 90, 107, 124 …**
  (template formula `n + (5 − n mod 17) mod 17`). If 73 looks bad, try 124 and trim.
- Prompt = author's structured shot list: `integrated_multimodal_description: [Shot 1] <Picture 1> is the first frame …`
  with appearance/background locks, timed shots, camera, `overall_soundscape`, `non_diegetic_music: None`, `negative:`.""", w=420)
    h3 = g.add('MiniMaxH3ImageToVideo', 'MiniMax H3 Image to Video', col=1, w=520, h=640, clip=clip, vae=vvae,
               first_frame=sc, prompt=PROMPT_VIDEO_5S, width=VW, height=VH, length=LEN)

    g.group('4 · Sampling', 'pass1')
    g.note("""### 4 · Sampling (no CFG)
RandomNoise → **BasicGuider** (positive only) → **KSamplerSelect euler** → **BasicScheduler simple, 8 steps** →
SamplerCustomAdvanced. Template default sampler is `res_multistep` — worth an A/B.

Optional live preview: **Model Preview Override** (KJNodes) with `taeh3` tiny VAE — bypassed by default, un-bypass to see
animated previews while sampling.""", w=400)
    prev = g.add('ModelPreviewOverrideKJ', 'Preview override · taeh3 (optional)', col=1, w=360, h=290, mode=4, model=lora,
                 max_resolution=512, jpeg_quality=80, suppress_default_preview=True, preview_frames=24, preview_fps=12,
                 tiny_vae='taeh3.safetensors')
    noise = g.add('RandomNoise', col=1, noise_seed=SEED)
    samp = g.add('KSamplerSelect', col=1, sampler_name='euler')
    shift = g.add('MiniMaxH3SigmaShift', 'ModelSampling H3 · shift 8', col=2, model=prev, shift_video=8.0, shift_audio=3.0)
    sch = g.add('BasicScheduler', 'BasicScheduler · 8 steps', col=2, model=shift, scheduler='simple', steps=8, denoise=1.0)
    gd = g.add('BasicGuider', col=2, model=shift, conditioning=h3[0])
    sca = g.add('SamplerCustomAdvanced', col=2, noise=noise, guider=gd, sampler=samp, sigmas=sch, latent_image=h3[1])

    g.group('5 · Decode', 'decode')
    g.note("""### 5 · Decode
- Video: **VAE Decode (Tiled)** 512 / 64 overlap / temporal 64 / 8 — keeps decode under 16 GB
- Audio: **VAE Decode Audio** from the same latent""", w=360)
    dv = g.add('VAEDecodeTiled', 'VAE Decode (Tiled) · video', col=1, samples=sca[0], vae=vvae, tile_size=512,
               overlap=64, temporal_size=64, temporal_overlap=8)
    da = g.add('VAEDecodeAudio', 'VAE Decode · audio', col=1, samples=sca[0], vae=avae)

    g.group('6 · Save', 'save')
    g.note("""### 6 · Save
CreateVideo **24 fps** + audio → SaveVideo **mp4 / h264 re-encode crf 16**.
Post-processing (lanczos ×2, RIFE ×2 → 48 fps) is workflow **04**.""", w=360)
    cv = g.add('CreateVideo', col=0, images=dv, audio=da, fps=24.0)
    g.add('SaveVideo', 'Save video', col=1, w=420, h=520, video=cv, filename_prefix='video/H3test_h3',
          format='mp4', format__codec='h264', format__codec__encoding='re-encode', format__codec__encoding__crf=16.0)
    return save(g, '03_video_h3_i2v.json')


# ------------------------------------------------------------------ 04 RIFE + upscale
def wf04():
    g = Graph('04_post_rife_upscale')
    g.group('0 · About', 'about')
    g.note(f"""# 04 · Post: upscale ×2 + RIFE ×2 → 48 fps
The reference author's "upscale" is plain **lanczos** (to 1600×2000), then frame interpolation.
Here: 768×960 → **1536×1920**, RIFE 4.7 ×2 (24 → 48 fps), audio passed through.
×3 → 72 fps also works, but at 768×960 / 124 frames system RAM peaks at 61 of 62 GB — use it only for short/small clips.

**Input:** the H3 mp4 from 03 (copy into `ComfyUI-Shared/input`).
**Timings:** {t('04')}""", w=440)

    g.group('1 · Load', 'input')
    g.note("""### 1 · Load video
Core **Load Video** → **Get Video Components** (frames, audio, fps).""", w=340)
    lv = g.add('LoadVideo', 'Load H3 video', col=0, w=340, h=420, file='H3test_h3.mp4')
    comp = g.add('GetVideoComponents', col=1, video=lv)

    g.group('2 · Upscale', 'upscale')
    g.note("""### 2 · Upscale
Default: **lanczos ×2** (author's method — fast, no hallucinated detail).

Variant (bypassed, purple): **OmniSR ×4 → lanczos ×0.5** = model-sharpened ×2.
To switch: bypass *Lanczos ×2* and un-bypass the two OmniSR nodes (Ctrl+B). Costs much more time/VRAM per frame.""", w=380)
    up = g.add('ImageScaleBy', 'Lanczos ×2', col=1, image=comp['images'], upscale_method='lanczos', scale_by=2.0)
    um = g.add('UpscaleModelLoader', 'OmniSR ×4 (variant)', col=1, mode=4, model_name='OmniSR_X4_DIV2K.safetensors')
    om = g.add('ImageUpscaleWithModel', 'OmniSR ×4 (variant, bypassed)', col=2, mode=4, upscale_model=um, image=up)
    dn = g.add('ImageScaleBy', 'Lanczos ×0.5 after OmniSR (variant)', col=2, mode=4, image=om,
               upscale_method='lanczos', scale_by=0.5)

    g.group('3 · RIFE', 'pass1')
    g.note("""### 3 · RIFE VFI
**rife47**, multiplier **2** (24 → 48 fps; ×3 → 72 fps needs ~61 GB RAM at 1536×1920×124 f), fast_mode on, ensemble on, scale_factor 1.
clear_cache_after_n_frames 10 keeps VRAM flat. Interpolated frames are clean (only fast hand moves blur slightly).
fps must equal 24 × multiplier, otherwise the motion speed changes.""", w=380)
    rife = g.add('RIFE VFI', 'RIFE VFI ×2 (rife47)', col=1, frames=dn, ckpt_name='rife47.pth',
                 clear_cache_after_n_frames=10, multiplier=2, fast_mode=True, ensemble=True, scale_factor=1.0,
                 dtype='float32', torch_compile=False, batch_size=1)

    g.group('4 · Save', 'save')
    g.note("""### 4 · Save
VHS Video Combine **48 fps** (set 72 with RIFE ×3), h264-mp4 **crf 14**, yuv420p, audio from the source.""", w=340)
    g.add('VHS_VideoCombine', 'Video Combine · 48 fps', col=1, w=420, h=560, images=rife, audio=comp['audio'],
          frame_rate=48, loop_count=0, filename_prefix='H3test/h3_rife48', format='video/h264-mp4', pingpong=False,
          save_output=True, pix_fmt='yuv420p', crf=14, save_metadata=True, trim_to_audio=False)
    return save(g, '04_post_rife_upscale.json')


if __name__ == '__main__':
    print('->', OUT)
    # wf01 is NOT rebuilt by default: 01_image_krea2_realism.json was hand-patched to the U2 settings (main session)
    for f in (wf01b, wf02, wf03, wf04): f()
