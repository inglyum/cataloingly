#!/usr/bin/env python3
"""
INGLY DESIGN — Controllo qualita' del catalogo
==============================================

Applica la checklist QC a ogni prodotto PRIMA che entri in catalogo. Serve a
impedire che un errore banale — uno spessore che non esiste, un dettaglio sotto
il minimo del laser, un pacco che non entra nella scatola — arrivi in produzione.

    python3 scripts/validate.py

Esce con codice 1 se trova errori bloccanti, cosi' puo' stare in una CI.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

REF = json.load(open(DATA / "reference.json", encoding="utf-8"))
CATS = json.load(open(DATA / "categories.json", encoding="utf-8"))["categorie"]

MAT = REF["materiali"]
COMP = REF["componenti"]
PACK = REF["packaging"]
PLAT = REF["piattaforme"]

# Minimi producibili, da references/produzione.md
PONTICELLO_MIN_MM = 2.5
TESTO_INCISO_MIN_MM = 4
TESTO_TRAFORO_MIN_MM = 12

TAG_VALIDI = {
    "FAST SELLER", "PREMIUM", "BUNDLE", "B2B", "PERSONALIZZABILE",
    "SEASONAL", "LIMITED EDITION", "TOURISM", "SOUVENIR",
}


def carica_prodotti():
    prodotti = []
    for path in sorted((DATA / "products").glob("*.json")):
        blocco = json.load(open(path, encoding="utf-8"))
        for p in blocco.get("prodotti", []):
            p["_file"] = path.name
            prodotti.append(p)
    return prodotti


def controlla(p):
    """Ritorna (errori_bloccanti, avvisi)."""
    err, warn = [], []

    # --- identita' e campi obbligatori -----------------------------------
    for campo in ("id", "cat", "name", "tipo", "concept", "target", "desire",
                  "usp", "diff", "platform", "mat", "tech", "dim",
                  "prompt_prod", "prompt_img", "ref", "kw"):
        if not p.get(campo):
            err.append(f"campo obbligatorio mancante: {campo}")

    if p.get("cat") not in CATS:
        err.append(f"categoria sconosciuta: {p.get('cat')}")

    if not str(p.get("id", "")).startswith("ING-"):
        err.append("lo SKU deve iniziare con ING-")

    # --- materiali e tecnologia ------------------------------------------
    for m in p.get("mat", []):
        if m not in MAT:
            err.append(f"materiale inesistente a magazzino: {m}")

    if p.get("tech", "").find("UV") > -1 and not p.get("uv_cm2"):
        warn.append("tecnologia dichiara UV ma uv_cm2 e' zero")
    if p.get("tech", "").find("MOPA") > -1 and not p.get("mopa_cm2"):
        warn.append("tecnologia dichiara MOPA ma mopa_cm2 e' zero")
    if p.get("uv_cm2") and "UV" not in p.get("tech", ""):
        warn.append("ha area UV ma la tecnologia non dichiara UV")

    # acrilico e ambienti umidi
    if any(m.startswith("acrilico") for m in p.get("mat", [])):
        pass
    elif "estern" in p.get("concept", "").lower() or "dehors" in p.get("concept", "").lower():
        warn.append("prodotto da esterno progettato in legno: valutare acrilico")

    # --- geometria e producibilita' --------------------------------------
    dim = p.get("dim", [])
    if len(dim) < 2:
        err.append("dimensioni incomplete")
    else:
        for d in dim[:2]:
            if d <= 0:
                err.append("dimensione nulla o negativa")
        # modulo 12 mm del sistema Griglia Mediterranea
        fuori = [d for d in dim[:2] if d % 12 != 0]
        if fuori:
            warn.append(f"dimensioni fuori dal modulo 12 mm: {fuori}")

    if p.get("platform") not in PLAT:
        err.append(f"piattaforma sconosciuta: {p.get('platform')}")

    # --- packaging --------------------------------------------------------
    pk = p.get("pack", "busta")
    if pk not in PACK:
        err.append(f"formato packaging inesistente: {pk}")
    elif len(dim) >= 2:
        maxd = PACK[pk]["max_mm"]
        if maxd[0]:
            # il pezzo si puo' ruotare dentro la scatola: confronto lato lungo con lato lungo
            pezzo = sorted(dim[:2], reverse=True)
            scatola = sorted(maxd[:2], reverse=True)
            if pezzo[0] > scatola[0] or pezzo[1] > scatola[1]:
                err.append(
                    f"il prodotto ({dim[0]}x{dim[1]}) non entra nel packaging "
                    f"'{PACK[pk]['nome']}' ({maxd[0]}x{maxd[1]}), nemmeno ruotato"
                )

    # --- componenti -------------------------------------------------------
    for c in p.get("comp", {}):
        if c not in COMP:
            err.append(f"componente inesistente: {c}")

    # orologi: controlli specifici
    if "movimento_std" in p.get("comp", {}) or "movimento_coppia" in p.get("comp", {}):
        sp = dim[2] if len(dim) > 2 else 0
        if sp > 15 and "movimento_coppia" not in p.get("comp", {}):
            if "20 mm" not in p.get("prompt_prod", "") and "alberino" not in p.get("prompt_prod", ""):
                warn.append(
                    f"orologio con pacco da {sp} mm: verificare la lunghezza dell'alberino "
                    "(sopra i 15 mm servono 16-20 mm, non 12)"
                )
        if "sfere_std" not in p.get("comp", {}) and "sfere_grandi" not in p.get("comp", {}):
            err.append("orologio senza set sfere in distinta base")

    # --- sicurezza bambini ------------------------------------------------
    if p.get("cat") == "KIDS":
        pp = p.get("prompt_prod", "").lower()
        if "atossic" not in pp and "r12" not in pp and "carteggia" not in pp:
            warn.append(
                "prodotto per bambini senza riferimenti a vernici atossiche, "
                "spigoli raggiati o carteggiatura nel prompt di produzione"
            )
        if "magnet" in pp and "anneg" not in pp and "copert" not in pp:
            err.append("magneti in un prodotto per bambini senza indicazione che siano annegati e coperti")

    # --- proprieta' intellettuale ----------------------------------------
    testo = " ".join(str(p.get(k, "")) for k in
                     ("name", "concept", "usp", "diff", "prompt_prod", "prompt_img", "kw"))

    # Termini inequivocabili: si cercano come PAROLA INTERA, senza distinzione di maiuscole.
    vietati_parola = ["pokemon", "disney", "marvel", "ghibli", "totoro", "naruto",
                      "nintendo", "batman", "spiderman", "pikachu", "minecraft"]
    for v in vietati_parola:
        if re.search(rf"\b{re.escape(v)}\b", testo, re.IGNORECASE):
            err.append(f"RISCHIO COPYRIGHT/TRADEMARK: riferimento a proprieta' protetta '{v}'")

    # Termini ambigui: 'one piece' e 'star wars' sono anche espressioni comuni in inglese
    # ('lifting one piece out'). Qui si cerca solo la forma esatta del marchio, maiuscole comprese.
    vietati_marchio = ["One Piece", "Star Wars", "Harry Potter", "Hello Kitty",
                       "Super Mario", "Le Petit Prince"]
    for v in vietati_marchio:
        if re.search(rf"\b{re.escape(v)}\b", testo):
            err.append(f"RISCHIO COPYRIGHT/TRADEMARK: riferimento a proprieta' protetta '{v}'")

    # --- commerciale ------------------------------------------------------
    for t in p.get("tags", []):
        if t not in TAG_VALIDI:
            warn.append(f"tag non standard: '{t}'")

    if len(p.get("upsell", [])) < 3:
        warn.append("meno di 3 prodotti di upsell indicati")
    if len(p.get("bundle", [])) < 2:
        warn.append("meno di 2 bundle indicati")

    if not str(p.get("ref", "")).startswith("http"):
        warn.append("link di riferimento di mercato mancante o non valido")

    mkt = p.get("mkt")
    if not mkt:
        warn.append("fascia di mercato non rilevata: il prezzo resta a solo costo+margine")
    elif len(mkt) != 2 or mkt[0] >= mkt[1]:
        err.append(f"fascia di mercato incoerente: {mkt}")

    # --- prompt -----------------------------------------------------------
    if len(str(p.get("prompt_prod", ""))) < 80:
        warn.append("prompt di produzione troppo scarno per essere eseguibile")
    if len(str(p.get("prompt_img", ""))) < 80:
        warn.append("prompt immagine troppo scarno")

    return err, warn


def main():
    prodotti = carica_prodotti()
    if not prodotti:
        sys.exit("Nessun prodotto trovato in data/products/")

    tot_err = tot_warn = 0
    con_problemi = 0

    for p in prodotti:
        err, warn = controlla(p)
        if err or warn:
            con_problemi += 1
            print(f"\n{p.get('id', '???')}  ({p.get('_file')})  {p.get('name', '')}")
            for e in err:
                print(f"   ERRORE   {e}")
            for w in warn:
                print(f"   avviso   {w}")
        tot_err += len(err)
        tot_warn += len(warn)

    print("\n" + "=" * 70)
    print(f"{len(prodotti)} prodotti controllati · {con_problemi} con segnalazioni")
    print(f"{tot_err} errori bloccanti · {tot_warn} avvisi")
    print("=" * 70)

    if tot_err:
        print("\nGli errori bloccanti vanno risolti prima della produzione.")
        sys.exit(1)
    print("\nNessun errore bloccante: il catalogo puo' andare in produzione.")


if __name__ == "__main__":
    main()
