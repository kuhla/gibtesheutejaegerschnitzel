#!/usr/bin/env python3
"""Erzeugt die statische GitHub-Pages-Website mit aktuellen Speiseplandaten."""
import json
from pathlib import Path
import shutil
import server

ROOT = Path(__file__).resolve().parent


def build(output=None):
    output = Path(output) if output is not None else ROOT / 'dist'
    output.mkdir(parents=True, exist_ok=True)
    # Nur die benötigten Website-Dateien veröffentlichen, keine Python-Quellen.
    for name in ('index.html', 'app.js'):
        shutil.copyfile(ROOT / name, output / name)
    status = {**server.get_status(), 'updateIntervalMinutes': 30}
    (output / 'status.json').write_text(json.dumps(status, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (output / '.nojekyll').touch()
    return status


if __name__ == '__main__':
    result = build()
    for source in result['sources']:
        print(f"{source['name']}: {source['note']}")
    if not result['complete']:
        # Fehlerzustand ebenfalls ausliefern statt unbemerkt alte Treffer zu behalten.
        print('::warning::Mindestens ein Speiseplan konnte nicht geprüft werden.')
    print('Website erstellt: dist/')
