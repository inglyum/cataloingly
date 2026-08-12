#!/usr/bin/env python3
"""
INGLY DESIGN — Enciclopedia dei prodotti e delle fonti
======================================================

Genera il SECONDO catalogo: non i prodotti Ingly Design, ma la mappa di cosa
gia' vende nel mondo, perche' vende, e dove trovarne i file — con la licenza
come primo criterio, perche' e' li' che si fanno i danni.

Ogni voce porta un PROMPT DI DESIGN per costruirne una versione originale,
non per copiarla.

    python3 scripts/build_enciclopedia.py   ->  out/enciclopedia.html + .json + .csv
"""

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from build import CSS, DL_JS, esc          # noqa: E402  riuso lo stesso sistema visivo

DATA = ROOT / "data"
OUT = ROOT / "out"

ENC = json.load(open(DATA / "enciclopedia.json", encoding="utf-8"))
FONTI = json.load(open(DATA / "fonti.json", encoding="utf-8"))
CATS = json.load(open(DATA / "categories.json", encoding="utf-8"))["categorie"]

CSS_EXTRA = """
.sec{margin:52px 0 0}
.sec-h{font-family:var(--mono);font-size:10px;letter-spacing:.24em;text-transform:uppercase;
color:var(--acc);border-bottom:1px solid var(--rule2);padding-bottom:8px;margin-bottom:6px}
.warnbox{background:var(--accw);border-left:3px solid var(--crit);padding:16px 20px;margin:18px 0}
.warnbox b{display:block;font-family:var(--mono);font-size:10px;letter-spacing:.18em;
text-transform:uppercase;color:var(--crit);margin-bottom:8px}
.warnbox p{margin:0 0 8px;font-family:var(--serif);font-size:15.5px;line-height:1.6;color:var(--mid)}
.warnbox ul{margin:8px 0 0;padding-left:20px;font-family:var(--serif);font-size:15.5px;color:var(--mid)}
.warnbox li{margin-bottom:4px}
.fgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:12px;margin:16px 0}
.f{border:1px solid var(--rule2);background:var(--surface);padding:14px 16px}
.f-h{display:flex;align-items:baseline;gap:8px;flex-wrap:wrap;margin-bottom:8px}
.f-h h4{margin:0;font-size:16px;font-weight:800;letter-spacing:-.01em}
.f p{margin:0 0 7px;font-family:var(--serif);font-size:14.5px;line-height:1.5;color:var(--mid)}
.f dl{margin:8px 0 0;font-family:var(--mono);font-size:11px}
.f dl>div{display:grid;grid-template-columns:74px 1fr;gap:8px;padding:3px 0;border-bottom:1px dotted var(--rule)}
.f dl>div:last-child{border-bottom:none}
.f dt{color:var(--soft);text-transform:uppercase;font-size:9.5px;letter-spacing:.06em}
.f dd{margin:0;color:var(--ink)}
.lic-COMMERCIALE{color:var(--ok)}
.lic-COMMERCIALE_LIMITATA{color:var(--warn)}
.lic-PERSONALE{color:var(--crit)}
.lic-VARIABILE{color:var(--warn)}
.lic-ATTRIBUZIONE{color:var(--sea)}
.lic-DA_VERIFICARE{color:var(--crit)}
.e{border:1px solid var(--rule2);background:var(--surface);margin:12px 0}
.e-h{display:flex;flex-wrap:wrap;align-items:baseline;gap:8px 12px;padding:11px 16px;
border-bottom:1px solid var(--rule2);background:var(--surface2)}
.e-h .id{font-family:var(--mono);font-size:11px;color:var(--soft)}
.e-h h3{margin:0;font-size:18px;font-weight:800;letter-spacing:-.02em}
.e-h .en{font-family:var(--serif);font-style:italic;font-size:13.5px;color:var(--soft)}
.e-h .sp{flex:1}
.e-b{display:grid;grid-template-columns:1fr 300px;gap:0}
@media(max-width:860px){.e-b{grid-template-columns:1fr}}
.e-d{padding:14px 16px;border-right:1px solid var(--rule)}
@media(max-width:860px){.e-d{border-right:none;border-bottom:1px solid var(--rule)}}
.e-d p{margin:0 0 8px;font-family:var(--serif);font-size:15.5px;line-height:1.58;color:var(--mid)}
.e-d p:last-child{margin-bottom:0}
.e-d b{color:var(--ink)}
.e-m{padding:14px 16px;font-family:var(--mono);font-size:11px;line-height:1.5}
.e-m>div{display:grid;grid-template-columns:82px 1fr;gap:8px;padding:3px 0;border-bottom:1px dotted var(--rule)}
.e-m>div:last-child{border-bottom:none}
.e-m dt{color:var(--soft);text-transform:uppercase;font-size:9.5px;letter-spacing:.06em}
.e-m dd{margin:0;color:var(--ink)}
.e-p{border-top:1px solid var(--rule2);background:var(--surface2)}
.e-p b{display:block;font-family:var(--mono);font-size:9.5px;letter-spacing:.18em;
text-transform:uppercase;color:var(--acc);padding:10px 16px 0}
.e-p pre{margin:0;padding:6px 16px 14px;font-family:var(--mono);font-size:11.5px;line-height:1.62;
color:var(--mid);white-space:pre-wrap;word-break:break-word}
.ip-ALTO{color:var(--crit);background:var(--accw);font-weight:700}
.ip-medio{color:var(--warn)}
.dom-molto-alta,.dom-alta{color:var(--ok)}
.strat{background:var(--surface2);border:1px solid var(--rule2);padding:18px 22px;margin:18px 0}
.strat b{display:block;font-family:var(--mono);font-size:10px;letter-spacing:.18em;
text-transform:uppercase;color:var(--acc);margin-bottom:10px}
.strat ol{margin:0;padding-left:20px;font-family:var(--serif);font-size:15.5px;line-height:1.6;color:var(--mid)}
.strat li{margin-bottom:8px}
"""

FILTRI_JS = """
const q=document.getElementById('q'),fc=document.getElementById('fcat'),
fi=document.getElementById('fip'),fd=document.getElementById('fdom'),n=document.getElementById('n');
function apply(){const t=(q.value||'').toLowerCase(),c=fc.value,ip=fi.value,dm=fd.value;let v=0;
document.querySelectorAll('.e').forEach(function(el){
 const ok=(!t||el.dataset.s.indexOf(t)>-1)&&(!c||el.dataset.cat===c)
  &&(!ip||el.dataset.ip===ip)&&(!dm||el.dataset.dom===dm);
 el.style.display=ok?'':'none';if(ok)v++;});
document.querySelectorAll('section.cat').forEach(function(s){
 s.style.display=s.querySelectorAll('.e:not([style*="none"])').length?'':'none';});
n.textContent=v+' voci';}
[q,fc,fi,fd].forEach(function(e){e.addEventListener('input',apply)});
"""


def costruisci():
    voci = ENC["voci"]
    fonti = FONTI["fonti"]
    meta = FONTI["_meta"]

    per_cat = {}
    for v in voci:
        per_cat.setdefault(v["cat"], []).append(v)

    gratuite = [f for f in fonti if f["tipo"] == "GRATUITO"]
    pagamento = [f for f in fonti if f["tipo"] == "A PAGAMENTO"]
    altre = [f for f in fonti if f["tipo"] not in ("GRATUITO", "A PAGAMENTO")]
    commerciali = [f for f in fonti if f["licenza"].startswith("COMMERCIALE")]
    ip_alto = [v for v in voci if v["rischio_ip"].startswith("ALTO")]

    h = []
    a = h.append
    a("<title>Ingly Design — Enciclopedia Prodotti e Fonti</title>")
    a(f"<style>{CSS}{CSS_EXTRA}</style>")

    a('<header class="top"><div class="wrap" style="padding-top:26px">')
    a('<div class="marchio">Ingly Design · Enciclopedia</div>')
    a('<h1>Cosa vende<br><em>nel mondo</em></h1>')
    a('<p class="sub">La mappa dei prodotti laser piu' + "'" + ' venduti e piu' + "'" + ' cercati, '
      'con le fonti dei file e la licenza come primo criterio. Ogni voce porta un prompt per '
      'costruirne una versione originale — non per copiarla.</p>')
    a('</div><dl class="kpis" style="max-width:1180px;margin:0 auto;padding:0 24px">')
    a(f'<div><dt>Voci</dt><dd>{len(voci)}</dd></div>')
    a(f'<div><dt>Categorie</dt><dd>{len(per_cat)}</dd></div>')
    a(f'<div><dt>Fonti</dt><dd>{len(fonti)}</dd></div>')
    a(f'<div><dt>Gratuite</dt><dd>{len(gratuite)}</dd></div>')
    a(f'<div><dt>A pagamento</dt><dd>{len(pagamento)}</dd></div>')
    a(f'<div><dt>Uso commerciale</dt><dd>{len(commerciali)}</dd></div>')
    a(f'<div><dt>Rischio IP alto</dt><dd>{len(ip_alto)}</dd></div>')
    a('</dl></header>')

    a('<nav class="tools"><div class="tools-in">')
    a('<input type="search" id="q" placeholder="cerca prodotto, materiale, tecnologia…" aria-label="Cerca">')
    a('<select id="fcat" aria-label="Categoria"><option value="">tutte le categorie</option>')
    for cid in per_cat:
        a(f'<option value="{cid}">{esc(CATS[cid]["nome"])}</option>')
    a('</select><select id="fip" aria-label="Rischio IP"><option value="">tutti i rischi IP</option>'
      '<option value="ALTO">rischio IP alto — non replicabile</option>'
      '<option value="medio">rischio IP medio</option>'
      '<option value="nullo">nessun rischio IP</option>')
    a('</select><select id="fdom" aria-label="Domanda"><option value="">tutta la domanda</option>')
    for d in ["molto alta", "alta", "media", "bassa"]:
        a(f'<option value="{d}">domanda {d}</option>')
    a(f'</select><span class="count" id="n">{len(voci)} voci</span>')
    a('<span class="dl">'
      '<button class="dl-b" data-dl="html" type="button">scarica pagina</button>'
      '<button class="dl-b" data-dl="csv" type="button">csv</button>'
      '<button class="dl-b" data-dl="json" type="button">json</button>'
      '</span>')
    a('</div></nav><div class="wrap">')

    # ---------------- avvertenza licenze ----------------
    a('<section class="sec"><div class="sec-h">Prima di scaricare qualsiasi cosa</div>')
    a('<div class="warnbox"><b>Regola generale verificata</b>')
    a(f'<p>{esc(meta["avvertenza_licenze"])}</p></div>')
    a('<div class="warnbox" style="border-left-color:var(--accb)"><b>La regola Ingly Design</b>')
    a(f'<p>{esc(meta["regola_ingly"])}</p></div>')
    a('<div class="warnbox"><b>Cosa non fare mai</b><ul>')
    for r in meta["mai_fare"]:
        a(f'<li>{esc(r)}</li>')
    a('</ul></div></section>')

    # ---------------- fonti ----------------
    for titolo, gruppo, nota in [
        ("Fonti gratuite", gratuite, "Gratuito non significa libero: la licenza va letta comunque."),
        ("Fonti a pagamento", pagamento, "Qui la licenza commerciale c'e', ma quasi sempre con limiti."),
        ("Rassegne e documentazione", altre, "Valgono piu' degli archivi: servono a mappare cosa esiste."),
    ]:
        a(f'<section class="sec"><div class="sec-h">{titolo} — {len(gruppo)}</div>')
        a(f'<p class="cat-an">{esc(nota)}</p><div class="fgrid">')
        for f in gruppo:
            a('<article class="f"><div class="f-h">')
            a(f'<span class="sku" style="font-family:var(--mono);font-size:10px;color:var(--soft)">{f["id"]}</span>')
            a(f'<h4>{esc(f["nome"])}</h4>')
            a(f'<span class="badge lic-{f["licenza"]}">{esc(f["licenza"].replace("_", " ").lower())}</span>')
            a('</div>')
            a(f'<p>{esc(f["cosa_offre"])}</p>')
            a(f'<p style="color:var(--ink)"><b>{esc(f["note"])}</b></p>')
            a('<dl>')
            for k, v in [("Costo", f["costo"]), ("Formati", ", ".join(f["formati"])),
                         ("Qualità", f["qualita"]), ("Utile per", f["utile_per"])]:
                a(f'<div><dt>{k}</dt><dd>{esc(v)}</dd></div>')
            a(f'<div><dt>Link</dt><dd><a href="{esc(f["url"])}" target="_blank" rel="noopener">apri</a></dd></div>')
            a('</dl></article>')
        a('</div></section>')

    # ---------------- strategia ----------------
    st = FONTI["strategia_ingly"]
    a(f'<section class="sec"><div class="sec-h">Strategia</div><div class="strat"><b>{esc(st["titolo"])}</b><ol>')
    for p in st["punti"]:
        a(f'<li>{esc(p)}</li>')
    a('</ol></div></section>')

    # ---------------- enciclopedia ----------------
    a('<section class="sec"><div class="sec-h">Enciclopedia dei prodotti — '
      f'{len(voci)} voci</div>')
    a('<p class="cat-an">Ogni voce descrive un prodotto che gia'
      + "'" + ' vende nel mondo. Il prompt di design in fondo '
      'serve a costruirne una versione originale dentro il sistema Griglia Mediterranea, '
      'partendo dalla funzione che lo fa vendere.</p></section>')

    idx_fonti = {f["id"]: f for f in fonti}

    for cid, vs in per_cat.items():
        a(f'<section class="cat" id="enc-{cid}"><h2>{esc(CATS[cid]["nome"])}</h2>')
        for v in vs:
            ip = v["rischio_ip"]
            ip_key = "ALTO" if ip.startswith("ALTO") else ("medio" if ip.startswith("medio") else "nullo")
            hay = " ".join([v["id"], v["nome"], v["nome_en"], v["cosa_e"], v["materiali"],
                            v["tech"], v["perche_vende"]]).lower()
            a(f'<article class="e" data-id="{v["id"]}" data-cat="{cid}" data-ip="{ip_key}" '
              f'data-dom="{v["domanda"]}" data-s="{esc(hay)}">')
            a('<div class="e-h">')
            a(f'<span class="id">{v["id"]}</span><h3>{esc(v["nome"])}</h3>')
            a(f'<span class="en">{esc(v["nome_en"])}</span><span class="sp"></span>')
            a(f'<span class="badge dom-{v["domanda"].replace(" ", "-")}">domanda {esc(v["domanda"])}</span>')
            if ip_key != "nullo":
                a(f'<span class="badge ip-{ip_key}">IP {ip_key}</span>')
            a('</div>')
            a('<div class="e-b"><div class="e-d">')
            a(f'<p>{esc(v["cosa_e"])}</p>')
            a(f'<p><b>Perché vende.</b> {esc(v["perche_vende"])}</p>')
            if ip_key != "nullo":
                a(f'<p style="color:var(--crit)"><b>Proprietà intellettuale.</b> {esc(ip)}</p>')
            fs = [idx_fonti[i] for i in v.get("fonti", []) if i in idx_fonti]
            if fs:
                link = " · ".join(
                    f'<a href="{esc(f["url"])}" target="_blank" rel="noopener">{esc(f["nome"])}</a>'
                    f' <span style="color:var(--soft)">({esc(f["licenza"].replace("_", " ").lower())})</span>'
                    for f in fs)
                a(f'<p style="font-family:var(--mono);font-size:11.5px;line-height:1.7">'
                  f'<span style="color:var(--soft)">DOVE TROVARE I FILE:</span> {link}</p>')
            else:
                a('<p style="font-family:var(--mono);font-size:11.5px;color:var(--crit)">'
                  'NESSUNA FONTE INDICATA — questo prodotto va disegnato da zero.</p>')
            a(f'<p style="font-family:var(--mono);font-size:11px"><span style="color:var(--soft)">'
              f'RIFERIMENTO DI MERCATO:</span> '
              f'<a href="{esc(v["ref"])}" target="_blank" rel="noopener">{esc(v["ref"])}</a></p>')
            a('</div><dl class="e-m">')
            for k, val in [("Prezzo", v["prezzo_range"]), ("Domanda", v["domanda"]),
                           ("Concorrenza", v["concorrenza"]), ("Difficoltà", v["difficolta"]),
                           ("Materiali", v["materiali"]), ("Tecnologia", v["tech"])]:
                a(f'<div><dt>{k}</dt><dd>{esc(val)}</dd></div>')
            a('</dl></div>')
            a(f'<div class="e-p"><b>Prompt di design — come costruirne una versione originale</b>'
              f'<pre>{esc(v["prompt_design"])}</pre></div>')
            a('</article>')
        a('</section>')

    a('</div><footer><div class="wrap">')
    a('<div class="marchio">Ingly Design</div>')
    a('<p style="margin-top:12px">I prezzi sono <b>fasce osservate a livello di categoria</b>, non '
      'prezzi di singole inserzioni verificate una per una. I livelli di domanda e concorrenza sono '
      'valutazioni qualitative basate sull\'ampiezza dell\'offerta rilevata: nessun marketplace '
      'pubblica i volumi di vendita reali, e chi dichiara numeri precisi se li sta inventando. '
      'Le licenze cambiano nel tempo e per singolo file: vanno verificate sul sito prima di ogni '
      'uso non personale.</p>')
    a('</div></footer>')

    a('<script type="application/json" id="dati">'
      + json.dumps(voci, ensure_ascii=False).replace("</", "<\\/") + "</script>")
    a('<script>const DATI=JSON.parse(document.getElementById("dati").textContent);'
      'const NOMEFILE="enciclopedia";</script>')
    a(f"<script>{DL_JS}</script>")
    a(f"<script>{FILTRI_JS}</script>")

    return "\n".join(h)


def main():
    OUT.mkdir(exist_ok=True)

    (OUT / "enciclopedia.html").write_text(costruisci(), encoding="utf-8")

    with open(OUT / "enciclopedia.json", "w", encoding="utf-8") as fh:
        json.dump({"voci": ENC["voci"], "fonti": FONTI["fonti"],
                   "strategia": FONTI["strategia_ingly"]}, fh, ensure_ascii=False, indent=2)

    righe = []
    for v in ENC["voci"]:
        r = dict(v)
        r["fonti"] = ", ".join(v.get("fonti", []))
        righe.append(r)
    with open(OUT / "enciclopedia.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(righe[0].keys()), extrasaction="ignore")
        w.writeheader()
        w.writerows(righe)

    righe_f = [{k: (", ".join(v) if isinstance(v, list) else v) for k, v in f.items()}
               for f in FONTI["fonti"]]
    with open(OUT / "fonti.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(righe_f[0].keys()), extrasaction="ignore")
        w.writeheader()
        w.writerows(righe_f)

    per_cat = {}
    for v in ENC["voci"]:
        per_cat.setdefault(v["cat"], []).append(v)

    print(f"\n{len(ENC['voci'])} voci di enciclopedia · {len(FONTI['fonti'])} fonti\n")
    print(f"{'Categoria':<34}{'Voci':>6}{'IP alto':>9}{'Dom. alta':>11}")
    print("-" * 60)
    for cid, vs in sorted(per_cat.items()):
        alta = sum(1 for v in vs if v["domanda"] in ("alta", "molto alta"))
        ipa = sum(1 for v in vs if v["rischio_ip"].startswith("ALTO"))
        print(f"{CATS[cid]['nome']:<34}{len(vs):>6}{ipa:>9}{alta:>11}")
    print("-" * 60)
    tipi = {}
    for f in FONTI["fonti"]:
        tipi[f["tipo"]] = tipi.get(f["tipo"], 0) + 1
    print("Fonti:", "  ".join(f"{k}={v}" for k, v in sorted(tipi.items())))
    print(f"\nOutput in {OUT}/")


if __name__ == "__main__":
    main()
