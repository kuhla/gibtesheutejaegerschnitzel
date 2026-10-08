const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const code = fs.readFileSync('app.js', 'utf8');

function run(data, now = '2026-10-08T10:00:00Z') {
  const elements = new Map();
  const classes = new Set();
  const intervals = [];
  let timestamp = new Date(now).getTime();
  let requestedUrl;
  class Clock extends Date {
    constructor(...args) { super(...(args.length ? args : [timestamp])); }
    static now() { return timestamp; }
  }
  const context = vm.createContext({
    Date: Clock, Intl, AbortController,
    document: {
      getElementById(id) {
        if (!elements.has(id)) elements.set(id, {textContent:'', hidden:false, addEventListener(){}});
        return elements.get(id);
      },
      body:{classList:{remove(name){classes.delete(name);},toggle(name,on){on ? classes.add(name) : classes.delete(name);}}},
      addEventListener() {}, hidden:false
    },
    location:{protocol:'https:'},
    setTimeout(){return 1;}, clearTimeout(){},
    setInterval(fn, ms){intervals.push({fn, ms});},
    async fetch(url){
      requestedUrl = url;
      if (data instanceof Error) throw data;
      return {ok:true, async json(){return data;}};
    }
  });
  vm.runInContext(code, context);
  return {elements, classes, intervals, context, url:()=>requestedUrl,
    setTime(value){timestamp = new Date(value).getTime();},
    async settled(){await new Promise(resolve=>setImmediate(resolve));}};
}

function status(found = false) {
  return {date:'2026-10-08',checkedAt:'2026-10-08T09:50:00Z',found,complete:true,updateIntervalMinutes:30,
    sources:[{ok:true,found,matches:found?['Jägerschnitzel']:[],note:'Kein Treffer'},
             {ok:true,found:false,matches:[],note:'Kein Treffer'}]};
}

test('Treffer wird angezeigt; JSON wird relativ zum Repository geladen', async()=>{
  const app=run(status(true)); await app.settled();
  assert.match(app.elements.get('message').textContent,/^Juchu!/);
  assert.ok(app.classes.has('yes'));
  assert.match(app.url(),/^\.\/status\.json\?t=/);
  assert.equal(app.elements.get('warning').hidden,true);
});

test('Kein Treffer zeigt die exakte Standardmeldung', async()=>{
  const app=run(status()); await app.settled();
  assert.equal(app.elements.get('message').textContent,'Leider, gibt es heute kein Jägerschnitzel auf dem Telegrafenberg');
});

test('Treffer vom Vortag zählt nicht', async()=>{
  const data=status(true);data.date='2026-10-07';data.checkedAt='2026-10-07T10:00:00Z';
  const app=run(data);await app.settled();
  assert.match(app.elements.get('message').textContent,/^Leider/);
  assert.match(app.elements.get('warning').textContent,/Für heute/);
});

test('Teilweiser Ausfall verhindert den Treffer der anderen Quelle nicht', async()=>{
  const data=status(true);data.complete=false;data.sources[1].ok=false;
  const app=run(data);await app.settled();
  assert.match(app.elements.get('message').textContent,/^Juchu!/);
  assert.match(app.elements.get('warning').textContent,/unvollständig/);
});

test('Netzwerkfehler zeigt Standardmeldung und Fehlerhinweis', async()=>{
  const app=run(new Error('Offline'));await app.settled();
  assert.match(app.elements.get('message').textContent,/^Leider/);
  assert.match(app.elements.get('warning').textContent,/nicht abrufbar/);
  assert.equal(app.elements.get('refresh').disabled,false);
});

test('Verzögerte Aktualisierung wird kenntlich gemacht', async()=>{
  const data=status(true);data.checkedAt='2026-10-08T07:00:00Z';
  const app=run(data);await app.settled();
  assert.match(app.elements.get('warning').textContent,/90 Minuten/);
});

test('Berliner Mitternacht entfernt den alten Treffer im offenen Tab', async()=>{
  const data=status(true);data.checkedAt='2026-10-08T21:40:00Z';
  const app=run(data,'2026-10-08T21:59:59Z');await app.settled();
  assert.match(app.elements.get('message').textContent,/^Juchu!/);
  app.setTime('2026-10-08T22:00:00Z');app.intervals.find(i=>i.ms===1000).fn();
  assert.match(app.elements.get('message').textContent,/^Leider/);
  await app.settled();assert.match(app.elements.get('warning').textContent,/Für heute/);
});

test('Berlin-Datum berücksichtigt Sommer- und Winterzeit', async()=>{
  const app=run(status());await app.settled();
  assert.equal(vm.runInContext("berlinDate(new Date('2026-07-01T22:30:00Z'))",app.context),'2026-07-02');
  assert.equal(vm.runInContext("berlinDate(new Date('2026-01-01T22:30:00Z'))",app.context),'2026-01-01');
});

test('Zukünftiger Termin nennt Datum und beide Küchen', async()=>{
  const data=status();data.forecast={complete:true,next:{date:'2026-10-12',sources:[{name:'Mensa'},{name:'Café'}]},sources:[]};
  const app=run(data);await app.settled();
  assert.match(app.elements.get('next-date').textContent,/Montag, 12\. Oktober 2026/);
  assert.match(app.elements.get('next-detail').textContent,/Mensa und Café/);
  assert.match(app.elements.get('message').textContent,/^Leider/);
});

test('Keine Ankündigung und Ausfall werden unterschieden', async()=>{
  for (const complete of [true,false]) {
    const data=status();data.forecast={complete,next:null,sources:[]};
    const app=run(data);await app.settled();
    assert.match(app.elements.get('next-date').textContent,complete?/kein weiterer Termin/:/nicht vollständig prüfbar/);
  }
});

test('Vorschau verschwindet ebenfalls beim Tageswechsel', async()=>{
  const data=status();data.checkedAt='2026-10-08T21:40:00Z';
  data.forecast={complete:true,next:{date:'2026-10-09',sources:[{name:'Mensa'}]},sources:[]};
  const app=run(data,'2026-10-08T21:59:59Z');await app.settled();
  assert.match(app.elements.get('next-date').textContent,/9\. Oktober/);
  app.setTime('2026-10-08T22:00:00Z');app.intervals.find(i=>i.ms===1000).fn();
  await app.settled();assert.match(app.elements.get('next-date').textContent,/kein aktuelles/i);
});
