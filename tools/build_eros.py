"""Build 05_video_h3_erosmax_i2v.json (reference setup of Civitai 143911899: community turbo finetune + VBVR LoRA)."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comfytool import Graph
import build_workflows as bw
from build_long import decode
from subgraph import wrap
import paths
bw.OUT = paths.WF_DIR
TIM = json.load(open(os.path.join(os.path.dirname(__file__), 'timings.json'), encoding='utf-8'))
EROS = 'h3ErosMax_beta5_3185154.safetensors'
VBVR = 'H3_VBVR_Pro_attn_only.safetensors'
PROMPT = open(os.path.join(paths.PROMPTS, 'meditation_5s.txt'),
              encoding='utf-8').read().strip()


HOWTO = f"""# 05 · H3 Eros Max — image → video
**Use:** pick the first frame in *Load first frame* → write the shot-list in **prompt** on the middle node → Run.
Everything technical (models, VBVR LoRA 0.25, sampler 8 steps, decode, drop frame 0, RIFE) lives inside the
subgraph — double-click its title to open it, the breadcrumb at the top brings you back.

| Field | Meaning |
|---|---|
| size (MP) | pixel budget; aspect taken from your image, **never cropped**; 0.70 ≈ 768×960 (best quality/time), 1.0 ≈ 896×1120 (slower, more RAM) |
| frames | 17k+5 → 124 = 5 s · 226 = 9 s · 294 = 12 s (local max) |
| seed | same seed + same frame = repeatable |
| shift | 8 = sharper (series 0); model default ≈ softer |
| sound | off = video without audio track (add your own music in an editor) |
| sound volume | dB, e.g. −6 = half as loud |
| smooth 48 fps | on = RIFE ×2 → 48 fps (+15–25 s, +3–5 GB RAM) |

**Steer the sound in the prompt:** `overall_soundscape:` = what the room sounds like (quiet home ambience, distant
street through the window, soft room tone); `non_diegetic_music:` = background music (e.g. *soft calm ambient
meditation music, slow pads*); put unwanted sounds into `negative:` (breathing sounds, sighs, moaning, whispering).

**Background lock:** describe only what is in the still, or write *the room exactly as in <Picture 1>, nothing added*
— listing new objects makes H3 repaint the whole background in the first second.
**Tips:** hand contact mid-clip, calm hold at the end (fingers melt in the last second); repeat the body words of
the still in the appearance lock. Don't run H3 in two ComfyUI instances at once (system RAM).
Clothed scenes are sharper on **03** (official H3); 05 is the community-finetune reference setup.

**Measured (RTX 5070 Ti 16 GB / 62 GB RAM):** {TIM.get('05', '_pending_')}"""


def wf05():
    g = Graph('05_video_h3_erosmax_i2v')
    g.group('0 · About', 'about')
    g.note(f"""# 05 · MiniMax H3 — Eros Max (reference setup)
Mirrors the Civitai reference video **143911899**: community finetune **H3 Eros Max beta5 int8** ("hybrid turbo",
8 steps without CFG) + **VBVR Pro attn-only** video-reasoning LoRA @ 0.25, euler / simple / 8 steps, BasicGuider.
**No lightx2v turbo LoRA** — the checkpoint is already distilled. beta6 exists but is heavier (8–12 steps, shift 10/3) — skipped.

Content-specific LoRAs are the user's choice; none are included. Compare with **03** (official H3 + turbo LoRA).

**Measured (RTX 5070 Ti 16 GB / 62 GB RAM):** {TIM.get('05', '_pending_')}""", w=460)

    g.group('1 · Models', 'models')
    g.note("""### 1 · Models
- **UNet** Eros Max beta5 int8 (~20 GB file, streamed with dynamic VRAM loading)
- **LoRA** VBVR Pro attn-only @ **0.25** (reference value; improves action/causality reasoning)
- Text encoder + VAEs identical to 03
- **ModelSampling H3 shift 8** is **on** (series 0: +15 % sharpness vs the model default, same time). Bypass it to get the reference setup; the old default is kept as `05_video_h3_erosmax_i2v_baseline`.""", w=420)
    unet = g.add('UNETLoader', col=1, w=440, unet_name=EROS, weight_dtype='default')
    lora = g.add('LoraLoaderModelOnly', 'LoRA · VBVR Pro attn-only @0.25', col=1, w=440, model=unet, lora_name=VBVR, strength_model=0.25)
    clip = g.add('CLIPLoader', col=1, w=440, clip_name='qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors', type='minimax', device='default')
    vv = g.add('VAELoader', 'VAE · video', col=1, w=440, vae_name='minimax_h3_video_vae_fp16.safetensors')
    av = g.add('VAELoader', 'VAE · audio', col=1, w=440, vae_name='minimax_h3_audio_vae_fp32.safetensors')
    shift = g.add('MiniMaxH3SigmaShift', 'ModelSampling H3 · shift 8', col=1, w=440, model=lora,
                  shift_video=8.0, shift_audio=3.0)

    g.group('2 · First frame', 'input')
    img = g.add('LoadImage', 'Load first frame', col=0, w=360, h=420, image='h3_first_frame.png')
    sc = g.add('ImageScaleToTotalPixels', 'Scale to video size · keeps aspect, no crop', col=0, image=img[0],
               upscale_method='lanczos', megapixels=0.70, resolution_steps=32)
    size = g.add('GetImageSize', 'Video size from image', col=0, image=sc)

    g.group('3 · Conditioning', 'prompt')
    g.note("""### 3 · Conditioning
Size comes from the first frame: scaled to the **size (MP)** budget, aspect kept, sides snapped to multiples of 32,
**no crop** (0.70 MP = 768×960 at 4:5; a 5:8 still gives 672×1088). **124 frames (5 s)**, timed shot-list. Length rule 17k+5.""", w=380)
    h3 = g.add('MiniMaxH3ImageToVideo', 'MiniMax H3 Image to Video', col=1, w=560, h=700, clip=clip, vae=vv, first_frame=sc,
               prompt=PROMPT, width=size[0], height=size[1], length=124)

    g.group('4 · Sampling', 'pass1')
    g.note("""### 4 · Sampling (reference)
RandomNoise → BasicGuider (no CFG) → **euler / simple / 8 steps**.""", w=340)
    noise = g.add('RandomNoise', col=1, noise_seed=bw.SEED)
    samp = g.add('KSamplerSelect', col=1, sampler_name='euler')
    sch = g.add('BasicScheduler', 'BasicScheduler · 8 steps', col=2, model=shift, scheduler='simple', steps=8, denoise=1.0)
    gd = g.add('BasicGuider', col=2, model=shift, conditioning=h3[0])
    sca = g.add('SamplerCustomAdvanced', col=2, noise=noise, guider=gd, sampler=samp, sigmas=sch, latent_image=h3[1])

    dv, da = decode(g, sca, vv, av)
    dv = g.add('ImageFromBatch', 'Drop frame 0 (first-frame pop)', col=0, image=dv, batch_index=1, length=4096)

    g.group('6 · Output (24 fps or 48 fps)', 'post')
    g.note("""### 6 · Output
**smooth 48 fps (RIFE)** toggle on the subgraph node picks the branch. The switch is lazy: with the toggle off,
RIFE never runs. RIFE 4.7 ×2 → 48 fps costs ≈ +15–25 s and +3–5 GB RAM.
**Drop frame 0:** frame 0 is the input still itself (sharper, slightly different colour); H3 frames start at 1 →
visible pop. `ImageFromBatch` index 1 removes it (audio 42 ms longer — inaudible).
For upscale ×2 use workflow 04 on the saved file.""", w=360)
    vol = g.add('AudioAdjustVolume', 'Sound volume (dB)', col=1, audio=da, volume=0)
    asw = g.add('ComfySwitchNode', 'Switch · sound on / off', col=1, on_true=vol, switch=True)
    da = asw
    cv = g.add('CreateVideo', 'CreateVideo · 24 fps', col=1, images=dv, audio=da, fps=24.0)
    rife = g.add('RIFE VFI', 'RIFE VFI ×2', col=1, frames=dv, ckpt_name='rife47.pth',
                 clear_cache_after_n_frames=10, multiplier=2, fast_mode=True, ensemble=True, scale_factor=1.0,
                 dtype='float32', torch_compile=False, batch_size=1)
    cv2 = g.add('CreateVideo', 'CreateVideo · 48 fps', col=1, images=rife, audio=da, fps=48.0)
    sw = g.add('ComfySwitchNode', 'Switch · 24 / 48 fps', col=2, on_false=cv, on_true=cv2, switch=False)
    save = g.add('SaveVideo', 'Save video', col=2, w=420, h=520, video=sw, filename_prefix='video/H3test_erosmax',
                 format='mp4', format__codec='h264', format__codec__encoding='re-encode', format__codec__encoding__crf=16.0)
    ui = g.to_ui()
    for n in ui['nodes']:                      # matchtype switch carries VIDEO here
        if n['id'] == asw.id:
            for io in n.get('inputs', []) + n.get('outputs', []):
                if io['type'] == 'COMFY_MATCHTYPE_V3': io['type'] = 'AUDIO'
        if n['id'] == sw.id:
            for io in n.get('inputs', []) + n.get('outputs', []):
                if io['type'] == 'COMFY_MATCHTYPE_V3': io['type'] = 'VIDEO'
    for l in ui['links']:
        if l[5] == 'COMFY_MATCHTYPE_V3': l[5] = 'AUDIO' if asw.id in (l[1], l[3]) and sw.id not in (l[1], l[3]) else 'VIDEO'
    about = ui['nodes'][0]
    about['widgets_values'] = [HOWTO]
    about['pos'], about['size'] = [0, 0], [440, 760]
    pos = {img.id: ([480, 0], [380, 460]), save.id: ([1420, 0], [440, 600])}
    for n in ui['nodes']:
        if n['id'] in pos: n['pos'], n['size'] = map(list, pos[n['id']])
    ui = wrap(ui, [about['id'], img.id, save.id], [
        ('prompt (shot-list)', 'STRING', PROMPT, [(h3.id, 'prompt')]),
        ('size (MP) · 0.70 = 768×960, no crop', 'FLOAT', 0.70, [(sc.id, 'megapixels')]),
        ('frames (124 = 5 s, 17k+5)', 'INT', 124, [(h3.id, 'length')]),
        ('seed', 'INT', bw.SEED, [(noise.id, 'noise_seed')]),
        ('shift (8 = sharper)', 'FLOAT', 8.0, [(shift.id, 'shift_video')]),
        ('sound (H3 audio)', 'BOOLEAN', True, [(asw.id, 'switch')]),
        ('sound volume (dB)', 'INT', 0, [(vol.id, 'volume')]),
        ('smooth 48 fps (RIFE)', 'BOOLEAN', False, [(sw.id, 'switch')]),
    ], 'H3 Eros Max · image → video', inst_pos=(900, 0), inst_size=(480, 760))
    p = os.path.join(bw.OUT, '05_video_h3_erosmax_i2v.json')
    json.dump(ui, open(p, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    warn = []
    api = bw.ui_to_api(ui, warn)
    print(f'  05_video_h3_erosmax_i2v.json: {len(ui["nodes"])} top nodes, {len(api)} api nodes, warnings={warn or "none"}')
    return p


if __name__ == '__main__':
    wf05()
