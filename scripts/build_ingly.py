#!/usr/bin/env python3
"""
INGLY PRODUCT INTELLIGENCE SYSTEM — motore di catalogo
======================================================

Espande 27 basi produttive in 108 SKU e calcola per ognuno:

  · COSTO INDUSTRIALE   materiale + macchina + energia + operatore + componenti + packaging
  · TRUE COST           il precedente + scarto + commissioni di canale + costi di
                        pagamento + marketing + spedizione
  · PROFITTO REALE      prezzo - TRUE COST, per ciascun canale di vendita
  · INGLY SCORE         su 100, con margine e velocita' CALCOLATI dal modello
  · CLASSIFICAZIONE     WINNER / TEST / RISERVA / SCARTARE

La differenza fra "margine" e "profitto reale" e' il punto di questo file.
Un prodotto al 67% di margine lordo su Etsy, con commissioni al 6,5%, pagamento
al 2,9%, marketing al 10% e spedizione inclusa, scende intorno al 35-40% di
profitto vero. Un catalogo che si ferma al margine lordo si racconta una storia.

    python3 scripts/build_ingly.py
"""

import csv
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "ingly"
OUT = ROOT / "out"

SYS = json.load(open(DATA / "sistema.json", encoding="utf-8"))
BASI = []
for f in ("basi_a.json", "basi_b.json"):
    BASI += json.load(open(DATA / f, encoding="utf-8"))["basi"]

MAC = SYS["macchine"]
MAT = SYS["materiali"]
COMP = SYS["componenti"]
PACK = SYS["packaging"]
CAT = SYS["categorie"]
FASCE = SYS["fasce_prezzo"]
TC = SYS["true_cost"]
SCORE = SYS["ingly_score"]


# --------------------------------------------------------------------------
# Espansione basi -> SKU
# --------------------------------------------------------------------------

def espandi():
    sku = []
    visti = set()
    for b in BASI:
        for v in b["varianti"]:
            codice = f"{b['cod']}-{v['sfx']}"
            if codice in visti:
                sys.exit(f"COLLISIONE DI CODICE: {codice} usato due volte. "
                         "E' esattamente l'errore del documento di partenza.")
            visti.add(codice)
            p = dict(v)
            p["sku"] = codice
            p["base"] = b["cod"]
            p["base_n"] = b["n"]
            p["base_nome"] = b["nome"]
            for k in ("cat", "target", "problema", "desiderio", "macchine", "tech",
                      "pack", "geometria", "pattern", "storytelling", "competitor",
                      "meglio_di", "seo", "prompt_prod", "prompt_img_scena"):
                p[k] = b[k]
            sku.append(p)
    return sku


# --------------------------------------------------------------------------
# Costo industriale
# --------------------------------------------------------------------------

def v_taglio(mk):
    """mm/s effettivi. Il metallo si taglia al fiber ed e' un altro mondo."""
    m = MAT[mk]
    if m["macchina"] == "F2":
        return 3.0 if m["sp"] <= 1 else 1.6
    return max(4.0, 90.0 / max(m["sp"], 1))


def costo_materiale(p):
    area = p["dim"][0] * p["dim"][1] / 1_000_000.0
    tot = 0.0
    for k in p["mat"]:
        m = MAT[k]
        quota = p.get("quota_mat", {}).get(k, 1.0)
        # lo scarto e' per materiale: il metallo si nesta meglio del legno
        tot += area * quota * m["eur_mq"] * (1 + m["scarto"] + 0.18)
    return tot


def tempi_macchina(p):
    """Minuti per macchina. Ritorna un dizionario, perche' le tariffe differiscono."""
    t = {"P3": 0.0, "F2": 0.0, "IR": 0.0, "UV": 0.0, "PRESS": 0.0}
    mats = [MAT[k] for k in p["mat"]]
    legno = [m for m in mats if m["macchina"] == "P3"]
    metallo = [m for m in mats if m["macchina"] == "F2"]

    if legno:
        v = sum(v_taglio(k) for k in p["mat"] if MAT[k]["macchina"] == "P3") / len(legno)
        t["P3"] += p.get("cut_mm", 0) / v / 60.0
        t["P3"] += p.get("vec_mm", 0) / 40.0 / 60.0
        t["P3"] += p.get("eng_cm2", 0) / 8.0
    if metallo:
        v = sum(v_taglio(k) for k in p["mat"] if MAT[k]["macchina"] == "F2") / len(metallo)
        t["F2"] += p.get("cut_mm", 0) / v / 60.0 if not legno else 0.0
    t["F2"] += p.get("mopa_cm2", 0) / 12.0
    t["UV"] += p.get("uv_cm2", 0) / 400.0
    return t


def costo_industriale(p):
    t = tempi_macchina(p)
    c_mac = sum(t[k] / 60.0 * MAC[k]["eur_h"] for k in t)
    min_mac = sum(t.values())
    c_ene = min_mac / 60.0 * TC["energia_eur_h"]
    c_lav = p["asm"] / 60.0 * TC["manodopera_eur_h"]
    c_mat = costo_materiale(p)
    c_com = sum(COMP[k]["eur"] * q for k, q in p.get("comp", {}).items())
    c_pack = PACK[p["pack"]]["eur"] if p["pack"] in PACK else 0.30
    tot = c_mat + c_mac + c_ene + c_lav + c_com + c_pack
    return {
        "t_macchina_min": round(min_mac, 2),
        "t_operatore_min": round(p["asm"], 1),
        "t_totale_min": round(min_mac + p["asm"], 1),
        "c_materiale": round(c_mat, 2),
        "c_macchina": round(c_mac, 2),
        "c_energia": round(c_ene, 2),
        "c_operatore": round(c_lav, 2),
        "c_componenti": round(c_com, 2),
        "c_packaging": round(c_pack, 2),
        "costo_industriale": round(tot, 2),
        "dettaglio_macchine": " · ".join(f"{k} {t[k]:.1f}min" for k in t if t[k] > 0.05),
    }


# --------------------------------------------------------------------------
# Prezzo e TRUE COST
# --------------------------------------------------------------------------

def prezzo(p, costo_ind):
    mkt = p["mkt"]
    target = mkt[0] + (mkt[1] - mkt[0]) * 0.45
    # pavimento: sotto 2,6x il costo industriale il canale si mangia tutto
    pav = costo_ind * 2.6
    val = max(target, pav)
    return math.floor(val) + 0.90 if val < 100 else round(val / 5.0) * 5.0 - 0.10


def true_cost(p, costo_ind, prezzo_v, canale):
    c = TC["canali"][canale]
    commissione = prezzo_v * c["commissione_pct"] + c["inserzione_eur"]
    pagamento = prezzo_v * TC["pagamento_pct"] + TC["pagamento_fisso_eur"]
    marketing = prezzo_v * TC["marketing_pct"]
    spedizione = TC["spedizione_eur"].get(p["pack"], 5.90)
    if canale == "B2B":
        marketing = prezzo_v * 0.03
        spedizione = spedizione * 0.35   # spedizione collettiva ripartita
    totale = costo_ind + commissione + pagamento + marketing + spedizione
    profitto = prezzo_v - totale
    return {
        "commissione": round(commissione, 2),
        "pagamento": round(pagamento, 2),
        "marketing": round(marketing, 2),
        "spedizione": round(spedizione, 2),
        "true_cost": round(totale, 2),
        "profitto": round(profitto, 2),
        "profitto_pct": round(profitto / prezzo_v * 100, 1) if prezzo_v else 0.0,
    }


def fascia(prezzo_v):
    for nome, f in FASCE.items():
        if f["min"] <= prezzo_v <= f["max"]:
            return nome
    return "EXECUTIVE" if prezzo_v > 400 else "ESSENTIAL"


# --------------------------------------------------------------------------
# INGLY SCORE
# --------------------------------------------------------------------------

def ingly_score(p, ind, tcs):
    w = SCORE["pesi"]
    pr = tcs["ETSY"]["profitto_pct"]
    # margine: 0% -> 0 punti, 50% di profitto reale -> pieno
    s_marg = max(0.0, min(w["margine"], pr / 50.0 * w["margine"]))
    # velocita': 5 minuti -> pieno, 40 minuti -> zero
    tt = ind["t_totale_min"]
    s_vel = max(0.0, min(w["velocita_produzione"],
                         (40.0 - tt) / 35.0 * w["velocita_produzione"]))
    s = p["s"]
    parti = {
        "domanda": min(s["dom"], w["domanda"]),
        "margine": round(s_marg, 1),
        "personalizzazione": min(s["pers"], w["personalizzazione"]),
        "differenziazione": min(s["diff"], w["differenziazione"]),
        "velocita_produzione": round(s_vel, 1),
        "spedibilita": min(s["sped"], w["spedibilita"]),
        "upsell": min(s["up"], w["upsell"]),
        "repeat_business": min(s["rep"], w["repeat_business"]),
    }
    tot = round(sum(parti.values()), 1)
    for nome, soglia in SCORE["soglie"].items():
        if tot >= soglia:
            cl = nome
            break
    else:
        cl = "SCARTARE"
    return parti, tot, cl


# --------------------------------------------------------------------------

def elabora(p):
    ind = costo_industriale(p)
    pv = prezzo(p, ind["costo_industriale"])
    tcs = {c: true_cost(p, ind["costo_industriale"], pv, c) for c in TC["canali"]}
    parti, tot, cl = ingly_score(p, ind, tcs)

    alert = []
    if tcs["ETSY"]["profitto_pct"] < 25:
        alert.append(f"PROFITTO SOTTILE su marketplace: {tcs['ETSY']['profitto_pct']:.0f}% "
                     f"dopo commissioni, pagamento, marketing e spedizione. "
                     f"Vendibile bene solo su canale proprio o B2B.")
    if tcs["ETSY"]["profitto"] < 0:
        alert.append("IN PERDITA su Etsy con spedizione inclusa: alzare il prezzo, "
                     "far pagare la spedizione o togliere il prodotto dal marketplace.")
    if ind["t_totale_min"] > 25:
        alert.append(f"LENTO: {ind['t_totale_min']} minuti a pezzo. Sopra i 25 minuti "
                     f"la produzione in lotto diventa il collo di bottiglia.")

    r = {
        "sku": p["sku"], "base": p["base"], "base_n": p["base_n"],
        "base_nome": p["base_nome"], "variante": p["nome"],
        "categoria": CAT[p["cat"]], "cat_id": p["cat"],
        "fascia": fascia(pv), "prezzo": pv,
        "target": p["target"], "problema": p["problema"], "desiderio": p["desiderio"],
        "tecnologia": p["tech"], "macchine": ", ".join(MAC[m]["nome"] for m in p["macchine"]),
        "materiali": " + ".join(MAT[k]["nome"] for k in p["mat"]),
        "dimensioni": f"{p['dim'][0]}×{p['dim'][1]}×{p['dim'][2]} mm",
        "componenti": ", ".join(COMP[k]["nome"] for k in p.get("comp", {})) or "—",
        "packaging": PACK[p["pack"]]["nome"] if p["pack"] in PACK else "imballo collettivo",
        "personalizzazione": p["pers"],
        "geometria": p["geometria"], "pattern": p["pattern"],
        "storytelling": p["storytelling"],
        "competitor": p["competitor"], "meglio_di": p["meglio_di"],
        "seo": ", ".join(p["seo"]),
        "prompt_prod": p["prompt_prod"], "prompt_img_scena": p["prompt_img_scena"],
        "lotto": p["lotto"],
        "ingly_score": tot, "classificazione": cl,
        "alert": " ".join(alert),
    }
    r.update(ind)
    for c, v in tcs.items():
        for k, val in v.items():
            r[f"{c.lower()}_{k}"] = val
    r.update({f"score_{k}": v for k, v in parti.items()})
    return r


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------

CSS = """
:root{--bg:#F4F4F2;--srf:#FFF;--srf2:#EBEBE8;--ink:#111;--mid:#4A4A48;--soft:#8A8A86;
--rule:#DCDCD8;--rule2:#BDBDB8;--acc:#8A6A05;--win:#2F6B3F;--tst:#8A6A05;--ris:#7A7A76;--scr:#A8412F;
--mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;--sans:ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
--serif:"Iowan Old Style",Palatino,Charter,Georgia,serif}
@media(prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#0F0F0E;--srf:#171716;--srf2:#1F1F1D;
--ink:#EDEDEA;--mid:#B6B6B1;--soft:#84847F;--rule:#282826;--rule2:#3C3C39;--acc:#D9A93A;
--win:#7FB08D;--tst:#D9A93A;--ris:#8A8A86;--scr:#DE8272}}
:root[data-theme=dark]{--bg:#0F0F0E;--srf:#171716;--srf2:#1F1F1D;--ink:#EDEDEA;--mid:#B6B6B1;
--soft:#84847F;--rule:#282826;--rule2:#3C3C39;--acc:#D9A93A;--win:#7FB08D;--tst:#D9A93A;--ris:#8A8A86;--scr:#DE8272}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--sans);font-size:16px;line-height:1.6}
.wrap{max-width:1200px;margin:0 auto;padding:0 24px}
header.top{border-bottom:1px solid var(--ink);background:var(--srf)}
.mk{font-family:var(--mono);font-size:10px;letter-spacing:.36em;text-transform:uppercase;color:var(--soft)}
h1{font-size:clamp(28px,5vw,52px);line-height:1;font-weight:300;letter-spacing:-.03em;margin:10px 0 0}
h1 b{font-weight:700}
.sub{font-family:var(--serif);font-size:17px;color:var(--mid);max-width:60ch;margin:14px 0 26px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(112px,1fr));border-top:1px solid var(--rule);font-family:var(--mono);font-size:11px}
.kpis div{padding:10px 14px 12px;border-right:1px solid var(--rule)}
.kpis div:last-child{border-right:none}
.kpis dt{color:var(--soft);letter-spacing:.14em;text-transform:uppercase;font-size:9.5px}
.kpis dd{margin:3px 0 0;font-weight:600;font-size:15px;font-variant-numeric:tabular-nums}
.tools{position:sticky;top:0;z-index:20;background:var(--bg);border-bottom:1px solid var(--rule);padding:11px 0}
.ti{max-width:1200px;margin:0 auto;padding:0 24px;display:flex;gap:8px;flex-wrap:wrap;align-items:center}
input,select{font-family:var(--mono);font-size:12px;padding:8px 10px;border:1px solid var(--rule2);background:var(--srf);color:var(--ink);border-radius:0}
input:focus-visible,select:focus-visible{outline:2px solid var(--acc);outline-offset:1px}
input[type=search]{min-width:200px;flex:1}
.cnt{font-family:var(--mono);font-size:11px;color:var(--soft);letter-spacing:.08em}
.dl{display:flex;gap:6px}
button.dlb{font-family:var(--mono);font-size:10px;letter-spacing:.1em;text-transform:uppercase;padding:8px 11px;
border:1px solid var(--rule2);background:var(--srf);color:var(--mid);cursor:pointer}
button.dlb:hover{border-color:var(--acc);color:var(--acc)}
h2{font-size:13px;font-family:var(--mono);letter-spacing:.2em;text-transform:uppercase;color:var(--acc);
margin:52px 0 4px;padding-bottom:8px;border-bottom:1px solid var(--rule2)}
.bh{background:var(--srf2);border:1px solid var(--rule2);padding:18px 20px;margin:18px 0 12px}
.bh h3{margin:0 0 4px;font-size:22px;font-weight:700;letter-spacing:-.02em}
.bh .n{font-family:var(--mono);font-size:11px;color:var(--soft);letter-spacing:.1em}
.bh p{margin:8px 0 0;font-family:var(--serif);font-size:15.5px;line-height:1.55;color:var(--mid)}
.bh b{color:var(--ink)}
.bh dl{margin:12px 0 0;font-family:var(--mono);font-size:11px}
.bh dl>div{display:grid;grid-template-columns:110px 1fr;gap:10px;padding:4px 0;border-bottom:1px dotted var(--rule)}
.bh dt{color:var(--soft);text-transform:uppercase;font-size:9.5px;letter-spacing:.06em}
.bh dd{margin:0;color:var(--ink)}
.v{border:1px solid var(--rule2);background:var(--srf);margin:8px 0}
.vh{display:flex;flex-wrap:wrap;align-items:baseline;gap:8px 12px;padding:10px 16px;border-bottom:1px solid var(--rule)}
.vh .s{font-family:var(--mono);font-size:11px;color:var(--soft);letter-spacing:.08em}
.vh h4{margin:0;font-size:16px;font-weight:600}
.vh .sp{flex:1}
.bd{font-family:var(--mono);font-size:9.5px;letter-spacing:.08em;text-transform:uppercase;padding:2px 7px;border:1px solid currentColor}
.b-WINNER{color:var(--win)}.b-TEST{color:var(--tst)}.b-RISERVA{color:var(--ris)}.b-SCARTARE{color:var(--scr);font-weight:700}
.sc{font-family:var(--mono);font-size:15px;font-weight:700;font-variant-numeric:tabular-nums}
.pz{font-family:var(--mono);font-size:15px;font-weight:700;color:var(--acc);font-variant-numeric:tabular-nums}
.vb{display:grid;grid-template-columns:1fr 340px}
@media(max-width:900px){.vb{grid-template-columns:1fr}}
.vd{padding:14px 16px;border-right:1px solid var(--rule)}
@media(max-width:900px){.vd{border-right:none;border-bottom:1px solid var(--rule)}}
.vd table{width:100%;border-collapse:collapse;font-family:var(--mono);font-size:11.5px}
.vd th{text-align:left;font-size:9.5px;letter-spacing:.08em;text-transform:uppercase;color:var(--soft);
padding:5px 8px 5px 0;border-bottom:1px solid var(--rule)}
.vd td{padding:5px 8px 5px 0;border-bottom:1px dotted var(--rule);font-variant-numeric:tabular-nums}
.vd td.neg{color:var(--scr)}
.vm{padding:14px 16px;font-family:var(--mono);font-size:11px}
.vm>div{display:grid;grid-template-columns:96px 1fr;gap:8px;padding:3px 0;border-bottom:1px dotted var(--rule)}
.vm dt{color:var(--soft);text-transform:uppercase;font-size:9.5px}
.vm dd{margin:0;font-variant-numeric:tabular-nums}
.al{padding:9px 16px;font-family:var(--mono);font-size:11px;line-height:1.5;background:var(--srf2);color:var(--scr);border-top:1px solid var(--rule)}
.pr{border-top:1px solid var(--rule);background:var(--srf2)}
.pr b{display:block;font-family:var(--mono);font-size:9px;letter-spacing:.18em;text-transform:uppercase;color:var(--acc);padding:9px 16px 0}
.pr pre{margin:0;padding:5px 16px 13px;font-family:var(--mono);font-size:11.5px;line-height:1.6;color:var(--mid);white-space:pre-wrap;word-break:break-word}
footer{margin-top:64px;border-top:1px solid var(--ink);background:var(--srf);padding:28px 0 48px}
footer p{font-family:var(--serif);font-size:15.5px;color:var(--mid);max-width:74ch}
@media(prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
"""

JS = """
const q=document.getElementById('q'),fc=document.getElementById('fc'),fk=document.getElementById('fk'),
ff=document.getElementById('ff'),n=document.getElementById('n');
function ap(){const t=(q.value||'').toLowerCase(),c=fc.value,k=fk.value,f=ff.value;let v=0;
document.querySelectorAll('.v').forEach(function(e){
 const ok=(!t||e.dataset.s.indexOf(t)>-1)&&(!c||e.dataset.c===c)&&(!k||e.dataset.k===k)&&(!f||e.dataset.f===f);
 e.style.display=ok?'':'none';if(ok)v++;});
document.querySelectorAll('.base').forEach(function(b){
 b.style.display=b.querySelectorAll('.v:not([style*="none"])').length?'':'none';});
document.querySelectorAll('section.cat').forEach(function(s){
 s.style.display=s.querySelectorAll('.base:not([style*="none"])').length?'':'none';});
n.textContent=v+' SKU';}
[q,fc,fk,ff].forEach(function(e){e.addEventListener('input',ap)});
const OGGI=new Date().toISOString().slice(0,10);
function msg(t,e){const el=document.getElementById('dm');if(!el)return;el.textContent=t;
 el.style.color=e?'var(--scr)':'var(--soft)';clearTimeout(window._t);window._t=setTimeout(function(){el.textContent=''},6000);}
function vis(){const s=new Set();document.querySelectorAll('.v').forEach(function(e){
 if(e.style.display!=='none')s.add(e.dataset.sku);});return DATI.filter(function(r){return s.has(r.sku)});}
function csv(rs){if(!rs.length)return'';const c=Object.keys(rs[0]);
 const e=function(v){if(v==null)v='';v=String(v);return /[",;\\n]/.test(v)?'"'+v.replace(/"/g,'""')+'"':v};
 return [c.join(';')].concat(rs.map(function(r){return c.map(function(k){return e(r[k])}).join(';')})).join('\\n');}
async function off(nm,tx,rip){const d=window.claude&&window.claude.downloads;
 if(!d){msg('download non disponibile in questa vista',true);return;}
 try{await d.save({filename:nm,data:tx});msg('salvato: '+nm);}
 catch(er){const c=er&&er.code;
  if(c==='extension_not_enabled'&&rip){try{await d.save({filename:rip,data:tx});msg('salvato: '+rip);return;}catch(e2){}}
  if(c==='declined'){msg('download annullato');return;}
  msg('non riuscito: '+(er&&er.message||'errore'),true);}}
document.addEventListener('click',function(ev){const b=ev.target.closest('[data-dl]');if(!b)return;
 const d=vis();if(!d.length){msg('nessuno SKU con i filtri attuali',true);return;}
 const base='ingly-catalogo-'+OGGI;
 if(b.dataset.dl==='json')off(base+'.json',JSON.stringify(d,null,2));
 if(b.dataset.dl==='csv')off(base+'.csv','\\ufeff'+csv(d),base+'.txt');
 if(b.dataset.dl==='md')off(base+'.md',MD(d));});
if(!(window.claude&&window.claude.downloads)){document.querySelectorAll('.dl').forEach(function(e){e.style.display='none'});}
"""


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def scrivi_html(recs, path):
    per_cat = {}
    for r in recs:
        per_cat.setdefault(r["cat_id"], {}).setdefault(r["base"], []).append(r)

    cl_conta = {}
    for r in recs:
        cl_conta[r["classificazione"]] = cl_conta.get(r["classificazione"], 0) + 1
    prof = sum(r["etsy_profitto_pct"] for r in recs) / len(recs)
    marg_lordo = sum((r["prezzo"] - r["costo_industriale"]) / r["prezzo"] * 100 for r in recs) / len(recs)

    idx = {b["cod"]: b for b in BASI}
    h = []
    a = h.append
    a("<title>INGLY Design — Catalogo Premium</title>")
    a(f"<style>{CSS}</style>")
    a('<header class="top"><div class="wrap" style="padding-top:26px">')
    a('<div class="mk">Ingly Product Intelligence System</div>')
    a('<h1>Catalogo <b>Premium</b></h1>')
    a('<p class="sub">27 basi produttive, 108 SKU. Il prezzo non è il costo per un moltiplicatore '
      'e il margine non è il profitto: qui il TRUE COST include commissioni di canale, costi di '
      'pagamento, marketing e spedizione, e l’INGLY SCORE ne tiene conto.</p>')
    a('</div><dl class="kpis" style="max-width:1200px;margin:0 auto;padding:0 24px">')
    a(f'<div><dt>SKU</dt><dd>{len(recs)}</dd></div>')
    a(f'<div><dt>Basi</dt><dd>{len(BASI)}</dd></div>')
    a(f'<div><dt>Categorie</dt><dd>{len(per_cat)}</dd></div>')
    for k in ("WINNER", "TEST", "RISERVA", "SCARTARE"):
        a(f'<div><dt>{k}</dt><dd>{cl_conta.get(k, 0)}</dd></div>')
    a(f'<div><dt>Margine lordo</dt><dd>{marg_lordo:.0f}%</dd></div>')
    a(f'<div><dt>Profitto reale</dt><dd>{prof:.0f}%</dd></div>')
    a('</dl></header>')

    a('<nav class="tools"><div class="ti">')
    a('<input type="search" id="q" placeholder="cerca SKU, prodotto, materiale, macchina…">')
    a('<select id="fc"><option value="">tutte le categorie</option>')
    for cid in sorted(per_cat):
        a(f'<option value="{cid}">{esc(CAT[cid])}</option>')
    a('</select><select id="fk"><option value="">tutte le classi</option>')
    for k in ("WINNER", "TEST", "RISERVA", "SCARTARE"):
        a(f'<option value="{k}">{k}</option>')
    a('</select><select id="ff"><option value="">tutte le fasce</option>')
    for k in FASCE:
        a(f'<option value="{k}">{k}</option>')
    a(f'</select><span class="cnt" id="n">{len(recs)} SKU</span>')
    a('<span class="dl"><button class="dlb" data-dl="md" type="button">scarica pagina</button>'
      '<button class="dlb" data-dl="csv" type="button">csv</button>'
      '<button class="dlb" data-dl="json" type="button">json</button></span>'
      '<span class="cnt" id="dm" role="status" aria-live="polite"></span>')
    a('</div></nav><div class="wrap">')

    for cid in sorted(per_cat):
        a(f'<section class="cat"><h2>{esc(CAT[cid])}</h2>')
        for cod, vs in per_cat[cid].items():
            b = idx[cod]
            a('<div class="base">')
            a('<div class="bh">')
            a(f'<div class="n">BASE {b["n"]:02d} · {cod}</div>')
            a(f'<h3>{esc(b["nome"])}</h3>')
            a(f'<p><b>Problema.</b> {esc(b["problema"])} <b>Desiderio.</b> {esc(b["desiderio"])}</p>')
            a(f'<p><b>Geometria proprietaria.</b> {esc(b["geometria"])}</p>')
            a(f'<p><b>Micro-pattern.</b> {esc(b["pattern"])}</p>')
            a(f'<p><b>Concorrenza.</b> {esc(b["competitor"])}</p>')
            a(f'<p><b>Cosa fa INGLY meglio.</b> {esc(b["meglio_di"])}</p>')
            a('<dl>')
            for k, v in [("Target", b["target"]), ("Tecnologia", b["tech"]),
                         ("Macchine", ", ".join(MAC[m]["nome"] for m in b["macchine"])),
                         ("Packaging", PACK[b["pack"]]["nome"] if b["pack"] in PACK else "collettivo"),
                         ("Storytelling", b["storytelling"]), ("SEO", ", ".join(b["seo"]))]:
                a(f'<div><dt>{k}</dt><dd>{esc(v)}</dd></div>')
            a('</dl></div>')
            a(f'<div class="pr"><b>Prompt di produzione — base</b><pre>{esc(b["prompt_prod"])}</pre></div>')
            a(f'<div class="pr"><b>Prompt immagine — base</b><pre>{esc(b["prompt_img_scena"])}</pre></div>')

            for r in vs:
                hay = " ".join([r["sku"], r["variante"], r["materiali"], r["macchine"],
                                r["base_nome"]]).lower()
                a(f'<article class="v" data-sku="{r["sku"]}" data-c="{cid}" '
                  f'data-k="{r["classificazione"]}" data-f="{r["fascia"]}" data-s="{esc(hay)}">')
                a('<div class="vh">')
                a(f'<span class="s">{r["sku"]}</span><h4>{esc(r["variante"])}</h4>')
                a('<span class="sp"></span>')
                a(f'<span class="bd">{r["fascia"]}</span>')
                a(f'<span class="pz">{r["prezzo"]:.2f} €</span>')
                a(f'<span class="sc">{r["ingly_score"]}</span>')
                a(f'<span class="bd b-{r["classificazione"]}">{r["classificazione"]}</span></div>')
                a('<div class="vb"><div class="vd">')
                a('<table><thead><tr><th>Canale</th><th>Prezzo</th><th>TRUE COST</th>'
                  '<th>Profitto</th><th>%</th></tr></thead><tbody>')
                for c in TC["canali"]:
                    k = c.lower()
                    neg = ' class="neg"' if r[f"{k}_profitto"] < 0 else ""
                    a(f'<tr><td>{TC["canali"][c]["nome"]}</td><td>{r["prezzo"]:.2f}</td>'
                      f'<td>{r[f"{k}_true_cost"]:.2f}</td><td{neg}>{r[f"{k}_profitto"]:.2f}</td>'
                      f'<td{neg}>{r[f"{k}_profitto_pct"]:.0f}%</td></tr>')
                a('</tbody></table>')
                a(f'<table style="margin-top:10px"><thead><tr><th>Voce di costo industriale</th>'
                  f'<th>€</th></tr></thead><tbody>')
                for et, kk in [("Materiale", "c_materiale"), ("Macchina", "c_macchina"),
                               ("Energia", "c_energia"), ("Operatore", "c_operatore"),
                               ("Componenti", "c_componenti"), ("Packaging", "c_packaging"),
                               ("TOTALE", "costo_industriale")]:
                    a(f'<tr><td>{et}</td><td>{r[kk]:.2f}</td></tr>')
                a('</tbody></table></div>')
                a('<dl class="vm">')
                for k, v in [("Materiali", r["materiali"]), ("Dimensioni", r["dimensioni"]),
                             ("Componenti", r["componenti"]), ("Person.", r["personalizzazione"]),
                             ("Tempo", f'{r["t_totale_min"]} min ({r["dettaglio_macchine"]})'),
                             ("Lotto", f'{r["lotto"]} pz'),
                             ("Domanda", f'{r["score_domanda"]}/20'),
                             ("Margine", f'{r["score_margine"]}/25'),
                             ("Person.pt", f'{r["score_personalizzazione"]}/15'),
                             ("Diff.", f'{r["score_differenziazione"]}/15'),
                             ("Velocità", f'{r["score_velocita_produzione"]}/10'),
                             ("Sped./Ups./Rep.", f'{r["score_spedibilita"]}+{r["score_upsell"]}+{r["score_repeat_business"]}')]:
                    a(f'<div><dt>{k}</dt><dd>{esc(v)}</dd></div>')
                a('</dl></div>')
                if r["alert"]:
                    a(f'<div class="al">{esc(r["alert"])}</div>')
                a('</article>')
            a('</div>')
        a('</section>')

    a('</div><footer><div class="wrap"><div class="mk">Ingly Design</div>')
    a('<p style="margin-top:12px">Il <b>margine lordo medio è il '
      f'{marg_lordo:.0f}%</b>, ma il <b>profitto reale medio su marketplace è il {prof:.0f}%</b>: '
      'la differenza sono commissioni, costi di pagamento, marketing e spedizione, che il modello '
      'conta sempre. I prezzi sono ancorati alle fasce di mercato osservate con un pavimento a 2,6× '
      'il costo industriale. Le tariffe orarie delle macchine e il costo di acquisizione cliente '
      'sono ipotesi documentate da tarare sui dati reali dopo i primi novanta giorni.</p>')
    a('</div></footer>')
    a('<script type="application/json" id="d">'
      + json.dumps(recs, ensure_ascii=False).replace("</", "<\\/") + "</script>")
    a('<script>const DATI=JSON.parse(document.getElementById("d").textContent);'
      'const MD=function(rs){return "# INGLY Design — Catalogo\\n\\n"+rs.length+" SKU\\n\\n"'
      '+rs.map(function(r){return "## "+r.sku+" — "+r.variante+"\\n\\n"'
      '+"**Base** "+r.base_nome+"  \\n**Categoria** "+r.categoria+"  \\n**Fascia** "+r.fascia'
      '+"  \\n**Prezzo** "+r.prezzo+" EUR  \\n**INGLY SCORE** "+r.ingly_score+" ("+r.classificazione+")"'
      '+"\\n\\n**Problema.** "+r.problema+"\\n\\n**Desiderio.** "+r.desiderio'
      '+"\\n\\n**Geometria.** "+r.geometria+"\\n\\n**Pattern.** "+r.pattern'
      '+"\\n\\n**Concorrenza.** "+r.competitor+"\\n\\n**Meglio di.** "+r.meglio_di'
      '+"\\n\\n**Materiali** "+r.materiali+"  \\n**Dimensioni** "+r.dimensioni'
      '+"  \\n**Macchine** "+r.macchine+"  \\n**Tempo** "+r.t_totale_min+" min"'
      '+"  \\n**Costo industriale** "+r.costo_industriale+" EUR"'
      '+"  \\n**TRUE COST Etsy** "+r.etsy_true_cost+" EUR  \\n**Profitto Etsy** "+r.etsy_profitto+" EUR ("+r.etsy_profitto_pct+"%)"'
      '+"  \\n**Profitto shop proprio** "+r.shopify_profitto+" EUR ("+r.shopify_profitto_pct+"%)"'
      '+"  \\n**SEO** "+r.seo'
      '+(r.alert?"\\n\\n> "+r.alert:"")'
      '+"\\n\\n### Prompt di produzione\\n\\n"+r.prompt_prod'
      '+"\\n\\n### Prompt immagine\\n\\n"+r.prompt_img_scena+"\\n"'
      '}).join("\\n---\\n\\n")};</script>')
    a(f"<script>{JS}</script>")
    Path(path).write_text("\n".join(h), encoding="utf-8")


def main():
    OUT.mkdir(exist_ok=True)
    sku = espandi()
    recs = [elabora(p) for p in sku]
    recs.sort(key=lambda r: (r["cat_id"], r["base_n"], r["sku"]))

    with open(OUT / "ingly_catalogo.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(recs[0].keys()), extrasaction="ignore")
        w.writeheader(); w.writerows(recs)
    json.dump({"sku": recs, "basi": BASI, "sistema": SYS},
              open(OUT / "ingly_catalogo.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    scrivi_html(recs, OUT / "ingly.html")

    cl = {}
    for r in recs:
        cl[r["classificazione"]] = cl.get(r["classificazione"], 0) + 1
    print(f"\n{len(recs)} SKU da {len(BASI)} basi\n")
    print(f"{'Categoria':<34}{'SKU':>5}{'Score':>8}{'Prezzo':>9}{'Marg.lordo':>12}{'Profitto Etsy':>15}")
    print("-" * 83)
    per = {}
    for r in recs:
        per.setdefault(r["categoria"], []).append(r)
    for c, rs in sorted(per.items()):
        ml = sum((x["prezzo"] - x["costo_industriale"]) / x["prezzo"] * 100 for x in rs) / len(rs)
        pf = sum(x["etsy_profitto_pct"] for x in rs) / len(rs)
        print(f"{c:<34}{len(rs):>5}{sum(x['ingly_score'] for x in rs)/len(rs):>8.1f}"
              f"{sum(x['prezzo'] for x in rs)/len(rs):>8.2f}€{ml:>11.0f}%{pf:>14.0f}%")
    print("-" * 83)
    print("Classificazione:", "  ".join(f"{k}={cl.get(k, 0)}"
                                        for k in ("WINNER", "TEST", "RISERVA", "SCARTARE")))
    perdita = [r for r in recs if r["etsy_profitto"] < 0]
    sottili = [r for r in recs if 0 <= r["etsy_profitto_pct"] < 25]
    print(f"In perdita su Etsy: {len(perdita)} · profitto sottile (<25%): {len(sottili)}")
    print(f"\nOutput in {OUT}/")


if __name__ == "__main__":
    main()
