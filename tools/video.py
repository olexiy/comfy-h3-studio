"""H3 video + post runner.
  python video.py h3 FRAME.png LABEL [--w 640 --h 800 --len 73 --sampler euler --steps 8 --nolora
                                      --shift V (adds ModelSamplingMiniMaxH3, audio shift 3) --prompt FILE --seed N]
  python video.py post VIDEO.mp4 LABEL [--fps 72 --mult 3 --scale 2 --omnisr]
FRAME/VIDEO relative paths are under $COMFY_DATA/output; they are copied to $COMFY_DATA/input as LABEL.ext."""
import json, os, sys, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comfytool as ct
import paths
WF = paths.WF_DIR
SH = paths.comfy_data()
a = sys.argv[1:]
def opt(k, d):
    return type(d)(a[a.index(k) + 1]) if k in a else d
mode, src, label = a[0], a[1], a[2]
srcp = src if os.path.isabs(src) else os.path.join(SH, 'output', src)
name = label + os.path.splitext(srcp)[1]
shutil.copyfile(srcp, os.path.join(SH, 'input', name))
if mode == 'h3':
    ui = json.load(open(os.path.join(WF, '03_video_h3_i2v.json'), encoding='utf-8'))
    if '--nolora' in a:
        for n in ui['nodes']:
            if n['type'] == 'LoraLoaderModelOnly': n['mode'] = 4
    api = ct.ui_to_api(ui)
    w, h, ln = opt('--w', 640), opt('--h', 800), opt('--len', 73)
    for k, v in api.items():
        c, i = v['class_type'], v['inputs']
        if c == 'LoadImage': i['image'] = name
        if c == 'ImageScale': i['width'], i['height'] = w, h
        if c == 'MiniMaxH3ImageToVideo':
            i['width'], i['height'], i['length'] = w, h, ln
            if '--prompt' in a: i['prompt'] = open(opt('--prompt', ''), encoding='utf-8').read().strip()
        if c == 'KSamplerSelect': i['sampler_name'] = opt('--sampler', 'euler')
        if c == 'BasicScheduler': i['steps'] = opt('--steps', 8)
        if c == 'RandomNoise' and '--seed' in a: i['noise_seed'] = opt('--seed', 0)
        if c == 'SaveVideo': i['filename_prefix'] = 'video/' + label
    if '--shift' in a:   # insert ModelSamplingMiniMaxH3 between model chain and scheduler/guider
        src_model = next(v['inputs']['model'] for v in api.values() if v['class_type'] == 'BasicGuider')
        api['900'] = {'class_type': 'MiniMaxH3SigmaShift', 'inputs': {'model': src_model, 'shift_video': opt('--shift', 12.0),
                      'shift_audio': 3.0}, '_meta': {'title': 'shift'}}
        for v in api.values():
            if v['class_type'] in ('BasicGuider', 'BasicScheduler'): v['inputs']['model'] = ['900', 0]
    wf = '03_video_h3_i2v.json'
else:
    ui = json.load(open(os.path.join(WF, '04_post_rife_upscale.json'), encoding='utf-8'))
    if '--omnisr' in a:
        for n in ui['nodes']:
            t = n.get('title', '')
            if 'variant' in t: n['mode'] = 0
            if t == 'Lanczos ×2': n['mode'] = 4
    api = ct.ui_to_api(ui)
    for k, v in api.items():
        c, i = v['class_type'], v['inputs']
        if c == 'LoadVideo': i['file'] = name
        if c == 'ImageScaleBy' and v['_meta']['title'] == 'Lanczos ×2': i['scale_by'] = opt('--scale', 2.0)
        if c == 'RIFE VFI': i['multiplier'] = opt('--mult', 3)
        if c == 'VHS_VideoCombine': i['frame_rate'] = opt('--fps', 72); i['filename_prefix'] = 'H3test/' + label
    wf = '04_post_rife_upscale.json'
if mode == 'post' or '--free' in a:
    ct.http('/free', {'unload_models': True, 'free_memory': True})   # drop cached H3 weights before big frame batches
rec = ct.queue_and_wait(api, label=label + ' ' + ' '.join(a[3:]), workflow=wf)
print(json.dumps({k: rec.get(k) for k in ('label', 'status', 'seconds', 'exec_seconds', 'peak_vram_mb', 'peak_ram_used_gb', 'outputs', 'error')}, ensure_ascii=False))
