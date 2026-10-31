"""PROFILO DELLE AZIENDE (v6.52): la scheda "chi e'" di ogni titolo dell'Azionario.

Cosa contiene (solo il necessario, in italiano dove possibile):
  - descrizione breve (cosa fa e cosa produce): riassunto di Wikipedia in italiano (in inglese se manca);
  - anno di fondazione, sede e paese, amministratore delegato (CEO), numero di dipendenti (ultimo dato);
  - borse dove e' quotata;
  - se negli ultimi 10 anni e' stata acquistata, da chi e in che anno.
Fonti libere e gratuite: Wikidata (dati strutturati, interrogazione SPARQL) e Wikipedia (riassunto della voce).
Il settore e il listino arrivano gia' dai dati di BoardEdge (azioni.py).

Come lavora (dentro il workflow Azioni, mai bloccante):
  - il ticker di Yahoo viene tradotto nel ticker di borsa di Wikidata (es. 0700.HK -> 700 su Hong Kong) e la borsa
    giusta e' riconosciuta dal suffisso, cosi' due aziende con lo stesso ticker su borse diverse non si confondono;
  - ogni profilo si riscarica al massimo una volta ogni 30 giorni, al massimo 300 titoli per giro (i dati cambiano
    di rado: CEO, dipendenti, acquisizioni);
  - User-Agent onesto con il nome del servizio e il contatto (Secret SEC_CONTATTO), come chiede Wikimedia.
Limite noto: "in vendita" non e' un dato pubblico affidabile, quindi non viene mostrato.
File scritto: pubblico/profili/<TICKER>.json (letto dalla scheda del titolo, solo quando la si apre)."""
import json
import logging
import os
import time
import urllib.parse
import urllib.request
from datetime import date, timedelta

from . import azioni as A

log = logging.getLogger(__name__)
SPARQL = "https://query.wikidata.org/sparql"
RIASSUNTO = "https://{lingua}.wikipedia.org/api/rest_v1/page/summary/{titolo}"
GIORNI_VALIDITA = 30            # un profilo si riscarica dopo 30 giorni
MAX_PER_GIRO = 300              # titoli aggiornati al massimo in un giro
LOTTO = 60                      # ticker per interrogazione SPARQL
PAUSA = 0.2                     # secondi tra le richieste a Wikipedia

# suffisso del ticker Yahoo -> parole che devono comparire nel nome (inglese) della borsa su Wikidata
BORSE = {"": ("nasdaq", "new york stock exchange", "nyse"), "MI": ("borsa italiana", "milan", "italian"),
         "DE": ("frankfurt", "xetra"), "PA": ("paris",), "AS": ("amsterdam",), "MC": ("madrid", "spanish"),
         "BR": ("brussels",), "HE": ("helsinki",), "T": ("tokyo",), "HK": ("hong kong",),
         "SS": ("shanghai",), "SZ": ("shenzhen",), "NS": ("national stock exchange of india", "bombay")}


def _ua():
    c = os.environ.get("SEC_CONTATTO", "").strip()
    return "BoardEdge/1.0 (https://github.com/yahyaallouchi5-2025/cot-radar" + (f"; {c}" if "@" in c else "") + ")"


def _get(url, timeout=40):
    req = urllib.request.Request(url, headers={"User-Agent": _ua(), "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def _sparql(q):
    return _get(SPARQL + "?format=json&query=" + urllib.parse.quote(q))["results"]["bindings"]


def ticker_borsa(t):
    """Ticker Yahoo -> (ticker come su Wikidata, suffisso). Hong Kong senza zeri iniziali (0700.HK -> 700)."""
    base, _, suf = t.partition(".")
    if suf == "HK":
        base = base.lstrip("0") or "0"
    return base.replace("-", "."), suf


def _v(b, k):
    return (b.get(k) or {}).get("value")


def _qid(url):
    return url.rsplit("/", 1)[-1] if url else None


def trova_item(lotto):
    """{ticker Yahoo: QID} per un lotto di ticker, scegliendo la borsa coerente con il suffisso."""
    per_tk = {}
    for t in lotto:
        tk, suf = ticker_borsa(t)
        per_tk.setdefault(tk, []).append((t, suf))
    valori = " ".join(json.dumps(k) for k in per_tk)
    righe = _sparql(f"""SELECT ?tk ?item ?exL WHERE {{ VALUES ?tk {{ {valori} }}
      ?item p:P414 ?st . ?st ps:P414 ?ex; pq:P249 ?tk . ?ex rdfs:label ?exL FILTER(lang(?exL)="en") }}""")
    candidati = {}
    for b in righe:
        candidati.setdefault(_v(b, "tk"), []).append((_qid(_v(b, "item")), (_v(b, "exL") or "").lower()))
    out = {}
    for tk, lista in per_tk.items():
        for t, suf in lista:
            c = candidati.get(tk, [])
            buoni = [q for q, ex in c if any(p in ex for p in BORSE.get(suf, ()))]
            scelta = buoni or ([c[0][0]] if len({q for q, _ in c}) == 1 and c else [])
            if scelta:
                out[t] = scelta[0]
    return out


def fatti(qids):
    """Dati strutturati per una lista di QID: fondazione, CEO, sede, paese, sito, voci Wikipedia, borse,
    dipendenti (ultimo dato), acquisizioni fatte e subite negli ultimi 10 anni."""
    val = " ".join("wd:" + q for q in qids)
    out = {q: {"ceo": [], "borse": [], "acq": [], "da": [], "dip": []} for q in qids}
    for b in _sparql(f"""SELECT ?item (MIN(?inc) AS ?fond) (SAMPLE(?hqL) AS ?sede) (SAMPLE(?paL) AS ?paese)
      (SAMPLE(?itA) AS ?it) (SAMPLE(?enA) AS ?en) (SAMPLE(?sito) AS ?web) WHERE {{ VALUES ?item {{ {val} }}
      OPTIONAL{{?item wdt:P571 ?inc}}
      OPTIONAL{{?item wdt:P159 ?h. ?h rdfs:label ?hqL FILTER(lang(?hqL)="it")}}
      OPTIONAL{{?item wdt:P17 ?p. ?p rdfs:label ?paL FILTER(lang(?paL)="it")}}
      OPTIONAL{{?itA schema:about ?item; schema:isPartOf <https://it.wikipedia.org/>}}
      OPTIONAL{{?enA schema:about ?item; schema:isPartOf <https://en.wikipedia.org/>}}
      OPTIONAL{{?item wdt:P856 ?sito}} }} GROUP BY ?item"""):
        q = _qid(_v(b, "item"))
        out[q].update({"fond": (_v(b, "fond") or "")[:4] or None, "sede": _v(b, "sede"), "paese": _v(b, "paese"),
                       "it": _v(b, "it"), "en": _v(b, "en"), "web": _v(b, "web")})
    for b in _sparql(f"""SELECT ?item ?l WHERE {{ VALUES ?item {{ {val} }} ?item wdt:P169 ?c.
      ?c rdfs:label ?l FILTER(lang(?l)="en") }}"""):
        out[_qid(_v(b, "item"))]["ceo"].append(_v(b, "l"))
    for b in _sparql(f"""SELECT ?item ?l WHERE {{ VALUES ?item {{ {val} }} ?item wdt:P414 ?e.
      ?e rdfs:label ?l FILTER(lang(?l)="it") }}"""):
        out[_qid(_v(b, "item"))]["borse"].append(_v(b, "l"))
    for b in _sparql(f"""SELECT ?item ?n ?d WHERE {{ VALUES ?item {{ {val} }} ?item p:P1128 ?s. ?s ps:P1128 ?n.
      OPTIONAL{{?s pq:P585 ?d}} }}"""):
        out[_qid(_v(b, "item"))]["dip"].append((_v(b, "d") or "", _v(b, "n")))
    anno_min = date.today().year - 10
    # "acquisita da" negli ultimi 10 anni (proprietario con data d'inizio). Le acquisizioni FATTE dall'azienda
    # su Wikidata sono troppo incomplete (e l'interrogazione inversa e' lenta): non vengono mostrate.
    try:
        for b in _sparql(f"""SELECT ?item ?xL ?inizio WHERE {{ VALUES ?item {{ {val} }}
          ?item p:P127 ?s. ?s ps:P127 ?x; pq:P580 ?inizio. FILTER(YEAR(?inizio) >= {date.today().year - 10})
          ?x rdfs:label ?xL FILTER(lang(?xL)="en") }}"""):
            voce = {"nome": _v(b, "xL"), "anno": int((_v(b, "inizio") or "0")[:4])}
            lista = out[_qid(_v(b, "item"))]["da"]
            if voce["nome"] not in [x["nome"] for x in lista]:
                lista.append(voce)
    except Exception as e:
        log.warning("profili: proprietari non scaricati (%s)", type(e).__name__)
    return out


def riassunto(url_voce):
    """Prime 2 frasi del riassunto di Wikipedia (max ~360 caratteri). None se la voce non c'e'."""
    if not url_voce:
        return None
    lingua = url_voce.split("//", 1)[1].split(".", 1)[0]
    titolo = url_voce.rsplit("/wiki/", 1)[-1]
    try:
        testo = (_get(RIASSUNTO.format(lingua=lingua, titolo=titolo)) or {}).get("extract") or ""
    except Exception as e:
        log.warning("profili: riassunto %s non scaricato (%s)", titolo, type(e).__name__)
        return None
    frasi, out = testo.replace("\n", " ").split(". "), ""
    for f in frasi:
        if len(out) + len(f) > 360 and out:
            break
        out += f.rstrip(".") + ". "
    return {"testo": out.strip(), "lingua": lingua, "url": url_voce} if out.strip() else None


def componi(t, f, desc, oggi):
    """Il profilo pubblicato (compatto). Dipendenti: il dato piu' recente."""
    dip = sorted((d, n) for d, n in f.get("dip", []) if n)
    return {"t": t, "agg": oggi.isoformat(), "desc": desc, "fondata": f.get("fond"), "sede": f.get("sede"),
            "paese": f.get("paese"), "ceo": sorted(set(f.get("ceo", [])))[:2],
            "dipendenti": {"n": int(float(dip[-1][1])), "anno": dip[-1][0][:4] or None} if dip else None,
            "borse": sorted(set(f.get("borse", [])))[:4],
            "acquisita_da": sorted(f.get("da", []), key=lambda x: -x["anno"])[:1],
            "sito": f.get("web"), "fonte": "Wikidata e Wikipedia"}


def aggiorna(cartella, oggi=None, el=None, pausa=PAUSA):
    """Aggiorna i profili scaduti (piu' vecchi di 30 giorni o mancanti), al massimo MAX_PER_GIRO per giro."""
    oggi = oggi or date.today()
    titoli = [x["t"] for x in (el if el is not None else A.elenco())]
    file_di = lambda t: os.path.join(cartella, "pubblico", "profili", A._nome_file(t) + ".json")
    limite = (oggi - timedelta(days=GIORNI_VALIDITA)).isoformat()
    da_fare = [t for t in titoli if ((A._leggi(file_di(t)) or {}).get("agg") or "") < limite][:MAX_PER_GIRO]
    fatti_ok, mancanti = 0, []
    for i in range(0, len(da_fare), LOTTO):
        lotto = da_fare[i:i + LOTTO]
        try:
            qid = trova_item(lotto)
            dati = fatti(sorted(set(qid.values()))) if qid else {}
        except Exception as e:                      # Wikidata lento o giu': riprova al prossimo giro, niente blocchi
            log.warning("profili: lotto %d non scaricato (%s: %s)", i // LOTTO + 1, type(e).__name__, e)
            continue
        for t in lotto:
            if t not in qid:
                mancanti.append(t)
                continue
            f = dati.get(qid[t], {})
            desc = riassunto(f.get("it")) or riassunto(f.get("en"))
            if pausa:
                time.sleep(pausa)
            A._scrivi(file_di(t), componi(t, f, desc, oggi))
            fatti_ok += 1
    log.info("profili aziende: %d aggiornati, %d senza voce su Wikidata", fatti_ok, len(mancanti))
    return {"aggiornati": fatti_ok, "mancanti": mancanti}
