#!/usr/bin/env python3
"""
INGLY DESIGN — I più venduti, e come rifarli con il nostro stile
===============================================================

Quarto catalogo. Non i nostri prodotti e non i nostri fornitori: cosa vende
davvero nel mondo, dove stanno i file, cosa sbagliano tutti, e per ognuno il
prompt per rifarlo con la geometria, la finitura e la palette di Ingly.

Due scelte che vale la pena dichiarare subito:

1. Nessun link a singole inserzioni con numeri di vendita. Quel dato cambia
   ogni giorno e chi lo pubblica in un catalogo lo pubblica già falso. I
   riferimenti sono pagine di categoria: mostrano lo stesso fenomeno senza
   indicare un venditore da copiare.

2. Il punteggio di opportunità premia la concorrenza BASSA. E' il contrario
   di come si leggono di solito le classifiche dei best seller: un prodotto
   con domanda enorme e concorrenza estrema e' una trappola, non un'occasione.

    python3 scripts/build_bestseller.py  ->  out/bestseller.html + .json + .csv
"""

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from build import CSS, DL_JS, esc          # noqa: E402  stesso sistema visivo

DATA = ROOT / "data" / "bestseller"
OUT = ROOT / "out"

SIS = json.load(open(DATA / "sistema.json", encoding="utf-8"))
VOCI = (json.load(open(DATA / "voci_a.json", encoding="utf-8"))["voci"]
        + json.load(open(DATA / "voci_b.json", encoding="utf-8"))["voci"])

CATS = SIS["categorie"]

SCALA_DOMANDA = {"molto alta": 4, "alta": 3, "media": 2, "bassa": 1}
SCALA_CONCORRENZA = {"bassa": 4, "media": 3, "alta": 2, "estrema": 1}
SCALA_DIFFICOLTA = {"bassa": 3, "media": 2, "alta": 1}
PESI = {"domanda": 25, "concorrenza": 25, "prezzo": 25, "difficolta": 15, "ip": 10}
SOGLIE = [("ENTRARE", 70), ("TESTARE", 58), ("VALUTARE", 46), ("EVITARE", 0)]


def livello_ip(testo):
    """Il rischio dichiarato all'inizio della stringa e' quello che conta.
    La punteggiatura che segue va tolta, altrimenti 'BASSO.' e 'BASSO,'
    diventano due livelli diversi e rompono filtri e conteggi."""
    t = testo.strip().upper()
    for lv in ("BASSO", "MEDIO", "ALTO"):
        if t.startswith(lv):
            return lv
    return "ALTO"


def scala_ip(testo):
    return {"BASSO": 3, "MEDIO": 2, "ALTO": 1}[livello_ip(testo)]


def punteggio_prezzo(prezzo_ingly):
    """0-1 saturante. Un prodotto da 15 euro non e' meta' di uno da 30:
    sotto una certa soglia il tempo macchina non rientra mai."""
    medio = (prezzo_ingly[0] + prezzo_ingly[1]) / 2.0
    if medio <= 10:
        return 0.0
    return min(1.0, (medio - 10) / 80.0)


def opportunita(v):
    d = SCALA_DOMANDA[v["domanda"]] / 4.0
    c = SCALA_CONCORRENZA[v["concorrenza"]] / 4.0
    f = SCALA_DIFFICOLTA[v["difficolta"]] / 3.0
    i = scala_ip(v["rischio_ip"]) / 3.0
    p = punteggio_prezzo(v["prezzo_ingly"])
    tot = (d * PESI["domanda"] + c * PESI["concorrenza"] + p * PESI["prezzo"]
           + f * PESI["difficolta"] + i * PESI["ip"])
    return round(tot, 1)


def verdetto(punti):
    for nome, soglia in SOGLIE:
        if punti >= soglia:
            return nome
    return "EVITARE"


def controlla():
    """Meglio fermarsi qui che scoprire un id doppio dentro l'HTML."""
    err = []
    visti = set()
    for v in VOCI:
        if v["id"] in visti:
            err.append(f'{v["id"]}: identificativo usato due volte')
        visti.add(v["id"])
        if v["cat"] not in CATS:
            err.append(f'{v["id"]}: categoria "{v["cat"]}" non esiste in sistema.json')
        if not v["ref"].startswith("https://"):
            err.append(f'{v["id"]}: riferimento non e\' un indirizzo valido')
        if v["prezzo_ingly"][0] >= v["prezzo_ingly"][1]:
            err.append(f'{v["id"]}: fascia di prezzo Ingly invertita')
        if v["prezzo_mkt"][0] >= v["prezzo_mkt"][1]:
            err.append(f'{v["id"]}: fascia di prezzo di mercato invertita')
        for campo in ("prompt_design", "prompt_img", "riscrittura", "il_gap"):
            if len(v.get(campo, "")) < 60:
                err.append(f'{v["id"]}: campo {campo} troppo corto per essere utile')
    if err:
        for e in err:
            print("  ERRORE:", e)
        sys.exit(f"\n{len(err)} errori: correggi i dati prima di generare.")


controlla()

for v in VOCI:
    v["punteggio"] = opportunita(v)
    v["verdetto"] = verdetto(v["punteggio"])
    mm = (v["prezzo_mkt"][0] + v["prezzo_mkt"][1]) / 2.0
    mi = (v["prezzo_ingly"][0] + v["prezzo_ingly"][1]) / 2.0
    v["posizionamento_pct"] = round((mi / mm - 1) * 100, 1)

ORDINE_CAT = list(CATS.keys())
VOCI.sort(key=lambda v: (ORDINE_CAT.index(v["cat"]), -v["punteggio"]))


# ---------------------------------------------------------------- html

CSS_EXTRA = """
.sec{margin:52px 0 0}
.sec-h{font-family:var(--mono);font-size:10px;letter-spacing:.24em;text-transform:uppercase;
color:var(--acc);border-bottom:1px solid var(--rule2);padding-bottom:8px;margin-bottom:6px}
.v{border:1px solid var(--rule2);background:var(--surface);margin:14px 0}
.v-h{display:flex;flex-wrap:wrap;align-items:baseline;gap:8px 14px;padding:12px 16px;
border-bottom:1px solid var(--rule2);background:var(--surface2)}
.v-h .id{font-family:var(--mono);font-size:11px;letter-spacing:.08em;color:var(--soft)}
.v-h h3{margin:0;font-size:19px;font-weight:800;letter-spacing:-.02em}
.v-h .en{font-family:var(--serif);font-style:italic;font-size:14px;color:var(--soft)}
.v-h .sp{flex:1}
.v-b{display:grid;grid-template-columns:1.15fr 1fr;gap:0}
@media(max-width:820px){.v-b{grid-template-columns:1fr}}
.v-l{padding:16px;border-right:1px solid var(--rule)}
@media(max-width:820px){.v-l{border-right:none;border-bottom:1px solid var(--rule)}}
.v-l p{margin:0 0 9px;font-family:var(--serif);font-size:15.5px;line-height:1.58;color:var(--mid)}
.v-l p:last-child{margin-bottom:0}
.v-l b{color:var(--ink)}
dl.v-s{margin:0;padding:16px;font-family:var(--mono);font-size:11.5px;line-height:1.5}
dl.v-s>div{display:grid;grid-template-columns:92px 1fr;gap:10px;padding:4px 0;
border-bottom:1px dotted var(--rule)}
dl.v-s>div:last-child{border-bottom:none}
dl.v-s dt{color:var(--soft);letter-spacing:.06em;text-transform:uppercase;font-size:9.5px;padding-top:1px}
dl.v-s dd{margin:0;color:var(--ink);font-variant-numeric:tabular-nums;word-break:break-word}
dl.v-s dd a{color:var(--acc)}
.gapbox{background:var(--accw);border-left:3px solid var(--accb);padding:12px 16px;margin:10px 0 0}
.gapbox b{display:block;font-family:var(--mono);font-size:9.5px;letter-spacing:.18em;
text-transform:uppercase;color:var(--acc);margin-bottom:6px}
.gapbox p{margin:0;font-family:var(--serif);font-size:15px;line-height:1.55;color:var(--mid)}
.pr{border-top:1px solid var(--rule2);background:var(--surface2)}
.pr b{display:block;font-family:var(--mono);font-size:9.5px;letter-spacing:.18em;
text-transform:uppercase;color:var(--acc);padding:9px 16px 0}
.pr pre{margin:0;padding:6px 16px 14px;font-family:var(--mono);font-size:11.5px;line-height:1.6;
color:var(--mid);white-space:pre-wrap;word-break:break-word}
.b-ENTRARE{color:var(--ok)}.b-TESTARE{color:var(--sea)}
.b-VALUTARE{color:var(--warn)}.b-EVITARE{color:var(--crit)}
.b-ip-ALTO{color:var(--crit)}.b-ip-MEDIO{color:var(--warn)}.b-ip-BASSO{color:var(--soft)}
.box{background:var(--accw);border-left:3px solid var(--accb);padding:16px 20px;margin:18px 0}
.box b.t{display:block;font-family:var(--mono);font-size:10px;letter-spacing:.18em;
text-transform:uppercase;color:var(--acc);margin-bottom:8px}
.box p,.box li{font-family:var(--serif);font-size:15.5px;line-height:1.6;color:var(--mid)}
.box ol,.box ul{margin:8px 0 0;padding-left:20px}
.box li{margin-bottom:6px}
.f{border:1px solid var(--rule2);background:var(--surface);padding:14px 16px;margin:10px 0}
.f h4{margin:0 0 4px;font-size:16px;font-weight:800}
.f p{margin:0 0 8px;font-family:var(--serif);font-size:15px;line-height:1.55;color:var(--mid)}
.f a{color:var(--acc);font-family:var(--mono);font-size:11px;word-break:break-all}
.fgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:12px;margin:16px 0}
"""

FILTRI_JS = """
const q=document.getElementById('q'),fc=document.getElementById('fcat'),
fv=document.getElementById('fver'),fi=document.getElementById('fip'),n=document.getElementById('n');
function apply(){const t=(q.value||'').toLowerCase(),c=fc.value,ve=fv.value,ip=fi.value;let v=0;
document.querySelectorAll('.v').forEach(function(el){
 const ok=(!t||el.dataset.s.indexOf(t)>-1)&&(!c||el.dataset.cat===c)
  &&(!ve||el.dataset.ver===ve)&&(!ip||el.dataset.ip===ip);
 el.style.display=ok?'':'none';if(ok)v++;});
document.querySelectorAll('section.grp').forEach(function(s){
 s.style.display=s.querySelectorAll('.v:not([style*="none"])').length?'':'none';});
n.textContent=v+' prodotti';}
[q,fc,fv,fi].forEach(function(e){e.addEventListener('input',apply)});
"""


def costruisci():
    per_cat = {}
    for v in VOCI:
        per_cat.setdefault(v["cat"], []).append(v)

    entrare = [v for v in VOCI if v["verdetto"] == "ENTRARE"]
    ip_alto = [v for v in VOCI if scala_ip(v["rischio_ip"]) == 1]
    top = sorted(VOCI, key=lambda v: -v["punteggio"])[:6]

    h = []
    a = h.append
    a('<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">')
    a("<title>Cosa vende nel mondo</title>")
    a(f"<style>{CSS}{CSS_EXTRA}</style>")

    a('<header class="top"><div class="wrap" style="padding-top:26px">')
    a('<div class="marchio">Ingly Design — Intelligence di mercato</div>')
    a("<h1>Cosa vende,<br>e <em>come rifarlo</em></h1>")
    a('<p class="sub">I prodotti più venduti e più cercati, categoria per categoria, con i link '
      'di riferimento, le fonti dei file, cosa sbagliano tutti — e per ognuno il prompt per '
      'ricostruirlo con la nostra geometria invece che copiarlo.</p>')
    a('</div><dl class="kpis">')
    for k, val in [("Prodotti", len(VOCI)), ("Categorie", len(per_cat)),
                   ("Da fare subito", len(entrare)), ("Rischio IP alto", len(ip_alto)),
                   ("Fonti file", len(SIS["fonti_file"])),
                   ("Parole chiave", len(SIS["parole_chiave"]["voci"]))]:
        a(f"<div><dt>{k}</dt><dd>{val}</dd></div>")
    a("</dl></header>")

    a('<div class="tools"><div class="tools-in">')
    a('<input type="search" id="q" placeholder="cerca prodotto, materiale, tecnica…" '
      'aria-label="Cerca">')
    a('<select id="fcat" aria-label="Categoria"><option value="">tutte le categorie</option>')
    for cid in ORDINE_CAT:
        if cid in per_cat:
            a(f'<option value="{cid}">{esc(CATS[cid]["nome"])}</option>')
    a("</select>")
    a('<select id="fver" aria-label="Verdetto"><option value="">tutti i verdetti</option>')
    for nome, _ in SOGLIE:
        a(f'<option value="{nome}">{nome.lower()}</option>')
    a("</select>")
    a('<select id="fip" aria-label="Rischio IP"><option value="">tutti i rischi</option>'
      '<option value="BASSO">ip basso</option><option value="MEDIO">ip medio</option>'
      '<option value="ALTO">ip alto</option></select>')
    a(f'<span class="count" id="n">{len(VOCI)} prodotti</span>')
    a('<span style="flex:1"></span>')
    a('<span class="dl"><button class="dl-b" data-dl="md">scarica md</button>'
      '<button class="dl-b" data-dl="csv">csv</button>'
      '<button class="dl-b" data-dl="json">json</button></span>')
    a('<span class="count" id="dlmsg" role="status" aria-live="polite"></span>')
    a("</div></div>")

    a('<div class="wrap">')

    a('<div class="box"><b class="t">Come leggere questa pagina</b>')
    a(f'<p>{esc(SIS["_meta"]["cosa_non_e_verificato"])}</p>')
    a(f'<p>{esc(SIS["_meta"]["perche_niente_inserzioni_singole"])}</p>')
    a(f'<p>{esc(SIS["_meta"]["regola_di_uso"])}</p>')
    a('<p><b>Il punteggio di opportunità premia la concorrenza bassa.</b> È il contrario di come '
      'si leggono di solito le classifiche dei più venduti: un prodotto con domanda enorme e '
      'concorrenza estrema non è un&#39;occasione, è una guerra di prezzo già persa. I cinque assi '
      'sono domanda 25, concorrenza 25, prezzo Ingly atteso 25, facilità 15, rischio di proprietà '
      'intellettuale 10.</p></div>')

    # ---- top
    a('<section class="sec"><div class="sec-h">Dove entrare per primo</div>')
    a("<h2>I sei con il rapporto migliore</h2>")
    a('<div class="tw"><table><thead><tr><th>Prodotto</th><th>Categoria</th><th>Domanda</th>'
      "<th>Concorrenza</th><th>Prezzo Ingly</th><th>Punt.</th><th>Verdetto</th></tr></thead><tbody>")
    for v in top:
        a(f'<tr><td><b>{esc(v["nome"])}</b></td><td>{esc(CATS[v["cat"]]["nome"])}</td>'
          f'<td>{esc(v["domanda"])}</td><td>{esc(v["concorrenza"])}</td>'
          f'<td>{v["prezzo_ingly"][0]}–{v["prezzo_ingly"][1]} &euro;</td>'
          f'<td>{v["punteggio"]:.0f}</td>'
          f'<td class="b-{v["verdetto"]}">{esc(v["verdetto"].lower())}</td></tr>')
    a("</tbody></table></div></section>")

    # ---- parole chiave
    pk = SIS["parole_chiave"]
    a('<section class="sec"><div class="sec-h">Domanda</div>')
    a("<h2>Le parole che la gente cerca</h2>")
    a(f'<p class="cat-an">{esc(pk["avvertenza"])} Fonte: {esc(pk["fonte"])}.</p>')
    a('<div class="tw"><table><thead><tr><th>Parola chiave</th><th>Ricerche/mese stimate</th>'
      "<th>Cosa significa per noi</th></tr></thead><tbody>")
    for k in pk["voci"]:
        a(f'<tr><td><b>{esc(k["kw"])}</b></td><td>{k["vol"]:,}</td>'
          f'<td>{esc(k["nota"])}</td></tr>'.replace(",", "."))
    a("</tbody></table></div>")
    a(f'<div class="box"><b class="t">La lettura che conta</b><p>{esc(pk["lettura_ingly"])}</p></div>')
    a("</section>")

    # ---- schede
    for cid in ORDINE_CAT:
        if cid not in per_cat:
            continue
        a(f'<section class="grp sec"><div class="sec-h">{esc(CATS[cid]["nome"])}</div>')
        a(f'<h2>{esc(CATS[cid]["nome"])}</h2>')
        a(f'<p class="cat-an">{esc(CATS[cid]["analisi"])}</p>')
        for v in per_cat[cid]:
            ipl = livello_ip(v["rischio_ip"])
            hay = " ".join([v["nome"], v["nome_en"], v["cosa_e"], v["materiali"],
                            v["tech"], v["riscrittura"]]).lower()
            a(f'<article class="v" data-dlid="{v["id"]}" data-cat="{v["cat"]}" '
              f'data-ver="{v["verdetto"]}" data-ip="{ipl}" data-s="{esc(hay)}">')
            a('<div class="v-h">')
            a(f'<span class="id">{v["id"]}</span><h3>{esc(v["nome"])}</h3>')
            a(f'<span class="en">{esc(v["nome_en"])}</span>')
            a('<span class="sp"></span>')
            a(f'<span class="badge b-ip-{ipl}">ip {esc(ipl.lower())}</span>')
            a(f'<span class="badge b-{v["verdetto"]}">{esc(v["verdetto"].lower())}</span>')
            a(f'<span class="sc">{v["punteggio"]:.0f}</span>')
            a("</div>")

            a('<div class="v-b"><div class="v-l">')
            a(f'<p>{esc(v["cosa_e"])}</p>')
            a(f'<p><b>Perché vende.</b> {esc(v["perche_vende"])}</p>')
            a(f'<p><b>Cosa fanno tutti.</b> {esc(v["cosa_fanno_tutti"])}</p>')
            a(f'<div class="gapbox"><b>Il buco</b><p>{esc(v["il_gap"])}</p></div>')
            a(f'<p style="margin-top:12px"><b>Come lo rifacciamo.</b> {esc(v["riscrittura"])}</p>')
            a("</div>")

            a('<dl class="v-s">')
            a(f'<div><dt>Riferimento</dt><dd><a href="{esc(v["ref"])}" target="_blank" '
              f'rel="noopener">{esc(v["ref"])}</a></dd></div>')
            a(f'<div><dt>Mercato</dt><dd>{v["prezzo_mkt"][0]}–{v["prezzo_mkt"][1]} &euro;</dd></div>')
            seg = "+" if v["posizionamento_pct"] >= 0 else ""
            a(f'<div><dt>Prezzo Ingly</dt><dd class="prz">{v["prezzo_ingly"][0]}–'
              f'{v["prezzo_ingly"][1]} &euro; <span style="color:var(--soft)">'
              f'({seg}{v["posizionamento_pct"]:.0f}% sul medio)</span></dd></div>')
            for k, val in [("Domanda", v["domanda"]), ("Concorrenza", v["concorrenza"]),
                           ("Difficoltà", v["difficolta"]), ("Materiali", v["materiali"]),
                           ("Tecnologia", v["tech"]), ("Piattaforma", v["piattaforma"]),
                           ("Base Ingly", v["base_ingly"]), ("Rischio IP", v["rischio_ip"]),
                           ("Fonti file", ", ".join(v["fonti"]))]:
                a(f"<div><dt>{k}</dt><dd>{esc(val)}</dd></div>")
            a("</dl></div>")

            a(f'<div class="pr"><b>Prompt di produzione — versione Ingly</b>'
              f'<pre>{esc(v["prompt_design"])}</pre></div>')
            a(f'<div class="pr"><b>Prompt immagine di catalogo</b>'
              f'<pre>{esc(v["prompt_img"])}</pre></div>')
            a("</article>")
        a("</section>")

    # ---- riscrittura
    rr = SIS["regole_di_riscrittura"]
    a('<section class="sec"><div class="sec-h">Metodo</div>')
    a(f'<h2>{esc(rr["titolo"])}</h2>')
    a('<div class="box"><ol>')
    for p in rr["passi"]:
        a(f"<li>{esc(p)}</li>")
    a("</ol></div></section>")

    # ---- fonti file
    a('<section class="sec"><div class="sec-h">Dove stanno i file</div>')
    a("<h2>Fonti di materiale digitale</h2>")
    a('<p class="cat-an">Ordinate per quello che conta davvero, che non è il prezzo ma la licenza. '
      'La regola generale del settore resta quella già documentata: la maggior parte dei file laser '
      'preconfezionati è concessa solo per uso personale. Le eccezioni qui sotto sono eccezioni, e '
      'vanno verificate sul singolo file prima di produrre.</p>')
    a('<div class="fgrid">')
    for f in SIS["fonti_file"]:
        a('<div class="f">')
        a(f'<h4>{esc(f["nome"])}</h4>')
        a(f'<p><b>Licenza.</b> {esc(f["licenza"])}</p>')
        a(f'<p>{esc(f["nota"])}</p>')
        a(f'<p><b>Come la usiamo.</b> {esc(f["uso_ingly"])}</p>')
        a('<dl class="v-s" style="padding:0">')
        for k, val in [("Tipo", f["tipo"]), ("Volume", f["volume"]),
                       ("Costo", f["costo"]), ("Formati", f["formati"])]:
            a(f"<div><dt>{k}</dt><dd>{esc(val)}</dd></div>")
        a("</dl>")
        a(f'<a href="{esc(f["url"])}" target="_blank" rel="noopener">{esc(f["url"])}</a>')
        a("</div>")
    a("</div></section>")

    # ---- competitor
    a('<section class="sec"><div class="sec-h">Chi fa già queste cose</div>')
    a("<h2>Competitor osservati</h2>")
    for c in SIS["competitor_osservati"]:
        a('<div class="f">')
        a(f'<h4>{esc(c["nome"])}</h4>')
        a(f'<p>{esc(c["cosa_fa"])}</p>')
        a(f'<p><b>Cosa impariamo.</b> {esc(c["cosa_impariamo"])}</p>')
        a(f'<p><b>Come ci differenziamo.</b> {esc(c["come_ci_differenziamo"])}</p>')
        a(f'<a href="{esc(c["url"])}" target="_blank" rel="noopener">{esc(c["url"])}</a>')
        a("</div>")
    a("</section>")

    # ---- fonti dati
    a('<section class="sec"><div class="sec-h">Da dove vengono questi dati</div>')
    a("<h2>Le fonti</h2>")
    a('<div class="tw"><table><thead><tr><th>Fonte</th><th>Cosa dà</th></tr></thead><tbody>')
    for f in SIS["fonti_dati"]:
        a(f'<tr><td><b>{esc(f["nome"])}</b><br>'
          f'<a href="{esc(f["url"])}" target="_blank" rel="noopener" '
          f'style="font-family:var(--mono);font-size:10.5px">{esc(f["url"])}</a></td>'
          f'<td>{esc(f["cosa_da"])}</td></tr>')
    a("</tbody></table></div></section>")

    a('</div><footer><div class="wrap">')
    a('<div class="marchio">Ingly Design</div>')
    a('<p style="margin-top:12px">Nessun marketplace pubblica i volumi di vendita reali per '
      'prodotto. I volumi di ricerca sono <b>stime di strumenti terzi</b> riprese da rassegne di '
      'settore, utili a confrontare le parole chiave fra loro e non a prevedere un fatturato. '
      'Le fasce di prezzo sono osservazioni di categoria. I riferimenti sono pagine di ricerca per '
      'parola chiave, non singole inserzioni: un catalogo che riporta il numero di vendite di un '
      'negozio nasce già falso, perché quel dato cambia ogni giorno. I prodotti elencati sono '
      '<b>archetipi</b>, cioè funzioni più forme generiche, e le funzioni non sono di nessuno: '
      'il disegno di un concorrente sì.</p>')
    a("</div></footer>")

    a('<script type="application/json" id="dati">'
      + json.dumps(VOCI, ensure_ascii=False).replace("</", "<\\/") + "</script>")
    a('<script type="application/json" id="extra">'
      + json.dumps({"fonti_file": SIS["fonti_file"], "competitor": SIS["competitor_osservati"],
                    "parole": SIS["parole_chiave"], "regole": SIS["regole_di_riscrittura"],
                    "fonti_dati": SIS["fonti_dati"]},
                   ensure_ascii=False).replace("</", "<\\/") + "</script>")
    a('<script>const DATI=JSON.parse(document.getElementById("dati").textContent);'
      'const EXTRA=JSON.parse(document.getElementById("extra").textContent);'
      'const NOMEFILE="bestseller";const IDKEY="id";'
      'const MD=function(rs){'
      'var o="# Ingly Design - Cosa vende, e come rifarlo\\n\\n";'
      'o+="## Parole chiave\\n\\n"+EXTRA.parole.avvertenza+"\\n\\n";'
      'EXTRA.parole.voci.forEach(function(k){o+="- **"+k.kw+"**: "+k.vol+"/mese stimate. "'
      '+k.nota+"\\n"});'
      'o+="\\n## Prodotti ("+rs.length+")\\n\\n";'
      'o+=rs.map(function(r){return "### "+r.nome+" ("+r.nome_en+")\\n\\n"'
      '+r.cosa_e+"\\n\\n**Perche vende.** "+r.perche_vende'
      '+"\\n\\n**Cosa fanno tutti.** "+r.cosa_fanno_tutti'
      '+"\\n\\n**Il buco.** "+r.il_gap'
      '+"\\n\\n**Come lo rifacciamo.** "+r.riscrittura'
      '+"\\n\\n**Mercato** "+r.prezzo_mkt[0]+"-"+r.prezzo_mkt[1]+" EUR'
      '  \\n**Prezzo Ingly** "+r.prezzo_ingly[0]+"-"+r.prezzo_ingly[1]+" EUR'
      '  \\n**Domanda** "+r.domanda+"  \\n**Concorrenza** "+r.concorrenza'
      '+"  \\n**Difficolta** "+r.difficolta+"  \\n**Materiali** "+r.materiali'
      '+"  \\n**Tecnologia** "+r.tech+"  \\n**Piattaforma** "+r.piattaforma'
      '+"  \\n**Base Ingly** "+r.base_ingly+"  \\n**Rischio IP** "+r.rischio_ip'
      '+"  \\n**Punteggio** "+r.punteggio+" ("+r.verdetto+")'
      '  \\n**Riferimento** "+r.ref'
      '+"  \\n**Fonti file** "+r.fonti.join(", ")'
      '+"\\n\\n#### Prompt di produzione\\n\\n"+r.prompt_design'
      '+"\\n\\n#### Prompt immagine\\n\\n"+r.prompt_img+"\\n"'
      '}).join("\\n---\\n\\n");'
      'o+="\\n\\n## "+EXTRA.regole.titolo+"\\n\\n";'
      'EXTRA.regole.passi.forEach(function(p,i){o+=(i+1)+". "+p+"\\n"});'
      'o+="\\n## Fonti di file\\n\\n";'
      'EXTRA.fonti_file.forEach(function(f){o+="### "+f.nome+"\\n\\n**Licenza** "+f.licenza'
      '+"  \\n**Costo** "+f.costo+"  \\n**Formati** "+f.formati+"  \\n**Link** "+f.url'
      '+"\\n\\n"+f.nota+"\\n\\n"+f.uso_ingly+"\\n\\n"});'
      'o+="## Competitor osservati\\n\\n";'
      'EXTRA.competitor.forEach(function(c){o+="### "+c.nome+"\\n\\n"+c.cosa_fa'
      '+"\\n\\n**Cosa impariamo.** "+c.cosa_impariamo'
      '+"\\n\\n**Come ci differenziamo.** "+c.come_ci_differenziamo+"\\n\\n"+c.url+"\\n\\n"});'
      'o+="## Fonti dei dati\\n\\n";'
      'EXTRA.fonti_dati.forEach(function(f){o+="- ["+f.nome+"]("+f.url+"): "+f.cosa_da+"\\n"});'
      "return o};</script>")
    a(f"<script>{DL_JS}</script>")
    a(f"<script>{FILTRI_JS}</script>")

    return "\n".join(h)


def main():
    OUT.mkdir(exist_ok=True)

    (OUT / "bestseller.html").write_text(costruisci(), encoding="utf-8")

    with open(OUT / "bestseller.json", "w", encoding="utf-8") as fh:
        json.dump({"voci": VOCI, "sistema": SIS}, fh, ensure_ascii=False, indent=2)

    righe = []
    for v in VOCI:
        r = dict(v)
        r["fonti"] = " | ".join(v["fonti"])
        r["prezzo_mkt"] = f'{v["prezzo_mkt"][0]}-{v["prezzo_mkt"][1]}'
        r["prezzo_ingly"] = f'{v["prezzo_ingly"][0]}-{v["prezzo_ingly"][1]}'
        r["categoria"] = CATS[v["cat"]]["nome"]
        righe.append(r)
    with open(OUT / "bestseller.csv", "w", newline="", encoding="utf-8") as fh:
        fh.write("﻿")
        w = csv.DictWriter(fh, fieldnames=list(righe[0].keys()),
                           extrasaction="ignore", delimiter=";")
        w.writeheader()
        w.writerows(righe)

    per_cat = {}
    for v in VOCI:
        per_cat.setdefault(v["cat"], []).append(v)

    print(f"\n{len(VOCI)} prodotti · {len(per_cat)} categorie su {len(CATS)}\n")
    print(f"{'Categoria':<28}{'N':>3}{'Punt. medio':>13}   {'Migliore':<30}")
    print("-" * 78)
    for cid in ORDINE_CAT:
        if cid not in per_cat:
            continue
        vs = per_cat[cid]
        med = sum(v["punteggio"] for v in vs) / len(vs)
        print(f'{CATS[cid]["nome"]:<28}{len(vs):>3}{med:>13.1f}   {vs[0]["nome"][:30]:<30}')
    print("-" * 78)

    conta = {}
    for v in VOCI:
        conta[v["verdetto"]] = conta.get(v["verdetto"], 0) + 1
    print("Verdetti: " + "  ".join(f"{k}={v}" for k, v in
                                   sorted(conta.items(), key=lambda x: -x[1])))
    ip = {}
    for v in VOCI:
        k = livello_ip(v["rischio_ip"])
        ip[k] = ip.get(k, 0) + 1
    print("Rischio IP: " + "  ".join(f"{k}={v}" for k, v in sorted(ip.items())))

    print("\nI sei con il rapporto migliore fra domanda, concorrenza e prezzo:")
    for v in sorted(VOCI, key=lambda x: -x["punteggio"])[:6]:
        print(f'  {v["punteggio"]:>5.1f}  {v["nome"][:32]:<32} '
              f'{v["prezzo_ingly"][0]}–{v["prezzo_ingly"][1]} € · '
              f'concorrenza {v["concorrenza"]}')

    print(f"\nOutput in {OUT}/")


if __name__ == "__main__":
    main()
