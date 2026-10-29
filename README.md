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
│   ├── eventi.py            calendario storico degli annunci USA (eventi_usa.csv) per lo studio del drawdown
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
- la settimana media e quella al 90° percentile (P90);
- la volatilità per mese del calendario e anno per anno;
- il regime attuale: ultime 20 sedute contro gli ultimi 5 anni, diviso in calma, normale e agitata.

Ogni segnale (live e backtest) riceve il regime del giorno prima della generazione, quindi senza dati dal futuro. Le statistiche si possono leggere anche per regime. La volatilità è misurata da chiusura a chiusura.

Test: `python -m unittest tests.test_motore -v`. Tra l'altro verificano la catena di hash, la manomissione e il backtest senza dati "dal futuro".

## Studio del drawdown (scheda "Backtest storico")

L'obiettivo del backtest non è solo "il segnale vince?", ma **quanto va contro prima di andare (o non andare) dove deve**, rispetto alla volatilità di ogni mercato e al guadagno. Per ogni durata del trade (da 1 giorno di mercato a 4 settimane, oppure al cambio di segnale) `motore.drawdown` calcola:

- **drawdown assoluto** (misurato dal prezzo d'ingresso): **mediano** e al **90° percentile** (P90: 1 trade su 10 va peggio), in % e, scegliendo uno strumento, in **punti** (pip, punti indice, dollari);
- drawdown **in volatilità**: diviso il movimento di una settimana normale di quel mercato, misurato prima dell'ingresso (stessa scala per EURUSD, petrolio e Bitcoin), con la distribuzione per fasce (sotto 0,5×, 0,5–1×, 1–2×, oltre 2× il movimento settimanale mediano);
- guadagno massimo mediano, quante volte il guadagno arriva prima del drawdown e il giorno mediano del punto peggiore;
- **annunci macro USA** (occupazione NFP e inflazione CPI dal 1985, decisioni della Fed dal 1994; file `cot_radar/eventi_usa.csv`, fonti ALFRED/St. Louis Fed e Federal Reserve): drawdown con e senza annunci nel trade e quante volte il giorno peggiore cade su un annuncio rispetto al puro caso. Conta l'ora: i cambi FRED chiudono alle 12 di New York, quindi la Fed delle 14 entra nella chiusura del giorno dopo (`cot_radar/eventi.py`).

Vinti e resa media restano visibili in piccolo, per non perdere il quadro completo. Test: `python -m unittest tests.test_drawdown -v`.

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

## Portafogli modello (v6.28: `portafogli.py` + `web/portafogli.js`, scheda "Portafogli")
- Tre profili con una **base fissa** di mercati e pesi: **conservativo** (S&P 500 20%, Europa/Asia 10%, Treasury
  10 anni 45%, oro 10%, liquidità 15%), **moderato** (S&P 35%, Europa/Asia 10%, emergenti 5%, Treasury 30%, oro 10%,
  liquidità 10%), **aggressivo** (S&P 40%, Nasdaq 15%, Europa/Asia 10%, emergenti 10%, Treasury 10%, oro 10%,
  Bitcoin 5%).
- **Filtro di trend** ogni mese, solo acquisti: un mercato sotto la media a 200 giorni va "in pausa" e il suo peso
  passa alla liquidità (Treasury 1-3 anni) finché non torna sopra. Costi 0,10% a rotazione.
- **Perché così (onestà del metodo)**: la versione 1 (ingresso con COT da BUY + trend, pesi a volatilità obiettivo)
  fuori campione rendeva 1-2% l'anno contro l'8% del 60/40. Sullo **storico 2006-2015** sono state confrontate
  varianti: il filtro COT (conferma o veto) peggiorava il rendimento a parità di rischio, il filtro di trend
  dimezzava le cadute. Scelta fatta solo su quel periodo, poi **una sola verifica fuori campione** (2016-oggi):
  conservativo 3,5%/anno (caduta max -13%), moderato 4,6% (-16%), aggressivo 10,5% (-20%); 60/40: 8,3% (-23%).
  Il COT resta mostrato accanto a ogni mercato come informazione.
- **Rischio del mese** (v6.28): a ogni rotazione la composizione del mese viene tenuta nello stesso mese di calendario
  di tutti gli anni dello storico (es. ogni ottobre dal 1993): rendimento e caduta massima dentro il mese anno per
  anno, mese peggiore, medio, anni positivi e stagionalità del mese per ogni mercato. Niente statistiche per anno
  solare: il portafoglio ruota ogni mese.
- **Provati sullo storico 2006-2015 e scartati** (v6.28): stagionalità mensile come filtro di uscita (rendimento
  -0,5/-1,6 punti l'anno, cadute quasi uguali), ETF settoriali al posto dello S&P 500 (con o senza scelta per
  stagionalità: rendimento più basso, cadute uguali), rotazione per forza relativa tra azioni, oro, argento,
  petrolio e rame (storico 10%/-25%, ma fuori campione 5%/-31%). La stagionalità resta mostrata come informazione.
- **Live** dalla prima rotazione pubblicata (`storico/portafogli/rotazioni_v2.json`, mai riscritto).
- **Robustezza dei prezzi** (v6.29): 3 tentativi per ticker (pausa 2 s e 6 s); serie incomplete o con salti assurdi
  scartate; dopo 3 ticker falliti di fila Yahoo è considerato fermo e si usano le copie (il workflow non resta
  appeso). Se i prezzi delle basi sono più vecchi di 4 giorni, o il calcolo fallisce e resta online l'ultima scheda
  buona (`storico/portafogli/ultimo.json`), la scheda mostra un banner e un popup (una volta per sessione) con il
  messaggio generico "Errore server 503 · I dati non sono stati aggiornati: manutenzione in corso". Nel registro va
  un ERRORE con i dettagli: l'admin riceve la mail di GitHub.
- **Prezzi**: Yahoo Finance (rettificati), copia in `storico/yahoo/`, al massimo un download al giorno. Per un servizio
  commerciale conviene un fornitore con licenza: basta sostituire `scarica_yahoo()`.

## Pattern Detector (v6.32: `pattern.py` + `web/pattern.js`, workflow `pattern.yml`)
- **Pattern**: BUY = candela 1 ribassista, candele 2 e 3 rialziste, chiusura della 3 sopra l'apertura della 1
  (assorbimento in due candele); SELL simmetrico. Ingresso indicativo = chiusura della candela 3.
- **Strumenti**: 28 coppie forex, oro, argento (spot Yahoo se c'è, altrimenti future), WTI, Brent, gas, rame, platino.
- **Timeframe**: H4 (candele orarie Yahoo aggregate, allineate a UTC 00-04-08-12-16-20: possono differire dal broker)
  e Daily; solo candele chiuse. Workflow ogni 4 ore a :08; il risultato va nel ramo `pattern` e la pagina lo legge da
  raw.githubusercontent.com (nessuna ripubblicazione del sito). Ritardo tipico 10-20 minuti dalla chiusura.
- **Statistica**: per ogni strumento quante volte, dopo 5 candele, il prezzo era nella direzione del segnale.
- **Anomalia**: Yahoo fermo -> restano i segnali del giro prima, popup di manutenzione, mail di GitHub all'admin.

### v6.43
Eventi ad alto impatto: la pillola confronta ora anche l'**ora di Roma**. Dall'ora del dato diventa "IN CORSO" (punto che pulsa) e sparisce dopo 60 minuti (dato macro) o 90 (banca centrale, conferenza stampa). La lista si aggiorna da sola ogni minuto; se non resta nulla la card scompare.

### v6.42
- **BCE più robusta**: se il servizio dati della BCE risponde con un errore temporaneo (5xx, es. "504 Gateway Time-out", o tempo scaduto) si riprova **una sola volta** dopo 4 secondi; errori 4xx non si riprovano. Poi si usano i dati salvati.
- **Niente barre rosse tecniche per gli utenti**: gli errori di download restano nel registro admin. Solo se un'intera fonte è ferma compare il popup di manutenzione con il codice d'errore (es. "Errore server 504").

### v6.41
- **Rischio del mese** ridisegnato: termometro del drawdown peggiore contro il limite del profilo (verdetto in parole), **heat map** anno per anno con le % (verde guadagno, rosso perdita) e interruttore "Risultato del mese" / "Scenario peggiore", fumetto con i dettagli; metriche allineate. Su PC la card non lascia più spazi vuoti. Tolta la parola "caduta" da tutte le scritte (si usa "drawdown").

### v6.40
- **Riquadri in alto della Dashboard ridisegnati**: ognuno risponde a una domanda semplice. Segnali attivi con barra verde/rossa (rialzo/ribasso) ed etichetta ★ STRONG; clima del mercato con tachimetro PAURA → FIDUCIA; prossima rotazione e nuovi dati COT con conto alla rovescia e barra del tempo passato. Cliccabili (segnali, Mercato, Portafogli, Forza degli strumenti), effetti al passaggio del mouse, leggibili anche nei riquadri stretti.

### v6.39
- **Briefing del lunedì su Telegram** (`cot_radar/briefing.py`): messaggio lungo con 📌 portafoglio (semaforo 🟢🟡🔴 sul trend), 🎯 messaggio chiave, ✍️ Forex update (una scheda per valuta), 🏦 banche centrali e dati, 🧭 altri mercati. Ogni frase nasce da un dato della dashboard (COT, driver FRED/BCE, trend dei portafogli, eventi): niente testi di terzi né previsioni; i "livelli" sono l'ampiezza tipica della settimana (prezzo ± movimento medio storico), dichiarata come tale. Parte una volta a settimana, il lunedì dalle 05:30 UTC (martedì se il giro salta); il cursore `briefing` in `notificati.json` evita i doppioni.
- **Riepilogo del venerdì sera** con racconto breve in testa ("🎯 In breve": segnali attivi/nuovi/chiusi, i più forti, quanti segnali aperti sono in guadagno dal registro pubblico, prossima rotazione).
- *Prova notifiche* ora manda anche un esempio di riepilogo e di briefing marcati [TEST].
- **Portafogli versione 3** (variante "E" dello studio): azioni scelte 5/10/15%, difesa con più liquidità e oro, Treasury e oro sempre in portafoglio (filtro di trend solo su azioni e Bitcoin), scambi solo se un mercato entra/esce o a inizio trimestre. Turnover molto più basso (conservativo da ~150% a ~56% l'anno). La v3 è stata decisa guardando tutto lo storico: la prova pulita è la linea live, che riparte dalla rotazione del 2/11/2026 (`rotazioni_v3.json`; v2 conservata).
- **Studio sui portafogli** (`tools/backtest_varianti.py`, risultati in `tools/risultati_varianti.txt`): confronto di quattro varianti (azioni scelte ridotte, difesa diversa, ribilancio lento, difesa sempre accesa) con benchmark 30/70, 60/40 e 80/20. Solo studio, nulla è cambiato sul sito. Limiti: ETF in dollari (niente effetto cambio/copertura), tasse non simulate (si misura il turnover) e storico delle azioni scelte simulato con volatilità sottostimata.

### v6.38
- Banner eventi: ora si trascina avanti e indietro con dito o mouse, con inerzia e ripartenza dolce (non si blocca piu' al tocco).
- Portafogli su telefono: tabella delle statistiche sempre leggibile (niente colonna che copre i valori).

## v6.37: portafoglio pronto da eseguire
- Scheda Portafogli: "Portafoglio di <mese>" del profilo scelto, righe raggruppate per classe di attivo, per ogni
  mercato lo strumento acquistabile in Europa (UCITS / ETC / ETP, `portafogli.STRUMENTI_UE`) con ISIN da copiare,
  importi in euro sul capitale indicato, le 5 azioni scelte elencate (anteprima provvisoria del mese prossimo da
  `satellite.json` -> `anteprima`, finche' la lista non e' registrata l'ultimo giorno di borsa).
- Conto alla rovescia al prossimo ribilanciamento (09:00 ora italiana del primo giorno di borsa del mese).
- Card "Rischio del mese" con metriche standard: max drawdown intra-mese, peggior rendimento, rendimento medio,
  win rate, max drawdown storico; tooltip sul grafico anno per anno.
- Dashboard: "Prossimi eventi ad alto impatto" come banner a scorrimento lento (si ferma col mouse o col tocco;
  fermo per chi ha "riduci animazioni" attivo).
- Consenso legale ricordato in modo affidabile: archivio locale + cookie tecnico di 1 anno + sessione.
- Test: `tests/test_strumenti_ue.py` (ogni mercato dei profili ha un ISIN valido, cifra di controllo inclusa).

## v6.36: voto a stelle
- `web/js/27_voto.js`: dopo un po' di utilizzo (25 clic in totale e 2 minuti nella visita) compare in basso a destra
  una scheda discreta "Ti sta piacendo BoardEdge?" con 1-5 stelle e un commento facoltativo. Il voto arriva via email
  con la stessa chiave Web3Forms del Feedback (Secret `WEB3FORMS_KEY`). Una volta votato non torna piu';
  se chiusa torna dopo 21 giorni, al massimo 2 volte. Non compare mai sopra altre finestre o mentre si scrive.

## v6.35: ordine nel codice e nuove funzioni
- **Codice della pagina diviso**: `web/app.js` (980 righe) e gli altri file JS sono ora in `web/js/`, un file per scheda
  (`01_base.js`, `04_dashboard.js`, `09_correlazioni.js`, `21_portafogli.js`...). `pagina.py` li unisce in ordine di
  nome in un solo script: comportamento identico, ma ogni scheda si modifica senza toccare le altre.
- **Correlazioni dei prezzi** (`correlazioni.py`, vista predefinita della scheda Correlazioni, ogni giorno): indici,
  11 settori USA (ETF SPDR, scaricati con i prezzi dei portafogli: `portafogli.EXTRA`), obbligazioni, metalli, energia,
  agricole, cripto e dollaro. Finestre 3 mesi e 1 anno, liste "insieme / al contrario / stanno cambiando" (escluse le
  coppie dello stesso mondo, es. S&P 500 e Tecnologia), legame con l'S&P 500 con mini linea mobile di ~3 anni, mappa
  di calore per gruppo o per strumento. La vista dei flussi COT resta con il pulsante "Flussi COT".
- **Stagionalità senza forex**: valute, dollaro e coppie non hanno più stagionalità né correzione del punteggio
  (effetti deboli e instabili); resta per indici, materie prime, metalli, tassi e cripto.
- **Scheda Mutui tolta** (e con lei i tassi dei mutui BCE e il mutuo USA 30 anni). Al suo posto, in Dashboard, il
  riquadro "Prossima rotazione" dei portafogli. Il paracadute non controlla più la sezione mutui.
- **Bilanci USA dalla SEC** (`fondamentali.py`, workflow Azioni, Secret `SEC_CONTATTO`): ultimi 5 anni fiscali,
  ricavi, utile, anni in perdita, debito netto e giudizio SOLIDA / NELLA MEDIA / INDEBITATA nel dettaglio del titolo.
  Una volta a settimana per titolo; i 10-K arrivano 60-90 giorni dopo la fine dell'anno fiscale.
- **Consenso legale** (`web/js/25_consenso.js`): popup all'ingresso, "Accetto" attivo solo dopo aver letto fino in fondo,
  "Non accetto" blocca la dashboard; salvato nel browser con la versione del testo (alzarla = tutti riaccettano).
- **Feedback** (`web/js/26_feedback.js`): pulsante nella sidebar, modulo che arriva all'email dell'admin con Web3Forms
  (chiave nel Secret `WEB3FORMS_KEY` o in `config.FEEDBACK_CHIAVE`); niente viene pubblicato.
- **Flusso serale**: il Sito parte appena finisce il workflow Azioni (`workflow_run`); il giro delle 22:15 UTC si ferma
  da solo se il sito è già stato aggiornato bene dopo le 21:40.
- **Studio Pattern + COT** (non pubblicato): con il pattern preso solo nella direzione del COT nessun vantaggio
  (2000-2015: 49,6% giusti a 5 giorni; dal 2016: 47,1%). Il Pattern Detector resta uno strumento di lettura grafica.

## Portafogli con Azioni scelte (v6.34: `satellite.py`, `portafogli.py`, `web/portafogli.js`)
- **Quote**: conservativo 10%, moderato 20%, aggressivo 40% in 5 azioni dell'Azionario; il resto è la base di ETF
  di sempre (pesi della base riscalati). Decisione del 26/10/2026; live dal 2 novembre 2026.
- **Scelta** (alla chiusura del mese, solo dati fino a quel giorno): 12 e 3 mesi positivi, prezzo sopra la media di
  10 mesi, non oltre il 15% sotto il massimo annuo, mese che entra positivo in almeno il 60% di almeno 8 anni;
  punteggio dell'Azionario, primi 5 con un titolo per settore, pari peso. Costi 0,20% per titolo cambiato.
- **Filtro di mercato** (in `portafogli.scegli`): S&P 500 sotto la media a 200 giorni → tutta la quota in liquidità.
  Senza filtro la quota perdeva il 55% nel 2008; con il filtro, test 2006-2026 (mensile): aggressivo +14% l'anno con
  caduta massima −18/−21% contro +8% / −17% senza azioni.
- **Onestà**: lo storico delle azioni è OTTIMISTICO (titoli che oggi stanno negli indici: survivorship bias) e dentro
  il mese la quota simulata non ha oscillazioni giornaliere. Dal live ogni scelta è registrata nel ramo `azioni`
  (`satellite_registro.json`, mai riscritto) con il prezzo di chiusura del giorno di registrazione: l'ultimo giorno
  feriale del mese dopo la chiusura (pronta per la rotazione), oppure al primo giro utile del mese.
- **Flusso**: workflow Azioni (21:35 UTC) → `pubblico/satellite.json` nel ramo `azioni` → il Sito lo legge
  (`satellite.leggi`) e lo passa a `portafogli.calcola(..., sat=...)`, che costruisce il prezzo sintetico `SAT`.
- **Scheda**: selettore a segmenti dei profili e card principale (rischio, rendimento annuo, caduta massima,
  10.000 € dall'inizio, mesi positivi, composizione per classe, le 5 azioni del mese, come funziona la rotazione).
- **Strumenti (telefono)**: la colonna del punteggio ora è larga quanto serve, "STRONG SELL" resta dentro la card.

### v6.33: correzioni
- **Storico mensile azioni**: con `range=max` Yahoo restituiva barre TRIMESTRALI per gli storici lunghi (circa 230 titoli,
  es. Apple dal 1980): la loro stagionalità era sbagliata. Ora lo storico mensile si scarica con `period1/period2`,
  `mensile_ok()` scarta e fa riscaricare le copie trimestrali e `stagionalita()` usa solo rendimenti di UN mese.
- **Pattern Detector, UI**: barra comandi con switch e filtri alla stessa altezza (38px) e centrati; nelle card i tre
  valori (ingresso, apertura candela 1, minimo/massimo) sempre sulla stessa linea; numeri in formato italiano anche nel
  pannello; niente più "-0,00%"; "1 candela fa" al singolare.

## Azionario per settore (v6.31: `azioni.py` + `web/azioni.js`, scheda "Azioni", workflow `azioni.yml`)
- **Titoli**: ~1.040 tra S&P 500, Nasdaq-100, FTSE MIB, DAX 40, Euro Stoxx 50, Nikkei 225, Hang Seng, SSE 50 e Nifty 50,
  negli 11 settori GICS (settori asiatici ricondotti al GICS a mano), più 9 indici. Emirati: Yahoo non ha i titoli (404).
  Elenco con settore e listini in `cot_radar/azioni_elenco.csv` (da aggiornare a ogni ribilanciamento trimestrale):
  Yahoo da GitHub Actions non concede il profilo aziendale (risposta 401/429), quindi il settore non arriva da lì;
  il nome del titolo invece sì, a ogni download.
- **Flusso serale** (`azioni.yml`, 21:35 UTC, separato dal sito): per titolo 2 anni giornalieri + storico mensile
  completo una volta a settimana (giorno sparso per ticker). 3 tentativi per richiesta, 5 fallimenti di fila = Yahoo
  fermo e si usano le copie. Copie nel ramo `azioni`, riscritto con un solo commit (non si gonfia). Il sito copia
  `pubblico/` in `/azioni/`: `indice.json` (~220 KB, tutti i titoli) e `titoli/<T>.json` (grafico e stagionalità).
- **Anomalia** (Yahoo fermo o oltre il 10% dei titoli non aggiornati): restano i dati del giorno prima, la scheda
  mostra il popup comune "Manutenzione in corso" con giorno e ora dell'anomalia (una volta per sessione, nessuna
  barra fissa), il workflow fallisce e GitHub manda la mail all'admin.
- **Frontend**: il file si scarica solo all'apertura della scheda, con lo scheletro di attesa; filtri per listino e
  settore, ricerca, colonne ordinabili, pannello di dettaglio con grafico (1 anno, 2 anni, storico mensile) e
  stagionalità mensile del titolo.
- **Punteggio e classifica** (v6.31): ogni sera ogni titolo riceve un punteggio 0-100 = percentili pesati di
  rendimento a 12 mesi (30%), a 3 mesi (20%), distanza dalla media a 200 giorni (15%) e stagionalità del mese in
  corso (rendimento medio 20%, anni positivi 15%). La tabella è in classifica per punteggio, a pagine da 50.
- **Vetrina della Dashboard** (`web/topaz.js`, `top.json`): al massimo 5 titoli, uno per settore, con punteggio
  alto e tutte le condizioni favorevoli (sopra la media a 200 giorni, 3 e 12 mesi positivi, mese in corso positivo
  in almeno il 60% di almeno 8 anni, non oltre il 15% sotto il massimo annuo). Carosello ogni 6 secondi.
- **Popup comune** (`web/manutenzione.js`): lo usano anche i Portafogli (la barra gialla fissa è stata tolta).

## Landing e note legali (v6.23)
- Landing: sezione **Il metodo** (COT + politica monetaria + notizie macro + stagionalità), orizzonte swing e
  medio-lungo periodo, **domande frequenti**, piè di pagina con link legali.
- **Note legali** in `/legale/` (`web/legale.html`, scritta da `vetrina.legale()`): termini di utilizzo, diritto
  d'autore, avvertenze sui rischi, privacy e statistiche, fonti, contatti. Titolare e e-mail pubblica in
  `config.TITOLARE` e `config.CONTATTO_EMAIL` (vuoti = testo generico e contatto via Telegram). Testo di base:
  da far rivedere a un avvocato prima di vendere abbonamenti.

## Statistiche di visita anonime (v6.21: `web/statistiche.js`)
- **Cosa**: visitatori, pagine viste, provenienza, telefono/PC e i click che contano (pass gratuito, Telegram, schede
  del terminale, grafici aperti, filtri, backtest, stagionalità, guida), più fin dove si scorre la landing ("sezione")
  e le sezioni del terminale che vanno in errore ai visitatori ("errore").
- **Privacy**: Umami (cloud.umami.is), **senza cookie e senza dati personali**: nessun banner, nessun visitatore escluso.
- **Attivazione**: crea il sito su Umami e copia il *Website ID* in `config.STATISTICHE_ID` (è pubblico, non è una
  chiave segreta). Vuoto = statistiche spente. Si conta solo sul dominio del sito, mai le prove in locale.
- **Nuovo evento**: `data-ev="nome"` (e `data-pos="dove"`) su un elemento HTML, oppure `ebStat.ev("nome", {...})` in JS.
- **Debug**: aggiungi `?statdebug` all'indirizzo: ogni evento viene stampato nella console del browser.

## Notizie macro su Telegram (v6.20-6.22: `agenda.py` + `avvisi.py`)

Flusso unico, ogni fonte un solo compito:
1. **Calendario** = financecalendar.com (gratuito, uso commerciale con link di attribuzione, presente in ogni
   messaggio e nel terminale): Fed, BCE, BoE, BoJ, BoC, RBA, RBNZ, SNB, CPI/NFP/PCE/PPI/PIL/ISM/vendite USA,
   CPI di Eurozona, UK, Canada, Australia. Se non risponde: ultima copia salvata (`dati/agenda.json`), poi il
   calendario interno di `notizie.py` (NFP, CPI, Fed, BCE).
2. **Esito** = reazione del mercato da FRED/BCE: movimento del tasso a 2 anni nel giorno dell'annuncio in deviazioni
   standard (USD, EUR). Arriva quando FRED/BCE pubblicano il dato (di solito il giorno dopo): finché manca, l'esito
   resta in attesa e si riprova al giro successivo; dopo 4 giorni parte comunque con quello che c'è.
3. **Segnali esposti** = coppie Forex con segnale COT che contengono la valuta: conferma / contrasto / neutro.

Messaggi (ognuno una sola volta, stato nel cursore `notificati.json`): **notizie della settimana** (v6.22: il
venerdì sera dopo il riepilogo COT, giorno per giorno; recupero entro lunedì mattina), **notizie in arrivo** (entro
30 ore: di solito la sera prima) ed **esito delle notizie** (per valuta e giorno; per le valute senza tasso a 2 anni
il dato confrontato con il precedente, dichiarato come stima).
**Prova**: Actions → *Prova notifiche* manda subito i tre messaggi marcati [TEST · esempio] con i dati veri del sito
(il riepilogo COT di prova: `python -m cot_radar.notifiche prova-cot URL`). Il consensus non è disponibile gratis: si confronta
il dato con il precedente e la sorpresa vera la misura il mercato.

## Stagionalità agganciata al COT (v6.18)

La stagionalità (settimana e 4 settimane) parte dal **venerdì di uscita del report COT in uso** (`stagionalita.ancora_cot`),
non da oggi: resta ferma per tutta la settimana e si sposta insieme al segnale quando esce il COT nuovo.
Nel pannello del grafico il giudizio è rispetto al segnale: **favorevole** (verde), **non favorevole** (rosso), **neutra** (ambra).

## Sito: landing page + terminale (v6.17)

- `https://…github.io/cot-radar/` = **landing page** (`web/landing.html`, riempita da `cot_radar/vetrina.py` con i numeri veri:
  data del COT, segnali attivi, mercati, anteprima dei segnali con i nomi sfocati).
- `https://…github.io/cot-radar/terminale/` = **terminale** (la dashboard). Accesso con un **pass gratuito** salvato nel
  browser (un clic sulla landing): NON è un login vero, serve a far passare i visitatori dalla landing.
  Il login vero (Supabase) sostituirà la funzione `entra()` della landing e il controllo in testa a `web/index.html`.
- Il link del canale Telegram è in `config.TELEGRAM_CANALE` (sidebar del terminale, landing, pulsante in alto su telefono).

## Notifiche dei segnali (Telegram + e-mail all'admin, `cot_radar/notifiche.py`)

Dopo ogni pubblicazione riuscita il workflow **Notifiche** (parte da solo dopo ogni giro riuscito di *Sito*) legge il registro live dei segnali e manda
**un solo messaggio** al canale Telegram con quello che è cambiato: nuovi segnali, rafforzamenti a STRONG,
indebolimenti, chiusure (con la durata) e conferme del nuovo COT. Una copia arriva via e-mail all'admin (facoltativa).

- **Riepilogo settimanale**: ogni venerdì sera, appena la dashboard mostra il nuovo report COT, arriva un unico
  messaggio con tutti i segnali attivi divisi per categoria (Forex, indici, tassi, energia, metalli, cereali, soft,
  bestiame, crypto), con punteggio, affidabilità, ★ per i segnali nuovi e l'elenco dei segnali chiusi
  (`cot_radar/riepilogo.py`). Se la CFTC slitta per una festività, il riepilogo parte quando esce il report.
- **Niente doppioni**: un cursore (`storico/segnali/notificati.json`) ricorda l'ultimo evento avvisato.
- **Niente avvisi persi**: se Telegram non risponde il cursore resta fermo e il messaggio parte al giro dopo
  (il job fallisce e GitHub manda la mail all'admin).
- **Niente arretrati**: al primo avvio il cursore parte dall'ultimo evento; eventi più vecchi di 36 ore non si mandano.
- **Solo dati ufficiali**: si avvisa solo di eventi già scritti nel registro (catena di hash integra) e già online.

Configurazione (una volta, le credenziali le inserisce solo il proprietario):
1. Telegram → **@BotFather** → `/newbot` → copia il token del bot.
2. Crea un **canale** (pubblico o privato) e aggiungi il bot come **amministratore** con il permesso di pubblicare.
3. GitHub → *Settings* → *Secrets and variables* → *Actions* → *New repository secret*:
   - `TELEGRAM_BOT_TOKEN` = token del bot
   - `TELEGRAM_CHAT_ID` = `@nomecanale` (canale pubblico) oppure l'id numerico `-100…` (canale privato)
   - facoltativi per l'e-mail all'admin: `SMTP_USER` (es. indirizzo Gmail), `SMTP_PASSWORD`
     (**password per le app** di Google, non la password dell'account), `ADMIN_EMAIL` (destinatario)
4. *Actions* → **Prova notifiche** → *Run workflow*: arriva subito il riepilogo della settimana marcato [TEST].

Anteprima senza inviare nulla: `python -m cot_radar.notifiche anteprima storico`.
Più avanti: e-mail a tutti gli iscritti tramite Supabase (login e lista iscritti).

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
