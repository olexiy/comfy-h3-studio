"""Wrap a flat UI workflow (Graph.to_ui()) into one subgraph node, like the official templates do.
wrap(ui, top_ids, promote, name) -> new ui
  top_ids  node ids that stay on the main canvas (LoadImage, SaveVideo, notes); everything else goes inside
  promote  [(label, type, value, [(node_id, widget_name), ...]), ...] -> widgets shown on the subgraph node
Links crossing the border become subgraph inputs/outputs automatically. Format mirrors
comfyui_workflow_templates_json/templates/video_minimax_h3_i2v.json (frontend 1.49+, workflow version 0.4)."""
import copy, uuid


def _links(ui):
    return {l[0]: list(l) for l in ui['links']}


def wrap(ui, top_ids, promote, name, inst_pos=(0, 0), inst_size=(480, 640)):
    ui = copy.deepcopy(ui)
    nodes = {n['id']: n for n in ui['nodes']}
    links = _links(ui)
    top_ids = set(top_ids)
    inner_ids = [i for i in nodes if i not in top_ids]
    next_link = max(links) + 1 if links else 1
    inst_id = max(nodes) + 1
    sg_id = str(uuid.uuid4())
    sg_inputs, sg_outputs, sg_links, top_links = [], [], [], []
    inst_inputs, inst_outputs, inst_wv = [], [], []

    used = set()
    def uniq(n):                       # subgraph input names must be unique (frontend + ui_to_api key by name)
        k, u = 0, n
        while u in used: k += 1; u = f'{n}_{k}'
        used.add(u); return u

    def slot_of(node, iname):
        for k, inp in enumerate(node.setdefault('inputs', [])):
            if inp['name'] == iname: return k
        return None

    # 1) existing links: inner-inner stay, crossing ones become subgraph inputs/outputs
    out_map = {}   # (origin, oslot) -> sg output index
    for lid, (_, o, os_, t, ts, typ) in sorted(links.items()):
        oi, ti = o in top_ids, t in top_ids
        if not oi and not ti:
            sg_links.append({'id': lid, 'origin_id': o, 'origin_slot': os_, 'target_id': t, 'target_slot': ts, 'type': typ})
        elif oi and ti:
            top_links.append([lid, o, os_, t, ts, typ])
        elif oi:   # top -> inner: subgraph input
            k = len(sg_inputs)
            iname = uniq(nodes[t]['inputs'][ts]['name'])
            sg_inputs.append({'id': str(uuid.uuid4()), 'name': iname, 'type': typ, 'linkIds': [lid]})
            sg_links.append({'id': lid, 'origin_id': -10, 'origin_slot': k, 'target_id': t, 'target_slot': ts, 'type': typ})
            inst_inputs.append({'name': iname, 'type': typ, 'link': next_link})
            top_links.append([next_link, o, os_, inst_id, k, typ]); next_link += 1
        else:      # inner -> top: subgraph output
            if (o, os_) not in out_map:
                j = out_map[(o, os_)] = len(sg_outputs)
                sg_outputs.append({'id': str(uuid.uuid4()), 'name': typ, 'type': typ, 'linkIds': [], 'localized_name': typ})
                sg_links.append({'id': next_link, 'origin_id': o, 'origin_slot': os_, 'target_id': -20, 'target_slot': j, 'type': typ})
                sg_outputs[j]['linkIds'].append(next_link); next_link += 1
                inst_outputs.append({'name': typ, 'type': typ, 'links': []})
            j = out_map[(o, os_)]
            nodes[t]['inputs'][ts]['link'] = lid
            top_links.append([lid, inst_id, j, t, ts, typ])
            inst_outputs[j]['links'].append(lid)
    # inner node outputs that pointed at top nodes: keep only the -20 link ids
    for i in inner_ids:
        for k, out in enumerate(nodes[i].get('outputs') or []):
            keep = [l for l in (out.get('links') or []) if any(s['id'] == l and s['target_id'] != -20 for s in sg_links)]
            keep += [s['id'] for s in sg_links if s['origin_id'] == i and s['origin_slot'] == k and s['target_id'] == -20]
            out['links'] = keep or None
    # 2) promoted widgets
    for label, typ, value, targets in promote:
        k = len(sg_inputs)
        wname = uniq(targets[0][1])
        entry = {'id': str(uuid.uuid4()), 'name': wname, 'type': typ, 'linkIds': [], 'label': label}
        for nid, w in targets:
            n = nodes[nid]
            s = slot_of(n, w)
            if s is None:
                n['inputs'].append({'localized_name': w, 'name': w, 'type': typ, 'widget': {'name': w}, 'link': None}); s = len(n['inputs']) - 1
            n['inputs'][s]['link'] = next_link
            sg_links.append({'id': next_link, 'origin_id': -10, 'origin_slot': k, 'target_id': nid, 'target_slot': s, 'type': typ})
            entry['linkIds'].append(next_link); next_link += 1
        sg_inputs.append(entry)
        inst_inputs.append({'label': label, 'name': wname, 'type': typ, 'widget': {'name': wname}, 'link': None})
        inst_wv.append(value)
    # 3) subgraph definition
    inner = [nodes[i] for i in inner_ids]
    xs = [n['pos'][0] for n in inner]; ys = [n['pos'][1] for n in inner]
    xe = [n['pos'][0] + n['size'][0] for n in inner]
    x0, x1, y0 = min(xs), max(xe), min(ys)
    for s in sg_inputs: s['pos'] = [x0 - 220, y0 + 20]
    for s in sg_outputs: s['pos'] = [x1 + 110, y0 + 20]
    inner_groups = [g for g in ui.get('groups', []) if not g['title'].startswith('0 ')]
    for k, g in enumerate(inner_groups, 1): g['id'] = k
    sg = {'id': sg_id, 'version': 1, 'state': {'lastGroupId': len(inner_groups), 'lastNodeId': max(inner_ids),
          'lastLinkId': next_link, 'lastRerouteId': 0}, 'revision': 0, 'config': {}, 'name': name,
          'inputNode': {'id': -10, 'bounding': [x0 - 260, y0, 180, 60 + 24 * len(sg_inputs)]},
          'outputNode': {'id': -20, 'bounding': [x1 + 80, y0, 140, 68]},
          'inputs': sg_inputs, 'outputs': sg_outputs, 'widgets': [], 'nodes': inner, 'groups': inner_groups,
          'links': sg_links, 'extra': {}}
    inst = {'id': inst_id, 'type': sg_id, 'title': name, 'pos': list(inst_pos), 'size': list(inst_size), 'flags': {},
            'order': 0, 'mode': 0, 'inputs': inst_inputs, 'outputs': inst_outputs,
            'properties': {'cnr_id': 'comfy-core'}, 'widgets_values': inst_wv}
    ui['nodes'] = [nodes[i] for i in nodes if i in top_ids] + [inst]
    ui['links'] = top_links
    ui['groups'] = []
    ui['definitions'] = {'subgraphs': [sg]}
    ui['last_node_id'] = inst_id
    ui['last_link_id'] = next_link
    return ui
