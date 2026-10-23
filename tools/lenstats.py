"""python lenstats.py OUT.jpg [--cols 6] video1.mp4 ... (run with the ComfyUI venv python: needs numpy)
Per video: frames, sharpness (Laplacian var) at start/mid/end thirds, temporal diff, face drift first->last and
first->max over the clip; grid row = N evenly spaced full frames (for checking which beats play)."""
import sys, os, subprocess, numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths
OUT = paths.output_dir()
a = sys.argv[1:]; out = a.pop(0); cols = 6
if '--cols' in a: i = a.index('--cols'); cols = int(a[i + 1]); del a[i:i + 2]
def frames(p):
    w, h = map(int, subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height',
                                    '-of', 'csv=p=0', p], capture_output=True, text=True).stdout.strip().split(','))
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', p, '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, h, w, 3)
def lap(x):
    return np.var(np.abs(np.diff(x, 2, 0))[:, 1:-1] + np.abs(np.diff(x, 2, 1))[1:-1])
rows = []
print('video'.ljust(24), 'frames  sharp start/mid/end   tempdiff  drift last / max')
for p in a:
    fp = p if os.path.isabs(p) else os.path.join(OUT, p)
    F = frames(fp); n, H, W, _ = F.shape; g = F.mean(-1)
    thirds = [np.mean([lap(g[k]) for k in range(s, e, 4)]) for s, e in ((0, n // 3), (n // 3, 2 * n // 3), (2 * n // 3, n))]
    td = np.abs(np.diff(g[::2], axis=0)).mean()
    fc = lambda x: x[int(.04 * H):int(.40 * H), int(.25 * W):int(.75 * W)]
    dr = [np.abs(fc(g[0]) - fc(g[k])).mean() for k in range(0, n, 6)]
    print(os.path.basename(p)[:24].ljust(24), str(n).ljust(7), ' / '.join(f'{x:5.0f}' for x in thirds).ljust(22),
          f'{td:7.2f}   {dr[-1]:6.1f} / {max(dr):6.1f}')
    th = 240; tiles = []
    for k in np.linspace(0, n - 1, cols).astype(int):
        im = Image.fromarray(F[k]); im = im.resize((int(im.width * th / im.height), th), Image.LANCZOS)
        ImageDraw.Draw(im).text((3, 3), f'{k / 24:.1f}s', fill=(255, 255, 0)); tiles.append(im)
    row = Image.new('RGB', (sum(t.width for t in tiles) + 3 * cols, th + 14), (30, 30, 30)); x = 0
    for t in tiles: row.paste(t, (x, 14)); x += t.width + 3
    ImageDraw.Draw(row).text((3, 1), os.path.basename(p), fill=(255, 255, 255)); rows.append(row)
G = Image.new('RGB', (max(r.width for r in rows), sum(r.height + 3 for r in rows)), (30, 30, 30)); y = 0
for r in rows: G.paste(r, (0, y)); y += r.height + 3
if G.width > 1400: G = G.resize((1400, int(G.height * 1400 / G.width)), Image.LANCZOS)
G.save(out, quality=82); print(out, G.size)
