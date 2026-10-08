#!/usr/bin/env python3
"""Jägerschnitzel-Check. Python 3.10+, keine externen Pakete."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from html.parser import HTMLParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import threading
import time
import unicodedata
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
BERLIN = ZoneInfo('Europe/Berlin')
MENSA_URL = 'https://company-catering.widynski-roick.de/menu/Wissenschaftspark%20Albert%20Einstein%20%20GFZ/Wissenschaftspark%20Albert%20Einstein%20'
CAFE_URL = 'https://cafe-freundlich.de/mittagstisch/'
FIRESTORE = 'https://firestore.googleapis.com/v1/projects/qnips-wrcompanycatering/databases/(default)/documents'
# Öffentliche Client-Konfiguration der Originalseite, keine persönlichen Zugangsdaten.
FIREBASE_KEY = 'AIzaSyBfu8YP7O9rtcb2BKnEwOF8ceTePr4BFbw'
APP_HEADER = '0083cbac6cfb6fe585614e95a39a6be10e'
NO = 'Leider, gibt es heute kein Jägerschnitzel auf dem Telegrafenberg'
YES = 'Juchu! Heute gibt es Jägerschnitzel auf dem Telegrafenberg'


def fetch(url, body=None, headers=None):
    request = Request(url, data=json.dumps(body).encode() if body is not None else None,
                      headers={'User-Agent': 'Telegrafenberg-Speiseplan/1.0', 'Accept-Language': 'de-DE',
                               **({'Content-Type': 'application/json'} if body is not None else {}), **(headers or {})})
    with urlopen(request, timeout=12) as response:
        return response.read(5_000_000).decode('utf-8')


def contains_schnitzel(text):
    return bool(re.search(r'jägerschnitzel|jaegerschnitzel', unicodedata.normalize('NFC', text).casefold()))


class TodayParser(HTMLParser):
    """Nur sichtbarer Text zwischen der Heute- und der nächsten Überschrift."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.heading = None
        self.heading_text = []
        self.active = False
        self.found = False
        self.closed = False
        self.parts = []
        self.ignored = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'template'):
            self.ignored += 1
        if self.ignored:
            return
        if re.fullmatch(r'h[1-6]', tag):
            if self.active:
                self.active = False
                self.closed = True
            self.heading = tag
            self.heading_text = []
        elif self.active and tag in ('div', 'p', 'li', 'br'):
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'template'):
            self.ignored = max(0, self.ignored - 1)
            return
        if self.ignored:
            return
        if tag == self.heading:
            if not self.closed and ' '.join(''.join(self.heading_text).split()).casefold() == 'heute':
                self.active = self.found = True
            self.heading = None
        elif self.active and tag in ('div', 'p', 'li'):
            self.parts.append('\n')

    def handle_data(self, data):
        if self.ignored:
            return
        if self.heading:
            self.heading_text.append(data)
        elif self.active:
            self.parts.append(data)


def cafe_today(html):
    parser = TodayParser()
    parser.feed(html)
    if not parser.found or not parser.closed:
        raise ValueError('Der Heute-Abschnitt konnte nicht sicher abgegrenzt werden.')
    return [' '.join(line.split()) for line in ''.join(parser.parts).splitlines() if line.strip()]


def decode_value(value):
    if 'mapValue' in value:
        return {k: decode_value(v) for k, v in value['mapValue'].get('fields', {}).items()}
    if 'arrayValue' in value:
        return [decode_value(v) for v in value['arrayValue'].get('values', [])]
    return next(iter(value.values()), None)


def menu_today(menu, day):
    if not isinstance(menu.get('Days'), list):
        raise ValueError('Der Wochenplan hat keine lesbare Tagesstruktur.')
    result = []
    def texts(item):
        if not isinstance(item, dict) or item.get('IsHidden'):
            return
        for field in ('Name', 'Description', 'LongDescription'):
            if isinstance(item.get(field), str):
                result.append(item[field])
        for field in ('Categories', 'Products', 'ComponentGroups', 'Components'):
            for child in item.get(field, []):
                texts(child)
    for entry in menu['Days']:
        # Qnips kodiert den Kalendertag als UTC-Mitternacht, nicht als Essenszeit.
        if str(entry.get('Date', ''))[:10] == day.isoformat():
            texts(entry)
    return result


class MensaClient:
    def __init__(self):
        self.token = None
        self.expires = 0
        self.environment = None

    def authenticate(self):
        if self.token and time.monotonic() < self.expires:
            return
        identity = json.loads(fetch('https://apps-live-eu.qnips.com/cons/api/NewIdentity', headers={
            'App-Brand': 'wrcompcatering', 'Response-Version': 'v3', 'Authorization': APP_HEADER}))
        auth = json.loads(fetch('https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken?key=' + FIREBASE_KEY,
                                {'token': identity['FirebaseCustomToken'], 'returnSecureToken': True}))
        self.token = auth['idToken']
        self.environment = identity['Environment']
        self.expires = time.monotonic() + int(auth.get('expiresIn', 3600)) - 120

    def today(self, day):
        self.authenticate()
        year, week, _ = day.isocalendar()
        path = f'{self.environment}/de-DE/Menus/17728/Years/{year}/Weeks/{week}'
        try:
            data = json.loads(fetch(f'{FIRESTORE}/{path}', headers={'Authorization': 'Bearer ' + self.token}))
        except HTTPError as error:
            if error.code in (401, 403):
                self.expires = 0
            if error.code == 404:
                raise ValueError('Für diese Woche wurde kein Menü veröffentlicht.') from error
            raise
        return menu_today(decode_value({'mapValue': data}), day)


mensa = MensaClient()
_cache = None
_cache_until = 0
_lock = threading.Lock()


def check_source(name, url, reader):
    try:
        lines = reader()
        matches = list(dict.fromkeys(line for line in lines if contains_schnitzel(line)))
        return {'name': name, 'url': url, 'ok': True, 'found': bool(matches), 'matches': matches,
                'note': 'Jägerschnitzel gefunden' if matches else 'Kein Jägerschnitzel im heutigen Menü'}
    except Exception:
        return {'name': name, 'url': url, 'ok': False, 'found': False, 'matches': [],
                'note': 'Speiseplan konnte nicht geprüft werden'}


def get_status():
    global _cache, _cache_until
    with _lock:
        now = datetime.now(BERLIN)
        if _cache and _cache['date'] == now.date().isoformat() and time.monotonic() < _cache_until:
            return _cache
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(check_source, 'Mensa · Widynski & Roick', MENSA_URL, lambda: mensa.today(now.date()))
            second = pool.submit(check_source, 'Café Freundlich', CAFE_URL, lambda: cafe_today(fetch(CAFE_URL)))
            sources = [first.result(), second.result()]
        # Bei einem Tageswechsel während des Abrufs niemals den Vortag als heute ausliefern.
        if datetime.now(BERLIN).date() != now.date():
            return {'date': datetime.now(BERLIN).date().isoformat(), 'checkedAt': None, 'found': False,
                    'message': NO, 'complete': False, 'sources': []}
        found = any(source['found'] for source in sources)
        _cache = {'date': now.date().isoformat(), 'checkedAt': datetime.now(BERLIN).isoformat(),
                  'found': found, 'message': YES if found else NO,
                  'complete': all(source['ok'] for source in sources), 'sources': sources}
        _cache_until = time.monotonic() + (300 if _cache['complete'] else 30)
        return _cache


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split('?', 1)[0]
        if path in ('/api/status', '/status.json'):
            body = json.dumps(get_status(), ensure_ascii=False).encode()
            content_type = 'application/json; charset=utf-8'
        elif path in ('/', '/index.html'):
            body = (ROOT / 'index.html').read_bytes()
            content_type = 'text/html; charset=utf-8'
        elif path == '/app.js':
            body = (ROOT / 'app.js').read_bytes()
            content_type = 'text/javascript; charset=utf-8'
        elif path == '/favicon.ico':
            self.send_response(204)
            self.end_headers()
            return
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--host', default='127.0.0.1')
    args = parser.parse_args()
    print(f'Jägerschnitzel-Check: http://{args.host}:{args.port}', flush=True)
    try:
        ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()
    except KeyboardInterrupt:
        pass
