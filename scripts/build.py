#!/usr/bin/env python3
"""
INGLY DESIGN — Catalog Build Engine
===================================

Legge i dati sorgente e produce il catalogo completo calcolando tutto cio' che
non ha senso scrivere a mano 300 volte: costi, prezzi, margini, punteggi e
priorita' di lancio.

Il principio: i costi NON sono opinioni. Derivano da area di materiale, lunghezza
di taglio, area di incisione, area di stampa, tempo di assemblaggio e componenti,
moltiplicati per le tariffe in data/reference.json. Cambia una tariffa la' dentro
e tutto il catalogo si ricalcola coerentemente.

    python3 scripts/build.py

Produce in out/:
    catalogo.csv            catalogo completo, tutti i campi
    catalogo.json           stesso contenuto, per ERP e API
    shopify_import.csv      pronto per Shopify
    woocommerce_import.csv  pronto per WooCommerce
    catalogo.xlsx           foglio di lavoro (se openpyxl e' installato)
    index.html              catalogo navigabile
"""

import csv
import json
import math
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "out"


# --------------------------------------------------------------------------
# Caricamento
# --------------------------------------------------------------------------

def load(name):
    path = DATA / f"{name}.json"
    if not path.exists():
        sys.exit(f"Manca {path}. Esegui prima la creazione dei dati sorgente.")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load_products():
    """
    I prodotti stanno in data/products/*.json, un file per categoria.
    Tenerli separati rende il catalogo leggibile in diff e permette di lavorare
    su una categoria senza toccare le altre.
    """
    folder = DATA / "products"
    if not folder.exists():
        sys.exit(f"Manca {folder}.")
    prodotti = []
    visti = set()
    for path in sorted(folder.glob("*.json")):
        with open(path, encoding="utf-8") as fh:
            blocco = json.load(fh)
        for p in blocco.get("prodotti", []):
            if p["id"] in visti:
                sys.exit(f"SKU duplicato: {p['id']} (in {path.name})")
            visti.add(p["id"])
            prodotti.append(p)
    return {"prodotti": prodotti}


REF = load("reference")
CATEGORIES = load("categories")
PRODUCTS = load_products()

MAT = REF["materiali"]
COMP = REF["componenti"]
MACH = REF["macchina"]
PACK = REF["packaging"]
PLAT = REF["piattaforme"]
MULT = REF["listino_moltiplicatori"]
PESI = REF["score_pesi"]
SOGLIE = REF["priorita_soglie"]


# --------------------------------------------------------------------------
# Modello di costo
# --------------------------------------------------------------------------

def area_mq(dim_mm):
    """Area di ingombro in metri quadri, dalla bounding box."""
    w, h = dim_mm[0], dim_mm[1]
    return (w * h) / 1_000_000.0


def costo_materiale(p):
    """
    Costo materiale = somma degli strati, ciascuno con la sua area e il suo
    prezzo al metro quadro, maggiorato dello sfrido di nesting.
    """
    tot = 0.0
    sfrido = 1.0 + p.get("sfrido", 0.22)   # 22% di scarto se non dichiarato
    base = area_mq(p["dim"])
    for key in p["mat"]:
        m = MAT.get(key)
        if not m:
            raise KeyError(f"{p['id']}: materiale sconosciuto '{key}'")
        quota = p.get("quota_mat", {}).get(key, 1.0)
        tot += base * quota * m["eur_mq"] * sfrido
    return tot


def tempo_co2_min(p):
    """Minuti di macchina CO2: taglio + incisione vettoriale + raster."""
    mats = [MAT[k] for k in p["mat"] if MAT[k]["co2_mm_s"] > 0]
    if not mats:
        return 0.0
    # velocita' media pesata sugli spessori effettivamente tagliati
    v_cut = sum(m["co2_mm_s"] for m in mats) / len(mats)
    t_cut = p.get("cut_mm", 0) / max(v_cut, 1e-6) / 60.0
    t_vec = p.get("vec_mm", 0) / MACH["vettoriale_mm_s"] / 60.0
    t_ras = p.get("eng_cm2", 0) / MACH["raster_cm2_min"]
    return t_cut + t_vec + t_ras


def tempo_uv_min(p):
    return p.get("uv_cm2", 0) / MACH["uv_cm2_min"]


def tempo_mopa_min(p):
    return p.get("mopa_cm2", 0) / MACH["mopa_cm2_min"]


def costo_inchiostro(p):
    uv = p.get("uv_cm2", 0)
    c = uv * MACH["inchiostro_colore_eur_cm2"]
    if p.get("uv_white"):
        c += uv * MACH["inchiostro_bianco_eur_cm2"]
    if p.get("uv_gloss_cm2"):
        c += p["uv_gloss_cm2"] * MACH["inchiostro_gloss_eur_cm2"]
    return c


def costo_componenti(p):
    tot = 0.0
    for key, qty in p.get("comp", {}).items():
        c = COMP.get(key)
        if not c:
            raise KeyError(f"{p['id']}: componente sconosciuto '{key}'")
        tot += c["eur"] * qty
    return tot


def costo_packaging(p):
    pk = PACK.get(p.get("pack", "busta"))
    return pk["eur"] + PACK["cartellino"]["eur"]


def calcola_costo(p):
    """Ritorna il dizionario completo dei costi di un prodotto."""
    lotto = p.get("lotto", 20)

    t_co2 = tempo_co2_min(p)
    t_uv = tempo_uv_min(p)
    t_mopa = tempo_mopa_min(p)
    t_asm = p.get("assembly_min", PLAT[p["platform"]]["assemblaggio_min"])
    t_setup = MACH["setup_min_lotto"] / max(lotto, 1)

    c_mat = costo_materiale(p)
    c_co2 = (t_co2 + t_setup) / 60.0 * MACH["co2_eur_h"]
    c_uv = t_uv / 60.0 * MACH["uv_eur_h"] + costo_inchiostro(p)
    c_mopa = t_mopa / 60.0 * MACH["mopa_eur_h"]
    c_lav = t_asm / 60.0 * MACH["manodopera_eur_h"]
    c_comp = costo_componenti(p)
    c_pack = costo_packaging(p)

    totale = c_mat + c_co2 + c_uv + c_mopa + c_lav + c_comp + c_pack
    t_totale = t_co2 + t_uv + t_mopa + t_asm + t_setup

    return {
        "t_co2_min": round(t_co2, 2),
        "t_uv_min": round(t_uv, 2),
        "t_mopa_min": round(t_mopa, 2),
        "t_assemblaggio_min": round(t_asm, 2),
        "t_totale_min": round(t_totale, 1),
        "c_materiale": round(c_mat, 2),
        "c_co2": round(c_co2, 2),
        "c_uv": round(c_uv, 2),
        "c_mopa": round(c_mopa, 2),
        "c_manodopera": round(c_lav, 2),
        "c_componenti": round(c_comp, 2),
        "c_packaging": round(c_pack, 2),
        "costo_totale": round(totale, 2),
    }


def prezzo_psicologico(v):
    """Arrotonda come si fa in un listino vero: ,90 sotto i 100 €, multipli di 5 sopra."""
    if v < 100:
        return math.floor(v) + 0.90
    return round(v / 5.0) * 5.0 - 0.10


def calcola_prezzi(costo, mkt=None):
    """
    Il costo-piu-margine da' il PAVIMENTO, non il prezzo. Da solo sottoprezza
    sistematicamente i prodotti economici che il mercato valuta molto piu' del
    loro costo industriale (un set di sottobicchieri costa 4 € e si vende a 30).

    Quando conosciamo la fascia di mercato osservata la usiamo per posizionare
    il prezzo, tenendo il costo-piu-margine come soglia minima invalicabile.
    Se il pavimento di costo supera il tetto di mercato il prodotto non e'
    competitivo, e va segnalato invece che venduto in perdita.
    """
    p = {}
    for k, mult in MULT.items():
        if k.startswith("_"):
            continue
        p[f"prezzo_{k}"] = round(prezzo_psicologico(costo * mult), 2)

    p["alert_competitivita"] = ""
    if not mkt:
        p["posizionamento"] = "costo+margine (fascia di mercato non rilevata)"
        return p

    mkt_min, mkt_max = mkt
    pavimento = costo * 3.0

    if pavimento > mkt_max:
        p["alert_competitivita"] = (
            f"NON COMPETITIVO — il costo industriale impone almeno "
            f"{pavimento:.0f} € ma il mercato si ferma a {mkt_max:.0f} €. "
            f"Rivedere materiali e tempi, oppure spostare il prodotto in fascia premium con un contenuto diverso."
        )
        p["posizionamento"] = "fuori mercato"
        return p

    # posiziona lo standard al 40% dentro la fascia osservata, mai sotto il pavimento
    target = mkt_min + (mkt_max - mkt_min) * 0.40
    standard = max(target, pavimento, p["prezzo_standard"])
    p["prezzo_entry"] = round(prezzo_psicologico(max(mkt_min, costo * 2.6)), 2)
    p["prezzo_standard"] = round(prezzo_psicologico(standard), 2)
    p["prezzo_premium"] = round(prezzo_psicologico(max(standard * 1.45, mkt_max * 0.85)), 2)
    p["posizionamento"] = f"ancorato al mercato {mkt_min:.0f}-{mkt_max:.0f} €"

    if p["prezzo_standard"] > costo * 5.0:
        p["alert_competitivita"] = (
            f"MARGINE MOLTO ALTO — il mercato regge {p['prezzo_standard']:.0f} € "
            f"su un costo di {costo:.2f} €. Verificare che la qualita' percepita sia all'altezza del prezzo."
        )
    return p


def calcola_margini(costo, prezzi):
    m = {}
    for k, prezzo in prezzi.items():
        if not isinstance(prezzo, (int, float)):
            continue
        nome = k.replace("prezzo_", "")
        lordo = prezzo - costo
        m[f"margine_{nome}"] = round(lordo, 2)
        m[f"margine_pct_{nome}"] = round(lordo / prezzo * 100, 1) if prezzo else 0.0
    return m


# --------------------------------------------------------------------------
# Market score
# --------------------------------------------------------------------------

def score_margine(costo, prezzo_std):
    """
    0-20, sul MARGINE LORDO ASSOLUTO in euro, non sul moltiplicatore.

    Il moltiplicatore non puo' essere il criterio: siccome il prezzo lo deriviamo
    dal costo, sarebbe identico per tutti i prodotti e non misurerebbe niente.
    Quello che conta davvero per l'azienda e' quanti euro restano in tasca su
    ogni pezzo venduto: 25 € di margine valgono piu' di 3 €, a parita' di tutto.
    I prodotti a basso margine unitario ma altissimo volume (bomboniere,
    segnaposto) recuperano sul punteggio di domanda, dove e' giusto che stiano.

    Curva satura: 14 € -> 12,6 punti ; 30 € -> 17,6 ; 50 € -> 19,4.
    """
    margine = prezzo_std - costo
    if margine <= 0:
        return 0
    val = PESI["margin"] * (1 - math.exp(-margine / 14.0))
    return round(val, 1)


def score_produzione(p, costi):
    """0-15. Penalizza tempo totale e complessita' della piattaforma."""
    t = costi["t_totale_min"]
    compl = PLAT[p["platform"]]["complessita"]
    # 5 min e complessita' 1 -> quasi pieno ; 45 min e complessita' 4 -> basso
    val = PESI["production"] - (t / 5.0) - (compl - 1) * 1.4
    return max(0, min(PESI["production"], round(val, 1)))


def calcola_score(p, costi, prezzi):
    s_margin = score_margine(costi["costo_totale"], prezzi["prezzo_standard"])
    s_prod = score_produzione(p, costi)
    parti = {
        "demand": min(p.get("s_demand", 10), PESI["demand"]),
        "competition": min(p.get("s_comp", 7), PESI["competition"]),
        "margin": s_margin,
        "production": s_prod,
        "personalization": min(p.get("s_person", 5), PESI["personalization"]),
        "giftability": min(p.get("s_gift", 5), PESI["giftability"]),
        "uniqueness": min(p.get("s_uniq", 5), PESI["uniqueness"]),
    }
    totale = round(sum(parti.values()), 1)
    for nome, soglia in SOGLIE.items():
        if totale >= soglia:
            prio = nome
            break
    else:
        prio = "D"
    return parti, totale, prio


# --------------------------------------------------------------------------
# Generazione contenuti pubblicabili
# --------------------------------------------------------------------------

MATERIA_LABEL = {
    "betulla": "legno di betulla",
    "mdf": "MDF",
    "acrilico": "acrilico",
    "sughero": "sughero",
    "feltro": "feltro",
    "pioppo": "compensato di pioppo",
    "ardesia": "pietra",
}


def materiale_leggibile(p):
    visti = []
    for k in p["mat"]:
        for radice, label in MATERIA_LABEL.items():
            if k.startswith(radice) and label not in visti:
                visti.append(label)
    return " e ".join(visti) if visti else "legno"


def dimensioni_leggibili(p):
    d = p["dim"]
    if len(d) >= 3 and d[2] > 0:
        return f"{d[0]}×{d[1]}×{d[2]} mm"
    return f"{d[0]}×{d[1]} mm"


def tecnologia_leggibile(p):
    return {
        "CO2": "taglio e incisione laser",
        "UV": "stampa UV diretta",
        "CO2+UV": "taglio laser e stampa UV",
        "CO2+MOPA": "taglio laser e marcatura su metallo",
        "CO2+UV+MOPA": "taglio laser, stampa UV e marcatura su metallo",
    }.get(p["tech"], "lavorazione laser")


def genera_titolo(p, cat):
    """Titolo commerciale pubblicabile: nome + cosa e' + leva principale."""
    base = f"{p['name']} — {p['tipo']}"
    if p.get("person"):
        base += " personalizzabile"
    return base[:140]


def genera_titolo_en(p):
    base = f"{p['name']} — {p.get('tipo_en', p['tipo'])}"
    if p.get("person"):
        base += ", personalised"
    return base[:140]


def genera_desc_breve(p):
    return (
        f"{p['concept']} Realizzato in {materiale_leggibile(p)} con "
        f"{tecnologia_leggibile(p)}. {dimensioni_leggibili(p)}."
    )


def genera_desc_lunga(p, cat):
    righe = [
        p["concept"],
        "",
        f"**Perché piace.** {p['usp']}",
        "",
        f"**Cosa lo rende diverso.** {p['diff']}",
        "",
        f"**Materiali e lavorazione.** {materiale_leggibile(p).capitalize()}, "
        f"lavorato con {tecnologia_leggibile(p)}. Dimensioni {dimensioni_leggibili(p)}.",
    ]
    if p.get("person"):
        righe += ["", f"**Personalizzazione.** {', '.join(p['person'])}."]
    righe += ["", f"**Per chi è.** {p['target']}"]
    return "\n".join(righe)


def genera_desc_breve_en(p):
    return (
        f"{p.get('concept_en', p['concept'])} Handmade in Sicily, "
        f"{dimensioni_leggibili(p)}."
    )


def slugify(s):
    s = re.sub(r"[^\w\s-]", "", s.lower())
    return re.sub(r"[\s_]+", "-", s).strip("-")


def genera_seo(p, cat):
    kw = p.get("kw", [])
    seo_title = f"{p['name']} {p['tipo']} | Ingly Design"
    if len(seo_title) > 60:
        seo_title = f"{p['name']} | Ingly Design"
    meta = genera_desc_breve(p)
    if len(meta) > 158:
        meta = meta[:155].rsplit(" ", 1)[0] + "..."
    return {
        "seo_title": seo_title,
        "meta_description": meta,
        "keywords": ", ".join(kw),
        "handle": slugify(f"{p['name']}-{p['tipo']}"),
        "search_intent": p.get("intent", "commerciale — acquisto regalo personalizzato"),
    }


# --------------------------------------------------------------------------
# Assemblaggio del record finale
# --------------------------------------------------------------------------

def elabora(p):
    cat = CATEGORIES["categorie"][p["cat"]]
    costi = calcola_costo(p)
    prezzi = calcola_prezzi(costi["costo_totale"], p.get("mkt"))
    margini = calcola_margini(costi["costo_totale"], prezzi)
    parti, totale, prio = calcola_score(p, costi, prezzi)
    seo = genera_seo(p, cat)

    rec = {
        "sku": p["id"],
        "categoria": cat["nome"],
        "categoria_id": p["cat"],
        "collezione": p.get("coll", ""),
        "nome": p["name"],
        "tipo": p["tipo"],
        "titolo_it": genera_titolo(p, cat),
        "titolo_en": genera_titolo_en(p),
        "descrizione_breve_it": genera_desc_breve(p),
        "descrizione_lunga_it": genera_desc_lunga(p, cat),
        "descrizione_breve_en": genera_desc_breve_en(p),
        "concept": p["concept"],
        "target": p["target"],
        "desiderio": p["desire"],
        "usp": p["usp"],
        "differenziazione": p["diff"],
        "piattaforma": p["platform"],
        "piattaforma_nome": PLAT[p["platform"]]["nome"],
        "tecnologia": p["tech"],
        "materiali": " + ".join(MAT[k]["nome"] for k in p["mat"]),
        "dimensioni_mm": dimensioni_leggibili(p),
        "strati": p.get("layers", 1),
        "componenti": ", ".join(COMP[k]["nome"] for k in p.get("comp", {})) or "—",
        "packaging": PACK[p.get("pack", "busta")]["nome"],
        "personalizzazione": ", ".join(p.get("person", [])) or "—",
        "tag": ", ".join(p.get("tags", [])),
        "upsell": ", ".join(p.get("upsell", [])),
        "bundle": " | ".join(p.get("bundle", [])),
        "link_riferimento": p.get("ref", ""),
        "prompt_produzione": p.get("prompt_prod", ""),
        "prompt_immagine": p.get("prompt_img", ""),
        "lotto_riferimento": p.get("lotto", 20),
    }
    rec.update(costi)
    rec.update(prezzi)
    rec.update(margini)
    rec.update({f"score_{k}": v for k, v in parti.items()})
    rec["market_score"] = totale
    rec["priorita"] = prio
    rec.update(seo)
    return rec


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------

def scrivi_csv(records, path, campi=None):
    campi = campi or list(records[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=campi, extrasaction="ignore")
        w.writeheader()
        w.writerows(records)


def scrivi_shopify(records, path):
    righe = []
    for r in records:
        righe.append({
            "Handle": r["handle"],
            "Title": r["titolo_it"],
            "Body (HTML)": r["descrizione_lunga_it"].replace("\n", "<br>"),
            "Vendor": "Ingly Design",
            "Product Category": r["categoria"],
            "Type": r["tipo"],
            "Tags": r["tag"] + ", " + r["keywords"],
            "Published": "TRUE",
            "Option1 Name": "Versione",
            "Option1 Value": "Standard",
            "Variant SKU": r["sku"],
            "Variant Grams": "",
            "Variant Inventory Tracker": "shopify",
            "Variant Inventory Policy": "deny",
            "Variant Fulfillment Service": "manual",
            "Variant Price": r["prezzo_standard"],
            "Variant Compare At Price": r["prezzo_premium"],
            "Variant Requires Shipping": "TRUE",
            "Variant Taxable": "TRUE",
            "SEO Title": r["seo_title"],
            "SEO Description": r["meta_description"],
            "Status": "draft",
        })
    scrivi_csv(righe, path, list(righe[0].keys()))


def scrivi_woocommerce(records, path):
    righe = []
    for r in records:
        righe.append({
            "SKU": r["sku"],
            "Name": r["titolo_it"],
            "Published": 1,
            "Visibility in catalogue": "visible",
            "Short description": r["descrizione_breve_it"],
            "Description": r["descrizione_lunga_it"],
            "Regular price": r["prezzo_premium"],
            "Sale price": r["prezzo_standard"],
            "Categories": r["categoria"],
            "Tags": r["tag"],
            "Position": 0,
            "Meta: _yoast_wpseo_title": r["seo_title"],
            "Meta: _yoast_wpseo_metadesc": r["meta_description"],
        })
    scrivi_csv(righe, path, list(righe[0].keys()))


def scrivi_xlsx(records, path):
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment
    except ImportError:
        print("  openpyxl non installato — salto il .xlsx (pip install openpyxl)")
        return
    wb = Workbook()
    ws = wb.active
    ws.title = "Catalogo"
    campi = list(records[0].keys())
    ws.append(campi)
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF", size=9)
        c.fill = PatternFill("solid", fgColor="1C2023")
        c.alignment = Alignment(vertical="center", wrap_text=False)
    for r in records:
        ws.append([r.get(k, "") for k in campi])
    ws.freeze_panes = "C2"
    for i, campo in enumerate(campi, 1):
        larghezza = 14
        if campo in ("descrizione_lunga_it", "prompt_produzione", "prompt_immagine"):
            larghezza = 60
        elif campo in ("titolo_it", "titolo_en", "concept", "usp", "diff"):
            larghezza = 40
        ws.column_dimensions[ws.cell(1, i).column_letter].width = larghezza
    wb.save(path)


# --------------------------------------------------------------------------



# --------------------------------------------------------------------------
# Catalogo navigabile
# --------------------------------------------------------------------------

CSS = """
:root{--bg:#EFF1F0;--surface:#FAFBFA;--surface2:#E7EAE9;--ink:#14171A;--mid:#3E4749;
--soft:#697476;--rule:#D2D8D6;--rule2:#B4BDBB;--acc:#8A6A05;--accb:#E4B426;--accw:#F7EFD4;
--sea:#1B4B6B;--ok:#3F6B4F;--warn:#9A6B18;--crit:#A8412F;
--mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
--sans:ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
--serif:"Iowan Old Style",Palatino,Charter,Georgia,serif}
@media(prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#14171A;--surface:#1C2023;
--surface2:#23282B;--ink:#E9ECEB;--mid:#B9C1C0;--soft:#8B9594;--rule:#2D3336;--rule2:#414951;
--acc:#E4B426;--accb:#F2C230;--accw:#2A2517;--sea:#6FB0CB;--ok:#7FB08D;--warn:#D6A344;--crit:#DE8272}}
:root[data-theme=dark]{--bg:#14171A;--surface:#1C2023;--surface2:#23282B;--ink:#E9ECEB;
--mid:#B9C1C0;--soft:#8B9594;--rule:#2D3336;--rule2:#414951;--acc:#E4B426;--accb:#F2C230;
--accw:#2A2517;--sea:#6FB0CB;--ok:#7FB08D;--warn:#D6A344;--crit:#DE8272}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--sans);font-size:16px;line-height:1.6}
.wrap{max-width:1180px;margin:0 auto;padding:0 24px}
header.top{border-bottom:2px solid var(--ink);background:var(--surface)}
.marchio{font-family:var(--mono);font-size:11px;letter-spacing:.28em;text-transform:uppercase;color:var(--soft)}
h1{font-size:clamp(30px,5.5vw,56px);line-height:.95;font-weight:800;letter-spacing:-.03em;margin:8px 0 0}
h1 em{font-style:normal;color:var(--acc)}
.sub{font-family:var(--serif);font-size:18px;color:var(--mid);max-width:52ch;margin:14px 0 24px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));border-top:1px solid var(--rule);font-family:var(--mono);font-size:11px}
.kpis div{padding:10px 14px 12px;border-right:1px solid var(--rule)}
.kpis div:last-child{border-right:none}
.kpis dt{color:var(--soft);letter-spacing:.14em;text-transform:uppercase;font-size:10px}
.kpis dd{margin:3px 0 0;font-weight:600;font-size:14px;font-variant-numeric:tabular-nums}
.tools{position:sticky;top:0;z-index:20;background:var(--bg);border-bottom:1px solid var(--rule);padding:12px 0}
.tools-in{max-width:1180px;margin:0 auto;padding:0 24px;display:flex;gap:10px;flex-wrap:wrap;align-items:center}
input,select{font-family:var(--mono);font-size:12px;padding:8px 10px;border:1px solid var(--rule2);
background:var(--surface);color:var(--ink);border-radius:0}
input:focus-visible,select:focus-visible{outline:2px solid var(--acc);outline-offset:1px}
input[type=search]{min-width:220px;flex:1}
.count{font-family:var(--mono);font-size:11px;color:var(--soft);letter-spacing:.08em}
.dl{display:flex;gap:6px;flex-wrap:wrap}
button.dl-b{font-family:var(--mono);font-size:10px;letter-spacing:.1em;text-transform:uppercase;
padding:8px 11px;border:1px solid var(--rule2);background:var(--surface);color:var(--mid);cursor:pointer}
button.dl-b:hover{border-color:var(--acc);color:var(--acc)}
button.dl-b:focus-visible{outline:2px solid var(--acc);outline-offset:1px}
h2{font-size:26px;font-weight:800;letter-spacing:-.02em;margin:48px 0 6px}
.cat-an{font-family:var(--serif);font-size:17px;line-height:1.6;color:var(--mid);max-width:72ch;margin:0 0 8px}
.gaps{background:var(--accw);border-left:3px solid var(--accb);padding:14px 18px;margin:16px 0}
.gaps b{display:block;font-family:var(--mono);font-size:10px;letter-spacing:.18em;text-transform:uppercase;color:var(--acc);margin-bottom:8px}
.gaps ol{margin:0;padding-left:20px;font-family:var(--serif);font-size:15.5px;line-height:1.55;color:var(--mid)}
.gaps li{margin-bottom:5px}
details.refs{margin:14px 0;border:1px solid var(--rule)}
details.refs summary{cursor:pointer;padding:11px 16px;background:var(--surface2);font-family:var(--mono);
font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:var(--soft)}
details.refs summary:hover{color:var(--ink)}
.tw{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:13px;min-width:640px;background:var(--surface)}
th{text-align:left;font-family:var(--mono);font-size:10px;letter-spacing:.12em;text-transform:uppercase;
color:var(--soft);padding:10px 12px;border-bottom:1px solid var(--rule2);background:var(--surface2);white-space:nowrap}
td{padding:10px 12px;border-bottom:1px solid var(--rule);vertical-align:top;color:var(--mid)}
td a{color:var(--acc)}
.p{border:1px solid var(--rule2);background:var(--surface);margin:14px 0}
.ph{display:flex;flex-wrap:wrap;align-items:baseline;gap:8px 14px;padding:12px 16px;
border-bottom:1px solid var(--rule2);background:var(--surface2)}
.ph .sku{font-family:var(--mono);font-size:11px;letter-spacing:.08em;color:var(--soft)}
.ph h3{margin:0;font-size:19px;font-weight:800;letter-spacing:-.02em}
.ph .t{font-family:var(--serif);font-style:italic;font-size:14px;color:var(--soft)}
.ph .sp{flex:1}
.badge{font-family:var(--mono);font-size:10px;letter-spacing:.06em;text-transform:uppercase;
padding:2px 7px;border:1px solid currentColor;white-space:nowrap}
.b-ap{color:var(--crit);background:var(--accw)}
.b-a{color:var(--ok)}
.b-b{color:var(--warn)}
.b-c,.b-d{color:var(--soft)}
.b-pl{color:var(--sea)}
.sc{font-family:var(--mono);font-size:13px;font-weight:700;color:var(--ink);font-variant-numeric:tabular-nums}
.pb{display:grid;grid-template-columns:1.15fr 1fr;gap:0}
@media(max-width:820px){.pb{grid-template-columns:1fr}}
.pd{padding:16px;border-right:1px solid var(--rule)}
@media(max-width:820px){.pd{border-right:none;border-bottom:1px solid var(--rule)}}
.pd p{margin:0 0 9px;font-family:var(--serif);font-size:15.5px;line-height:1.58;color:var(--mid)}
.pd p:last-child{margin-bottom:0}
.pd b{color:var(--ink)}
dl.sp{margin:0;padding:16px;font-family:var(--mono);font-size:11.5px;line-height:1.5}
dl.sp>div{display:grid;grid-template-columns:96px 1fr;gap:10px;padding:4px 0;border-bottom:1px dotted var(--rule)}
dl.sp>div:last-child{border-bottom:none}
dl.sp dt{color:var(--soft);letter-spacing:.06em;text-transform:uppercase;font-size:9.5px;padding-top:1px}
dl.sp dd{margin:0;color:var(--ink);font-variant-numeric:tabular-nums}
.prz{color:var(--acc);font-weight:700}
.alert{padding:10px 16px;font-family:var(--mono);font-size:11.5px;line-height:1.5;
background:var(--accw);color:var(--crit);border-top:1px solid var(--rule2)}
.pr{border-top:1px solid var(--rule2);background:var(--surface2)}
.pr b{display:block;font-family:var(--mono);font-size:9.5px;letter-spacing:.18em;
text-transform:uppercase;color:var(--acc);padding:9px 16px 0}
.pr pre{margin:0;padding:6px 16px 14px;font-family:var(--mono);font-size:11.5px;line-height:1.6;
color:var(--mid);white-space:pre-wrap;word-break:break-word}
footer{margin-top:64px;border-top:2px solid var(--ink);background:var(--surface);padding:28px 0 48px}
footer p{font-family:var(--serif);font-size:15.5px;color:var(--mid);max-width:70ch}
@media(prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
"""

DL_JS = """
const OGGI=new Date().toISOString().slice(0,10);
function msg(t,err){const e=document.getElementById('dlmsg');if(!e)return;
 e.textContent=t;e.style.color=err?'var(--crit)':'var(--soft)';
 clearTimeout(window._dlt);window._dlt=setTimeout(function(){e.textContent=''},6000);}
function datiVisibili(){
 const vis=new Set();document.querySelectorAll('[data-dlid]').forEach(function(el){
  if(el.style.display!=='none')vis.add(el.dataset.dlid);});
 return DATI.filter(function(r){return vis.has(String(r[IDKEY]))});}
function csvDa(righe){
 if(!righe.length)return '';
 const c=Object.keys(righe[0]);
 const esc=function(v){if(v==null)v='';if(typeof v==='object')v=JSON.stringify(v);
  v=String(v);return /[",;\n]/.test(v)?'"'+v.replace(/"/g,'""')+'"':v};
 return [c.join(';')].concat(righe.map(function(r){
  return c.map(function(k){return esc(r[k])}).join(';')})).join('\n');}
async function offri(nome,testo,ripiego){
 const d=window.claude&&window.claude.downloads;
 if(!d){msg('download non disponibile in questa vista',true);return;}
 try{await d.save({filename:nome,data:testo});msg('salvato: '+nome);return;}
 catch(e){
  const c=e&&e.code;
  if(c==='extension_not_enabled'&&ripiego){
   try{await d.save({filename:ripiego,data:testo});msg('salvato: '+ripiego);return;}
   catch(e2){msg('non riuscito: '+(e2&&e2.message||'errore'),true);return;}}
  if(c==='declined'){msg('download annullato');return;}
  if(c==='too_large'){msg('file troppo grande: filtra prima di scaricare',true);return;}
  if(c==='rate_limited'){msg('attendi qualche secondo e riprova',true);return;}
  msg('non riuscito: '+(e&&e.message||'errore'),true);}}
document.addEventListener('click',function(e){
 const b=e.target.closest('[data-dl]');if(!b)return;
 const d=datiVisibili();
 if(!d.length){msg('nessun elemento da scaricare con i filtri attuali',true);return;}
 const base='ingly-'+NOMEFILE+'-'+OGGI;
 if(b.dataset.dl==='json')offri(base+'.json',JSON.stringify(d,null,2));
 if(b.dataset.dl==='csv')offri(base+'.csv','﻿'+csvDa(d),base+'.txt');
 if(b.dataset.dl==='md')offri(base+'.md',MD(d));});
if(!(window.claude&&window.claude.downloads)){
 document.querySelectorAll('.dl').forEach(function(e){e.style.display='none'});}
"""

JS = """
const q=document.getElementById('q'),fc=document.getElementById('fcat'),
fp=document.getElementById('fprio'),ft=document.getElementById('ftag'),n=document.getElementById('n');
function apply(){const t=(q.value||'').toLowerCase(),c=fc.value,pr=fp.value,tg=ft.value;let v=0;
document.querySelectorAll('.p').forEach(function(el){
 const hay=el.dataset.s,ok=(!t||hay.indexOf(t)>-1)&&(!c||el.dataset.cat===c)
  &&(!pr||el.dataset.prio===pr)&&(!tg||el.dataset.tag.indexOf(tg)>-1);
 el.style.display=ok?'':'none';if(ok)v++;});
document.querySelectorAll('section.cat').forEach(function(s){
 s.style.display=s.querySelectorAll('.p:not([style*="none"])').length?'':'none';});
n.textContent=v+' prodotti';}
[q,fc,fp,ft].forEach(function(e){e.addEventListener('input',apply)});
"""


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def scrivi_html(records, path):
    cats = CATEGORIES["categorie"]
    per_cat = {}
    for r in records:
        per_cat.setdefault(r["categoria_id"], []).append(r)

    tot = len(records)
    tot_cat = len(per_cat)
    prio_ap = sum(1 for r in records if r["priorita"] in ("A+", "A"))
    med_score = sum(r["market_score"] for r in records) / tot
    med_marg = sum(r["margine_pct_standard"] for r in records) / tot
    alerts = [r for r in records if r.get("alert_competitivita")]
    tutti_tag = sorted({t.strip() for r in records for t in r["tag"].split(",") if t.strip()})

    h = []
    a = h.append
    a('<title>Ingly Design — Catalogo Prodotti</title>')
    a(f"<style>{CSS}</style>")
    a('<header class="top"><div class="wrap" style="padding-top:26px">')
    a('<div class="marchio">Ingly Design · Catalogo prodotti</div>')
    a('<h1>Catalogo<br><em>commerciale</em></h1>')
    a('<p class="sub">Costi, prezzi, margini e punteggi non sono scritti a mano: '
      'sono calcolati dal modello di costo. Cambia una tariffa e tutto il catalogo si ricalcola.</p>')
    a('</div><dl class="kpis" style="max-width:1180px;margin:0 auto;padding:0 24px">')
    a(f'<div><dt>Prodotti</dt><dd>{tot}</dd></div>')
    a(f'<div><dt>Categorie</dt><dd>{tot_cat}</dd></div>')
    a(f'<div><dt>Priorità A / A+</dt><dd>{prio_ap}</dd></div>')
    a(f'<div><dt>Score medio</dt><dd>{med_score:.1f}</dd></div>')
    a(f'<div><dt>Margine medio</dt><dd>{med_marg:.0f}%</dd></div>')
    a(f'<div><dt>Alert</dt><dd>{len(alerts)}</dd></div>')
    a('</dl></header>')

    a('<nav class="tools"><div class="tools-in">')
    a('<input type="search" id="q" placeholder="cerca nome, tipo, SKU, materiale, parola chiave…" aria-label="Cerca">')
    a('<select id="fcat" aria-label="Categoria"><option value="">tutte le categorie</option>')
    for cid in per_cat:
        a(f'<option value="{cid}">{esc(cats[cid]["nome"])}</option>')
    a('</select><select id="fprio" aria-label="Priorità"><option value="">tutte le priorità</option>')
    for p in ["A+", "A", "B", "C", "D"]:
        a(f'<option value="{p}">priorità {p}</option>')
    a('</select><select id="ftag" aria-label="Tag"><option value="">tutti i tag</option>')
    for t in tutti_tag:
        a(f'<option value="{esc(t)}">{esc(t)}</option>')
    a(f'</select><span class="count" id="n">{tot} prodotti</span>')
    a('<span class="dl">'
      '<button class="dl-b" data-dl="md" type="button">scarica pagina</button>'
      '<button class="dl-b" data-dl="csv" type="button">csv</button>'
      '<button class="dl-b" data-dl="json" type="button">json</button>'
      '</span><span class="count" id="dlmsg" role="status" aria-live="polite"></span>')
    a('</div></nav><div class="wrap">')

    for cid, rs in per_cat.items():
        cat = cats[cid]
        rs = sorted(rs, key=lambda r: -r["market_score"])
        a(f'<section class="cat" id="{cid}">')
        a(f'<h2>{esc(cat["nome"])}</h2>')
        a(f'<p class="cat-an">{esc(cat["analisi"])}</p>')
        if cat.get("avviso_ip"):
            a(f'<div class="gaps" style="border-left-color:var(--crit)"><b>Avviso proprietà intellettuale</b>'
              f'<ol style="list-style:none;padding-left:0"><li>{esc(cat["avviso_ip"])}</li></ol></div>')
        a('<div class="gaps"><b>Market gap — opportunità individuate</b><ol>')
        for g in cat["gaps"]:
            a(f'<li>{esc(g)}</li>')
        a('</ol></div>')

        a('<details class="refs"><summary>Riferimenti di mercato analizzati '
          f'({len(cat["top_market"])}) — non sono modelli da copiare</summary><div class="tw"><table>')
        a('<thead><tr><th>Prodotto di riferimento</th><th>Prezzo osservato</th><th>Tecnologia</th>'
          '<th>Perché vende</th><th>Concorrenza</th><th>Dove possiamo fare meglio</th><th>Link</th></tr></thead><tbody>')
        for t in cat["top_market"]:
            a(f'<tr><td><b style="color:var(--ink)">{esc(t["nome"])}</b><br>'
              f'<span style="font-size:11px;color:var(--soft)">{esc(t["tipo"])}</span></td>'
              f'<td>{esc(t["prezzo_range"])}</td><td>{esc(t["tech"])}</td>'
              f'<td>{esc(t["perche_vende"])}</td><td>{esc(t["concorrenza"])}</td>'
              f'<td>{esc(t["miglioramento"])}</td>'
              f'<td><a href="{esc(t["ref"])}" target="_blank" rel="noopener">apri</a></td></tr>')
        a('</tbody></table></div></details>')

        for r in rs:
            cls = {"A+": "b-ap", "A": "b-a", "B": "b-b", "C": "b-c", "D": "b-d"}[r["priorita"]]
            hay = " ".join([r["sku"], r["nome"], r["tipo"], r["materiali"], r["keywords"],
                            r["tag"], r["concept"]]).lower()
            a(f'<article class="p" data-dlid="{r["sku"]}" data-cat="{cid}" '
              f'data-prio="{r["priorita"]}" data-tag="{esc(r["tag"])}" data-s="{esc(hay)}">')
            a('<div class="ph">')
            a(f'<span class="sku">{r["sku"]}</span><h3>{esc(r["nome"])}</h3>')
            a(f'<span class="t">{esc(r["tipo"])}</span><span class="sp"></span>')
            a(f'<span class="badge b-pl">{r["piattaforma"]}</span>')
            a(f'<span class="sc">{r["market_score"]}</span>')
            a(f'<span class="badge {cls}">priorità {r["priorita"]}</span></div>')
            a('<div class="pb"><div class="pd">')
            a(f'<p><b>{esc(r["titolo_it"])}</b></p>')
            a(f'<p>{esc(r["concept"])}</p>')
            a(f'<p><b>Perché piace.</b> {esc(r["usp"])}</p>')
            a(f'<p><b>Perché non è una copia.</b> {esc(r["differenziazione"])}</p>')
            a(f'<p><b>Per chi è.</b> {esc(r["target"])} {esc(r["desiderio"])}</p>')
            if r["link_riferimento"]:
                a(f'<p style="font-family:var(--mono);font-size:11px">Riferimento di mercato: '
                  f'<a href="{esc(r["link_riferimento"])}" target="_blank" rel="noopener">{esc(r["link_riferimento"])}</a></p>')
            a('</div><dl class="sp">')
            campi = [
                ("Materiali", r["materiali"]), ("Dimensioni", r["dimensioni_mm"]),
                ("Tecnologia", r["tecnologia"]), ("Piattaforma", r["piattaforma_nome"]),
                ("Componenti", r["componenti"]), ("Packaging", r["packaging"]),
                ("Tempo tot.", f'{r["t_totale_min"]} min'),
                ("Costo", f'{r["costo_totale"]:.2f} €'),
                ("Entry", f'{r["prezzo_entry"]:.2f} €'),
                ("Standard", f'<span class="prz">{r["prezzo_standard"]:.2f} €</span>'),
                ("Premium", f'{r["prezzo_premium"]:.2f} €'),
                ("B2B 50pz", f'{r["prezzo_b2b_50"]:.2f} €'),
                ("Margine", f'{r["margine_standard"]:.2f} € · {r["margine_pct_standard"]:.0f}%'),
                ("Posizion.", r.get("posizionamento", "—")),
                ("Person.", r["personalizzazione"]),
                ("Tag", r["tag"]),
                ("Upsell", r["upsell"]),
                ("Bundle", r["bundle"]),
                ("SEO", r["seo_title"]),
                ("Keywords", r["keywords"]),
            ]
            for k, v in campi:
                a(f'<div><dt>{k}</dt><dd>{v if k in ("Standard",) else esc(v)}</dd></div>')
            a('</dl></div>')
            if r.get("alert_competitivita"):
                a(f'<div class="alert">{esc(r["alert_competitivita"])}</div>')
            a(f'<div class="pr"><b>Prompt di produzione — come si realizza</b><pre>{esc(r["prompt_produzione"])}</pre></div>')
            a(f'<div class="pr"><b>Prompt immagine — foto di catalogo</b><pre>{esc(r["prompt_immagine"])}</pre></div>')
            a('</article>')
        a('</section>')

    a('</div><footer><div class="wrap">')
    a('<div class="marchio">Ingly Design</div>')
    a('<p style="margin-top:12px">I prezzi sono <b>calcolati</b> dal modello di costo in '
      '<code>data/reference.json</code> e ancorati alle fasce di mercato rilevate, non stimati a mano. '
      'Restano da validare sui costi reali di produzione prima di andare a mercato: la regola di sanità '
      'è 3× il costo diretto in B2C e 1,65× in B2B. I riferimenti di mercato servono a capire cosa vende, '
      'mai come modelli da replicare.</p>')
    a('</div></footer>')
    a('<script type="application/json" id="dati">'
      + json.dumps(records, ensure_ascii=False).replace("</", "<\\/") + "</script>")
    a('<script>const DATI=JSON.parse(document.getElementById("dati").textContent);'
      'const NOMEFILE="catalogo";const IDKEY="sku";'
      'const MD=function(rs){return "# Ingly Design - Catalogo prodotti\\n\\n"'
      '+rs.length+" prodotti\\n\\n"+rs.map(function(r){return '
      '"## "+r.titolo_it+"\\n\\n"'
      '+"**SKU** "+r.sku+" - "+r.categoria+" - priorita "+r.priorita+" (score "+r.market_score+")\\n\\n"'
      '+r.descrizione_lunga_it+"\\n\\n"'
      '+"**Materiali** "+r.materiali+"  \\n**Dimensioni** "+r.dimensioni_mm'
      '+"  \\n**Tecnologia** "+r.tecnologia+"  \\n**Piattaforma** "+r.piattaforma_nome'
      '+"  \\n**Componenti** "+r.componenti+"  \\n**Packaging** "+r.packaging'
      '+"  \\n**Tempo** "+r.t_totale_min+" min  \\n**Costo** "+r.costo_totale+" EUR"'
      '+"  \\n**Prezzi** entry "+r.prezzo_entry+" / standard "+r.prezzo_standard'
      '+" / premium "+r.prezzo_premium+" / b2b50 "+r.prezzo_b2b_50'
      '+"  \\n**Margine** "+r.margine_standard+" EUR ("+r.margine_pct_standard+"%)"'
      '+"  \\n**Posizionamento** "+r.posizionamento'
      '+"  \\n**Personalizzazione** "+r.personalizzazione+"  \\n**Tag** "+r.tag'
      '+"  \\n**Upsell** "+r.upsell+"  \\n**Bundle** "+r.bundle'
      '+"  \\n**Riferimento** "+r.link_riferimento'
      '+"  \\n**SEO** "+r.seo_title+"  \\n**Keywords** "+r.keywords'
      '+(r.alert_competitivita?"\\n\\n> ALERT: "+r.alert_competitivita:"")'
      '+"\\n\\n### Prompt di produzione\\n\\n"+r.prompt_produzione'
      '+"\\n\\n### Prompt immagine\\n\\n"+r.prompt_immagine+"\\n"'
      '}).join("\\n---\\n\\n")};</script>')
    a(f"<script>{DL_JS}</script>")
    a(f"<script>{JS}</script>")

    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(h))


def main():
    OUT.mkdir(exist_ok=True)
    records = []
    errori = []
    for p in PRODUCTS["prodotti"]:
        try:
            records.append(elabora(p))
        except Exception as exc:                    # noqa: BLE001
            errori.append(f"{p.get('id', '???')}: {exc}")

    if errori:
        print("ERRORI:")
        for e in errori:
            print("  -", e)

    if not records:
        sys.exit("Nessun prodotto elaborato.")

    records.sort(key=lambda r: (-r["market_score"], r["sku"]))

    scrivi_csv(records, OUT / "catalogo.csv")
    with open(OUT / "catalogo.json", "w", encoding="utf-8") as fh:
        json.dump({"prodotti": records, "categorie": CATEGORIES["categorie"]},
                  fh, ensure_ascii=False, indent=2)
    scrivi_shopify(records, OUT / "shopify_import.csv")
    scrivi_woocommerce(records, OUT / "woocommerce_import.csv")
    scrivi_xlsx(records, OUT / "catalogo.xlsx")
    scrivi_html(records, OUT / "index.html")

    # riepilogo
    print(f"\n{len(records)} prodotti elaborati\n")
    per_cat = {}
    for r in records:
        per_cat.setdefault(r["categoria"], []).append(r)
    print(f"{'Categoria':<34}{'N':>4}{'Score medio':>13}{'Costo medio':>13}{'Prezzo medio':>14}{'Marg.%':>8}")
    print("-" * 86)
    for cat, rs in sorted(per_cat.items()):
        n = len(rs)
        sc = sum(r["market_score"] for r in rs) / n
        co = sum(r["costo_totale"] for r in rs) / n
        pr = sum(r["prezzo_standard"] for r in rs) / n
        mg = sum(r["margine_pct_standard"] for r in rs) / n
        print(f"{cat:<34}{n:>4}{sc:>13.1f}{co:>12.2f}€{pr:>13.2f}€{mg:>7.1f}%")
    print("-" * 86)
    prio = {}
    for r in records:
        prio[r["priorita"]] = prio.get(r["priorita"], 0) + 1
    print("Priorità:", "  ".join(f"{k}={prio.get(k, 0)}" for k in ["A+", "A", "B", "C", "D"]))
    print(f"\nOutput in {OUT}/")


if __name__ == "__main__":
    main()
