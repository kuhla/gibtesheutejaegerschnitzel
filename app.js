'use strict';
const no = 'Leider, gibt es heute kein Jägerschnitzel auf dem Telegrafenberg';
const yes = 'Juchu! Heute gibt es Jägerschnitzel auf dem Telegrafenberg';
const $ = id => document.getElementById(id);
let loading = false;
let displayedDate = null;
let calendarDate = berlinDate();

function berlinDate(now = new Date()) {
  const parts = new Intl.DateTimeFormat('en', {
    timeZone: 'Europe/Berlin', year: 'numeric', month: '2-digit', day: '2-digit'
  }).formatToParts(now);
  const value = type => parts.find(part => part.type === type).value;
  return `${value('year')}-${value('month')}-${value('day')}`;
}

function reset() {
  $('message').textContent = no;
  document.body.classList.remove('yes');
  $('symbol').textContent = '–';
  $('next-date').textContent = 'Noch kein aktuelles Vorschauergebnis.';
  $('next-detail').textContent = 'Ab morgen, soweit bereits angekündigt.';
  $('next-coverage').textContent = '';
}

function unavailable(message) {
  reset();
  $('warning').hidden = false;
  $('warning').textContent = message;
  [0, 1].forEach(i => {
    $('source-' + i).textContent = 'Aktuell nicht geprüft';
    $('source-' + i).className = 'error';
  });
  $('checked').textContent = 'Keine aktuelle Prüfung verfügbar';
}

function renderForecast(forecast) {
  if (!forecast) return;
  const dateLabel = value => new Intl.DateTimeFormat('de-DE', {
    timeZone: 'Europe/Berlin', weekday: 'long', day: 'numeric', month: 'long', year: 'numeric'
  }).format(new Date(value + 'T12:00:00Z'));
  if (forecast.next && forecast.next.date > berlinDate()) {
    $('next-date').textContent = dateLabel(forecast.next.date);
    $('next-detail').textContent = forecast.next.sources.map(source => source.name).join(' und ') +
      (forecast.complete ? ' · Frühester angekündigter Termin nach heute.' :
        ' · Frühester gefundener Termin; die Vorschau ist nur teilweise prüfbar.');
  } else {
    $('next-date').textContent = forecast.complete ? 'Noch kein weiterer Termin angekündigt.' :
      'Der nächste Termin ist gerade nicht vollständig prüfbar.';
    $('next-detail').textContent = 'In den abrufbaren kommenden Speiseplänen wurde bisher kein Jägerschnitzel gefunden.';
  }
  $('next-coverage').textContent = forecast.sources.map(source =>
    source.name + ': ' + (source.through ? 'Plan bis ' + dateLabel(source.through) :
      source.ok ? 'noch keine kommenden Tage veröffentlicht' : 'Vorschau nicht abrufbar') +
      (source.through && !source.ok ? ' (unvollständig)' : '')).join(' · ');
}

async function update() {
  if (loading) return;
  loading = true;
  $('refresh').disabled = true;
  $('today').textContent = new Intl.DateTimeFormat('de-DE', {
    timeZone: 'Europe/Berlin', weekday: 'long', day: 'numeric', month: 'long', year: 'numeric'
  }).format(new Date());
  if (displayedDate !== berlinDate()) reset();
  $('warning').hidden = false;
  $('warning').textContent = 'Das aktuelle Prüfergebnis wird geladen …';
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 55000);
  try {
    // Relativ, damit auch /repository-name/ auf GitHub Pages funktioniert.
    const response = await fetch('./status.json?t=' + Date.now(), {
      cache: 'no-store', signal: controller.signal
    });
    if (!response.ok) throw new Error('Abruf fehlgeschlagen');
    const data = await response.json();
    const checkedAt = new Date(data.checkedAt);
    if (!data.checkedAt || !Number.isFinite(checkedAt.getTime()) ||
        !Array.isArray(data.sources) || data.sources.length !== 2 ||
        typeof data.found !== 'boolean' || typeof data.complete !== 'boolean') {
      throw new Error('Ungültiges Ergebnis');
    }
    if (data.date !== berlinDate() || berlinDate(checkedAt) !== berlinDate()) {
      unavailable('Für heute liegt noch keine aktuelle Prüfung vor. Die Speisepläne werden automatisch erneut abgefragt.');
      return;
    }
    displayedDate = data.date;
    $('message').textContent = data.found ? yes : no;
    document.body.classList.toggle('yes', data.found);
    $('symbol').textContent = data.found ? '!' : '–';
    data.sources.forEach((source, i) => {
      const element = $('source-' + i);
      element.textContent = source.found ? source.matches.join(' · ') : source.note;
      element.className = source.found ? 'match' : source.ok ? '' : 'error';
    });
    renderForecast(data.forecast);
    const warnings = [];
    if (!data.complete) warnings.push('Die Prüfung ist unvollständig: Mindestens ein Speiseplan war nicht abrufbar.');
    if (Date.now() - checkedAt.getTime() > 90 * 60 * 1000) {
      warnings.push('Die letzte Prüfung ist über 90 Minuten alt. Die automatische Aktualisierung ist möglicherweise verzögert.');
    }
    $('warning').hidden = warnings.length === 0;
    $('warning').textContent = warnings.join(' ');
    const checked = new Intl.DateTimeFormat('de-DE', {
      timeZone: 'Europe/Berlin', hour: '2-digit', minute: '2-digit'
    }).format(checkedAt);
    $('checked').textContent = 'Zuletzt geprüft: ' + checked + ' Uhr' +
      (data.updateIntervalMinutes ? ' · Geplant alle ' + data.updateIntervalMinutes + ' Minuten' : '');
  } catch (error) {
    unavailable(location.protocol === 'file:'
      ? 'Bitte die Website über einen Webserver öffnen (siehe README).'
      : 'Das Prüfergebnis ist gerade nicht abrufbar. Bitte später erneut versuchen.');
  } finally {
    clearTimeout(timeout);
    loading = false;
    $('refresh').disabled = false;
  }
}

$('refresh').addEventListener('click', update);
setInterval(update, 300000);
setInterval(() => {
  const today = berlinDate();
  if (calendarDate !== today) {
    calendarDate = today;
    unavailable('Ein neuer Tag beginnt. Das heutige Prüfergebnis wird geladen …');
    update();
  }
}, 1000);
document.addEventListener('visibilitychange', () => {
  if (!document.hidden) update();
});
update();
