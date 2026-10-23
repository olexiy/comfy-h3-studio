"""Contact sheet: python sheet.py OUT.jpg [--h 640] [--crop x0,y0,x1,y1 (fractions)] img1 img2 ...  (labels = file stems)"""
import sys, os
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths
OUTDIR = paths.output_dir()
args = sys.argv[1:]
out = args.pop(0)
H, crop = 640, None
if '--h' in args: i = args.index('--h'); H = int(args[i + 1]); del args[i:i + 2]
if '--crop' in args: i = args.index('--crop'); crop = [float(x) for x in args[i + 1].split(',')]; del args[i:i + 2]
tiles = []
for p in args:
    fp = p if os.path.isabs(p) else os.path.join(OUTDIR, p)
    im = Image.open(fp).convert('RGB')
    if crop:
        w, h = im.size; im = im.crop((int(crop[0] * w), int(crop[1] * h), int(crop[2] * w), int(crop[3] * h)))
    im = im.resize((max(1, int(im.width * H / im.height)), H), Image.LANCZOS)
    d = ImageDraw.Draw(im); d.rectangle([0, 0, im.width, 18], fill=(0, 0, 0)); d.text((4, 3), os.path.basename(p)[:40], fill=(255, 255, 0))
    tiles.append(im)
W = sum(t.width for t in tiles) + 4 * (len(tiles) - 1)
sheet = Image.new('RGB', (W, H), (40, 40, 40)); x = 0
for t in tiles: sheet.paste(t, (x, 0)); x += t.width + 4
if sheet.width > 1600: sheet = sheet.resize((1600, int(H * 1600 / sheet.width)), Image.LANCZOS)
sheet.save(out, quality=80); print(out, sheet.size)
