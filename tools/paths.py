"""Machine-specific locations. Everything is overridable by environment variables, nothing is hard-coded.

  COMFY_WF_DIR  folder the build_* scripts write to and the runners read from
                (default: <repo>/workflows; point it at <ComfyUI>/user/default/workflows/H3-test to build in place)
  COMFY_DATA    ComfyUI data folder that holds input/ and output/
                (ComfyUI Desktop: %LOCALAPPDATA%\\Comfy-Desktop\\ComfyUI-Shared; portable/git install: the ComfyUI folder)
  COMFY_URL     server for comfytool.py (default http://127.0.0.1:8189, see comfytool.py)
"""
import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WF_DIR = os.environ.get('COMFY_WF_DIR') or os.path.join(REPO, 'workflows')
PROMPTS = os.path.join(REPO, 'prompts')


def comfy_data():
    d = os.environ.get('COMFY_DATA')
    if not d:
        raise SystemExit('Set COMFY_DATA to the ComfyUI folder that contains input/ and output/')
    return d


def output_dir():
    """Base for relative media paths in sheet.py / lenstats.py: COMFY_DATA/output if set, else the current folder."""
    d = os.environ.get('COMFY_DATA')
    return os.path.join(d, 'output') if d else os.getcwd()
