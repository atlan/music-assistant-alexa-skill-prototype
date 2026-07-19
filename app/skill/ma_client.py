# -*- coding: utf-8 -*-
"""Minimal client for Music Assistant's own REST API (POST /api).

Separate from music_assistant_api/ma_routes.py, which is the endpoint MA
pushes stream URLs *to*. This module lets the skill call back *into* MA
to look up in-progress audiobooks/podcasts and start playback on a
specific player queue - needed for the "continue my audiobook" intent.

Auth: a long-lived API token generated in MA's own user settings
(Settings > user profile > API tokens), configured via MA_API_TOKEN.
This is unrelated to APP_USERNAME/APP_PASSWORD (which protect this
skill's own web UI/API) and to the Home Assistant integration's own
system token (which is scoped to MA's WebSocket protocol, not this
REST wrapper).
"""

import logging
import os

import requests

from env_secrets import get_env_secret

logger = logging.getLogger(__name__)


class MAClientError(Exception):
    pass


def _api_url():
    base = (os.environ.get('MA_API_URL') or '').strip().rstrip('/')
    if not base:
        raise MAClientError('MA_API_URL is not configured')
    return f'{base}/api'


def call(command, args=None, timeout=10):
    """Call a Music Assistant API command and return its parsed JSON result."""
    token = get_env_secret('MA_API_TOKEN')
    if not token:
        raise MAClientError('MA_API_TOKEN is not configured')

    body = {'command': command}
    if args:
        body['args'] = args

    try:
        resp = requests.post(
            _api_url(),
            json=body,
            headers={'Authorization': f'Bearer {token}'},
            timeout=timeout,
        )
    except requests.RequestException as e:
        raise MAClientError(f'Request to Music Assistant failed: {e}') from e

    if resp.status_code >= 400:
        raise MAClientError(f'Music Assistant API returned HTTP {resp.status_code}: {resp.text[:200]}')

    try:
        return resp.json()
    except ValueError as e:
        raise MAClientError(f'Music Assistant API returned non-JSON response: {resp.text[:200]}') from e


def get_in_progress_items(limit=5):
    """Return the list of in-progress audiobooks/podcast episodes, most recent first."""
    result = call('music/in_progress_items', {'limit': limit})
    return result if isinstance(result, list) else []


def play_media(queue_id, uri):
    """Start playback of the given media URI on the given player queue."""
    call('player_queues/play_media', {'queue_id': queue_id, 'media': uri})


def list_players():
    """Return all registered MA players (used to populate the device-assignment UI)."""
    result = call('players/all')
    return result if isinstance(result, list) else []
