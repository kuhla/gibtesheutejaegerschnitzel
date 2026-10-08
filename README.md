# Schnitzelcheck · Telegrafenberg

Eine kleine Website für die Frage: Gibt es heute Jägerschnitzel auf dem Telegrafenberg?

Die Website ist für **kostenloses GitHub Pages in einem öffentlichen Repository** vorbereitet. Ein GitHub-Actions-Auftrag prüft beide Speisepläne und veröffentlicht die HTML-Seite zusammen mit `status.json`. Ein eigener dauerhaft laufender Server ist dafür nicht nötig.

## GitHub Pages einrichten

1. Bei GitHub anmelden und ein **öffentliches** Repository erstellen, zum Beispiel `gibtesheutejaegerschnitzel`.
2. Dieses Projekt einschließlich `.github/workflows/pages.yml` auf den Branch `main` hochladen. Der erzeugte Ordner `dist/` muss nicht ins Repository.
3. Im Repository unter **Settings → Pages → Build and deployment → Source** die Option **GitHub Actions** auswählen.
4. Unter **Actions → Speiseplaene pruefen und Website veroeffentlichen → Run workflow** den ersten Lauf starten. Weitere Änderungen auf `main` starten ihn automatisch.
5. Nach erfolgreicher Veröffentlichung steht die Adresse unter **Settings → Pages** und beim Deployment. Üblicherweise lautet sie `https://DEIN-NAME.github.io/gibtesheutejaegerschnitzel/`.

Für die Veröffentlichung durch die GitHub-Kommandozeile zunächst anmelden:

```bash
gh auth login --hostname github.com --git-protocol https --web
```

Keine persönlichen Tokens, Passwörter oder Firebase-Sitzungen in das Repository laden. Der Workflow benötigt keine selbst angelegten Secrets; GitHub stellt die eingeschränkten Veröffentlichungsrechte automatisch bereit.

Offizielle Anleitung: [GitHub Pages mit Actions](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages).

## Aktualisierung

- Der Workflow ist rund um die Uhr alle **30 Minuten** eingeplant, zu Minute 7 und 37. Das Datum wird in `Europe/Berlin` bestimmt.
- Im Browser wird das veröffentlichte Ergebnis beim Öffnen, bei Rückkehr zum Tab und alle fünf Minuten geladen.
- **Ergebnis aktualisieren** lädt das zuletzt veröffentlichte Ergebnis. Der Button startet keinen neuen GitHub-Auftrag.
- Die Seite nennt den tatsächlichen Prüfzeitpunkt. Bei mehr als 90 Minuten alten Daten erscheint ein Hinweis.
- Ergebnisse vom Vortag werden nicht als heutiger Treffer angezeigt. Auch ein bereits geöffneter Tab setzt die Meldung bei Berliner Mitternacht zurück.
- GitHub kann geplante Läufe verzögern oder auslassen. Nach **60 Tagen ohne Repository-Aktivität** kann GitHub den Zeitplan deaktivieren. Dann unter **Actions** den Workflow wieder aktivieren. [GitHub-Hinweise zu geplanten Workflows](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)

## Suchregeln

- Ohne Treffer: „Leider, gibt es heute kein Jägerschnitzel auf dem Telegrafenberg“.
- Sobald mindestens eine Quelle im heutigen deutschen Menü `Jägerschnitzel` oder `Jaegerschnitzel` enthält: „Juchu! Heute gibt es Jägerschnitzel auf dem Telegrafenberg“.
- Groß-/Kleinschreibung wird ignoriert, Unicode-Umlaute werden normalisiert.
- Mensa: deutsches Qnips-Menü `17728`, nur der aktuelle Kalendertag in `Europe/Berlin`. Andere Wochentage und versteckte Kategorien zählen nicht.
- Café Freundlich: nur Text zwischen der Überschrift `Heute` und der nächsten Überschrift. Skripte, Kommentare und kommende Tage zählen nicht.
- Abruffehler erscheinen separat. Ein Treffer einer funktionierenden Quelle reicht auch dann, wenn die andere ausfällt. Ohne positiven Treffer bleibt bei Fehlern die Standardmeldung stehen.

## Lokal ausprobieren

Python 3.10 oder neuer genügt; es werden keine zusätzlichen Python-Pakete benötigt.

Mit direkter Speiseplanprüfung:

```bash
python3 server.py
```

Dann `http://localhost:8000` öffnen. Dieser lokale Server verwendet einen Cache von maximal fünf Minuten (30 Sekunden bei Fehlern), der beim Tageswechsel verworfen wird.

Genau die statische GitHub-Pages-Version erstellen und ansehen:

```bash
python3 build_site.py
python3 -m http.server 8000 --directory dist --bind 127.0.0.1
```

Danach ebenfalls `http://localhost:8000` öffnen. In diesem Modus werden neue Speiseplandaten erst durch einen erneuten Aufruf von `build_site.py` erzeugt.

## Tests

```bash
python3 -m unittest -v
node --test test_app.cjs
```

Node.js 22 oder neuer wird nur für die JavaScript-Tests benötigt. GitHub Actions führt beide Testsuiten vor der Veröffentlichung aus.

## Datenanbindung

Die Mensa lädt ihre Menüs dynamisch aus Qnips/Firebase. Das Python-Skript verwendet denselben anonymen Zugriff wie die öffentliche Originalseite. Die öffentlichen Client-Konfigurationswerte sind keine persönlichen Zugangsdaten. Kurzlebige Sitzungstoken bleiben ausschließlich im Arbeitsspeicher und werden weder veröffentlicht noch protokolliert.

Veröffentlicht werden nur `index.html`, `app.js`, `status.json` und `.nojekyll`. Der Quellcode ist zusätzlich im öffentlichen GitHub-Repository einsehbar. Änderungen an der externen Schnittstelle oder dem HTML des Cafés können Anpassungen erfordern.
