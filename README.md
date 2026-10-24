# COT Radar

Dashboard che si aggiorna da sola e mette insieme tre fonti pubbliche e gratuite:

| Fonte | Cosa | Quando esce |
|---|---|---|
| **CFTC** – Commitments of Traders | posizioni dei grandi speculatori (Non-Commercial) su 54 mercati | venerdì 15:30 New York (21:30 in Italia) |
| **FRED** – Fed di St. Louis | tassi, rendimenti reali, VIX, spread, cambi, indici, petrolio, bilancio Fed | ogni giorno / giovedì |
| **BCE** – Data Portal | tassi sui mutui (Italia, Eurozona, DE, FR, ES), Euribor, ESTR, curva dei rendimenti | ogni giorno / ogni mese |

> ⚠️ Strumento di analisi statistica. **Non è una consulenza finanziaria.**

---

## Struttura del progetto

```
cot-radar/
├── main.py                  ← punto di partenza (doppio clic o da terminale)
├── cot_radar/               ← il "motore" in Python, un file per ogni compito
│   ├── config.py            impostazioni: pesi, soglie, strumenti, fonti   ← si modifica qui
│   ├── fonti.py             download CFTC / FRED / BCE + copia locale
│   ├── calcoli.py           matematica: z-score, COT Index, regressione
│   ├── cot.py               punteggio COT di ogni strumento
│   ├── mercato.py           punteggio "Mercato" (già scontato?) + liquidità Fed
│   ├── mutui.py             mutui BCE + stima dei mesi non ancora pubblicati
│   ├── analisi.py           unisce tutto: strumenti, coppie, correlazioni
│   ├── calendario.py        orari di uscita, ritardi, stato delle fonti
│   ├── pagina.py            crea la pagina HTML
│   ├── controlli.py         controlli di qualità dei dati (errori "invisibili")
│   ├── confronto.py         backtest delle letture COT alternative (opzioni, TFF, Disaggregated)
│   ├── demo.py              dati finti per provare senza internet
│   └── log.py               registro: schermo + dati/registro.log + riepilogo
├── web/                     ← la grafica
│   ├── index.html           struttura della pagina
│   ├── stile.css            colori, spazi, versione telefono, tema scuro
│   └── app.js               disegna schede, tabelle e grafici
├── tests/test_calcoli.py    ← test automatici
├── .github/workflows/
│   ├── sito.yml             aggiorna e pubblica il sito in automatico
│   └── test.yml             lancia i test a ogni modifica
├── dati/                    (creata da sola) copia locale dei dati scaricati
├── README.md  LICENSE  .gitignore
```

Il viaggio dei dati: `fonti.py` → `cot.py` + `mercato.py` + `mutui.py` → `analisi.py` → `pagina.py` → `web/` → **dashboard**.

---

## Usarlo sul PC

Serve solo **Python 3.9 o più recente** (python.org, spunta "Add Python to PATH"). Nessuna libreria da installare.

```bash
python main.py              # scarica i dati, crea cot_radar.html e lo apre
python main.py --demo       # dati FINTI, nessun internet: per provare le modifiche
python main.py --debug      # mostra i dettagli di ogni passaggio
python main.py --pianifica  # Windows: si aggiorna da solo ogni venerdì alle 21:45
```

Su Windows puoi anche fare doppio clic su `avvia.pyw` (nessuna finestra nera).

---

## Debug: come trovare un problema

1. **Il programma si ferma con un errore** → l'ultima riga del messaggio dice *cosa*, le righe `File "...", line N` dicono *dove*. Parti dall'ultima che nomina un file di `cot_radar/`.
2. **Una fonte non arriva** → `python main.py --debug`: per ogni serie vedi `FRED DGS2 ... punti, ultimo 2026-10-16` oppure l'errore preciso.
3. **Ho cambiato qualcosa e voglio sapere se ho rotto qualcosa** → `python -m unittest discover -s tests -v`. Poi `python main.py --demo` per vedere la pagina.
4. **La pagina si apre ma qualcosa non si vede** → nel browser **F12 → Console**: gli errori JavaScript sono in rosso con file e riga. Scrivi `D` per vedere tutti i dati, `D.assets.EUR` per uno strumento.
5. **Il sito non si aggiorna** → su GitHub, scheda **Actions** → ultima esecuzione di "Sito" → passaggio rosso.

Esercizio per imparare: in `config.py` cambia `MACRO_WEIGHT = 0.25` in `0.5`, lancia `python main.py --demo` e guarda come cambiano i segnali.

---

## Grafico a candele

Clic su una scheda, una riga delle tabelle o uno strumento: si apre il grafico di **TradingView** (gratuito) con
timeframe **H1 / H4 / D / W**, periodo visibile H1 = 3 mesi, H4 ≈ 10 mesi, D = 1 anno, W = 5 anni (si zooma con la rotellina), strumenti di disegno, **schermo intero** e link a tradingview.com.
Sotto il grafico c'e' il **pannello COT**: per ognuna delle ultime 26 settimane quanto i Non Commercial hanno
comprato (verde) o venduto (rosso), in % dell'open interest; per una coppia e' il flusso della base meno quello
della quotata. La data e' il martedi' di riferimento, pubblicato il venerdi' dopo.
La riga **Ultime 3 settimane** somma i flussi recenti (per lo swing): "concentrati" = 3 settimane su 3 nello
stesso verso, "prevalenti" = 2 su 3; accanto c'e' la posizione netta attuale (net long/short in % OI).
Il pannello si **allarga o schiaccia trascinando la barretta** sopra di esso (doppio clic = misura iniziale).
Gli strumenti usano i **nomi originali in inglese** (come CFTC, CME e TradingView: es. *Class III Milk*, simbolo
`CME:DC1!`), con il nome italiano sotto (`NOMI_EN` in `cot_radar/config.py`).
Se la pagina aperta e' vecchia (cache del browser) compare l'avviso "versione piu' recente" con il pulsante Aggiorna.
I simboli sono in `cot_radar/config.py` → `TV_SYMBOLS` / `TV_PAIRS` (modificabili). Alcuni strumenti sono quotati
"al contrario" (es. segnale su JPY → grafico USDJPY; tassi → grafico del rendimento): il pannello lo segnala.

## Conferme del segnale

Per ogni strumento e coppia (`cot_radar/conferme.py`):
- **Commercials** (hedger) agli estremi del loro COT Index: *conferma* o *contrasto* del segnale.
- **Open interest** a 4 settimane letto con il flusso degli speculatori: nuovi long/short (trend sano) oppure
  chiusura di posizioni (spinta piu' debole).
- **Storico**: % di segnali passati in cui il prezzo, 4 settimane dopo la pubblicazione, e' andato nel verso giusto
  (solo dove c'e' un prezzo storico gratuito; senza costi; i risultati passati non garantiscono quelli futuri).

## Notizie (motore fase 1)

`cot_radar/notizie.py`: calendario ufficiale di CPI e NFP USA (BLS), Fed (FOMC) e BCE (da aggiornare una volta
l'anno). Prima dell'evento la card mostra l'avviso; dopo, la **sorpresa** e' misurata dal mercato (variazione del tasso
a 2 anni nel giorno del dato in deviazioni standard). Correttivo: 10 punti per sigma, tetto +-30 per valuta,
dimezzamento ogni giorno (3 giorni per Fed/BCE). Il segnale COT non cambia: la card mostra il punteggio corretto accanto.
Le card delle coppie hanno 3 righe: **Smart money** (COT), **Macro** (modello di mercato), **Notizie**.

## Stagionalità (mesi, giorni della settimana, prossime 4 settimane)

- **Archivio permanente** (`cot_radar/storico.py`): prezzi giornalieri FRED di decenni (cambi dal 1971/1999,
  petrolio dal 1986, Nasdaq dal 1971...), un CSV per serie nel ramo **`storico`** del repository (sul PC nella
  cartella `storico/`). Il primo giro scarica tutta la storia, poi si aggiungono solo i giorni nuovi già scaricati
  per la dashboard: **nessuna chiamata in più** ai server. Lo storico salvato non viene mai riscritto; valori
  impossibili o salti anomali non confermati non vengono salvati (CRITICAL nel registro admin + mail).
- **Analisi** (`cot_radar/stagionalita.py`): prossime 4 settimane, 12 mesi (con mappa anni × mesi) e
  lunedì-venerdì. Trend tolto e filtri anti-coincidenza (anni d'accordo, test t, stabilità nel tempo e nelle date):
  sul puro rumore passano circa 1-3 casi su 100 (vedi `tests/test_stagionalita.py`).
- **Peso nel punteggio** deciso dal backtest (segnali COT con stagionalità a favore vs contraria, calcolata solo con
  gli anni precedenti). Il punteggio originale resta nell'anello; il "punteggio corretto" è nella riga sotto i riquadri.
- Strumenti senza un prezzo storico gratuito (oro, grano, caffè...) mostrano "n/d".

### Aggiornamento di fine giornata
Ogni sera feriale (22:15 UTC) il sito si aggiorna; se qualcosa non va riprova alle 22:20 e alle 22:25.
La mail all'admin parte **solo se falliscono tutti e 3** i tentativi. Nel frattempo online restano gli ultimi dati validi.
(GitHub può ritardare gli avvii programmati di qualche minuto nelle ore di punta.)

## Backtest storico: registro live e backtest

Un **motore unico** (`cot_radar/motore.py`) decide quando nasce, si conferma e finisce un segnale, e lo misura.
Le stesse regole servono a due finestre separate (scheda "Backtest storico"):

- **Registro live** (`cot_radar/registro.py`): file `storico/segnali/registro.jsonl` nel ramo `storico`.
  - Ogni evento (apertura, conferma, chiusura) ha data e ora vere.
  - Ogni evento contiene l'hash SHA-256 del precedente. Se si modifica un evento vecchio la catena si rompe: il sito lo mostra e il registro smette di scrivere.
  - Si scrive solo dal sito, solo con COT e FRED completi e solo se l'aggiornamento viene pubblicato.
- **Backtest SIMULATO** (`cot_radar/backtest.py`): tutte le settimane dal 1986.
  - L'archivio COT completo `storico/COT.csv` viene scaricato una volta sola e poi solo aggiornato.
  - Calcolo point-in-time: ogni settimana usa solo i dati di allora.
  - Gli ultimi 2 anni restano separati (holdout).
  - Dal risultato si tolgono i costi stimati.
  - La parte macro, le notizie e la stagionalità non sono incluse.

**Come si misura un segnale:**
- **Ingresso:** la prima chiusura giornaliera dopo la generazione. I cambi FRED sono le 12:00 di New York.
- **Orizzonti:** risultato a 1, 2 e 4 settimane e fino al cambio di etichetta, con un massimo di 12 settimane.
- **Guadagno e drawdown massimi:** misurati sulle chiusure.
- **Tre ingressi a confronto:**
  - A: subito;
  - B: ordine limite a 0,5× il movimento settimanale tipico, valido 5 giorni;
  - C: metà e metà.

**Orizzonte a scelta.** Nella pagina si sceglie l'uscita: da 1 a 20 sedute (5 = una settimana) oppure al cambio di etichetta. Il backtest si può filtrare anche per periodo: tutto, sviluppo o holdout. Per ogni seduta Python salva una lista compatta con, per quel giorno: numero di segnali, segnali vinti, somma dei risultati, somma dei guadagni massimi e somma dei drawdown massimi. Il calcolo è `motore.giorni_stat`. Medie, % di vinti e intervallo di Wilson li calcola `app.js`. Per ogni strumento ci sono anche la volatilità annua e la mossa settimanale tipica (`motore.profilo`).

**Volatilità per asset** (`cot_radar/volatilita.py`). Si calcola dall'archivio prezzi e copre:
- il movimento medio per giorno della settimana;
- la settimana tipica e quella "brutta", cioè il 90° percentile;
- la volatilità per mese del calendario e anno per anno;
- il regime attuale: ultime 20 sedute contro gli ultimi 5 anni, diviso in calma, normale e agitata.

Ogni segnale (live e backtest) riceve il regime del giorno prima della generazione, quindi senza dati dal futuro. Le statistiche si possono leggere anche per regime. La volatilità è misurata da chiusura a chiusura.

Test: `python -m unittest tests.test_motore -v`. Tra l'altro verificano la catena di hash, la manomissione e il backtest senza dati "dal futuro".

## Confronto: opzioni, TFF e Disaggregated (`cot_radar/confronto.py`)

Il sito usa il report CFTC **Legacy, solo futures**. La CFTC pubblica anche altri report, che ora vengono archiviati nel ramo `storico` (un file per report, stesse regole dei prezzi: scaricati una volta, poi solo le settimane nuove, mai riscritti):

| File | Report | Dal | Cosa aggiunge |
|---|---|---|---|
| `COT_COMB.csv` | Legacy **futures + opzioni** (`jun7-fc8e`) | 1995 | le opzioni convertite in futures equivalenti (delta) |
| `TFF.csv` | Traders in Financial Futures, combined (`yw9f-hn96`) | 2006 | valute/indici/tassi/crypto: Leveraged Funds (fondi veloci) e Asset Manager (fondi lenti) |
| `DIS.csv` | Disaggregated, combined (`kh3c-gbw2`) | 2006 | materie prime: Managed Money, Producer/Merchant, Swap Dealer |

**Questi dati NON entrano nel punteggio.** Prima si misura se migliorano qualcosa: `confronto.py` rifà il backtest con lo stesso motore cambiando solo chi conta come "speculatore", sullo stesso periodo e con gli stessi costi, e confronta ogni variante con la versione di oggi sugli stessi strumenti. In più verifica un filtro: le opzioni degli speculatori vanno a favore o contro il segnale? Una lettura entra nel sito solo se migliora sia lo sviluppo sia l'holdout.

Limite: si può misurare solo dove c'è un prezzo storico gratuito (cambi, indici USA, petrolio, gas, crypto). Oro, cereali e bestiame, dove le opzioni pesano di più, restano fuori.

Uso: `python -m cot_radar.confronto storico` (con la cartella dell'archivio). Il risultato completo finisce anche in `storico/confronto.json`. Test: `python -m unittest tests.test_archivi_cot -v`.

## Registro di monitoraggio e protezione anti-crollo

| Dove | Cosa |
|---|---|
| `dati/registro.log` | tutti i messaggi (DEBUG → CRITICAL), a rotazione 1 MB × 3 |
| `dati/stato.json` | riepilogo COMPLETO dell'ultima esecuzione: esito, fonti, avvisi, errori (privato) |
| `stato.json` sul sito | versione "vetrina": solo esito generico e stato delle fonti, nessun messaggio interno |
| scheda **Registro** | sul PC: visibile. Sul sito: **solo admin**, cifrata (vedi sotto) |
| **mail privata di GitHub** (solo all'amministratore) | se l'aggiornamento fallisce, viene scartato dal paracadute o ha esito CRITICO (job `avviso-admin`) |

### Registro riservato all'amministratore (`cot_radar/admin.py`)
Il sito è pubblico: tutto ciò che è nella pagina lo può leggere chiunque. Per questo il registro completo viene
**cifrato** (AES-GCM 256, chiave da password con PBKDF2-SHA256) prima di essere pubblicato.
1. GitHub → repository → *Settings* → *Secrets and variables* → *Actions* → *New repository secret*:
   nome `ADMIN_PASSWORD`, valore = una password solo tua (lunga, non usata altrove).
2. Apri il sito aggiungendo `#admin` in fondo all'indirizzo (es. `.../cot-radar/#admin`), scrivi la password:
   la pagina decifra il registro nel browser. La password non viene inviata da nessuna parte.
3. Senza il Secret il registro semplicemente non viene pubblicato (resta la mail di GitHub).

- **Paracadute** (`cot_radar/paracadute.py`): ogni aggiornamento è confrontato con l'ultimo buono. Se mancano pezzi
  (strumenti, coppie, mercati, mutui) la pagina **non** viene pubblicata e resta online quella precedente; se una
  fonte è giù si pubblicano gli ultimi dati salvati. In entrambi i casi: riga CRITICAL nel registro e mail a te.
  (Nota: il repository è pubblico, quindi la pagina Actions è leggibile da tutti: contiene solo l'esito e i
  messaggi essenziali, mai chiavi né il registro dettagliato.)
- Ogni sezione della pagina è isolata: se una si rompe compare "Sezione non disponibile" e le altre funzionano.
- `cot_radar/controlli.py` scova gli errori "invisibili": dati vecchi, mercati spariti, valori impossibili, salti anomali.
- Le chiavi API non finiscono mai nei registri: vengono sostituite con `***`.

## Chiave FRED (gratuita)

FRED dai server cloud funziona in modo affidabile solo con la chiave API (richiedila su fred.stlouisfed.org).
**Mai** scriverla nel codice o nel README. Su GitHub: Settings → Secrets and variables → Actions →
`FRED_API_KEY` (solo i 32 caratteri della chiave). Sul PC: `setx FRED_API_KEY "la-tua-chiave"` nel Prompt dei comandi.

**Se FRED e' in manutenzione** il programma non insiste: prova una sola serie, salta le altre e passa alle
**fonti di riserva** (`cot_radar/riserva.py`), cioe' a chi pubblica davvero quei numeri, gratis e senza chiave:
Tesoro USA (tassi 2/10 anni, reale 10 anni, inflazione attesa, conto TGA), NY Fed (reverse repo), CBOE (VIX),
Freddie Mac (mutuo USA 30 anni), BCE (cambi), Coinbase (BTC/ETH). Quello che resta (bilancio Fed, indici, petrolio)
viene dai dati salvati. Su GitHub il job `sonda` di `sito.yml` controlla **ogni ora** con una sola richiesta leggera
(senza chiave) e, appena FRED torna online, rilancia da solo l'aggiornamento completo.

## Pubblicarlo su internet (GitHub Pages)

1. Crea un account su **github.com** → **New repository** → nome `cot-radar` → **Public** → *Create*.
2. Carica i file: **Add file → Upload files**, trascina tutto il contenuto della cartella (compresa `.github`).
   *Se la cartella `.github` non viene caricata*: **Add file → Create new file**, scrivi come nome
   `.github/workflows/sito.yml`, incolla il contenuto del file e salva (stesso per `test.yml`).
3. **Settings → Pages → Source: GitHub Actions**.
4. **Actions → Sito → Run workflow**. Dopo 1–2 minuti il sito è su `https://yahyaallouchi5-2025.github.io/cot-radar/`.

Da quel momento si aggiorna da solo: venerdì sera (COT), giovedì sera (Fed), ogni mattina feriale (mercati e BCE).
Se un download fallisce, il sito **non** viene sostituito: resta online l'ultima versione buona.

### Dominio personale (es. `cotradar.it`)

1. Compra il dominio da un registrar (Aruba, Register.it, Cloudflare, Namecheap… circa 10–15 €/anno).
2. Nel pannello DNS del registrar aggiungi:

   | Tipo | Nome | Valore |
   |---|---|---|
   | A | @ | 185.199.108.153 |
   | A | @ | 185.199.109.153 |
   | A | @ | 185.199.110.153 |
   | A | @ | 185.199.111.153 |
   | CNAME | www | yahyaallouchi5-2025.github.io |

3. Su GitHub: **Settings → Pages → Custom domain** → scrivi il dominio → *Save*. Quando il controllo è verde, spunta **Enforce HTTPS**.
4. Consigliato: **Settings del tuo account → Pages → Add a domain** per "verificare" il dominio (impedisce ad altri di usarlo).

La propagazione DNS può richiedere da pochi minuti a 24 ore.

---

## Cose da sapere prima di renderlo pubblico

- Con il piano gratuito di GitHub il repository deve essere **pubblico**: codice e pagina sono visibili a tutti.
- Segnali "BUY/SELL" pubblicati per tutti possono rientrare nelle regole europee sulle **raccomandazioni di investimento** (Regolamento UE 596/2014, MAR): chi le produce, metodo, avvertenze. La sezione "Metodo" e il disclaimer aiutano, ma per un uso pubblico o a pagamento chiedi un parere a un professionista.
- Dati: CFTC e Fed sono dati pubblici USA; BCE riutilizzabile citando la fonte. Le fonti sono indicate in fondo alla pagina.

## Licenza

Codice sotto licenza MIT (vedi `LICENSE`): chiunque può usarlo e modificarlo citando l'autore.
Se preferisci il **pubblico dominio** vero e proprio (nessun obbligo di citazione), sostituisci `LICENSE` con il testo della licenza *Unlicense* o *CC0*.
