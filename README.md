# Ingly Design — Catalogo prodotti

Catalogo commerciale per prodotti in taglio laser CO₂, stampa UV e marcatura fiber MOPA.

Non è un documento: è un **database**. Costi, prezzi, margini, punteggi di mercato e
priorità di lancio non sono scritti a mano — sono **calcolati** da un modello di costo
parametrico. Cambi una tariffa e tutto il catalogo si ricalcola in modo coerente.

---

## Stato

| | |
| --- | --- |
| Prodotti completi | **68** su 300 previsti |
| Categorie complete | **2** su 10 (01 Casa & Arredamento, 04 Aziendale & B2B) |
| Piattaforme costruttive | 8 |
| Analisi di mercato | **10 categorie su 10** — completa |
| Motore di calcolo | completo e collaudato |

Le otto categorie mancanti (02 Eventi, 03 Animali, 05 Bambini, 06 Stagionale,
07 Edizioni limitate, 08 Anime, 09 Turismo, 10 Sicilia) hanno **analisi di mercato,
riferimenti e market gap già completi** in `data/categories.json`: manca solo la
scrittura dei prodotti, che segue esattamente lo stesso schema dei 68 esistenti.

---

## Come si usa

```bash
python3 scripts/validate.py     # controllo qualità: blocca gli errori di producibilità
python3 scripts/build.py        # calcola tutto e genera gli output
```

`build.py` produce in `out/`:

| File | A cosa serve |
| --- | --- |
| `index.html` | Catalogo navigabile con ricerca e filtri |
| `catalogo.csv` | Tutti i campi, per Excel e per l'ERP |
| `catalogo.json` | Stesso contenuto, per API e integrazioni |
| `shopify_import.csv` | Import diretto in Shopify (prodotti in bozza) |
| `woocommerce_import.csv` | Import diretto in WooCommerce |
| `catalogo.xlsx` | Foglio di lavoro (richiede `pip install openpyxl`) |

---

## Il modello di costo

Il costo di ogni prodotto è ricostruito dai suoi ingredienti fisici, non stimato:

```
costo = materiale (area × €/m² × sfrido)
      + tempo CO₂  (taglio + incisione vettoriale + raster)
      + tempo UV   (area / velocità) + inchiostro (colore + bianco + gloss)
      + tempo MOPA
      + manodopera di assemblaggio
      + componenti acquistati
      + packaging
```

Tutte le tariffe stanno in `data/reference.json` e sono **parametri da tarare**, non
verità. Sono ipotesi documentate: vanno sostituite con i costi reali Ingly Design prima
di andare a mercato.

### Il prezzo non è il costo per un moltiplicatore

Il costo-più-margine dà il **pavimento**, non il prezzo. Da solo sottoprezza
sistematicamente i prodotti economici che il mercato valuta molto più del loro costo
industriale: un set di sottobicchieri costa 4 € e si vende a 30.

Dove è nota la fascia di mercato osservata (campo `mkt`), il prezzo viene **ancorato al
mercato** tenendo il costo-più-margine come soglia minima invalicabile. Se il pavimento
di costo supera il tetto di mercato, il prodotto viene marcato `NON COMPETITIVO` invece
di essere venduto in perdita.

### Il punteggio non si può barare

Il market score su 100 combina sette voci. Cinque sono valutate per prodotto
(domanda, concorrenza, personalizzazione, regalabilità, unicità). Due — **margine** e
**semplicità di produzione** — sono calcolate dal modello di costo e non sono modificabili
a mano.

Il punteggio di margine misura il **margine lordo assoluto in euro**, non il
moltiplicatore: siccome il prezzo deriva dal costo, il moltiplicatore sarebbe identico
per tutti e non misurerebbe niente. I prodotti a basso margine unitario ma altissimo
volume recuperano sul punteggio di domanda, dove è giusto che stiano.

---

## Le otto piattaforme costruttive

I prodotti non sono progetti separati: sono **otto geometrie di incastro**, collaudate
una volta ciascuna, su cui si montano pannelli diversi. Chi progetta un prodotto alla
volta rifà le tolleranze ogni volta e sbaglia ogni volta.

| | Piattaforma | Usi |
| --- | --- | --- |
| **P1** | Piastra piana | Sottobicchieri, magneti, targhe, addobbi, bomboniere |
| **P2** | Piastra + base ad asola | Numeri tavolo, porta QR, calendari, targhe cameretta |
| **P3** | Scatola a incastro 45° | Portatovaglioli, organizer, lanterne, scatole |
| **P4** | Leggio inclinato 15° | Porta menu, porta conto, espositori, leggii |
| **P5** | Multilayer a telaio | Orologi, quadri, metri crescita, insegne |
| **P6** | Piastra + metallo MOPA | Targhe premium, premi, medagliette, memorial |
| **P7** | Puzzle e tessere | Puzzle nome, alfabeti, memory, tabelle routine |
| **P8** | Pannello UV | Coaster grafici, magneti fotografici, ritratti |

**Regola non negoziabile:** la geometria di interfaccia — asole, sedi, perni, fori —
resta identica dentro ogni piattaforma. Se un pannello ha incastri suoi, il sistema è
finito e si torna a progettare un pezzo alla volta.

---

## Il sistema di design: Griglia Mediterranea

Tre elementi generativi da cui deriva tutto il catalogo:

- **Modulo M** — 12 mm. Ogni misura è un multiplo di 12: nesting prevedibile, pezzi intercambiabili.
- **Arco A** — raggio unico R12. Finestre, angoli, volute, pattern.
- **Taglio T** — smusso costante a 45°. Angoli e incastri.

Tre firme riconoscibili a tre metri:

- **La finestra** — apertura ad arco ribassato che mostra uno strato colorato dietro.
- **Il filo** — linea incisa a 4 mm dal bordo, interrotta dove sta il nome.
- **Il bordo** — il bordo ambrato bruciato dal laser tenuto a vista, non carteggiato via.

---

## Struttura

```
data/
  reference.json      materiali, componenti, tariffe macchina, packaging,
                      piattaforme con processo produttivo in 10 passi,
                      moltiplicatori di listino, pesi dello score
  categories.json     analisi di mercato delle 10 categorie, riferimenti
                      con link reali, market gap (10 per categoria)
  products/
    01_home.json      30 prodotti
    04_b2b.json       38 prodotti
scripts/
  build.py            motore di calcolo e generazione output
  validate.py         controllo qualità pre-produzione
out/                  generato — non versionare a mano
```

---

## Controllo qualità

`validate.py` blocca gli errori che costano di più se scoperti in produzione:

- materiali e componenti che non esistono a magazzino
- prodotti che **non entrano nel packaging** assegnato
- orologi senza sfere in distinta base o con alberino non verificato
- prodotti per bambini senza vernici atossiche, spigoli raggiati o magneti annegati
- **riferimenti a proprietà intellettuale protetta** (blocca il prodotto)
- fasce di mercato incoerenti, campi obbligatori mancanti, prompt non eseguibili

Esce con codice 1 se trova errori bloccanti: si può mettere in una CI.

---

## Proprietà intellettuale

I pattern del catalogo sono **regole generative** — griglia, arco a raggio costante,
taglio a 45° — non motivi ricalcati: sono originali e difendibili.

La categoria **08 Anime & Supereroi** ha un problema strutturale documentato in
`categories.json`: i best seller di quel segmento sono in larga parte fan art non
licenziata. Non sono replicabili. La strada percorribile è costruire archetipi originali
— kawaii, cyberpunk, mecha, dark fantasy sono generi estetici, non proprietà di nessuno.
Il rispetto dell'IP diventa un vantaggio competitivo verso negozi e rivenditori, che
non possono acquistare merce contraffatta.

---

## Cosa resta da fare

1. Scrivere i prodotti delle 8 categorie mancanti (analisi e gap già pronti)
2. **Tarare le tariffe** in `reference.json` sui costi reali di produzione
3. Verificare le tolleranze con una tavola di test sulla macchina reale —
   soprattutto l'asola della piattaforma P2, che si porta dietro otto prodotti
4. Generare le immagini di catalogo con i prompt già presenti in ogni scheda
5. Prototipare nell'ordine: prima le piattaforme, poi i prodotti
