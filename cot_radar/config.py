# -*- coding: utf-8 -*-
"""
config.py - TUTTE le impostazioni del progetto in un solo posto.

Se vuoi cambiare un peso, una soglia o aggiungere uno strumento, si fa qui:
il resto del codice legge questi valori e non contiene numeri "magici".
"""
import os

# --------------------------------------------------------------------------- pesi e soglie del segnale
# Il punteggio COT di ogni strumento (da -100 a +100) e' una media pesata di tre componenti.
# La somma dei pesi deve fare 1.0, altrimenti la scala da -100 a +100 non torna.
WEIGHTS = {
    "posizione": 0.25,   # dove sono posizionati rispetto agli ultimi 3 anni (COT Index)
    "flusso_1w": 0.35,   # quanto hanno comprato/venduto questa settimana rispetto al solito
    "flusso_4w": 0.40,   # la tendenza delle ultime 4 settimane
}
STRONG, NORMAL = 50, 25          # |punteggio| >= 50 -> STRONG, >= 25 -> BUY/SELL, sotto -> NEUTRO
DIVERGENCE_MIN = 20              # per una "divergenza" serve forza >= 20 da un lato e <= -20 dall'altro
CROWD_HI, CROWD_LO = 95, 5       # COT Index oltre questi valori = posizionamento "affollato"
CROWD_DAMPING = 0.7              # quando e' affollato, la forza viene moltiplicata per 0.7 (-30%)

MACRO_WEIGHT = 0.25              # peso del punteggio "Mercato" nel finale (0 = solo COT)
REG_WEEKS = 104                  # settimane usate dalla regressione prezzi/driver (2 anni)
HISTORY_WEEKS = 175              # settimane di storico scaricate (servono 156 per il COT Index a 3 anni)
TIMEOUT = 45                     # secondi massimi di attesa per ogni download

# --------------------------------------------------------------------------- indirizzi delle fonti
# CFTC: API "Socrata" del report Legacy, Futures Only (gratis, senza registrazione)
CFTC_URL = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"
# Altri report COT, archiviati per il CONFRONTO nel backtest (vedi storico.aggiorna_extra e confronto.py).
# NON entrano nel punteggio del sito: prima si misura se migliorano qualcosa, poi eventualmente si pesano.
#   COMB = Legacy "Futures and Options Combined": come il nostro, ma con le opzioni convertite in futures (delta)
#   TFF  = Traders in Financial Futures (combined): valute, indici, tassi, crypto divisi in Dealer,
#          Asset Manager (fondi lenti: pensioni, assicurazioni) e Leveraged Funds (fondi veloci: hedge fund, CTA)
#   DIS  = Disaggregated (combined): materie prime divise in Producer/Merchant, Swap Dealer e Managed Money
# Nomi di colonna verificati sull'API CFTC il 24/10/2026. ATTENZIONE: non sono uniformi
# (es. "swap__positions_short_all" con DUE trattini bassi, "asset_mgr_positions_long" senza "_all"):
# vanno copiati esattamente, un nome sbagliato fa fallire la richiesta.
CFTC_RISORSA = "https://publicreporting.cftc.gov/resource/{id}.json"
_BASE_COT = ["cftc_contract_market_code", "report_date_as_yyyy_mm_dd", "open_interest_all"]
ARCHIVI_COT = {
    "COMB": {"id": "jun7-fc8e", "file": "COT_COMB.csv", "dal": "1995-01-01", "min": 20000,
             "campi": _BASE_COT + ["noncomm_positions_long_all", "noncomm_positions_short_all",
                                   "comm_positions_long_all", "comm_positions_short_all"]},
    "TFF": {"id": "yw9f-hn96", "file": "TFF.csv", "dal": "2006-01-01", "min": 8000,
            "campi": _BASE_COT + ["dealer_positions_long_all", "dealer_positions_short_all",
                                  "asset_mgr_positions_long", "asset_mgr_positions_short",
                                  "lev_money_positions_long", "lev_money_positions_short"]},
    "DIS": {"id": "kh3c-gbw2", "file": "DIS.csv", "dal": "2006-01-01", "min": 8000,
            "campi": _BASE_COT + ["prod_merc_positions_long", "prod_merc_positions_short",
                                  "swap_positions_long_all", "swap__positions_short_all",
                                  "m_money_positions_long_all", "m_money_positions_short_all"]},
}
# FRED (Fed di St. Louis): ogni serie si scarica come CSV con il suo codice (id)
FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}&cosd={since}"
# API ufficiale FRED (serve una chiave gratuita, vedi README): piu' affidabile dai server cloud
FRED_API_URL = "https://api.stlouisfed.org/fred/series/observations"
# BCE: API SDMX del Data Portal, in formato CSV
ECB_URL = "https://data-api.ecb.europa.eu/service/data/{flow}/{key}?startPeriod={since}&format=csvdata"

# --------------------------------------------------------------------------- strumenti del report COT
# (chiave interna, codice CFTC, nome leggibile, settore). I codici sono quelli ufficiali CFTC:
# per aggiungere un mercato basta trovare il suo "cftc_contract_market_code" e aggiungere una riga.
ASSETS = [
    ("EUR", "099741", "Euro", "Valute"), ("GBP", "096742", "Sterlina", "Valute"),
    ("JPY", "097741", "Yen", "Valute"), ("CHF", "092741", "Franco svizzero", "Valute"),
    ("CAD", "090741", "Dollaro canadese", "Valute"), ("AUD", "232741", "Dollaro australiano", "Valute"),
    ("NZD", "112741", "Dollaro neozelandese", "Valute"), ("MXN", "095741", "Peso messicano", "Valute"),
    ("BRL", "102741", "Real brasiliano", "Valute"), ("ZAR", "122741", "Rand sudafricano", "Valute"),
    ("DXY", "098662", "Indice del dollaro", "Valute"),
    ("SP500", "13874A", "S&P 500", "Indici azionari"), ("NASDAQ", "209742", "Nasdaq 100", "Indici azionari"),
    ("DOW", "124603", "Dow Jones", "Indici azionari"), ("RUSSELL", "239742", "Russell 2000", "Indici azionari"),
    ("EAFE", "244041", "MSCI EAFE (Europa+Asia)", "Indici azionari"), ("EM", "244042", "MSCI Emergenti", "Indici azionari"),
    ("VIX", "1170E1", "VIX (volatilita')", "Indici azionari"),
    ("US2Y", "042601", "Treasury 2 anni", "Tassi USA"), ("US5Y", "044601", "Treasury 5 anni", "Tassi USA"),
    ("US10Y", "043602", "Treasury 10 anni", "Tassi USA"), ("USBOND", "020601", "Treasury Bond 30 anni", "Tassi USA"),
    ("ULTRA", "020604", "Ultra Treasury Bond", "Tassi USA"), ("FEDFUNDS", "045601", "Fed Funds", "Tassi USA"),
    ("SOFR", "134741", "SOFR 3 mesi", "Tassi USA"),
    ("WTI", "067651", "Petrolio WTI", "Energia"), ("BRENT", "06765T", "Petrolio Brent", "Energia"),
    ("NATGAS", "023651", "Gas naturale", "Energia"), ("HEATOIL", "022651", "Gasolio (ULSD)", "Energia"),
    ("GASOLINE", "111659", "Benzina RBOB", "Energia"),
    ("GOLD", "088691", "Oro", "Metalli"), ("SILVER", "084691", "Argento", "Metalli"),
    ("COPPER", "085692", "Rame", "Metalli"), ("PLATINUM", "076651", "Platino", "Metalli"),
    ("PALLADIUM", "075651", "Palladio", "Metalli"),
    ("CORN", "002602", "Mais", "Cereali"), ("SOY", "005602", "Soia", "Cereali"),
    ("SOYOIL", "007601", "Olio di soia", "Cereali"), ("SOYMEAL", "026603", "Farina di soia", "Cereali"),
    ("WHEAT", "001602", "Grano (Chicago)", "Cereali"), ("KCWHEAT", "001612", "Grano rosso duro (Kansas)", "Cereali"),
    ("RICE", "039601", "Riso", "Cereali"),
    ("SUGAR", "080732", "Zucchero", "Soft"), ("COFFEE", "083731", "Caffe'", "Soft"),
    ("COCOA", "073732", "Cacao", "Soft"), ("COTTON", "033661", "Cotone", "Soft"),
    ("OJ", "040701", "Succo d'arancia", "Soft"),
    ("CATTLE", "057642", "Bovini vivi", "Bestiame"), ("FEEDER", "061641", "Bovini da ingrasso", "Bestiame"),
    ("HOGS", "054642", "Suini magri", "Bestiame"), ("MILK", "052641", "Latte (Classe III)", "Bestiame"),
    ("BTC", "133741", "Bitcoin", "Crypto"), ("ETH", "146021", "Ether", "Crypto"),
]
# Nomi ORIGINALI in inglese (come su CFTC / CME / ICE e su TradingView): sono quelli mostrati in pagina.
# Il nome italiano di ASSETS resta come sottotitolo, per capire al volo di cosa si tratta.
NOMI_EN = {
    "EUR": "Euro FX", "GBP": "British Pound", "JPY": "Japanese Yen", "CHF": "Swiss Franc",
    "CAD": "Canadian Dollar", "AUD": "Australian Dollar", "NZD": "New Zealand Dollar", "MXN": "Mexican Peso",
    "BRL": "Brazilian Real", "ZAR": "South African Rand", "DXY": "U.S. Dollar Index",
    "SP500": "E-mini S&P 500", "NASDAQ": "Nasdaq-100", "DOW": "Dow Jones Industrial Average",
    "RUSSELL": "Russell 2000", "EAFE": "MSCI EAFE", "EM": "MSCI Emerging Markets", "VIX": "VIX Futures",
    "US2Y": "2-Year T-Note", "US5Y": "5-Year T-Note", "US10Y": "10-Year T-Note", "USBOND": "U.S. Treasury Bond",
    "ULTRA": "Ultra U.S. Treasury Bond", "FEDFUNDS": "30-Day Fed Funds", "SOFR": "3-Month SOFR",
    "WTI": "WTI Crude Oil", "BRENT": "Brent Crude Oil", "NATGAS": "Natural Gas (Henry Hub)",
    "HEATOIL": "NY Harbor ULSD (Heating Oil)", "GASOLINE": "RBOB Gasoline",
    "GOLD": "Gold", "SILVER": "Silver", "COPPER": "Copper", "PLATINUM": "Platinum", "PALLADIUM": "Palladium",
    "CORN": "Corn", "SOY": "Soybeans", "SOYOIL": "Soybean Oil", "SOYMEAL": "Soybean Meal",
    "WHEAT": "Chicago SRW Wheat", "KCWHEAT": "KC HRW Wheat", "RICE": "Rough Rice",
    "SUGAR": "Sugar No. 11", "COFFEE": "Coffee C", "COCOA": "Cocoa", "COTTON": "Cotton No. 2",
    "OJ": "Frozen Orange Juice", "CATTLE": "Live Cattle", "FEEDER": "Feeder Cattle", "HOGS": "Lean Hogs",
    "MILK": "Class III Milk", "BTC": "Bitcoin", "ETH": "Ether",
}
SECTORS = ["Valute", "Indici azionari", "Tassi USA", "Energia", "Metalli", "Cereali", "Soft", "Bestiame", "Crypto"]

# Ordine "di mercato" delle valute: decide quale sta davanti nel nome della coppia (EURUSD e non USDEUR)
FX_ORDER = ["EUR", "GBP", "AUD", "NZD", "USD", "CAD", "CHF", "JPY"]
EXTRA_PAIRS = [("USD", "MXN"), ("USD", "BRL"), ("USD", "ZAR"), ("GOLD", "USD"), ("SILVER", "USD")]
PAIR_NAMES = {("GOLD", "USD"): "XAUUSD", ("SILVER", "USD"): "XAGUSD"}

# --------------------------------------------------------------------------- prezzi per il modello di mercato
# chiave -> (codice FRED, verso). Verso -1 = FRED quota "valuta estera per 1 dollaro" (es. JPY per USD),
# quindi il prezzo della valuta in dollari e' 1/x. Senza questa inversione il segno del modello sarebbe sbagliato.
PRICES = {
    "EUR": ("DEXUSEU", 1), "GBP": ("DEXUSUK", 1), "AUD": ("DEXUSAL", 1), "NZD": ("DEXUSNZ", 1),
    "JPY": ("DEXJPUS", -1), "CHF": ("DEXSZUS", -1), "CAD": ("DEXCAUS", -1), "MXN": ("DEXMXUS", -1),
    "BRL": ("DEXBZUS", -1), "ZAR": ("DEXSFUS", -1), "DXY": ("DTWEXBGS", 1),
    "SP500": ("SP500", 1), "NASDAQ": ("NASDAQCOM", 1), "DOW": ("DJIA", 1),
    "WTI": ("DCOILWTICO", 1), "BRENT": ("DCOILBRENTEU", 1), "NATGAS": ("DHHNGSP", 1),
    "BTC": ("CBBTCUSD", 1), "ETH": ("CBETHUSD", 1),
}

# Driver di mercato: indicatori prezzati OGNI GIORNO dal mercato (quindi gia' "scontano" le notizie).
# (chiave, nome, codice FRED, unita'). "diff" non esiste su FRED: e' calcolato come tasso USA 2a - tasso euro 2a (BCE).
DRIVERS = [
    ("us2y", "Tasso USA 2 anni", "DGS2", "pb"),
    ("real", "Rendimento reale USA 10a", "DFII10", "pb"),
    ("be", "Inflazione attesa USA 10a", "T10YIE", "pb"),
    ("vix", "VIX (paura)", "VIXCLS", "pt"),
    ("hy", "Spread obbligazioni high yield", "BAMLH0A0HYM2", "pb"),
    ("diff", "Differenziale 2a USA - Europa", None, "pb"),
]

# Tutte le serie FRED da scaricare -> fattore di scala. RRPONTSYD e' in miliardi: x1000 per avere milioni
# come WALCL e WTREGEN, cosi' si possono sommare/sottrarre.
FRED_IDS = {
    "WALCL": 1,          # bilancio Fed (milioni $, dato del mercoledi')
    "WTREGEN": 1,        # conto del Tesoro presso la Fed, TGA (milioni $)
    "RRPONTSYD": 1000,   # reverse repo overnight (miliardi $ -> milioni)
    "DGS2": 1, "DGS10": 1, "DFII10": 1, "T10YIE": 1, "VIXCLS": 1, "BAMLH0A0HYM2": 1,
    **{v[0]: 1 for v in PRICES.values()},
}

# --------------------------------------------------------------------------- serie BCE (tassi euro)
# v6.35: tolti i tassi dei mutui (MIR) e il mutuo USA 30 anni insieme alla scheda Mutui: non servono a chi fa trading.
# Ogni richiesta e' (flusso, chiave SDMX). Il "+" chiede piu' valori in una volta sola
# (es. IT+U2+DE = Italia, Eurozona, Germania).
ECB_REQ = [
    ("FM", "M.U2.EUR.RT.MM.EURIBOR3MD_.HSTA"),                # Euribor 3 mesi (mensile)
    ("EST", "B.EU000A2X2A25.WT"),                              # ESTR (tasso overnight, giornaliero)
    ("YC", "B.U2.EUR.4F.G_N_A.SV_C_YM.SR_2Y+SR_10Y"),          # curva titoli di Stato AAA: 2 e 10 anni
    ("FM", "D.U2.EUR.4F.KR.DFR.LEV"),                          # tasso BCE sui depositi
]
K_MIR = "MIR.M.{c}.B.A2C.{m}.R.A.2250.EUR.N"   # modello di chiave: {c}=paese, {m}=tipo di tasso
K_EURIBOR = "FM.M.U2.EUR.RT.MM.EURIBOR3MD_.HSTA"
K_ESTR = "EST.B.EU000A2X2A25.WT"
K_Y2 = "YC.B.U2.EUR.4F.G_N_A.SV_C_YM.SR_2Y"
K_Y10 = "YC.B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y"
K_DFR = "FM.D.U2.EUR.4F.KR.DFR.LEV"
COUNTRIES = [("IT", "Italia"), ("U2", "Eurozona"), ("DE", "Germania"), ("FR", "Francia"), ("ES", "Spagna")]

# --------------------------------------------------------------------------- percorsi dei file
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # cartella principale del progetto
WEB_DIR = os.path.join(ROOT, "web")                                    # template HTML/CSS/JS
CACHE = os.path.join(ROOT, "dati", "cache.json")                       # ultima copia dei dati scaricati
# CANALE TELEGRAM pubblico (gratuito): link nella sidebar del terminale e nella landing page (vetrina.py)
TELEGRAM_CANALE = "https://t.me/edgeboard"
# SITO: la landing page sta nella radice, il terminale nella sottocartella TERMINALE (vedi main.py e vetrina.py)
TERMINALE = "terminale"
# STATISTICHE DI VISITA anonime e senza cookie (Umami, cloud.umami.is), vedi web/statistiche.js.
# Qui va il "Website ID" del sito su Umami (pubblico: compare comunque nel codice della pagina, NON e' una chiave
# segreta). Vuoto = statistiche spente.
STATISTICHE_ID = "dbfc644a-1987-4769-9339-f231a41ecc8c"
# NOTE LEGALI (pagina /legale/, vedi web/legale.html e vetrina.py). TITOLARE vuoto = descrizione generica del
# servizio; prima di vendere abbonamenti va indicato chi gestisce il servizio (nome o ditta, P.IVA, sede).
TITOLARE = ""
# FEEDBACK DEGLI UTENTI (pulsante "Feedback" nella sidebar, web/js/26_feedback.js): "Access Key" di Web3Forms
# (web3forms.com, gratuito: i messaggi arrivano all'email con cui si crea la chiave). E' una chiave PUBBLICA per
# progetto (sta comunque nel codice della pagina), ma la si puo' anche mettere nel Secret WEB3FORMS_KEY: se c'e',
# vince il Secret. Vuota = modulo visibile ma "in attivazione".
FEEDBACK_CHIAVE = ""
CONTATTO_EMAIL = ""      # e-mail pubblica per segnalazioni e richieste; vuota = contatto tramite il canale Telegram
OUT = os.path.join(ROOT, "cot_radar.html")                             # dashboard creata in locale
REGISTRO = os.path.join(ROOT, "dati", "registro.log")                  # file di registro (a rotazione)
STATO = os.path.join(ROOT, "dati", "stato.json")                       # riepilogo dell'ultima esecuzione

# --------------------------------------------------------------------------- grafici a candele (TradingView)
# Simbolo TradingView da aprire al clic su ogni strumento/coppia. Formato "BORSA:SIMBOLO".
#   FX:      cambi spot (forex)            OANDA:  CFD (indici, metalli)
#   TVC:     indici/rendimenti di riferimento   "1!" = futures continuo (contratto piu' vicino)
# "inv": True = il grafico e' quotato al contrario rispetto al segnale (es. JPY: BUY yen = USDJPY che SCENDE).
# Per cambiare un simbolo basta modificarlo qui: provalo prima su tradingview.com.
TV_SYMBOLS = {
    # valute (contro dollaro)
    "EUR": ("FX:EURUSD", False), "GBP": ("FX:GBPUSD", False), "AUD": ("FX:AUDUSD", False),
    "NZD": ("FX:NZDUSD", False), "JPY": ("FX:USDJPY", True), "CHF": ("FX:USDCHF", True),
    "CAD": ("FX:USDCAD", True), "MXN": ("FX:USDMXN", True), "BRL": ("FX_IDC:USDBRL", True),
    "ZAR": ("FX:USDZAR", True), "DXY": ("TVC:DXY", False), "USD": ("TVC:DXY", False),
    # indici azionari (CFD) e volatilita'
    "SP500": ("OANDA:SPX500USD", False), "NASDAQ": ("OANDA:NAS100USD", False), "DOW": ("OANDA:US30USD", False),
    "RUSSELL": ("OANDA:US2000USD", False), "EAFE": ("AMEX:EFA", False), "EM": ("AMEX:EEM", False),
    "VIX": ("TVC:VIX", False),
    # tassi: il grafico e' il RENDIMENTO, che si muove al contrario del prezzo del futures
    "US2Y": ("TVC:US02Y", True), "US5Y": ("TVC:US05Y", True), "US10Y": ("TVC:US10Y", True),
    "USBOND": ("TVC:US30Y", True), "ULTRA": ("TVC:US30Y", True), "FEDFUNDS": ("CBOT:ZQ1!", False),
    "SOFR": ("CME:SR31!", False),
    # energia
    "WTI": ("TVC:USOIL", False), "BRENT": ("TVC:UKOIL", False), "NATGAS": ("NYMEX:NG1!", False),
    "HEATOIL": ("NYMEX:HO1!", False), "GASOLINE": ("NYMEX:RB1!", False),
    # metalli
    "GOLD": ("OANDA:XAUUSD", False), "SILVER": ("OANDA:XAGUSD", False), "COPPER": ("COMEX:HG1!", False),
    "PLATINUM": ("OANDA:XPTUSD", False), "PALLADIUM": ("OANDA:XPDUSD", False),
    # agricoli e bestiame (futures continui)
    "CORN": ("CBOT:ZC1!", False), "SOY": ("CBOT:ZS1!", False), "SOYOIL": ("CBOT:ZL1!", False),
    "SOYMEAL": ("CBOT:ZM1!", False), "WHEAT": ("CBOT:ZW1!", False), "KCWHEAT": ("CBOT:KE1!", False),
    "RICE": ("CBOT:ZR1!", False), "SUGAR": ("ICEUS:SB1!", False), "COFFEE": ("ICEUS:KC1!", False),
    "COCOA": ("ICEUS:CC1!", False), "COTTON": ("ICEUS:CT1!", False), "OJ": ("ICEUS:OJ1!", False),
    "CATTLE": ("CME:LE1!", False), "FEEDER": ("CME:GF1!", False), "HOGS": ("CME:HE1!", False),
    "MILK": ("CME:DC1!", False),
    # crypto
    "BTC": ("BITSTAMP:BTCUSD", False), "ETH": ("BITSTAMP:ETHUSD", False),
}
# coppie che non sono "FX:" + nome
TV_PAIRS = {"XAUUSD": "OANDA:XAUUSD", "XAGUSD": "OANDA:XAGUSD", "USDBRL": "FX_IDC:USDBRL"}
