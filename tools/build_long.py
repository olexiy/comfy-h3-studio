"""Build 03b_video_h3_long.json (single long clip) and 03c_video_h3_chain.json (continuation via MiniMaxH3AddGuide).
python build_long.py chain            -> 03c
python build_long.py LEN PROMPT_FILE  -> 03b"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comfytool import Graph
import build_workflows as bw
import paths
OUT = paths.WF_DIR
TIM = json.load(open(os.path.join(os.path.dirname(__file__), 'timings.json'), encoding='utf-8'))
SEED = bw.SEED
OV = 22                     # anchor frames (17k+5)
CONT_PROMPT = """integrated_multimodal_description: [Shot 1] The anchored opening frames continue the previous clip exactly. Whole clip is 5 seconds. Live-action. Static medium shot of a fictional 28-year-old woman sitting on a black metal mesh bench inside a glass bus shelter in daylight.
Appearance lock: long wavy copper-red hair, freckles, mature adult face, light everyday makeup, untucked white linen blouse with rolled sleeves, dark-blue high-waisted jeans, small silver pendant, silver hoop earrings, black bag on the bench. Keep face, outfit and proportions exactly as in the opening frames.
Background lock: red brick shop with striped awning, yellow curb, glass shelter panels with soft reflections; background stays consistent.
[Shot 2] 0s-2.5s: a red city bus drives past behind the glass in the background while she smiles and watches it.
[Shot 3] 2.5s-5s: she stands up from the bench, lifts the black bag and puts its strap over her shoulder, adjusting it, then looks at the camera with a relaxed smile.
camera: handheld phone feel, almost static, very slight natural sway, no zoom, no cuts.
overall_soundscape: quiet city street ambience, distant traffic, a city bus passing, faint footsteps on the pavement.
non_diegetic_music: None.
negative: nudity, revealing clothing, morphing face, identity drift, extra fingers, warped hands, flicker, jitter, text, subtitles, watermark, music, talking."""


def models(g):
    g.group('1 · Models', 'models')
    unet = g.add('UNETLoader', col=0, w=440, unet_name='minimax_h3_fl2va_pruned_int8_convrot.safetensors', weight_dtype='default')
    lora = g.add('LoraLoaderModelOnly', 'LoRA · H3 turbo 8-step @1.0', col=0, w=440, model=unet,
                 lora_name='minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors', strength_model=1.0)
    clip = g.add('CLIPLoader', col=0, w=440, clip_name='qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors', type='minimax', device='default')
    vv = g.add('VAELoader', 'VAE · video', col=0, w=440, vae_name='minimax_h3_video_vae_fp16.safetensors')
    av = g.add('VAELoader', 'VAE · audio', col=0, w=440, vae_name='minimax_h3_audio_vae_fp32.safetensors')
    shift = g.add('MiniMaxH3SigmaShift', 'ModelSampling H3 · shift 8', col=0, w=440, model=lora, shift_video=8.0, shift_audio=3.0)
    return shift, clip, vv, av


def sampling(g, model, pos, latent, seed):
    g.group('4 · Sampling', 'pass1')
    noise = g.add('RandomNoise', col=0, noise_seed=seed)
    samp = g.add('KSamplerSelect', col=0, sampler_name='euler')
    sch = g.add('BasicScheduler', 'BasicScheduler · 8 steps', col=1, model=model, scheduler='simple', steps=8, denoise=1.0)
    gd = g.add('BasicGuider', col=1, model=model, conditioning=pos)
    return g.add('SamplerCustomAdvanced', col=1, noise=noise, guider=gd, sampler=samp, sigmas=sch, latent_image=latent)


def decode(g, sca, vv, av):
    g.group('5 · Decode', 'decode')
    dv = g.add('VAEDecodeTiled', 'VAE Decode (Tiled) · video', col=0, samples=sca[0], vae=vv, tile_size=512, overlap=64,
               temporal_size=64, temporal_overlap=8)
    da = g.add('VAEDecodeAudio', 'VAE Decode · audio', col=0, samples=sca[0], vae=av)
    return dv, da


def wf03b(length, prompt, timing):
    g = Graph('03b_video_h3_long')
    secs = round(length / 24, 1)
    g.group('0 · About', 'about')
    g.note(f"""# 03b · MiniMax H3 — long single clip ({secs} s)
Same settings as 03 (768×960, turbo 8-step, euler, shift 8) with a longer timed shot list.
**length = {length}** frames (rule 17k+5; trained range ≈ 124–362 = 5–15 s).

**Measured (RTX 5070 Ti 16 GB / 62 GB RAM):** {timing}
See `learning/minimax-h3-local.md` → *Video length limits* for the full table.

Shot-list tip: one beat per 1.5–2.5 s; give every beat a time range; keep the appearance/background locks.""", w=460)
    model, clip, vv, av = models(g)
    g.group('2 · First frame', 'input')
    img = g.add('LoadImage', 'Load first frame', col=0, w=360, h=420, image='h3_first_frame.png')
    sc = g.add('ImageScale', 'Scale to video size (lanczos)', col=0, image=img[0], upscale_method='lanczos',
               width=768, height=960, crop='center')
    g.group('3 · Conditioning', 'prompt')
    h3 = g.add('MiniMaxH3ImageToVideo', 'MiniMax H3 Image to Video', col=0, w=560, h=700, clip=clip, vae=vv,
               first_frame=sc, prompt=prompt, width=768, height=960, length=length)
    sca = sampling(g, model, h3[0], h3[1], SEED)
    dv, da = decode(g, sca, vv, av)
    g.group('6 · Save', 'save')
    cv = g.add('CreateVideo', col=0, images=dv, audio=da, fps=24.0)
    g.add('SaveVideo', 'Save video', col=1, w=420, h=520, video=cv, filename_prefix='video/H3test_long',
          format='mp4', format__codec='h264', format__codec__encoding='re-encode', format__codec__encoding__crf=16.0)
    return bw.save(g, '03b_video_h3_long.json')


def wf03c(timing):
    g = Graph('03c_video_h3_chain')
    g.group('0 · About', 'about')
    g.note(f"""# 03c · MiniMax H3 — chain clips (continuation)
Extends an existing H3 clip by ~4 s. Instead of only re-using the last frame, the **last {OV} frames + their audio** of the
previous clip are anchored at frame 0 of the new clip with core **Add Guide for MiniMax H3** → motion, light and sound continue.
The overlap is then dropped and both parts are joined (video + audio) into one file.

1. Put the previous clip into `input/` and pick it in *Load previous clip*.
2. Write the continuation shot list (beats for the new 5 s).
3. Run → `output/video/H3test_chain_*.mp4` = previous + new part. Feed the result in again to chain further.

The overlap must be 17k+5 frames (5, 22, 39 …). The official `video_minimax_h3_i2v_continuation` template only re-uses one image.
**Measured:** {timing}""", w=460)
    model, clip, vv, av = models(g)
    g.group('2 · Previous clip', 'input')
    lv = g.add('LoadVideo', 'Load previous clip', col=0, w=340, h=420, file='H3test_h3.mp4')
    comp = g.add('GetVideoComponents', col=0, video=lv)
    anchor = g.add('ImageFromBatch', f'Last {OV} frames (anchor)', col=1, image=comp['images'], batch_index=-OV, length=OV)
    first = g.add('ImageFromBatch', 'First anchor frame (= <Picture 1>)', col=1, image=anchor, batch_index=0, length=1)
    aud = g.add('TrimAudioDuration', f'Audio of last {OV} frames', col=1, audio=comp['audio'],
                start_index=round(-OV / 24, 4), duration=round(OV / 24, 4))
    g.group('3 · Conditioning', 'prompt')
    h3 = g.add('MiniMaxH3ImageToVideo', 'MiniMax H3 Image to Video', col=0, w=560, h=700, clip=clip, vae=vv,
               first_frame=first, prompt=CONT_PROMPT, width=768, height=960, length=124)
    guide = g.add('MiniMaxH3AddGuide', f'Anchor {OV} frames + audio at 0', col=1, w=340, positive=h3[0], vae=vv,
                  audio_vae=av, latent=h3[1], image=anchor, audio=aud, frame_idx=0)
    sca = sampling(g, model, guide, h3[1], SEED + 1)
    dv, da = decode(g, sca, vv, av)
    g.group('6 · Join + save', 'save')
    tail = g.add('ImageFromBatch', f'New part without {OV} overlap frames', col=0, image=dv, batch_index=OV, length=4096)
    joined = g.add('ImageBatch', 'Previous + new frames', col=0, image1=comp['images'], image2=tail)
    atail = g.add('TrimAudioDuration', 'New audio without overlap', col=1, audio=da, start_index=round(OV / 24, 4), duration=600.0)
    ajoin = g.add('AudioConcat', 'Previous + new audio', col=1, audio1=comp['audio'], audio2=atail, direction='after')
    cv = g.add('CreateVideo', col=1, images=joined, audio=ajoin, fps=24.0)
    g.add('SaveVideo', 'Save joined video', col=2, w=420, h=520, video=cv, filename_prefix='video/H3test_chain',
          format='mp4', format__codec='h264', format__codec__encoding='re-encode', format__codec__encoding__crf=16.0)
    return bw.save(g, '03c_video_h3_chain.json')


if __name__ == '__main__':
    bw.OUT = OUT
    what = sys.argv[1]
    if what == 'chain':
        wf03c(TIM.get('03c', '_pending_'))
    else:
        wf03b(int(what), open(sys.argv[2], encoding='utf-8').read().strip(), TIM.get('03b', '_pending_'))
