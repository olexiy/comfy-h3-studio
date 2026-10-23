"""Official H3 (03) vs Eros Max (05) on the same first frame / seed / shot-list.
  python eros_cmp.py WF LABEL FRAME_IN_INPUT PROMPT_FILE [--shift 8] [--len 124] [--seed N]
WF = 03 | 05. --shift on 05 inserts MiniMaxH3SigmaShift (audio shift 3) before guider/scheduler; on 03 it overrides the built-in shift."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comfytool as ct
import paths
WFDIR = paths.WF_DIR
a = sys.argv[1:]
def opt(k, d):
    return type(d)(a[a.index(k) + 1]) if k in a else d
wf = {'03': '03_video_h3_i2v.json', '05': '05_video_h3_erosmax_i2v.json'}[a[0]]
label, frame, prompt = a[1], a[2], open(a[3], encoding='utf-8').read().strip()
api = ct.ui_to_api(json.load(open(os.path.join(WFDIR, wf), encoding='utf-8')))
ln = opt('--len', 124)
for v in api.values():
    c, i = v['class_type'], v['inputs']
    if c == 'LoadImage': i['image'] = frame
    if c == 'MiniMaxH3ImageToVideo': i['prompt'], i['length'] = prompt, ln
    if c == 'RandomNoise' and '--seed' in a: i['noise_seed'] = opt('--seed', 0)
    if c == 'SaveVideo': i['filename_prefix'] = 'video/' + label
    if c == 'MiniMaxH3SigmaShift' and '--shift' in a: i['shift_video'] = opt('--shift', 8.0)
if '--shift' in a and not any(v['class_type'] == 'MiniMaxH3SigmaShift' for v in api.values()):
    src = next(v['inputs']['model'] for v in api.values() if v['class_type'] == 'BasicGuider')
    api['900'] = {'class_type': 'MiniMaxH3SigmaShift', 'inputs': {'model': src, 'shift_video': opt('--shift', 8.0),
                  'shift_audio': 3.0}, '_meta': {'title': 'shift'}}
    for v in api.values():
        if v['class_type'] in ('BasicGuider', 'BasicScheduler'): v['inputs']['model'] = ['900', 0]
if '--free' in a:
    ct.http('/free', {'unload_models': True, 'free_memory': True})   # model switch 03 <-> 05: drop the other 20 GB weights
rec = ct.queue_and_wait(api, label=label + ' ' + ' '.join(a[2:]), workflow=wf)
print(json.dumps({k: rec.get(k) for k in ('label', 'status', 'seconds', 'exec_seconds', 'peak_vram_mb', 'peak_ram_used_gb', 'outputs', 'error')}, ensure_ascii=False))
