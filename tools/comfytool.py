"""comfytool - build ComfyUI UI workflows from a compact spec, convert UI -> API, queue + measure.

CLI:
  python comfytool.py refresh                         # re-download /object_info into <repo>/object_info.json
  python comfytool.py api  WF.json [OUT.json]         # UI workflow -> API prompt (prints summary)
  python comfytool.py check WF.json                   # missing node types / widget-count problems
  python comfytool.py queue WF.json [--label L] [--set "Title:input=value" ...] [--no-wait] [--timeout S]
                                                     # convert, POST /prompt, wait, log timing + peak VRAM/RAM
Library: Graph (builder), ui_to_api(), queue_and_wait().
"""
import json, os, sys, time, uuid, subprocess, threading, urllib.request, urllib.error, copy

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(HERE)
OI_PATH = os.path.join(BASE, 'object_info.json')
RESULTS = os.path.join(BASE, 'results.json')
SERVER = os.environ.get('COMFY_URL', 'http://127.0.0.1:8189')
WIDGET_TYPES = ('INT', 'FLOAT', 'STRING', 'BOOLEAN', 'COMBO')
FRONTEND_ONLY = {'Note', 'MarkdownNote', 'Reroute', 'PrimitiveNode', 'Label (rgthree)'}

# ---------------------------------------------------------------- object_info
_OI = None
def http(path, data=None, timeout=30):
    req = urllib.request.Request(SERVER + path, data=json.dumps(data).encode() if data is not None else None,
                                 headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read() or b'null')
    except urllib.error.HTTPError as e:
        body = e.read()
        try: return json.loads(body)
        except Exception: return {'error': {'message': body.decode(errors='replace')[:2000]}, 'http_status': e.code}
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
        return None

def oi(refresh=False):
    global _OI
    if refresh or (_OI is None and not os.path.exists(OI_PATH)):
        _OI = http('/object_info', timeout=120)
        json.dump(_OI, open(OI_PATH, 'w', encoding='utf-8'))
    if _OI is None:
        _OI = json.load(open(OI_PATH, encoding='utf-8'))
    return _OI

def ordered_inputs(spec_inputs, order=None):
    out = []
    for sec in ('required', 'optional'):
        d = spec_inputs.get(sec) or {}
        names = (order or {}).get(sec) or list(d.keys())
        for n in names:
            if n in d: out.append((n, d[n], sec))
    return out

def node_inputs(cls):
    v = oi().get(cls)
    if v is None: return None
    return ordered_inputs(v['input'], v.get('input_order'))

def _opts(spec): return spec[1] if len(spec) > 1 and isinstance(spec[1], dict) else {}

def is_widget(spec):
    t, o = spec[0], _opts(spec)
    if o.get('forceInput') or o.get('hidden'): return False
    if isinstance(t, list): return True
    return t in WIDGET_TYPES or t == 'COMFY_DYNAMICCOMBO_V3'

def has_control(name, spec, top):
    o = _opts(spec)
    return spec[0] == 'INT' and (bool(o.get('control_after_generate')) or (top and name in ('seed', 'noise_seed')))

def has_upload(spec):
    o = _opts(spec)
    return any(o.get(k) for k in ('image_upload', 'video_upload', 'audio_upload', 'animated_image_upload'))

def default_of(spec):
    t, o = spec[0], _opts(spec)
    if 'default' in o: return o['default']
    if isinstance(t, list): return t[0] if t else ''
    if t == 'COMBO': return (o.get('options') or [''])[0]
    if t == 'COMFY_DYNAMICCOMBO_V3': return o['options'][0]['key']
    return {'INT': 0, 'FLOAT': 0.0, 'STRING': '', 'BOOLEAN': False}.get(t)

def _dyn_option(spec, key):
    for op in _opts(spec).get('options', []):
        if op['key'] == key: return op
    return None

def widgets_from_values(cls, values, warn=None):
    """UI widgets_values (list or dict) -> {api_input_name: value}."""
    ins = node_inputs(cls)
    if ins is None: return {}
    if isinstance(values, dict):   # VHS style
        return {k: v for k, v in values.items() if k not in ('videopreview',) and not isinstance(v, dict)}
    values = list(values or [])
    out, idx = {}, 0
    def walk(items, prefix, top):
        nonlocal idx
        for name, spec, _ in items:
            if not is_widget(spec): continue
            full = prefix + name
            if idx >= len(values):
                return
            v = values[idx]; idx += 1
            out[full] = v
            if spec[0] == 'COMFY_DYNAMICCOMBO_V3':
                op = _dyn_option(spec, v)
                if op: walk(ordered_inputs(op.get('inputs', {})), full + '.', False)
                continue
            if has_control(name, spec, top): idx += 1
            if has_upload(spec) and idx < len(values) and values[idx] in ('image', 'video', 'audio', None, ''):
                idx += 1
    walk(ins, '', True)
    if warn is not None and idx != len(values):
        warn.append(f'{cls}: consumed {idx} of {len(values)} widget values')
    return out

def values_from_widgets(cls, given):
    """{name: value} (dotted names for dynamic combos) -> UI widgets_values list, defaults for the rest."""
    ins = node_inputs(cls)
    if ins is None: raise KeyError(f'unknown node type {cls}')
    vals, used = [], set()
    def walk(items, prefix, top):
        for name, spec, _ in items:
            if not is_widget(spec): continue
            full = prefix + name
            v = given[full] if full in given else default_of(spec)
            used.add(full)
            vals.append(v)
            if spec[0] == 'COMFY_DYNAMICCOMBO_V3':
                op = _dyn_option(spec, v)
                if op: walk(ordered_inputs(op.get('inputs', {})), full + '.', False)
                continue
            if has_control(name, spec, top): vals.append('fixed')
            if has_upload(spec): vals.append('image')
    walk(ins, '', True)
    extra = set(given) - used
    if extra: raise KeyError(f'{cls}: unknown widget(s) {sorted(extra)}')
    return vals

# ---------------------------------------------------------------- UI -> API
def _norm_links(links):
    out = {}
    for l in links or []:
        if isinstance(l, dict):
            out[l['id']] = (l['origin_id'], l['origin_slot'], l['target_id'], l['target_slot'], l.get('type'))
        else:
            out[l[0]] = (l[1], l[2], l[3], l[4], l[5] if len(l) > 5 else None)
    return out

class _Ctx:
    def __init__(self, graph, defs, prefix='', parent=None, outer=None):
        self.nodes = {n['id']: n for n in graph.get('nodes', [])}
        self.links = _norm_links(graph.get('links'))
        self.defs, self.prefix, self.parent, self.outer, self.graph = defs, prefix, parent, outer, graph
        self.outer_values = {}
        self.proxy = {}
        if outer is not None:
            sg = graph
            wv = outer.get('widgets_values') or []
            px = (outer.get('properties') or {}).get('proxyWidgets')
            if px:   # newer frontend: promoted inner widgets
                for (nid, wname), v in zip(px, wv):
                    self.proxy[(int(nid) if str(nid).lstrip('-').isdigit() else nid, wname)] = v
            else:
                wnames = [i['name'] for i in sg.get('inputs', []) if str(i.get('type')) in WIDGET_TYPES]
                for n, v in zip(wnames, wv): self.outer_values[n] = v

def ui_to_api(wf, warn=None):
    warn = [] if warn is None else warn
    defs = {s['id']: s for s in (wf.get('definitions') or {}).get('subgraphs', [])}
    api = {}

    def resolve_link(ctx, link_id, seen=0):
        if link_id is None or link_id not in ctx.links: return None
        o, os_, _, _, _ = ctx.links[link_id]
        return resolve_origin(ctx, o, os_, seen + 1)

    def resolve_origin(ctx, oid, oslot, seen):
        if seen > 200: raise RuntimeError('link cycle')
        if oid == -10:   # subgraph input
            sg_in = ctx.graph['inputs'][oslot]
            name = sg_in['name']
            for inp in ctx.outer.get('inputs') or []:
                if inp['name'] == name and inp.get('link') is not None:
                    return resolve_link(ctx.parent, inp['link'], seen)
            if name in ctx.outer_values: return ('value', ctx.outer_values[name])
            return None
        n = ctx.nodes.get(oid)
        if n is None: return None
        t, mode = n['type'], n.get('mode', 0)
        if t in defs:
            sub = sub_ctx(ctx, n)
            if mode in (2, 4) and mode == 2: return None
            for lid, (o2, s2, t2, ts2, _) in sub.links.items():
                if t2 == -20 and ts2 == oslot: return resolve_origin(sub, o2, s2, seen)
            return None
        if t == 'Reroute':
            return resolve_link(ctx, (n.get('inputs') or [{}])[0].get('link'), seen)
        if t == 'PrimitiveNode':
            return ('value', (n.get('widgets_values') or [None])[0])
        if mode == 2: return None
        if mode == 4:   # bypass: pass through first input of matching type
            otype = (n.get('outputs') or [{}])[oslot].get('type')
            for inp in n.get('inputs') or []:
                if inp.get('type') == otype and inp.get('link') is not None:
                    return resolve_link(ctx, inp['link'], seen)
            return None
        return ('link', ctx.prefix + str(oid), oslot)

    sub_cache = {}
    def sub_ctx(ctx, n):
        key = ctx.prefix + str(n['id'])
        if key not in sub_cache:
            sub_cache[key] = _Ctx(defs[n['type']], defs, prefix=key + ':', parent=ctx, outer=n)
        return sub_cache[key]

    def emit(ctx):
        for nid, n in ctx.nodes.items():
            t, mode = n['type'], n.get('mode', 0)
            if t in defs:
                if mode == 0: emit(sub_ctx(ctx, n))
                continue
            if t in FRONTEND_ONLY or mode in (2, 4): continue
            if t not in oi():
                warn.append(f'MISSING node type {t} (#{ctx.prefix}{nid})'); continue
            inputs = widgets_from_values(t, n.get('widgets_values'), warn)
            for (pid, wname), v in ctx.proxy.items():
                if pid == nid: inputs[wname] = v
            for inp in n.get('inputs') or []:
                if inp.get('link') is None: continue
                r = resolve_link(ctx, inp['link'])
                name = inp['name']
                if r is None:
                    if not (inp.get('widget')): inputs.pop(name, None)
                elif r[0] == 'link': inputs[name] = [r[1], r[2]]
                else: inputs[name] = r[1]
            api[ctx.prefix + str(nid)] = {'class_type': t, 'inputs': inputs,
                                          '_meta': {'title': n.get('title') or oi()[t].get('display_name') or t}}
    emit(_Ctx(wf, defs))
    # drop dangling links to nodes that were not emitted (e.g. muted)
    for k, v in api.items():
        for name, val in list(v['inputs'].items()):
            if isinstance(val, list) and len(val) == 2 and isinstance(val[0], str) and val[0] not in api:
                del v['inputs'][name]
    return api

# ---------------------------------------------------------------- builder
GROUP_COLORS = {'models': '#3f789e', 'prompt': '#8A8', 'pass1': '#a1309b', 'hires': '#b06634',
                'face': '#b58b2a', 'upscale': '#4a7a3f', 'save': '#444', 'about': '#335', 'video': '#88A',
                'input': '#3f5f8a', 'decode': '#4a3f8a', 'post': '#6a3f5a'}
NODE_COLORS = {'models': ('#223', '#335'), 'prompt': ('#232', '#353'), 'note': ('#432', '#653'),
               'bypass': ('#322', '#533')}

class Out:
    def __init__(self, node, slot): self.node, self.slot = node, slot

class Node:
    def __init__(self, g, nid, cls, title, widgets, inputs, w, h, color, mode, props):
        self.g, self.id, self.cls, self.title = g, nid, cls, title
        self.widgets, self.inputs, self.w, self.h = widgets, inputs, w, h
        self.color, self.mode, self.props = color, mode, props
        self.pos = [0, 0]
    def out(self, which=0):
        if isinstance(which, int): return Out(self, which)
        outs = self.g.out_types(self.cls)
        for i, (t, n) in enumerate(outs):
            if n == which or t == which: return Out(self, i)
        raise KeyError(f'{self.cls} has no output {which}')
    def __getitem__(self, k): return self.out(k)

class Graph:
    """Compact spec -> litegraph UI workflow.  Layout: groups left->right, columns inside groups, nodes stacked."""
    def __init__(self, title='workflow'):
        self.title, self.nodes, self.groups, self._id = title, [], [], 0
        self.cur_group = None
    def out_types(self, cls):
        if cls in ('MarkdownNote', 'Note'): return []
        v = oi()[cls]
        return list(zip(v['output'], v.get('output_name') or v['output']))
    def group(self, title, color_key='models', cols=None, gap_after=60):
        g = {'title': title, 'color': GROUP_COLORS.get(color_key, color_key), 'cols': [], 'gap_after': gap_after}
        self.groups.append(g); self.cur_group = g
        return g
    def add(self, cls, title=None, col=0, w=None, h=None, color=None, mode=0, props=None, **kw):
        self._id += 1
        widgets, links = {}, {}
        for k, v in kw.items():
            key = k.replace('__', '.')
            (links if isinstance(v, (Out, Node)) else widgets)[key] = v.out(0) if isinstance(v, Node) else v
        if cls not in ('MarkdownNote', 'Note') and not cls.startswith('VHS_'):
            values_from_widgets(cls, widgets)    # validates names early
        n = Node(self, self._id, cls, title, widgets, links, w, h, color, mode, props or {})
        n.group, n.col = self.cur_group, col
        self.nodes.append(n)
        if self.cur_group is not None:
            while len(self.cur_group['cols']) <= col: self.cur_group['cols'].append([])
            self.cur_group['cols'][col].append(n)
        return n
    def note(self, text, title='Note', col=0, w=None, h=None):
        return self.add('MarkdownNote', title=title, col=col, w=w, h=h, color='note', text=text)

    def _est(self, n):
        if n.cls in ('MarkdownNote', 'Note'):
            lines = sum(max(1, len(l) // 52 + 1) for l in n.widgets['text'].split('\n'))
            return n.w or 400, n.h or max(120, 22 * lines + 30)
        ins = node_inputs(n.cls)
        sockets = [x for x in ins if not is_widget(x[1])]
        nw = len(n.widgets) + 4 if n.cls.startswith('VHS_') else len(values_from_widgets(n.cls, n.widgets))
        multiline = sum(1 for nm, s, _ in ins if is_widget(s) and s[0] == 'STRING' and _opts(s).get('multiline'))
        rows = max(len(sockets), len(self.out_types(n.cls)))
        h = 12 + rows * 22 + nw * 24 + multiline * 140
        return n.w or 340, n.h or h

    def layout(self, x0=0, y0=0, col_gap=40, row_gap=60, pad=30, title_h=46, group_gap=80):
        x = x0
        for g in self.groups:
            cx, maxy = x + pad, y0
            for col in g['cols']:
                cy, cw = y0 + title_h + 30, 0
                for n in col:
                    w, h = self._est(n)
                    n.w, n.h = w, h
                    n.pos = [cx, cy]
                    cy += h + row_gap
                    cw = max(cw, w)
                maxy = max(maxy, cy - row_gap)
                cx += cw + col_gap
            g['bounding'] = [x, y0, cx - col_gap + pad - x, maxy + pad - y0]
            x = cx - col_gap + pad + group_gap
        return self

    def to_ui(self, extra_ds=None):
        self.layout()
        links, lid = [], 0
        node_out_links = {}
        for n in self.nodes:
            for name, o in n.inputs.items():
                lid += 1
                links.append([lid, o.node.id, o.slot, n.id, name, None])
                node_out_links.setdefault((o.node.id, o.slot), []).append(lid)
        lid_by = {(l[3], l[4]): l for l in links}
        ui_nodes = []
        for order, n in enumerate(self.nodes):
            col = NODE_COLORS.get(n.color) if isinstance(n.color, str) else None
            base = {'id': n.id, 'type': n.cls, 'pos': n.pos, 'size': [n.w, n.h], 'flags': {}, 'order': order,
                    'mode': n.mode, 'properties': dict({'Node name for S&R': n.cls}, **n.props)}
            if n.title: base['title'] = n.title
            if col: base['color'], base['bgcolor'] = col
            if n.cls in ('MarkdownNote', 'Note'):
                base.update(inputs=[], outputs=[], widgets_values=[n.widgets['text']])
                ui_nodes.append(base); continue
            ins = node_inputs(n.cls)
            ui_in = []
            slot = 0
            for name, spec, sec in ins:
                wid = is_widget(spec)
                if wid and name not in n.inputs: continue
                if spec[0] == 'COMFY_AUTOGROW_V3':
                    for k in sorted(x for x in n.inputs if x.startswith(name + '.')):
                        l = lid_by[(n.id, k)]; l[4] = slot; l[5] = self.out_types(l[1] and next(m.cls for m in self.nodes if m.id == l[1]))[l[2]][0]
                        ui_in.append({'name': k, 'type': '*', 'link': l[0]}); slot += 1
                    continue
                t = spec[0] if isinstance(spec[0], str) else 'COMBO'
                if t == 'COMFY_MATCHTYPE_V3': t = '*'
                entry = {'name': name, 'type': t, 'link': None}
                if wid: entry['widget'] = {'name': name}
                if name in n.inputs:
                    l = lid_by[(n.id, name)]; l[4] = slot; entry['link'] = l[0]
                    src = next(m for m in self.nodes if m.id == l[1])
                    l[5] = self.out_types(src.cls)[l[2]][0]
                    if entry['type'] == '*': entry['type'] = l[5]
                ui_in.append(entry); slot += 1
            missing = set(n.inputs) - {e['name'] for e in ui_in}
            if missing: raise KeyError(f'{n.cls}: unknown link inputs {missing}')
            outs = [{'name': nm, 'type': t, 'links': node_out_links.get((n.id, i), []), 'slot_index': i}
                    for i, (t, nm) in enumerate(self.out_types(n.cls))]
            if n.cls.startswith('VHS_'):
                wv = {}
                for nm, spec, _ in ins:
                    if is_widget(spec): wv[nm] = n.widgets.get(nm, default_of(spec))
                wv.update(n.widgets); wv['videopreview'] = {'hidden': False, 'paused': False, 'params': {}}
            else:
                wv = values_from_widgets(n.cls, n.widgets)
            base.update(inputs=ui_in, outputs=outs, widgets_values=wv)
            ui_nodes.append(base)
        groups = [{'id': i + 1, 'title': g['title'], 'bounding': g['bounding'], 'color': g['color'],
                   'font_size': 24, 'flags': {}} for i, g in enumerate(self.groups)]
        return {'id': str(uuid.uuid5(uuid.NAMESPACE_URL, self.title)), 'revision': 0,
                'last_node_id': self._id, 'last_link_id': lid, 'nodes': ui_nodes, 'links': links,
                'groups': groups, 'config': {},
                'extra': {'ds': extra_ds or {'scale': 0.45, 'offset': [60, 120]}, 'workflowRendererVersion': 'LG'},
                'version': 0.4}

def check_overlaps(ui):
    """Return list of overlapping node pairs (by bounding box incl. 30px title)."""
    boxes = [(n['id'], n['pos'][0], n['pos'][1] - 30, n['pos'][0] + n['size'][0], n['pos'][1] + n['size'][1])
             for n in ui['nodes']]
    bad = []
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            a, b = boxes[i], boxes[j]
            if a[1] < b[3] and b[1] < a[3] and a[2] < b[4] and b[2] < a[4]: bad.append((a[0], b[0]))
    return bad

# ---------------------------------------------------------------- queue + measure
def _nvsmi():
    try:
        r = subprocess.run(['nvidia-smi', '--query-gpu=memory.used', '--format=csv,noheader,nounits'],
                           capture_output=True, text=True, timeout=5)
        return int(r.stdout.strip().splitlines()[0])
    except Exception:
        return None

def queue_and_wait(api, label='', workflow='', wait=True, timeout=7200, poll=1.0):
    base_vram = _nvsmi()
    st = http('/system_stats')
    ram_total = st['system']['ram_total'] if st else None
    base_ram_free = st['system']['ram_free'] if st else None
    cid = str(uuid.uuid4())
    t0 = time.time()
    resp = http('/prompt', {'prompt': api, 'client_id': cid})
    rec = {'label': label, 'workflow': workflow, 'queued_at': time.strftime('%Y-%m-%d %H:%M:%S'),
           'baseline_vram_mb': base_vram}
    if not resp or 'prompt_id' not in resp:
        rec.update(status='rejected', error=_short_err(resp))
        _log(rec); return rec
    pid = rec['prompt_id'] = resp['prompt_id']
    if not wait:
        rec['status'] = 'queued'; return rec
    peak_vram, min_ram_free, stop = [base_vram or 0], [base_ram_free or 0], [False]
    def sampler():
        while not stop[0]:
            v = _nvsmi()
            if v: peak_vram[0] = max(peak_vram[0], v)
            s = http('/system_stats', timeout=5)
            try: min_ram_free[0] = min(min_ram_free[0], s['system']['ram_free'])
            except Exception: pass
            time.sleep(0.5)
    th = threading.Thread(target=sampler, daemon=True); th.start()
    h = None
    try:
        while time.time() - t0 < timeout:
            h = http(f'/history/{pid}', timeout=30)
            if h is None:
                fails = locals().get('fails', 0) + 1
                if fails > 120: break          # server gone for ~2+ min
            else:
                fails = 0
            if h and pid in h and h[pid].get('status', {}).get('completed') is not None:
                if h[pid]['status'].get('status_str') in ('success', 'error'): break
            time.sleep(poll)
    finally:
        stop[0] = True; th.join(timeout=3)
    rec['seconds'] = round(time.time() - t0, 1)
    rec['peak_vram_mb'] = peak_vram[0]
    if ram_total: rec['peak_ram_used_gb'] = round((ram_total - min_ram_free[0]) / 2**30, 1)
    if ram_total and base_ram_free: rec['baseline_ram_used_gb'] = round((ram_total - base_ram_free) / 2**30, 1)
    if h and pid in h:
        s = h[pid]['status']
        rec['status'] = s.get('status_str')
        msgs = s.get('messages') or []
        for m in msgs:
            if m[0] == 'execution_error':
                d = m[1]; rec['error'] = f"{d.get('node_type')}#{d.get('node_id')}: {d.get('exception_message','')[:600]}"
        ts = {m[0]: m[1].get('timestamp') for m in msgs if isinstance(m[1], dict) and 'timestamp' in m[1]}
        if ts.get('execution_start') and (ts.get('execution_success') or ts.get('execution_error')):
            rec['exec_seconds'] = round(((ts.get('execution_success') or ts['execution_error']) - ts['execution_start']) / 1000, 1)
        outs = []
        for nid, o in (h[pid].get('outputs') or {}).items():
            for k in ('images', 'gifs', 'videos', 'video', 'audio'):
                for f in o.get(k, []) or []:
                    if isinstance(f, dict) and 'filename' in f:
                        outs.append(os.path.join(f.get('subfolder', ''), f['filename']).replace('\\', '/') + f" [{f.get('type','')}]")
        rec['outputs'] = outs
    else:
        rec['status'] = 'timeout'
    _log(rec)
    return rec

def _short_err(resp):
    if not resp: return 'no response'
    out = []
    e = resp.get('error')
    if e: out.append(f"{e.get('type','')}: {e.get('message','')} {e.get('details','')}"[:400])
    for nid, ne in (resp.get('node_errors') or {}).items():
        for er in ne.get('errors', []):
            out.append(f"#{nid} {ne.get('class_type')}: {er.get('message')} | {str(er.get('details'))[:160]}")
    return out

def _log(rec):
    data = json.load(open(RESULTS, encoding='utf-8')) if os.path.exists(RESULTS) else []
    data.append(rec)
    json.dump(data, open(RESULTS, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)

def apply_sets(api, sets):
    """'Title:input=value' or 'id:input=value'; value parsed as JSON when possible."""
    for s in sets or []:
        target, rest = s.rsplit(':', 1) if s.count(':') >= 1 and '=' in s.rsplit(':', 1)[1] else (None, s)
        name, val = rest.split('=', 1)
        try: val = json.loads(val)
        except Exception: pass
        hits = [k for k, v in api.items() if k == target or v['_meta']['title'] == target]
        if not hits: raise KeyError(f'no node {target!r}')
        for k in hits: api[k]['inputs'][name] = val

def validate_only(api):
    """Server-side validation WITHOUT executing: every output node gets an INT linked into a STRING widget
    (type mismatch -> that output fails, but all ancestors are still validated); preview-only outputs are dropped.
    Returns list of real errors (marker errors filtered)."""
    api = copy.deepcopy(api)
    api['990001'] = {'class_type': 'PrimitiveInt', 'inputs': {'value': 0}, '_meta': {'title': '__validate_marker__'}}
    dropped = []
    for k, v in list(api.items()):
        info = oi().get(v['class_type']) or {}
        if not info.get('output_node'): continue
        ins = node_inputs(v['class_type'])
        sw = [n for n, s, _ in ins if is_widget(s) and s[0] == 'STRING']
        if sw: v['inputs'][sw[0]] = ['990001', 0]
        else: dropped.append(f"{k} {v['class_type']}"); del api[k]
    for k, v in api.items():   # remove links into dropped nodes
        for n, val in list(v['inputs'].items()):
            if isinstance(val, list) and len(val) == 2 and isinstance(val[0], str) and val[0] not in api:
                del v['inputs'][n]
    resp = http('/prompt', {'prompt': api, 'client_id': 'validate'})
    if resp and 'prompt_id' in resp:
        http('/interrupt', {}); return ['!! prompt was accepted and queued (should not happen)'], dropped
    errs = [e for e in _short_err(resp) if '990001' not in e and 'received_type(INT) mismatch input_type(STRING)' not in e
            and 'prompt_outputs_failed_validation' not in e]
    return errs, dropped

def main(argv):
    cmd = argv[0]
    if cmd == 'refresh':
        d = oi(refresh=True); print(len(d), 'node types'); return
    wf_path = argv[1]
    wf = json.load(open(wf_path, encoding='utf-8'))
    warn = []
    api = ui_to_api(wf, warn) if 'nodes' in wf else wf
    if cmd == 'api':
        if len(argv) > 2: json.dump(api, open(argv[2], 'w', encoding='utf-8'), indent=1)
        print(len(api), 'api nodes'); [print('WARN', w) for w in warn]; return
    if cmd == 'check':
        print(len(api), 'api nodes'); [print('WARN', w) for w in warn]
        if 'nodes' in wf:
            types = {n['type'] for n in wf['nodes']}
            for s in (wf.get('definitions') or {}).get('subgraphs', []): types |= {n['type'] for n in s['nodes']}
            sg = {s['id'] for s in (wf.get('definitions') or {}).get('subgraphs', [])}
            miss = sorted(t for t in types if t not in oi() and t not in FRONTEND_ONLY and t not in sg)
            print('missing types:', miss or 'none'); print('overlaps:', check_overlaps(wf) or 'none')
        return
    if cmd == 'validate':
        for w in warn: print('WARN', w)
        errs, dropped = validate_only(api)
        print('dropped preview outputs:', dropped or 'none')
        print('errors:', len(errs)); [print('  ', e[:300]) for e in errs]
        return
    if cmd == 'queue':
        label, sets, wait, timeout = '', [], True, 7200
        i = 2
        while i < len(argv):
            if argv[i] == '--label': label = argv[i + 1]; i += 2
            elif argv[i] == '--set': sets.append(argv[i + 1]); i += 2
            elif argv[i] == '--no-wait': wait = False; i += 1
            elif argv[i] == '--timeout': timeout = float(argv[i + 1]); i += 2
            else: raise SystemExit('bad arg ' + argv[i])
        apply_sets(api, sets)
        for w in warn: print('WARN', w)
        rec = queue_and_wait(api, label=label, workflow=os.path.basename(wf_path), wait=wait, timeout=timeout)
        print(json.dumps(rec, indent=1, ensure_ascii=False))

if __name__ == '__main__':
    main(sys.argv[1:])
