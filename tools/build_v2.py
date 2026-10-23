"""Build the user-facing H3-test workflows in the approved style (series 0, model = old 05):
main canvas = how-to note + loader + ONE subgraph node (only the knobs the user changes + toggles) + save.
Toggles drive lazy ComfySwitchNodes, so switched-off branches never run.
  python build_v2.py            -> 01, 01b, 03, 03c, 04 into $COMFY_WF_DIR (default <repo>/workflows)
Replaces the older generators; build_workflows.py / build_long.py stay as libraries (default prompts, seed)."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comfytool import Graph, ui_to_api
import build_workflows as bw
from subgraph import wrap
import paths

OUT = paths.WF_DIR
HERE = os.path.dirname(os.path.abspath(__file__))
TIM = json.load(open(os.path.join(HERE, 'timings.json'), encoding='utf-8'))
PROMPTS = paths.PROMPTS
SEED = bw.SEED
RAM_NOTE = "Don't run H3 in two ComfyUI instances at once (62 GB RAM is shared)."


def finish(g, name, top, promote, title, extra_types, layout, inst_size=(480, 760)):
    """to_ui → concrete types for matchtype switches → place top nodes → wrap → save → check."""
    ui = g.to_ui()
    for n in ui['nodes']:
        if n['id'] in extra_types:
            for io in n.get('inputs', []) + n.get('outputs', []):
                if io['type'] == 'COMFY_MATCHTYPE_V3': io['type'] = extra_types[n['id']]
    for l in ui['links']:
        if l[5] == 'COMFY_MATCHTYPE_V3': l[5] = extra_types.get(l[3]) or extra_types.get(l[1])
    for n in ui['nodes']:
        if n['id'] in layout: n['pos'], n['size'] = [list(v) for v in layout[n['id']]]
    x_inst = max(p[0] + s[0] for p, s in layout.values() if p[0] < 1000) + 40
    ui = wrap(ui, top, promote, title, inst_pos=(x_inst, 0), inst_size=inst_size)
    os.makedirs(OUT, exist_ok=True)
    p = os.path.join(OUT, name)
    json.dump(ui, open(p, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    warn = []
    api = ui_to_api(ui, warn)
    print(f'  {name}: {len(ui["nodes"])} top nodes, {len(api)} api nodes, warnings={warn or "none"}')
    return p


def about(g, text):
    g.group('0 · About', 'about')
    return g.note(text, w=440)


# ------------------------------------------------------------------ video parts shared by 03 / 03c
def h3_models(g):
    """Official H3 + turbo LoRA, or Eros Max + VBVR (toggle); only the selected branch loads (lazy switch)."""
    g.group('1 · Models', 'models')
    g.note("""### 1 · Models
- **official** `minimax_h3_fl2va_pruned_int8_convrot` + turbo 8-step LoRA @1.0 → sharpest, best for clothed scenes
- **Eros Max** beta5 int8 (community finetune, already turbo) + VBVR Pro attn-only @0.25 → community finetune reference setup;
  ≈ 30 % softer, drifts darker (use *keep first-frame light*)
- text encoder `qwen3vl_32b_minimax_h3_nvfp4_awq` (32 B → ~58 GB system RAM), video/audio VAEs
- **shift** (MiniMaxH3SigmaShift, audio 3): 8 = sharper; lower = softer, less darkening on Eros""", w=420)
    u1 = g.add('UNETLoader', 'UNet · official H3', col=1, w=440, unet_name='minimax_h3_fl2va_pruned_int8_convrot.safetensors', weight_dtype='default')
    l1 = g.add('LoraLoaderModelOnly', 'LoRA · H3 turbo 8-step @1.0', col=1, w=440, model=u1,
               lora_name='minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors', strength_model=1.0)
    u2 = g.add('UNETLoader', 'UNet · H3 Eros Max beta5', col=1, w=440, unet_name='h3ErosMax_beta5_3185154.safetensors', weight_dtype='default')
    l2 = g.add('LoraLoaderModelOnly', 'LoRA · VBVR Pro attn-only @0.25', col=1, w=440, model=u2,
               lora_name='H3_VBVR_Pro_attn_only.safetensors', strength_model=0.25)
    msw = g.add('ComfySwitchNode', 'Switch · official / Eros Max', col=2, on_false=l1, on_true=l2, switch=False)
    clip = g.add('CLIPLoader', col=2, w=440, clip_name='qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors', type='minimax', device='default')
    vv = g.add('VAELoader', 'VAE · video', col=2, w=440, vae_name='minimax_h3_video_vae_fp16.safetensors')
    av = g.add('VAELoader', 'VAE · audio', col=2, w=440, vae_name='minimax_h3_audio_vae_fp32.safetensors')
    shift = g.add('MiniMaxH3SigmaShift', 'ModelSampling H3 · shift', col=2, w=440, model=msw, shift_video=8.0, shift_audio=3.0)
    return shift, clip, vv, av, msw


def h3_sample(g, model, pos, latent, seed):
    g.group('4 · Sampling', 'pass1')
    noise = g.add('RandomNoise', col=0, noise_seed=seed)
    samp = g.add('KSamplerSelect', col=0, sampler_name='euler')
    sch = g.add('BasicScheduler', 'BasicScheduler · 8 steps', col=1, model=model, scheduler='simple', steps=8, denoise=1.0)
    gd = g.add('BasicGuider', col=1, model=model, conditioning=pos)
    sca = g.add('SamplerCustomAdvanced', col=1, noise=noise, guider=gd, sampler=samp, sigmas=sch, latent_image=latent)
    return noise, sca


def h3_output(g, sca, vv, av, ref, frames_in=None, audio_in=None, overlap=0):
    """Decode → drop frame 0 → light lock vs ref → (join with previous clip) → sound switch → 24/48 fps switch."""
    g.group('5 · Decode + finish', 'decode')
    g.note("""### 5 · Decode + finish
- **drop frame 0**: frame 0 is the input still itself (sharper, other colour) → visible pop
- **keep first-frame light**: ColorMatch mkl of every frame against the first frame — stops the slow darkening/warming drift
- **sound**: H3 audio through a volume stage; off = no audio track
- **smooth 48 fps**: RIFE 4.7 ×2 (+15–25 s, +3–5 GB RAM); lazy switch, off = never runs""", w=380)
    dv = g.add('VAEDecodeTiled', 'VAE Decode (Tiled) · video', col=1, samples=sca[0], vae=vv, tile_size=512, overlap=64,
               temporal_size=64, temporal_overlap=8)
    da = g.add('VAEDecodeAudio', 'VAE Decode · audio', col=1, samples=sca[0], vae=av)
    start = overlap if overlap else 1
    cut = g.add('ImageFromBatch', f'Drop first {start} frame(s)', col=1, image=dv, batch_index=start, length=4096)
    cm = g.add('ColorMatch', 'Keep first-frame light (ColorMatch mkl)', col=2, image_ref=ref, image_target=cut, method='mkl',
               strength=1.0, multithread=True)
    lsw = g.add('ComfySwitchNode', 'Switch · light lock', col=2, on_true=cm, on_false=cut, switch=True)
    frames, audio = lsw, da
    if frames_in is not None:          # chain: previous clip + new part
        frames = g.add('ImageBatch', 'Previous + new frames', col=2, image1=frames_in, image2=lsw)
        atail = g.add('TrimAudioDuration', 'New audio without overlap', col=2, audio=da, start_index=round(overlap / 24, 4), duration=600.0)
        audio = g.add('AudioConcat', 'Previous + new audio', col=2, audio1=audio_in, audio2=atail, direction='after')
    else:
        audio = g.add('TrimAudioDuration', 'Audio without frame 0', col=2, audio=da, start_index=round(1 / 24, 4), duration=600.0)
    g.group('6 · Output', 'post')
    vol = g.add('AudioAdjustVolume', 'Sound volume (dB)', col=0, audio=audio, volume=0)
    asw = g.add('ComfySwitchNode', 'Switch · sound', col=0, on_true=vol, switch=True)
    cv = g.add('CreateVideo', 'CreateVideo · 24 fps', col=1, images=frames, audio=asw, fps=24.0)
    rife = g.add('RIFE VFI', 'RIFE VFI ×2', col=1, frames=frames, ckpt_name='rife47.pth', clear_cache_after_n_frames=10,
                 multiplier=2, fast_mode=True, ensemble=True, scale_factor=1.0, dtype='float32', torch_compile=False, batch_size=1)
    cv2 = g.add('CreateVideo', 'CreateVideo · 48 fps', col=1, images=rife, audio=asw, fps=48.0)
    fsw = g.add('ComfySwitchNode', 'Switch · 24 / 48 fps', col=2, on_false=cv, on_true=cv2, switch=False)
    return fsw, lsw, asw, vol


VIDEO_TIPS = f"""**Prompt tips:** timed shot-list (`[Shot N] 0s-2s: …`); appearance lock repeats the body/outfit words of the still;
background lock = *the room exactly as in <Picture 1>, nothing added* (listing new objects repaints the background);
`Lighting lock: exposure, white balance and light exactly as in <Picture 1>`; no mood words (warm, dim, cosy) anywhere,
also not in `non_diegetic_music:`; hand contact mid-clip, calm hold at the end; unwanted sounds into `negative:`.
{RAM_NOTE}"""


def wf03():
    g = Graph('03_video_h3_i2v')
    a = about(g, f"""# 03 · MiniMax H3 — image → video
**Use:** pick the first frame in *Load first frame* → write the shot-list in **prompt** on the middle node → Run.
Everything technical lives inside the subgraph (double-click its title; the breadcrumb brings you back).

| Field | Meaning |
|---|---|
| size (MP) | pixel budget; aspect from your image, **never cropped**; 0.70 ≈ 768×960 (best quality/time) |
| frames | 17k+5 → 124 = 5 s · 226 = 9 s · 294 = 12 s (local max; longer → 03c) |
| seed / shift | same seed + frame = repeatable · shift 8 = sharper |
| Eros Max | off = official H3 (sharper, clothed scenes) · on = Eros Max community finetune |
| keep first-frame light | ColorMatch against darkening/warming drift; off if the light should change |
| sound / volume | off = no audio track · dB (−6 = half) |
| smooth 48 fps | RIFE ×2 |

{VIDEO_TIPS}

**Measured:** official {TIM.get('03', '')} · Eros Max {TIM.get('05', '')}""")
    model, clip, vv, av, msw = h3_models(g)
    g.group('2 · First frame', 'input')
    img = g.add('LoadImage', 'Load first frame', col=0, w=360, h=420, image='h3_first_frame.png')
    sc = g.add('ImageScaleToTotalPixels', 'Scale to video size · keeps aspect, no crop', col=1, image=img[0],
               upscale_method='lanczos', megapixels=0.70, resolution_steps=32)
    size = g.add('GetImageSize', 'Video size from image', col=1, image=sc)
    g.group('3 · Conditioning', 'prompt')
    h3 = g.add('MiniMaxH3ImageToVideo', 'MiniMax H3 Image to Video', col=0, w=560, h=700, clip=clip, vae=vv, first_frame=sc,
               prompt=open(os.path.join(PROMPTS, 'prompt_5s.txt'), encoding='utf-8').read().strip(),
               width=size[0], height=size[1], length=124)
    noise, sca = h3_sample(g, model, h3[0], h3[1], SEED)
    fsw, lsw, asw, vol = h3_output(g, sca, vv, av, sc)
    save = g.add('SaveVideo', 'Save video', col=2, w=440, h=600, video=fsw, filename_prefix='video/H3test_h3',
                 format='mp4', format__codec='h264', format__codec__encoding='re-encode', format__codec__encoding__crf=16.0)
    return finish(g, '03_video_h3_i2v.json', [a.id, img.id, save.id], [
        ('prompt (shot-list)', 'STRING', h3.widgets['prompt'], [(h3.id, 'prompt')]),
        ('size (MP) · 0.70 = 768×960, no crop', 'FLOAT', 0.70, [(sc.id, 'megapixels')]),
        ('frames (124 = 5 s, 17k+5)', 'INT', 124, [(h3.id, 'length')]),
        ('seed', 'INT', SEED, [(noise.id, 'noise_seed')]),
        ('shift (8 = sharper)', 'FLOAT', 8.0, [(model.id, 'shift_video')]),
        ('Eros Max (community finetune)', 'BOOLEAN', False, [(msw.id, 'switch')]),
        ('keep first-frame light', 'BOOLEAN', True, [(lsw.id, 'switch')]),
        ('sound (H3 audio)', 'BOOLEAN', True, [(asw.id, 'switch')]),
        ('sound volume (dB)', 'INT', 0, [(vol.id, 'volume')]),
        ('smooth 48 fps (RIFE)', 'BOOLEAN', False, [(fsw.id, 'switch')]),
    ], 'H3 · image → video', {msw.id: 'MODEL', lsw.id: 'IMAGE', asw.id: 'AUDIO', fsw.id: 'VIDEO'},
        {a.id: ((0, 0), (440, 900)), img.id: ((480, 0), (380, 460)), save.id: ((1440, 0), (440, 600))})


def wf03c():
    OV = 22
    g = Graph('03c_video_h3_chain')
    a = about(g, f"""# 03c · MiniMax H3 — continue a clip (+5 s)
**Use:** pick the previous clip in *Load previous clip* → write the shot-list for the **new** 5 s → Run →
`video/H3test_chain_*.mp4` = previous + new part. Feed the result in again to chain further (no length limit).

The last **{OV} frames + their audio** of the previous clip are anchored at frame 0 of the new part
(`MiniMaxH3AddGuide`), so motion, light and sound continue; the overlap is dropped and both parts are joined.
Size follows the previous clip automatically. Fields as in 03 (seed, shift, Eros Max, light lock, sound, 48 fps).

{VIDEO_TIPS}

**Measured:** {TIM.get('03c', '')}""")
    model, clip, vv, av, msw = h3_models(g)
    g.group('2 · Previous clip', 'input')
    lv = g.add('LoadVideo', 'Load previous clip', col=0, w=360, h=420, file='H3test_h3.mp4')
    comp = g.add('GetVideoComponents', col=1, video=lv)
    anchor = g.add('ImageFromBatch', f'Last {OV} frames (anchor)', col=1, image=comp['images'], batch_index=-OV, length=OV)
    first = g.add('ImageFromBatch', 'First anchor frame (= <Picture 1>)', col=1, image=anchor, batch_index=0, length=1)
    size = g.add('GetImageSize', 'Size of previous clip', col=1, image=first)
    aud = g.add('TrimAudioDuration', f'Audio of last {OV} frames', col=1, audio=comp['audio'],
                start_index=round(-OV / 24, 4), duration=round(OV / 24, 4))
    g.group('3 · Conditioning', 'prompt')
    h3 = g.add('MiniMaxH3ImageToVideo', 'MiniMax H3 Image to Video', col=0, w=560, h=700, clip=clip, vae=vv, first_frame=first,
               prompt=__import__('build_long').CONT_PROMPT, width=size[0], height=size[1], length=124)
    guide = g.add('MiniMaxH3AddGuide', f'Anchor {OV} frames + audio at 0', col=1, w=340, positive=h3[0], vae=vv,
                  audio_vae=av, latent=h3[1], image=anchor, audio=aud, frame_idx=0)
    noise, sca = h3_sample(g, model, guide, h3[1], SEED + 1)
    fsw, lsw, asw, vol = h3_output(g, sca, vv, av, first, frames_in=comp['images'], audio_in=comp['audio'], overlap=OV)
    save = g.add('SaveVideo', 'Save joined video', col=2, w=440, h=600, video=fsw, filename_prefix='video/H3test_chain',
                 format='mp4', format__codec='h264', format__codec__encoding='re-encode', format__codec__encoding__crf=16.0)
    return finish(g, '03c_video_h3_chain.json', [a.id, lv.id, save.id], [
        ('prompt (new 5 s)', 'STRING', h3.widgets['prompt'], [(h3.id, 'prompt')]),
        ('frames of new part (124 = 5 s)', 'INT', 124, [(h3.id, 'length')]),
        ('seed', 'INT', SEED + 1, [(noise.id, 'noise_seed')]),
        ('shift (8 = sharper)', 'FLOAT', 8.0, [(model.id, 'shift_video')]),
        ('Eros Max (community finetune)', 'BOOLEAN', False, [(msw.id, 'switch')]),
        ('keep light of previous clip', 'BOOLEAN', True, [(lsw.id, 'switch')]),
        ('sound (H3 audio)', 'BOOLEAN', True, [(asw.id, 'switch')]),
        ('sound volume (dB)', 'INT', 0, [(vol.id, 'volume')]),
        ('smooth 48 fps (RIFE)', 'BOOLEAN', False, [(fsw.id, 'switch')]),
    ], 'H3 · continue clip', {msw.id: 'MODEL', lsw.id: 'IMAGE', asw.id: 'AUDIO', fsw.id: 'VIDEO'},
        {a.id: ((0, 0), (440, 760)), lv.id: ((480, 0), (380, 460)), save.id: ((1440, 0), (440, 600))})


# ------------------------------------------------------------------ 04 post
def wf04():
    g = Graph('04_post_upscale_rife')
    a = about(g, f"""# 04 · Post: upscale + smooth an existing video
**Use:** pick a finished H3 clip in *Load video* → set the fields → Run → `H3test/post_*.mp4`.

| Field | Meaning |
|---|---|
| upscale ×2 | lanczos ×2 (768×960 → 1536×1920); the reference author's method — fast, no invented detail |
| smooth (RIFE) | frame interpolation; **multiplier** 2 = 48 fps, 3 = 72 fps (×3 at 1536×1920 needs ~61 GB RAM) |
| fps | must be 24 × multiplier, otherwise motion speed changes |

Audio is passed through. OmniSR model upscale was tested: 2.4× slower, no visible gain → dropped.

**Measured:** {TIM.get('04', '')}""")
    g.group('1 · Load', 'input')
    lv = g.add('LoadVideo', 'Load video', col=0, w=360, h=420, file='H3test_h3.mp4')
    comp = g.add('GetVideoComponents', col=1, video=lv)
    g.group('2 · Upscale + RIFE', 'upscale')
    up = g.add('ImageScaleBy', 'Lanczos ×2', col=0, image=comp['images'], upscale_method='lanczos', scale_by=2.0)
    usw = g.add('ComfySwitchNode', 'Switch · upscale', col=0, on_true=up, on_false=comp['images'], switch=True)
    rife = g.add('RIFE VFI', 'RIFE VFI (rife47)', col=1, frames=usw, ckpt_name='rife47.pth', clear_cache_after_n_frames=10,
                 multiplier=2, fast_mode=True, ensemble=True, scale_factor=1.0, dtype='float32', torch_compile=False, batch_size=1)
    rsw = g.add('ComfySwitchNode', 'Switch · RIFE', col=1, on_true=rife, on_false=usw, switch=True)
    cv = g.add('CreateVideo', 'CreateVideo', col=2, images=rsw, audio=comp['audio'], fps=48.0)
    save = g.add('SaveVideo', 'Save video', col=2, w=440, h=600, video=cv, filename_prefix='H3test/post',
                 format='mp4', format__codec='h264', format__codec__encoding='re-encode', format__codec__encoding__crf=14.0)
    return finish(g, '04_post_upscale_rife.json', [a.id, lv.id, save.id], [
        ('upscale ×2 (lanczos)', 'BOOLEAN', True, [(usw.id, 'switch')]),
        ('smooth (RIFE)', 'BOOLEAN', True, [(rsw.id, 'switch')]),
        ('RIFE multiplier (2 = 48 fps)', 'INT', 2, [(rife.id, 'multiplier')]),
        ('fps (24 × multiplier)', 'FLOAT', 48.0, [(cv.id, 'fps')]),
    ], 'Post · upscale + RIFE', {usw.id: 'IMAGE', rsw.id: 'IMAGE'},
        {a.id: ((0, 0), (440, 620)), lv.id: ((480, 0), (380, 460)), save.id: ((1440, 0), (440, 600))}, inst_size=(480, 320))


# ------------------------------------------------------------------ 01 / 01b stills
def krea_models(g, loras_default, realism=0.5):
    g.group('1 · Models', 'models')
    unet = g.add('UNETLoader', col=0, w=400, unet_name='krea2_turbo_int8_convrot.safetensors', weight_dtype='default')
    clip = g.add('CLIPLoader', col=0, w=400, clip_name='qwen3vl_4b_fp8_scaled.safetensors', type='krea2', device='default')
    l1 = g.add('LoraLoader', 'LoRA · Realism Engine', col=1, w=360, model=unet, clip=clip,
               lora_name='realism_engine_krea2_v3.1.safetensors', strength_model=realism, strength_clip=realism)
    l2 = g.add('LoraLoader', 'LoRA · Realistic Snapshot @0.9', col=1, w=360, model=l1[0], clip=l1[1],
               lora_name='RealisticSnapshotKrea2V2.safetensors', strength_model=0.9, strength_clip=0.9)
    ms = g.add('ComfySwitchNode', 'Switch · LoRAs (model)', col=2, on_true=l2[0], on_false=unet, switch=loras_default)
    cs = g.add('ComfySwitchNode', 'Switch · LoRAs (clip)', col=2, on_true=l2[1], on_false=clip, switch=loras_default)
    return ms, cs, l1, (ms, cs)


IMG_TIPS = """**Prompt tips:** booru-style tags work as well as prose (`photo \\(medium\\), crisp detailed instagram photograph` = glossy,
`amateur phone photo` = raw). Body shape needs **strong**, concrete build words
plus a body–pose relation — soft words (large, full, curvy hourglass) are ignored at cfg 1.
Write the age explicitly (25+, late-20s, mature facial features). For video stills use a 4:5 size (896×1120)."""


def wf01b():
    g = Graph('01b_image_krea2_simple')
    a = about(g, f"""# 01b · Krea 2 — fast & natural (one pass)
**Use:** write the **prompt** on the node → set size → Run → `H3test/krea2_simple_*.png`. 13–32 s.
One pass, 8 steps, euler/beta, cfg 1, `qwen_image_vae` — the most natural "phone photo" look.
**realism LoRAs** toggle adds Realism Engine 0.5 + Realistic Snapshot 0.9 (glossier).

{IMG_TIPS}

**Measured:** {TIM.get('01b', '')}""")
    ms, cs, l1, sws = krea_models(g, False)
    vae = g.add('VAELoader', col=2, w=400, vae_name='qwen_image_vae.safetensors')
    g.group('2 · Sample', 'pass1')
    pos = g.add('CLIPTextEncode', 'Positive prompt', col=0, w=420, h=300, clip=cs, text=bw.PROMPT_SIMPLE)
    neg = g.add('ConditioningZeroOut', 'Negative = zero (cfg 1)', col=0, conditioning=pos)
    lat = g.add('EmptyLatentImage', 'Empty Latent', col=1, width=896, height=1120, batch_size=1)
    ks = g.add('KSampler', 'KSampler · 8 steps euler/beta', col=1, model=ms, positive=pos, negative=neg, latent_image=lat,
               seed=SEED, steps=8, cfg=1.0, sampler_name='euler', scheduler='beta', denoise=1.0)
    dec = g.add('VAEDecode', col=1, samples=ks, vae=vae)
    save = g.add('SaveImage', 'Save image', col=2, w=440, h=600, images=dec, filename_prefix='H3test/krea2_simple')
    return finish(g, '01b_image_krea2_simple.json', [a.id, save.id], [
        ('prompt', 'STRING', bw.PROMPT_SIMPLE, [(pos.id, 'text')]),
        ('width (4:5 for video: 896)', 'INT', 896, [(lat.id, 'width')]),
        ('height (4:5 for video: 1120)', 'INT', 1120, [(lat.id, 'height')]),
        ('seed', 'INT', SEED, [(ks.id, 'seed')]),
        ('realism LoRAs', 'BOOLEAN', False, [(ms.id, 'switch'), (cs.id, 'switch')]),
    ], 'Krea 2 · fast still', {ms.id: 'MODEL', cs.id: 'CLIP'},
        {a.id: ((0, 0), (440, 640)), save.id: ((1000, 0), (440, 600))}, inst_size=(480, 560))


def wf01():
    W, H = 896, 1120
    g = Graph('01_image_krea2_realism')
    a = about(g, f"""# 01 · Krea 2 — realism recipe (2 passes + face + upscale)
**Use:** write the **prompt** on the node → Run → `H3test/krea2_*.png`. ≈ 55–110 s.
Recipe of Civitai *just_a_prompt_guy* with the series-0 "AI face" fixes: Realism Engine **0.5** + Realistic Snapshot 0.9,
pass 1 8 steps euler_ancestral/sgm_uniform → latent ×1.5 hi-res pass (4 steps, denoise 0.54) + ColorMatch →
FaceDetailer (1440 px, denoise 0.5) → Ultimate SD Upscale ×1.9 (OmniSR, denoise **0.22**).

| Field | Meaning |
|---|---|
| width / height | base size; **896×1120 (4:5) for video stills**, 1000×1600 for tall photos |
| realism strength | Realism Engine LoRA; 0.5 tested best, 0.7 = glossy "AI face" |
| face detail | FaceDetailer pass (fixes small faces) |
| upscale ×1.9 | USDU to ≈ 2.5–2.9 K; off = hi-res size, faster |

{IMG_TIPS}

**Measured:** {TIM.get('01', '')}""")
    g.group('1 · Models', 'models')
    unet = g.add('UNETLoader', col=0, w=400, unet_name='krea2_turbo_int8_convrot.safetensors', weight_dtype='default')
    clip = g.add('CLIPLoader', col=0, w=400, clip_name='qwen3vl_4b_fp8_scaled.safetensors', type='krea2', device='default')
    vae = g.add('VAELoader', 'VAE · wan 2.1', col=0, w=400, vae_name='wan_2.1_vae.safetensors')
    l1 = g.add('LoraLoader', 'LoRA · Realism Engine', col=1, w=360, model=unet, clip=clip,
               lora_name='realism_engine_krea2_v3.1.safetensors', strength_model=0.5, strength_clip=0.5)
    l2 = g.add('LoraLoader', 'LoRA · Realistic Snapshot @0.9', col=1, w=360, model=l1[0], clip=l1[1],
               lora_name='RealisticSnapshotKrea2V2.safetensors', strength_model=0.9, strength_clip=0.9)
    model, clipm = l2[0], l2[1]
    g.group('2 · Pass 1', 'pass1')
    pos = g.add('CLIPTextEncode', 'Positive prompt', col=0, w=420, h=440, clip=clipm, text=bw.PROMPT_IMG)
    neg = g.add('ConditioningZeroOut', 'Negative = zero (cfg 1)', col=0, conditioning=pos)
    lat = g.add('EmptyLatentImage', 'Empty Latent · base size', col=1, width=W, height=H, batch_size=1)
    ks1 = g.add('KSamplerAdvanced', 'KSampler · pass 1', col=1, model=model, positive=pos, negative=neg, latent_image=lat,
                add_noise='enable', noise_seed=SEED, steps=8, cfg=1.0, sampler_name='euler_ancestral', scheduler='sgm_uniform',
                start_at_step=0, end_at_step=10000, return_with_leftover_noise='disable')
    dec1 = g.add('VAEDecode', 'VAE Decode · pass 1', col=1, samples=ks1, vae=vae)
    g.group('3 · Hi-res pass', 'hires')
    up = g.add('LatentUpscaleBy', col=0, samples=ks1, upscale_method='bicubic', scale_by=1.5)
    ks2 = g.add('KSampler', 'KSampler · hi-res', col=0, model=model, positive=pos, negative=neg, latent_image=up, seed=SEED,
                steps=4, cfg=1.0, sampler_name='euler', scheduler='simple', denoise=0.54)
    dec2 = g.add('VAEDecode', 'VAE Decode · hi-res', col=1, samples=ks2, vae=vae)
    cm = g.add('ColorMatch', 'ColorMatch → pass 1', col=1, image_ref=dec1, image_target=dec2, method='hm-mkl-hm', strength=0.22, multithread=True)
    g.group('4 · Face + upscale', 'face')
    det = g.add('UltralyticsDetectorProvider', col=0, model_name='bbox/face_yolov8m.pt')
    fd = g.add('FaceDetailer', 'FaceDetailer', col=0, w=360, image=cm, model=model, clip=clipm, vae=vae, positive=pos, negative=neg,
               bbox_detector=det['BBOX_DETECTOR'], guide_size=1440, guide_size_for=True, max_size=1440, seed=SEED, steps=4, cfg=1.0,
               sampler_name='dpmpp_2m_sde', scheduler='sgm_uniform', denoise=0.5, feather=5, noise_mask=True, force_inpaint=True,
               bbox_threshold=0.5, bbox_dilation=10, bbox_crop_factor=3.0, sam_detection_hint='center-1', drop_size=10, cycle=1)
    fsw = g.add('ComfySwitchNode', 'Switch · face detail', col=1, on_true=fd['image'], on_false=cm, switch=True)
    hw, hh = int(W * 1.5), int(H * 1.5)
    um = g.add('UpscaleModelLoader', col=1, model_name='OmniSR_X4_DIV2K.safetensors')
    us = g.add('UltimateSDUpscale', 'Ultimate SD Upscale ×1.9', col=2, w=360, image=fsw, model=model, positive=pos, negative=neg,
               vae=vae, upscale_model=um, upscale_by=1.9, seed=SEED, steps=2, cfg=1.0, sampler_name='euler', scheduler='simple',
               denoise=0.22, mode_type='Linear', tile_width=int(round((hw * 1.9 + 192) / 2 / 8) * 8),
               tile_height=int(round((hh * 1.9 + 192) / 2 / 8) * 8), mask_blur=64, tile_padding=96, seam_fix_mode='None',
               seam_fix_denoise=1.0, seam_fix_width=64, seam_fix_mask_blur=8, seam_fix_padding=16, force_uniform_tiles=True,
               tiled_decode=False, batch_size=1)
    usw = g.add('ComfySwitchNode', 'Switch · upscale', col=2, on_true=us, on_false=fsw, switch=True)
    save = g.add('SaveImage', 'Save image', col=2, w=440, h=600, images=usw, filename_prefix='H3test/krea2')
    return finish(g, '01_image_krea2_realism.json', [a.id, save.id], [
        ('prompt', 'STRING', bw.PROMPT_IMG, [(pos.id, 'text')]),
        ('width (4:5 for video: 896)', 'INT', W, [(lat.id, 'width')]),
        ('height (4:5 for video: 1120)', 'INT', H, [(lat.id, 'height')]),
        ('seed', 'INT', SEED, [(ks1.id, 'noise_seed'), (ks2.id, 'seed'), (fd.id, 'seed'), (us.id, 'seed')]),
        ('realism strength', 'FLOAT', 0.5, [(l1.id, 'strength_model'), (l1.id, 'strength_clip')]),
        ('face detail', 'BOOLEAN', True, [(fsw.id, 'switch')]),
        ('upscale ×1.9', 'BOOLEAN', True, [(usw.id, 'switch')]),
    ], 'Krea 2 · realism still', {fsw.id: 'IMAGE', usw.id: 'IMAGE'},
        {a.id: ((0, 0), (440, 820)), save.id: ((1000, 0), (440, 600))}, inst_size=(480, 620))


if __name__ == '__main__':
    for f in (wf01, wf01b, wf03, wf03c, wf04): f()
