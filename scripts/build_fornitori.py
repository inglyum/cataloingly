#!/usr/bin/env python3
"""
INGLY DESIGN — Fornitori di materiale grezzo e di blank
=======================================================

Terzo catalogo: non cosa vendere, ma dove comprare. Pannelli in legno 3-4-6 mm,
PMMA, laminati e metalli per la fiber, blank neutri per la ristorazione e
grossisti di articoli promozionali, italiani ed europei.

Due cose che questo script fa e che un elenco non farebbe:

1. Il punteggio. Cinque assi dichiarati (prezzo, qualita', gamma, facilita',
   logistica) pesati, cosi' il ranking e' discutibile invece che oracolare.

2. Il confronto preventivi. Se esiste data/preventivi.csv lo legge e calcola
   l'unica cifra che conta davvero: l'euro per metro quadro UTILE, cioe'
   materiale piu' trasporto diviso la superficie che resta dopo lo scarto.
   Il prezzo del pannello non e' il costo del pannello.

    python3 scripts/build_fornitori.py
        -> out/fornitori.html + .json + .csv + preventivi_template.csv
"""

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from build import CSS, DL_JS, esc          # noqa: E402  stesso sistema visivo

DATA = ROOT / "data"
OUT = ROOT / "out"

DB = json.load(open(DATA / "fornitori.json", encoding="utf-8"))
PESI = DB["pesi_punteggio"]
ASSI = [("p_prezzo", "prezzo"), ("p_qualita", "qualita"), ("p_gamma", "gamma"),
        ("p_facilita", "facilita"), ("p_logistica", "logistica")]

ORDINE_TIPI = ["LEGNO_IT", "LEGNO_EU", "PLASTICHE", "LAMINATI_METALLI",
               "BLANK_HORECA", "GADGET_PROMO", "DIRECTORY"]


# ---------------------------------------------------------------- calcoli

def punteggio(f):
    """0-100. Media pesata dei cinque assi dichiarati, niente di piu'."""
    tot = sum(f[k] / 10.0 * PESI[nome] for k, nome in ASSI)
    return round(tot, 1)


def eur_mq(voce):
    """Euro al metro quadro di una singola riga di listino rilevata."""
    a, b = voce["formato_mm"]
    mq = (a / 1000.0) * (b / 1000.0)
    return round(voce["eur"] / mq, 2) if mq else None


def arricchisci(f):
    r = dict(f)
    r["punteggio"] = punteggio(f)
    pr = f.get("prezzo_rilevato")
    if pr:
        calc = []
        for v in pr["voci"]:
            calc.append({**v, "eur_mq": eur_mq(v)})
        r["prezzo_rilevato"] = {**pr, "voci": calc}
        vals = [c["eur_mq"] for c in calc if c["eur_mq"]]
        r["eur_mq_min"] = min(vals) if vals else None
        r["eur_mq_max"] = max(vals) if vals else None
    else:
        r["eur_mq_min"] = None
        r["eur_mq_max"] = None
    return r


FORNITORI = [arricchisci(f) for f in DB["fornitori"]]
FORNITORI.sort(key=lambda f: (ORDINE_TIPI.index(f["tipo"]), -f["punteggio"]))


# ------------------------------------------------- confronto preventivi

COLONNE_PREV = ["fornitore", "materiale", "spessore_mm", "lato_a_mm", "lato_b_mm",
                "n_lastre", "prezzo_lastre_eur", "trasporto_eur", "scarto_pct", "note"]


def scrivi_template_preventivi(path):
    """Il foglio da compilare mano a mano che arrivano le risposte."""
    esempio = {
        "fornitore": "ESEMPIO — cancella questa riga",
        "materiale": "compensato betulla BB/BB",
        "spessore_mm": "3",
        "lato_a_mm": "1200", "lato_b_mm": "600",
        "n_lastre": "20",
        "prezzo_lastre_eur": "268.00",
        "trasporto_eur": "72.00",
        "scarto_pct": "12",
        "note": "grado dichiarato, campione ricevuto il ...",
    }
    with open(path, "w", newline="", encoding="utf-8") as fh:
        fh.write("\ufeff")
        w = csv.DictWriter(fh, fieldnames=COLONNE_PREV, delimiter=";")
        w.writeheader()
        w.writerow(esempio)


def leggi_preventivi(path):
    if not path.exists():
        return []
    righe = []
    with open(path, encoding="utf-8-sig") as fh:
        for i, r in enumerate(csv.DictReader(fh, delimiter=";"), start=2):
            if not (r.get("fornitore") or "").strip():
                continue
            if r["fornitore"].startswith("ESEMPIO"):
                continue
            try:
                a = float(r["lato_a_mm"]); b = float(r["lato_b_mm"])
                n = float(r["n_lastre"])
                prezzo = float(r["prezzo_lastre_eur"])
                trasp = float(r.get("trasporto_eur") or 0)
                scarto = float(r.get("scarto_pct") or 0)
            except (ValueError, TypeError, KeyError):
                print(f"  riga {i}: numeri non leggibili, saltata")
                continue
            mq = (a / 1000.0) * (b / 1000.0) * n
            if mq <= 0:
                print(f"  riga {i}: superficie zero, saltata")
                continue
            if not 0 <= scarto < 100:
                print(f"  riga {i}: scarto {scarto}% fuori scala, forzato a 0")
                scarto = 0.0
            mat = prezzo / mq
            reso = (prezzo + trasp) / mq
            utile = reso / (1 - scarto / 100.0)
            righe.append({
                "fornitore": r["fornitore"].strip(),
                "materiale": (r.get("materiale") or "").strip(),
                "spessore_mm": (r.get("spessore_mm") or "").strip(),
                "mq_totali": round(mq, 2),
                "eur_mq_materiale": round(mat, 2),
                "eur_mq_reso": round(reso, 2),
                "eur_mq_utile": round(utile, 2),
                "incidenza_trasporto_pct": round(trasp / prezzo * 100, 1) if prezzo else 0.0,
                "scarto_pct": scarto,
                "note": (r.get("note") or "").strip(),
            })
    righe.sort(key=lambda x: x["eur_mq_utile"])
    return righe


PREVENTIVI = leggi_preventivi(DATA / "preventivi.csv")


# ---------------------------------------------------------------- html

CSS_EXTRA = """
.sec{margin:52px 0 0}
.sec-h{font-family:var(--mono);font-size:10px;letter-spacing:.24em;text-transform:uppercase;
color:var(--acc);border-bottom:1px solid var(--rule2);padding-bottom:8px;margin-bottom:6px}
.f{border:1px solid var(--rule2);background:var(--surface);margin:14px 0}
.f-h{display:flex;flex-wrap:wrap;align-items:baseline;gap:8px 14px;padding:12px 16px;
border-bottom:1px solid var(--rule2);background:var(--surface2)}
.f-h .id{font-family:var(--mono);font-size:11px;letter-spacing:.08em;color:var(--soft)}
.f-h h3{margin:0;font-size:19px;font-weight:800;letter-spacing:-.02em}
.f-h .zona{font-family:var(--serif);font-style:italic;font-size:14px;color:var(--soft)}
.f-h .sp{flex:1}
.f-b{display:grid;grid-template-columns:1.15fr 1fr;gap:0}
@media(max-width:820px){.f-b{grid-template-columns:1fr}}
.f-l{padding:16px;border-right:1px solid var(--rule)}
@media(max-width:820px){.f-l{border-right:none;border-bottom:1px solid var(--rule)}}
.f-l p{margin:0 0 9px;font-family:var(--serif);font-size:15.5px;line-height:1.58;color:var(--mid)}
.f-l p:last-child{margin-bottom:0}
.f-l b{color:var(--ink)}
.pro,.con{margin:0 0 8px;padding-left:18px;font-family:var(--serif);font-size:15px;
line-height:1.5;color:var(--mid)}
.pro li{margin-bottom:3px}.con li{margin-bottom:3px}
.lbl{font-family:var(--mono);font-size:9.5px;letter-spacing:.18em;text-transform:uppercase;
color:var(--soft);margin:12px 0 4px}
.lbl.ok{color:var(--ok)}.lbl.ko{color:var(--crit)}
dl.f-s{margin:0;padding:16px;font-family:var(--mono);font-size:11.5px;line-height:1.5}
dl.f-s>div{display:grid;grid-template-columns:92px 1fr;gap:10px;padding:4px 0;
border-bottom:1px dotted var(--rule)}
dl.f-s>div:last-child{border-bottom:none}
dl.f-s dt{color:var(--soft);letter-spacing:.06em;text-transform:uppercase;font-size:9.5px;padding-top:1px}
dl.f-s dd{margin:0;color:var(--ink);font-variant-numeric:tabular-nums;word-break:break-word}
dl.f-s dd a{color:var(--acc)}
.assi{display:grid;grid-template-columns:66px 1fr 30px;gap:6px;align-items:center;
font-family:var(--mono);font-size:9.5px;text-transform:uppercase;letter-spacing:.08em;
color:var(--soft);padding:2px 0}
.bar{height:6px;background:var(--surface2);border:1px solid var(--rule)}
.bar i{display:block;height:100%;background:var(--acc)}
.assi span{text-align:right;color:var(--ink);font-variant-numeric:tabular-nums}
.b-1{color:var(--ok)}.b-2{color:var(--warn)}.b-3{color:var(--soft)}
.b-ver{color:var(--sea)}.b-prz{color:var(--acc);font-weight:700}
.uso{border-top:1px solid var(--rule2);background:var(--surface2);padding:11px 16px}
.uso b{display:block;font-family:var(--mono);font-size:9.5px;letter-spacing:.18em;
text-transform:uppercase;color:var(--acc);margin-bottom:6px}
.uso p{margin:0;font-family:var(--serif);font-size:15.5px;line-height:1.58;color:var(--mid)}
.box{background:var(--accw);border-left:3px solid var(--accb);padding:16px 20px;margin:18px 0}
.box b.t{display:block;font-family:var(--mono);font-size:10px;letter-spacing:.18em;
text-transform:uppercase;color:var(--acc);margin-bottom:8px}
.box p,.box li{font-family:var(--serif);font-size:15.5px;line-height:1.6;color:var(--mid)}
.box ol,.box ul{margin:8px 0 0;padding-left:20px}
.box li{margin-bottom:6px}
.rfq{border:1px solid var(--rule2);background:var(--surface);margin:12px 0}
.rfq summary{cursor:pointer;padding:11px 16px;background:var(--surface2);font-family:var(--mono);
font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:var(--soft)}
.rfq summary:hover{color:var(--ink)}
.rfq pre{margin:0;padding:14px 16px;font-family:var(--mono);font-size:11.5px;line-height:1.65;
color:var(--mid);white-space:pre-wrap;word-break:break-word}
.rfq .cp{padding:0 16px 14px}
.top3{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:10px;margin:14px 0}
.t3{border:1px solid var(--rule2);background:var(--surface);padding:13px 15px}
.t3 .r{font-family:var(--mono);font-size:9.5px;letter-spacing:.18em;text-transform:uppercase;color:var(--soft)}
.t3 h4{margin:5px 0 4px;font-size:16px;font-weight:800;letter-spacing:-.01em}
.t3 .s{font-family:var(--mono);font-size:13px;font-weight:700;color:var(--acc);
font-variant-numeric:tabular-nums}
.t3 p{margin:6px 0 0;font-family:var(--serif);font-size:14px;line-height:1.5;color:var(--mid)}
.cmp{border:1px solid var(--rule2);background:var(--surface);margin:14px 0;padding:14px 16px}
.cmp h4{margin:0 0 4px;font-size:16px;font-weight:800}
.cmp p{margin:0 0 8px;font-family:var(--serif);font-size:15px;line-height:1.55;color:var(--mid)}
.cmp a{color:var(--acc);font-family:var(--mono);font-size:11px}
"""

COPY_JS = """
document.addEventListener('click',function(e){
 const b=e.target.closest('[data-cp]');if(!b)return;
 const pre=document.getElementById(b.dataset.cp);if(!pre)return;
 navigator.clipboard.writeText(pre.textContent).then(function(){
  const t=b.textContent;b.textContent='copiato';setTimeout(function(){b.textContent=t},2000);
 },function(){b.textContent='copia non riuscita';});});
"""

FILTRI_JS = """
const q=document.getElementById('q'),ft=document.getElementById('ftipo'),
fc=document.getElementById('fcan'),fp=document.getElementById('fprio'),n=document.getElementById('n');
function apply(){const t=(q.value||'').toLowerCase(),ti=ft.value,ca=fc.value,pr=fp.value;let v=0;
document.querySelectorAll('.f').forEach(function(el){
 const ok=(!t||el.dataset.s.indexOf(t)>-1)&&(!ti||el.dataset.tipo===ti)
  &&(!ca||el.dataset.can===ca)&&(!pr||el.dataset.prio===pr);
 el.style.display=ok?'':'none';if(ok)v++;});
document.querySelectorAll('section.grp').forEach(function(s){
 s.style.display=s.querySelectorAll('.f:not([style*="none"])').length?'':'none';});
n.textContent=v+' fornitori';}
[q,ft,fc,fp].forEach(function(e){e.addEventListener('input',apply)});
"""


def classe_prio(p):
    return {"PRIMA_SCELTA": "b-1", "CONFRONTO": "b-2", "RISERVA": "b-3"}.get(p, "b-3")


def costruisci():
    per_tipo = {}
    for f in FORNITORI:
        per_tipo.setdefault(f["tipo"], []).append(f)

    prime = [f for f in FORNITORI if f["priorita"] == "PRIMA_SCELTA"]
    paesi = {f["paese"].split(" (")[0] for f in FORNITORI}
    con_listino = [f for f in FORNITORI if f["prezzo_stato"] == "LISTINO_PUBBLICO"]

    h = []
    a = h.append
    a('<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">')
    a("<title>Fornitori del grezzo</title>")
    a(f"<style>{CSS}{CSS_EXTRA}</style>")

    a('<header class="top"><div class="wrap" style="padding-top:26px">')
    a('<div class="marchio">Ingly Design — Approvvigionamento</div>')
    a("<h1>Dove si compra<br><em>il grezzo</em></h1>")
    a('<p class="sub">Fornitori italiani ed europei di pannelli 3-4-6 mm, plexiglass, '
      'metalli per la fiber e blank neutri per la ristorazione. Con il capitolato da mandare, '
      'le domande da fare e il foglio per confrontare i preventivi quando arrivano.</p>')
    a('</div><dl class="kpis">')
    for k, v in [("Fornitori", len(FORNITORI)), ("Categorie", len(per_tipo)),
                 ("Prima scelta", len(prime)), ("Paesi", len(paesi)),
                 ("Con listino pubblico", len(con_listino)),
                 ("Concorrenti mappati", len(DB["concorrenti_da_osservare"]))]:
        a(f"<div><dt>{k}</dt><dd>{v}</dd></div>")
    a("</dl></header>")

    a('<div class="tools"><div class="tools-in">')
    a('<input type="search" id="q" placeholder="cerca fornitore, materiale, citta&#768;…" '
      'aria-label="Cerca">')
    a('<select id="ftipo" aria-label="Categoria"><option value="">tutte le categorie</option>')
    for t in ORDINE_TIPI:
        if t in per_tipo:
            a(f'<option value="{t}">{esc(t.replace("_", " ").lower())}</option>')
    a("</select>")
    a('<select id="fcan" aria-label="Canale"><option value="">tutti i canali</option>')
    for c in DB["legenda_canali"]:
        a(f'<option value="{c}">{esc(c.replace("_", " ").lower())}</option>')
    a("</select>")
    a('<select id="fprio" aria-label="Priorita"><option value="">tutte le priorita&#768;</option>'
      '<option value="PRIMA_SCELTA">prima scelta</option>'
      '<option value="CONFRONTO">da confrontare</option>'
      '<option value="RISERVA">riserva</option></select>')
    a(f'<span class="count" id="n">{len(FORNITORI)} fornitori</span>')
    a('<span class="sp" style="flex:1"></span>')
    a('<span class="dl"><button class="dl-b" data-dl="md">scarica md</button>'
      '<button class="dl-b" data-dl="csv">csv</button>'
      '<button class="dl-b" data-dl="json">json</button></span>')
    a('<span class="count" id="dlmsg" role="status" aria-live="polite"></span>')
    a("</div></div>")

    a('<div class="wrap">')

    a('<div class="box"><b class="t">Cosa e&#768; verificato e cosa no</b>')
    a(f'<p>{esc(DB["_meta"]["cosa_e_verificato"])}</p>')
    a(f'<p>{esc(DB["_meta"]["cosa_non_e_verificato"])}</p>')
    a(f'<p>{esc(DB["_meta"]["punteggi"])}</p></div>')

    # ---- classifica
    a('<section class="sec"><div class="sec-h">Da chi comprare, per materiale</div>')
    a("<h2>La classifica</h2>")
    etichette = {"LEGNO_IT": "Legno, Italia", "LEGNO_EU": "Legno, Europa",
                 "PLASTICHE": "Plexiglass e PMMA", "LAMINATI_METALLI": "Metalli e laminati",
                 "BLANK_HORECA": "Blank per la ristorazione",
                 "GADGET_PROMO": "Gadget promozionali neutri", "DIRECTORY": "Directory"}
    a('<div class="top3">')
    for t in ORDINE_TIPI:
        if t not in per_tipo:
            continue
        best = per_tipo[t][0]
        a('<div class="t3">')
        a(f'<div class="r">{esc(etichette.get(t, t))}</div>')
        a(f'<h4>{esc(best["nome"])}</h4>')
        a(f'<div class="s">{best["punteggio"]:.0f}/100</div>')
        a(f'<p>{esc(best["uso_ingly"])}</p>')
        a("</div>")
    a("</div></section>")

    # ---- schede
    for t in ORDINE_TIPI:
        if t not in per_tipo:
            continue
        a(f'<section class="grp sec"><div class="sec-h">{esc(etichette.get(t, t))}</div>')
        a(f"<h2>{esc(etichette.get(t, t))}</h2>")
        a(f'<p class="cat-an">{esc(DB["legenda_tipi"][t])}</p>')
        for f in per_tipo[t]:
            hay = " ".join([f["nome"], f["zona"], f["paese"], f["uso_ingly"],
                            " ".join(f["cosa_vende"]), f["spessori"]]).lower()
            a(f'<article class="f" data-dlid="{f["id"]}" data-tipo="{f["tipo"]}" '
              f'data-can="{f["canale"]}" data-prio="{f["priorita"]}" data-s="{esc(hay)}">')
            a('<div class="f-h">')
            a(f'<span class="id">{f["id"]}</span><h3>{esc(f["nome"])}</h3>')
            a(f'<span class="zona">{esc(f["zona"])} — {esc(f["paese"])}</span>')
            a('<span class="sp"></span>')
            a(f'<span class="badge {classe_prio(f["priorita"])}">'
              f'{esc(f["priorita"].replace("_", " ").lower())}</span>')
            if f["prezzo_stato"] == "LISTINO_PUBBLICO":
                a('<span class="badge b-prz">listino pubblico</span>')
            a(f'<span class="sc">{f["punteggio"]:.0f}</span>')
            a("</div>")

            a('<div class="f-b"><div class="f-l">')
            a(f'<p><b>Vende.</b> {esc(", ".join(f["cosa_vende"]))}.</p>')
            a(f'<p><b>Prezzo.</b> {esc(f["prezzo_nota"])}</p>')
            if f.get("prezzo_rilevato"):
                pr = f["prezzo_rilevato"]
                a(f'<p><b>Listino rilevato</b> — {esc(pr["descrizione"])}:</p><ul class="pro">')
                for v in pr["voci"]:
                    dim = f'{v["formato_mm"][0]}&times;{v["formato_mm"][1]} mm'
                    a(f'<li>{dim} — {v["eur"]:.2f} &euro; '
                      f'(<b>{v["eur_mq"]:.2f} &euro;/m&sup2;</b>)</li>')
                a("</ul>")
                a(f'<p style="font-size:14px"><i>{esc(pr["fonte"])}. {esc(pr["avvertenza"])}</i></p>')
            a('<div class="lbl ok">A favore</div><ul class="pro">')
            for p in f["punti_forti"]:
                a(f"<li>{esc(p)}</li>")
            a('</ul><div class="lbl ko">Contro</div><ul class="con">')
            for p in f["punti_deboli"]:
                a(f"<li>{esc(p)}</li>")
            a("</ul></div>")

            a('<dl class="f-s">')
            a(f'<div><dt>Sito</dt><dd><a href="{esc(f["url"])}" target="_blank" '
              f'rel="noopener">{esc(f["url"])}</a></dd></div>')
            for k, v in [("Canale", f["canale"].replace("_", " ").lower()),
                         ("Spessori", f["spessori"]), ("Formati", f["formati"]),
                         ("Minimo", f["moq"]), ("Sicilia", f["sped_sud"])]:
                a(f"<div><dt>{k}</dt><dd>{esc(v)}</dd></div>")
            if f["eur_mq_min"]:
                a(f'<div><dt>&euro;/m&sup2;</dt><dd>{f["eur_mq_min"]:.2f} – '
                  f'{f["eur_mq_max"]:.2f}</dd></div>')
            a(f'<div><dt>Verifica</dt><dd>{esc(f["verificato"])}</dd></div>')
            a("</dl></div>")

            a('<div style="padding:0 16px 14px">')
            for k, nome in ASSI:
                a(f'<div class="assi"><span style="text-align:left">{nome}</span>'
                  f'<span class="bar"><i style="width:{f[k] * 10}%"></i></span>'
                  f'<span>{f[k]}</span></div>')
            a("</div>")

            a(f'<div class="uso"><b>Che cosa ci compri</b><p>{esc(f["uso_ingly"])}</p></div>')
            a("</article>")
        a("</section>")

    # ---- benchmark
    bm = DB["benchmark_prezzi"]
    a('<section class="sec"><div class="sec-h">Metro di giudizio</div>')
    a("<h2>Quanto dovrebbe costare</h2>")
    a(f'<p class="cat-an">{esc(bm["avvertenza"])}</p>')
    a('<div class="tw"><table><thead><tr><th>Materiale</th><th>Fascia &euro;/m&sup2;</th>'
      "<th>Nota</th></tr></thead><tbody>")
    for v in bm["voci"]:
        a(f'<tr><td><b>{esc(v["materiale"])}</b></td><td>{esc(v["fascia_eur_mq"])}</td>'
          f'<td>{esc(v["note"])}</td></tr>')
    a("</tbody></table></div></section>")

    # ---- preventivi
    a('<section class="sec"><div class="sec-h">Il confronto vero</div>')
    a("<h2>Preventivi a confronto</h2>")
    if PREVENTIVI:
        a('<p class="cat-an">Calcolato da <code>data/preventivi.csv</code>. La colonna che decide '
          'e&#768; l&#39;ultima: euro per metro quadro <b>utile</b>, cioe&#768; materiale piu&#768; '
          'trasporto diviso la superficie che resta dopo lo scarto. Un pannello economico con molto '
          'scarto costa piu&#768; di uno caro che si taglia tutto.</p>')
        a('<div class="tw"><table><thead><tr><th>Fornitore</th><th>Materiale</th><th>Sp.</th>'
          "<th>m&sup2;</th><th>&euro;/m&sup2; materiale</th><th>&euro;/m&sup2; reso</th>"
          "<th>Trasp. %</th><th>Scarto %</th><th>&euro;/m&sup2; UTILE</th></tr></thead><tbody>")
        for i, p in enumerate(PREVENTIVI):
            cl = ' style="color:var(--ok);font-weight:700"' if i == 0 else ""
            a(f'<tr><td><b>{esc(p["fornitore"])}</b></td><td>{esc(p["materiale"])}</td>'
              f'<td>{esc(p["spessore_mm"])}</td><td>{p["mq_totali"]:.2f}</td>'
              f'<td>{p["eur_mq_materiale"]:.2f}</td><td>{p["eur_mq_reso"]:.2f}</td>'
              f'<td>{p["incidenza_trasporto_pct"]:.1f}</td><td>{p["scarto_pct"]:.0f}</td>'
              f'<td{cl}>{p["eur_mq_utile"]:.2f}</td></tr>')
        a("</tbody></table></div>")
    else:
        a('<div class="box"><b class="t">Il foglio e&#768; pronto, va compilato</b>'
          '<p>Non esiste ancora <code>data/preventivi.csv</code>, quindi qui non c&#39;e&#768; '
          'nulla da confrontare: i prezzi non si inventano, si chiedono.</p>'
          '<p>In <code>out/preventivi_template.csv</code> trovi il foglio con le colonne giuste. '
          'Man mano che arrivano le risposte compilalo, salvalo come '
          '<code>data/preventivi.csv</code> e rilancia lo script: questa sezione si riempie da sola '
          'e ti dice, in una riga, chi costa davvero meno.</p>'
          '<p>Le colonne da riempire sono nove: fornitore, materiale, spessore, i due lati del '
          'foglio in mm, quante lastre, il prezzo totale, il trasporto, e la percentuale di scarto '
          'che quel materiale ti ha lasciato sul lavoro reale. Lo scarto e&#768; l&#39;unica voce '
          'che non ti dira&#768; nessun fornitore, ed e&#768; quella che ribalta le classifiche.</p>'
          "</div>")
    a("</section>")

    # ---- rfq
    a('<section class="sec"><div class="sec-h">Da mandare</div>')
    a(f'<h2>{esc(DB["rfq"]["titolo"].split("—")[0].strip())}</h2>')
    a('<p class="cat-an">Quattro testi pronti, uno per famiglia di materiale. Contengono gia&#768; '
      'il capitolato tecnico: e&#768; la differenza tra ricevere preventivi confrontabili e '
      'ricevere quattro numeri che non vogliono dire niente.</p>')
    etich_rfq = {"legno": "Pannelli in legno", "plexiglass": "PMMA e plexiglass",
                 "metalli": "Metalli e laminati", "blank_horeca": "Blank neutri per la ristorazione"}
    for k, lab in etich_rfq.items():
        pid = f"rfq-{k}"
        a(f'<details class="rfq"><summary>{esc(lab)}</summary>')
        a(f'<pre id="{pid}">{esc(DB["rfq"][k])}</pre>')
        a(f'<div class="cp"><button class="dl-b" data-cp="{pid}">copia testo</button></div>')
        a("</details>")
    a("</section>")

    # ---- domande
    a('<section class="sec"><div class="sec-h">Al telefono</div>')
    a("<h2>Le domande che separano un fornitore da un rivenditore</h2>")
    a('<div class="box"><ol>')
    for d in DB["domande_da_fare_sempre"]:
        a(f"<li>{esc(d)}</li>")
    a("</ol></div></section>")

    # ---- logistica
    lg = DB["logistica_sud"]
    a('<section class="sec"><div class="sec-h">Isole</div>')
    a(f'<h2>{esc(lg["titolo"])}</h2>')
    a('<div class="box"><ul>')
    for p in lg["punti"]:
        a(f"<li>{esc(p)}</li>")
    a("</ul></div></section>")

    # ---- strategia
    st = DB["strategia_acquisto"]
    a('<section class="sec"><div class="sec-h">Metodo</div>')
    a(f'<h2>{esc(st["titolo"])}</h2>')
    a('<div class="box"><ol>')
    for p in st["passi"]:
        a(f"<li>{esc(p)}</li>")
    a("</ol></div></section>")

    # ---- concorrenti
    a('<section class="sec"><div class="sec-h">Chi c&#39;e&#768; gia&#768;</div>')
    a("<h2>Concorrenti da osservare</h2>")
    a('<p class="cat-an">Emersi cercando i fornitori, ed e&#768; normale: nel laser chi vende il '
      'grezzo spesso vende anche il finito. Vale la pena guardarli prima di lanciare la linea '
      'ristorazione, perche&#769; il primo e&#768; siciliano come te.</p>')
    for c in DB["concorrenti_da_osservare"]:
        a('<div class="cmp">')
        a(f'<h4>{esc(c["nome"])} <span class="zona" style="font-weight:400">— '
          f'{esc(c["zona"])}</span></h4>')
        a(f'<p>{esc(c["cosa_fa"])}</p>')
        a(f'<p><b>Perche&#769; conta.</b> {esc(c["perche_conta"])}</p>')
        a(f'<p><b>Come batterlo.</b> {esc(c["come_batterlo"])}</p>')
        a(f'<a href="{esc(c["url"])}" target="_blank" rel="noopener">{esc(c["url"])}</a>')
        a("</div>")
    a("</section>")

    a('</div><footer><div class="wrap">')
    a('<div class="marchio">Ingly Design</div>')
    a('<p style="margin-top:12px">Di ogni fornitore sono verificati esistenza, indirizzo web e '
      'categoria merceologica alla data di rilevazione. I prezzi <b>non</b> sono verificati, con '
      'l&#39;eccezione delle voci marcate come listino rilevato, che riportano la fonte. Le fasce '
      'di riferimento sono ordini di grandezza per giudicare un preventivo, non quotazioni. '
      'I cinque punteggi sono valutazioni di Ingly Design, non dati dichiarati dai fornitori: '
      'sono nel file JSON proprio perche&#769; tu possa cambiarli.</p>')
    a("</div></footer>")

    a('<script type="application/json" id="dati">'
      + json.dumps(FORNITORI, ensure_ascii=False).replace("</", "<\\/") + "</script>")
    a('<script type="application/json" id="extra">'
      + json.dumps({"benchmark": DB["benchmark_prezzi"], "rfq": DB["rfq"],
                    "domande": DB["domande_da_fare_sempre"],
                    "logistica": DB["logistica_sud"], "strategia": DB["strategia_acquisto"],
                    "concorrenti": DB["concorrenti_da_osservare"],
                    "preventivi": PREVENTIVI},
                   ensure_ascii=False).replace("</", "<\\/") + "</script>")
    a('<script>const DATI=JSON.parse(document.getElementById("dati").textContent);'
      'const EXTRA=JSON.parse(document.getElementById("extra").textContent);'
      'const NOMEFILE="fornitori";const IDKEY="id";'
      'const MD=function(rs){'
      'var o="# Ingly Design - Fornitori di grezzo e di blank\\n\\n";'
      'o+="## Fornitori ("+rs.length+")\\n\\n";'
      'o+=rs.map(function(r){return "### "+r.nome+" ["+r.tipo+", "+r.punteggio+"/100]\\n\\n"'
      '+"**Dove** "+r.zona+", "+r.paese+"  \\n**Sito** "+r.url'
      '+"  \\n**Canale** "+r.canale+"  \\n**Priorita** "+r.priorita'
      '+"  \\n**Vende** "+r.cosa_vende.join(", ")'
      '+"  \\n**Spessori** "+r.spessori+"  \\n**Formati** "+r.formati'
      '+"  \\n**Minimo** "+r.moq+"  \\n**Sicilia** "+r.sped_sud'
      '+"  \\n**Prezzo** "+r.prezzo_nota'
      '+(r.eur_mq_min?"  \\n**Euro/mq rilevati** "+r.eur_mq_min+" - "+r.eur_mq_max:"")'
      '+"\\n\\nA favore:\\n"+r.punti_forti.map(function(x){return "- "+x}).join("\\n")'
      '+"\\n\\nContro:\\n"+r.punti_deboli.map(function(x){return "- "+x}).join("\\n")'
      '+"\\n\\nChe cosa ci compri: "+r.uso_ingly+"\\n"'
      '}).join("\\n---\\n\\n");'
      'o+="\\n\\n## Quanto dovrebbe costare\\n\\n"+EXTRA.benchmark.avvertenza+"\\n\\n";'
      'EXTRA.benchmark.voci.forEach(function(v){'
      'o+="- **"+v.materiale+"**: "+v.fascia_eur_mq+" EUR/mq. "+v.note+"\\n"});'
      'o+="\\n## Domande da fare sempre\\n\\n";'
      'EXTRA.domande.forEach(function(d,i){o+=(i+1)+". "+d+"\\n"});'
      'o+="\\n## "+EXTRA.logistica.titolo+"\\n\\n";'
      'EXTRA.logistica.punti.forEach(function(p){o+="- "+p+"\\n"});'
      'o+="\\n## "+EXTRA.strategia.titolo+"\\n\\n";'
      'EXTRA.strategia.passi.forEach(function(p,i){o+=(i+1)+". "+p+"\\n"});'
      'o+="\\n## Richieste di preventivo\\n\\n";'
      'Object.keys(EXTRA.rfq).forEach(function(k){if(k==="titolo")return;'
      'o+="### "+k+"\\n\\n```\\n"+EXTRA.rfq[k]+"\\n```\\n\\n"});'
      'o+="## Concorrenti da osservare\\n\\n";'
      'EXTRA.concorrenti.forEach(function(c){o+="### "+c.nome+" ("+c.zona+")\\n\\n"'
      '+c.cosa_fa+"\\n\\n**Perche conta.** "+c.perche_conta'
      '+"\\n\\n**Come batterlo.** "+c.come_batterlo+"\\n\\n"+c.url+"\\n\\n"});'
      "return o};</script>")
    a(f"<script>{DL_JS}</script>")
    a(f"<script>{FILTRI_JS}</script>")
    a(f"<script>{COPY_JS}</script>")

    return "\n".join(h)


def main():
    OUT.mkdir(exist_ok=True)

    (OUT / "fornitori.html").write_text(costruisci(), encoding="utf-8")

    with open(OUT / "fornitori.json", "w", encoding="utf-8") as fh:
        json.dump({"fornitori": FORNITORI, "benchmark": DB["benchmark_prezzi"],
                   "rfq": DB["rfq"], "domande": DB["domande_da_fare_sempre"],
                   "logistica": DB["logistica_sud"], "strategia": DB["strategia_acquisto"],
                   "concorrenti": DB["concorrenti_da_osservare"],
                   "preventivi": PREVENTIVI}, fh, ensure_ascii=False, indent=2)

    righe = []
    for f in FORNITORI:
        r = {k: v for k, v in f.items() if k != "prezzo_rilevato"}
        for k in ("cosa_vende", "punti_forti", "punti_deboli"):
            r[k] = " | ".join(f[k])
        righe.append(r)
    with open(OUT / "fornitori.csv", "w", newline="", encoding="utf-8") as fh:
        fh.write("\ufeff")
        w = csv.DictWriter(fh, fieldnames=list(righe[0].keys()),
                           extrasaction="ignore", delimiter=";")
        w.writeheader()
        w.writerows(righe)

    scrivi_template_preventivi(OUT / "preventivi_template.csv")

    per_tipo = {}
    for f in FORNITORI:
        per_tipo.setdefault(f["tipo"], []).append(f)

    print(f"\n{len(FORNITORI)} fornitori · {len(per_tipo)} categorie · "
          f"{len({f['paese'].split(' (')[0] for f in FORNITORI})} paesi\n")
    print(f"{'Categoria':<20}{'N':>4}{'Prima scelta':>14}  {'Migliore':<28}{'Punt.':>7}")
    print("-" * 76)
    for t in ORDINE_TIPI:
        if t not in per_tipo:
            continue
        fs = per_tipo[t]
        prime = sum(1 for f in fs if f["priorita"] == "PRIMA_SCELTA")
        print(f"{t:<20}{len(fs):>4}{prime:>14}  {fs[0]['nome'][:28]:<28}"
              f"{fs[0]['punteggio']:>7.1f}")
    print("-" * 76)

    listini = [f for f in FORNITORI if f["eur_mq_min"]]
    if listini:
        print("\nPrezzi realmente rilevati (gli unici non stimati):")
        for f in listini:
            print(f"  {f['nome']}: {f['eur_mq_min']:.2f} – {f['eur_mq_max']:.2f} €/m²")
    print(f"\nFornitori senza prezzo: {len(FORNITORI) - len(listini)} su {len(FORNITORI)}. "
          "Vanno chiesti: i testi delle richieste sono in out/fornitori.html")

    if PREVENTIVI:
        print(f"\nConfronto preventivi ({len(PREVENTIVI)} righe da data/preventivi.csv):")
        for p in PREVENTIVI:
            print(f"  {p['fornitore'][:24]:<24} {p['materiale'][:22]:<22} "
                  f"{p['eur_mq_utile']:>7.2f} €/m² utile")
        print(f"  -> migliore: {PREVENTIVI[0]['fornitore']}")
    else:
        print("\nNessun preventivo caricato. Compila out/preventivi_template.csv, "
              "salvalo come data/preventivi.csv e rilancia.")

    print(f"\nOutput in {OUT}/")


if __name__ == "__main__":
    main()
