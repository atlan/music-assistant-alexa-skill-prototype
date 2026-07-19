# -*- coding: utf-8 -*-
"""Maps Alexa's per-skill device IDs to Music Assistant player_ids.

Alexa never tells a skill which physical device made a request - only an
opaque ID scoped to (this skill, that device), deliberately unlinkable to
the account-level device identity MA's own Alexa player provider sees
(e.g. "Echo Labor"). There's no API to bridge the two, so the mapping is
recorded here once per device: the device shows up as "unknown" after its
first request, and a human assigns it to an MA player via the setup page.

Persisted under /data (the one directory Supervisor guarantees survives
container recreates/updates), same pattern as ASK_CREDENTIALS_DIR.
"""

import json
import logging
import os
import threading
import time

logger = logging.getLogger(__name__)

_lock = threading.Lock()

# How long an unassigned device stays listed before it's pruned, so the
# "assign a device" list doesn't accumulate stale one-off entries forever.
_UNKNOWN_TTL_SECONDS = 7 * 24 * 60 * 60


def _registry_path():
    base = (os.environ.get('ASK_CREDENTIALS_DIR') or '').strip()
    if base:
        directory = os.path.dirname(base.rstrip('/')) or '/data'
    else:
        directory = '/data' if os.path.isdir('/data') else '.'
    return os.path.join(directory, 'device_registry.json')


def _load():
    path = _registry_path()
    if not os.path.exists(path):
        return {'mapped': {}, 'unknown': {}}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        logger.exception('Failed to read device registry at %s', path)
        return {'mapped': {}, 'unknown': {}}
    data.setdefault('mapped', {})
    data.setdefault('unknown', {})
    return data


def _save(data):
    path = _registry_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp_path = f'{path}.tmp'
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, path)
    except Exception:
        logger.exception('Failed to write device registry at %s', path)


def record_seen(device_id):
    """Note that a request came in from device_id. No-op if already mapped."""
    if not device_id:
        return
    with _lock:
        data = _load()
        if device_id in data['mapped']:
            return
        now = time.time()
        cutoff = now - _UNKNOWN_TTL_SECONDS
        data['unknown'] = {
            k: v for k, v in data['unknown'].items()
            if v.get('last_seen', 0) >= cutoff
        }
        entry = data['unknown'].setdefault(device_id, {'first_seen': now})
        entry['last_seen'] = now
        _save(data)


def get_player_id(device_id):
    """Return the MA player_id mapped to device_id, or None if unassigned."""
    if not device_id:
        return None
    data = _load()
    return data['mapped'].get(device_id)


def list_unknown():
    """Return {device_id: {first_seen, last_seen}} for devices seen but not yet assigned."""
    return dict(_load()['unknown'])


def list_mapped():
    """Return {device_id: player_id} for all assigned devices."""
    return dict(_load()['mapped'])


def set_mapping(device_id, player_id):
    with _lock:
        data = _load()
        data['mapped'][device_id] = player_id
        data['unknown'].pop(device_id, None)
        _save(data)


def remove_mapping(device_id):
    with _lock:
        data = _load()
        data['mapped'].pop(device_id, None)
        _save(data)
