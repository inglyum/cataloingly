# Ingly Design — Catalogo prodotti

Due cataloghi per prodotti in taglio laser CO₂, stampa UV e marcatura fiber MOPA.

**1. Il catalogo Ingly Design** (`out/index.html`) — i prodotti originali, con costi,
prezzi, margini e priorità di lancio **calcolati** da un modello di costo parametrico,
non scritti a mano. Ogni prodotto ha titolo, descrizione pubblicabile, prompt di
produzione e prompt per la foto di catalogo.

**2. L'enciclopedia** (`out/enciclopedia.html`) — la mappa di cosa già vende nel mondo,
perché vende, quanto costa e **dove trovarne i file**, con la licenza come primo criterio.
Ogni voce porta un prompt di design per costruirne una versione originale, non per copiarla.

Entrambe le pagine si possono **scaricare** dai pulsanti in alto: la pagina intera in
Markdown, oppure i soli dati **attualmente filtrati** in CSV o JSON. Se cerchi "orologio"
e scarichi, ottieni quei prodotti, non tutti.

---

## Stato

| | |
| --- | --- |
| Prodotti Ingly completi | **288** |
| Categorie prodotto complete | **10 su 10** |
| Voci di enciclopedia | **63** su tutte e 10 le categorie |
| Fonti di file catalogate | **24** (6 gratuite, 7 a pagamento, 11 fra rassegne e documentazione) |
| Strumenti di lavoro | **34** divisi per fase, con costo reale |
| Piattaforme costruttive | 8 |
| Analisi di mercato | **10 categorie su 10** — completa |
| Motore di calcolo | completo e collaudato |

Il catalogo copre tutte e dieci le categorie. Due hanno meno di 30 prodotti per scelta:
**07 Edizioni limitate** (16) è un meccanismo di prezzo più che una famiglia di prodotti, e
**08 Anime** (20) è limitata da ciò che si può fare senza violare proprietà intellettuale altrui.

---

## Come si usa

```bash
python3 scripts/validate.py           # controllo qualità: blocca gli errori di producibilità
python3 scripts/build.py              # catalogo Ingly: calcola tutto e genera gli output
python3 scripts/build_enciclopedia.py # enciclopedia prodotti e fonti
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
| `enciclopedia.html` | Enciclopedia navigabile dei prodotti e delle fonti |
| `enciclopedia.csv` / `.json` | Le 63 voci con i prompt di design |
| `fonti.csv` | Le 24 fonti di file con licenze e costi |
| `strumenti.csv` | I 34 strumenti con costo, fase e consiglio d'uso |

---

## La finitura: il 70% della percezione di qualità

Un oggetto laser sembra grezzo per tre motivi, sempre gli stessi: **il bordo bruciato
lasciato sporco di fuliggine**, **la superficie non carteggiata** che assorbe la luce a
chiazze, e **l'assenza di un livello di lucentezza controllato**. Nessuno dei tre riguarda
il disegno: riguardano tutti la lavorazione *dopo* il taglio.

`data/finiture.json` definisce il sistema: una palette di **12 vernici acriliche all'acqua**
atossiche con codice, tono e note d'uso; un **protocollo in 10 passi** dalla carteggiatura
progressiva alle due mani incrociate; **tre trattamenti del bordo** (ambra a vista — la firma
Ingly — sigillato, verniciato a filo); e tre **livelli di lucentezza**, con un limite: mai
sopra 40 gloss su legno, perché da lì in su l'occhio legge plastica.

### Tre livelli, perché il premium integrale non regge su tutto

| Livello | Cosa | Quando |
| --- | --- | --- |
| **NATURALE** | Carteggiatura, pulizia bordo, sigillante trasparente. Il colore lo fa la UV. | Lotti e prezzi d'impulso: bomboniere, segnaposto, tessere |
| **PREMIUM** | Ciclo completo con due mani incrociate di acrilico all'acqua | Prezzo atteso sopra i 22 € |
| **LUXURY** | Premium + terza mano, cera dura lucidata a mano, controllo pezzo per pezzo | Edizioni limitate e pezzi sopra i 70 € |

La ragione è aritmetica, non estetica: su una bomboniera da 2,50 € quindici minuti di
lavorazione a mano costano più del prezzo di vendita.

**La finitura è nel modello di costo.** Vale in media 15 minuti e 4,49 € a pezzo, e sui
pannelli grandi arriva al 40% del costo totale. Specificare una finitura premium senza
contarla significa vendere in perdita esattamente sui prodotti che si vogliono posizionare
in alto.

---

## Il brief fotografico

Il campo `prompt_immagine` non è più una frase scritta a mano: è un **brief costruito dal
motore**, in inglese, che combina la scena del prodotto con ottica, luce, superficie,
palette e un negative prompt. Un prompt che descrive solo il soggetto produce immagini
piatte — l'aspetto premium sta nella superficie, nella luce e nell'ottica, e vanno dette.

Ogni brief specifica: inquadratura e ottica (85 mm f/4 hero, 100 mm macro, flat-lay f/8),
schema luci (radente per far leggere le incisioni, notturna per i prodotti illuminati),
grana e sigillatura della superficie, livello di gloss in unità, trattamento del bordo,
colori con codice esadecimale, set e styling, più l'elenco di ciò che l'immagine non deve
avere.

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
  enciclopedia.json   63 voci dei prodotti più venduti al mondo, ciascuna
                      con il prompt di design per una versione originale
  fonti.json          24 fonti di file laser, ordinate per licenza
  finiture.json       palette vernici all'acqua, protocollo in 10 passi,
                      trattamenti del bordo, livelli di finitura, regole fotografiche
  strumenti.json      34 strumenti per disegnare, ottimizzare, produrre,
                      fotografare e vendere, divisi per fase di lavoro
  products/           un file per categoria, 288 prodotti in totale
    01_home.json      30    06_stagionale.json  34
    02_eventi.json    30    07_limitate.json    16
    03_animali.json   30    08_anime.json       20
    04_b2b.json       38    09_turismo.json     30
    05_bambini.json   30    10_sicilia.json     30
scripts/
  build.py            motore di calcolo e catalogo Ingly
  build_enciclopedia.py  enciclopedia prodotti e fonti
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
- **upsell che puntano a SKU inesistenti** (ne ha trovati 28 reali)
- fasce di mercato incoerenti, campi obbligatori mancanti, prompt non eseguibili

Esce con codice 1 se trova errori bloccanti: si può mettere in una CI.

---

## Le fonti di file: la licenza prima di tutto

`data/fonti.json` cataloga 24 fonti di file laser, gratuite e a pagamento. Il criterio
di ordinamento non è la qualità ma **la licenza**, perché è lì che si fanno i danni.

**Fatto verificato:** la maggior parte dei file laser preconfezionati è concessa **solo
per uso personale**. Puoi realizzare l'oggetto per te, ma **non puoi vendere** il prodotto
che ne ricavi. Le licenze commerciali esistono, sono quasi sempre a pagamento e spesso
hanno limiti — una fonte censita consente la vendita fino a 250 pezzi assemblati, e oltre
serve una licenza estesa.

**La regola Ingly Design:** questi file servono a **studio tecnico** (come è risolto un
incastro, una tolleranza, un meccanismo) e a **ricerca di mercato**. Non servono a produrre
merce da vendere, nemmeno quando la licenza lo consentirebbe. Il motivo non è legale ma
commerciale: un file acquistato da migliaia di persone produce un oggetto identico a quello
di migliaia di concorrenti, e il prezzo è già crollato prima che tu lo produca.

Le due eccezioni utili sono **i font** e **i pattern per la stampa UV**: si comprano con
licenza commerciale senza intaccare l'identità, perché la firma di Ingly Design sta nella
geometria costruttiva, non nel riempimento.

C'è anche un'opportunità rovesciata: Ingly Design può **vendere** i propri file. Il disegno
è già fatto e pagato dal catalogo fisico, il costo marginale è zero e non c'è logistica —
ma solo sui prodotti che non vogliamo tenere esclusivi.

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

1. **Tarare le tariffe** in `reference.json` sui costi reali di produzione
2. Verificare le tolleranze con una tavola di test sulla macchina reale —
   soprattutto l'asola della piattaforma P2, che si porta dietro otto prodotti
3. Generare le immagini di catalogo con i prompt già presenti in ogni scheda
4. Prototipare nell'ordine: prima le piattaforme, poi i prodotti
