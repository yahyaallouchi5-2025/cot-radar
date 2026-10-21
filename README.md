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
Gli strumenti usano i **nomi originali in inglese** (come CFTC, CME e TradingView: es. *Class III Milk*, simbolo
`CME:DC1!`), con il nome italiano sotto (`NOMI_EN` in `cot_radar/config.py`).
Se la pagina aperta e' vecchia (cache del browser) compare l'avviso "versione piu' recente" con il pulsante Aggiorna.
I simboli sono in `cot_radar/config.py` → `TV_SYMBOLS` / `TV_PAIRS` (modificabili). Alcuni strumenti sono quotati
"al contrario" (es. segnale su JPY → grafico USDJPY; tassi → grafico del rendimento): il pannello lo segnala.

## Registro di monitoraggio e protezione anti-crollo

| Dove | Cosa |
|---|---|
| `dati/registro.log` | tutti i messaggi (DEBUG → CRITICAL), a rotazione 1 MB × 3 |
| `dati/stato.json` (e `stato.json` sul sito) | riepilogo dell'ultima esecuzione: esito, fonti, avvisi, errori |
| scheda **Registro** della dashboard | lo stesso riepilogo + errori avvenuti nel browser |
| **mail privata di GitHub** (solo all'amministratore) | se l'aggiornamento fallisce, viene scartato dal paracadute o ha esito CRITICO (job `avviso-admin`) |

- **Paracadute** (`cot_radar/paracadute.py`): ogni aggiornamento è confrontato con l'ultimo buono. Se mancano pezzi
  (strumenti, coppie, mercati, mutui) la pagina **non** viene pubblicata e resta online quella precedente; se una
  fonte è giù si pubblicano gli ultimi dati salvati. In entrambi i casi: riga CRITICAL nel registro e mail a te.
  (Nota: il repository è pubblico, quindi anche i log di Actions sono leggibili; non contengono segreti.)
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
