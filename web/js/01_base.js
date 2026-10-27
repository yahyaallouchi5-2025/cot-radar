/* ==========================================================================
   01_base.js - PRIMO dei file della pagina (web/js/, uniti in ordine di nome da pagina.py in un solo script)
   --------------------------------------------------------------------------
   Qui: aiuti comuni, protezione anti-crollo, etichette (i). Ogni altro file disegna UNA scheda:
     02_stato  03_navigazione  04_dashboard  05_forex  06_strumenti  07_macro  09_correlazioni
     10_stagionalita  11_guida  12_grafico  13_verifica  14_registro  20_manutenzione  21_portafogli
     22_azioni  23_vetrina_top5  24_pattern  (+ consenso legale e feedback: vedi i file 25_ e 26_)
   Un errore in una scheda resta chiuso nel suo try/catch: le altre schede continuano a funzionare.
   I dati arrivano da Python nella costante D (vedi index.html):
     D.meta      impostazioni e ora di aggiornamento      D.sources   stato di ogni fonte
     D.assets    ogni strumento (punteggi, COT, mercato)   D.pairs     coppie di valute
     D.market    driver di mercato                         D.corr_px   correlazioni dei prezzi
     D.fed       liquidita' Fed                            D.corr      matrice delle correlazioni
   Ogni sezione qui sotto riempie un pezzo di pagina (gli id corrispondono a quelli di index.html).
   Si usano "template literal" `...${valore}...` per costruire l'HTML.
   DEBUG: F12 -> Console. Scrivi D per vedere i dati, D.assets.EUR per un singolo strumento.
          Un errore in rosso nella Console indica file e riga del problema.
   ========================================================================== */
const M=D.meta;            // impostazioni (pesi, soglie, ora di aggiornamento)

const COL={"STRONG BUY":"var(--sb)","BUY":"var(--b)","NEUTRO":"var(--n)","SELL":"var(--s)","STRONG SELL":"var(--ss)"};
const fmt=n=>{if(n==null||isNaN(n))return"n/d";const r=Math.round(n);return(r>0?"+":"")+(r==0?0:r).toLocaleString("it-IT");};
const fx=(n,d=2)=>n==null||isNaN(n)?"n/d":n.toLocaleString("it-IT",{minimumFractionDigits:d,maximumFractionDigits:d});
const sg=(n,d=2)=>n==null||isNaN(n)?"n/d":(n>0?"+":"")+fx(n,d);
const c2=v=>{const t=v.toFixed(2);return t=="-0.00"?"0.00":t;};const c1=v=>{const t=v.toFixed(1);return t=="-0.0"?"0.0":t;};
const verb=s=>s>=20?["COMPRANO","up","▲"]:s<=-20?["VENDONO","down","▼"]:["neutri","flat","■"];
const badge=l=>`<span class="badge" style="--bc:${COL[l]}">${l}</span>`;   // pillola: bordo e testo nel colore del segnale
const pos=s=>Math.max(0,Math.min(100,(s+100)/2));
const nm=k=>(D.assets[k]||{}).name||k;
const esc=t=>String(t).replace(/[&<>]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));
const lab=s=>Math.abs(s)>=M.strong?(s>0?"STRONG BUY":"STRONG SELL"):Math.abs(s)>=M.normal?(s>0?"BUY":"SELL"):"NEUTRO";
const $=id=>document.getElementById(id);


/* ---------- aiuti comuni a piu' sezioni ---------- */
const SEC=D.sectors,byS={};Object.values(D.assets).forEach(a=>{if(a.key!="USD")(byS[a.group]=byS[a.group]||[]).push(a);});
const NOTE={"Tassi USA":"Futures sui titoli di Stato: COMPRARE = scommettere su tassi in calo.","VIX":"Sul VIX comprare = aspettarsi piu' volatilita'."};
function mtag(cot,mac){if(mac==null)return`<span class="tag">mercato: n/d</span>`;if(Math.abs(mac)<25)return`<span class="tag">mercato: gia' scontato</span>`;
 if(Math.abs(cot)<10)return`<span class="tag">mercato ${mac>0?'rialzista':'ribassista'}</span>`;
 return (mac>0)==(cot>0)?`<span class="tag ok">Mercato conferma</span>`:`<span class="tag ko">Mercato contro</span>`;}
const split=(cot,mac)=>`<div class="split"><div>COT (${Math.round((1-M.mw)*100)}%)<b>${fmt(cot)}</b></div><div>Mercato (${Math.round(M.mw*100)}%)<b>${mac==null?'n/d':fmt(mac)}</b></div></div>`;
/* ANELLO del punteggio: il numero e' l'intensita' (0-100, senza segno), il colore la direzione
   (verde = acquisto, rosso = vendita, grigio = neutro). L'arco pieno = punteggio 100. */
const anello=s=>{const v=Math.min(100,Math.abs(Math.round(s||0))),r=24,c=2*Math.PI*r,
 col=s>=M.normal?"var(--b)":s<=-M.normal?"var(--s)":"var(--n)";
 return `<div class="anello" title="Punteggio finale ${fmt(s)} (intensita' ${v}/100)"><svg viewBox="0 0 60 60"><circle cx="30" cy="30" r="${r}" class="fondo"/>`+
  `<circle cx="30" cy="30" r="${r}" class="arco" style="stroke:${col}" stroke-dasharray="${(c*v/100).toFixed(1)} ${c.toFixed(1)}" transform="rotate(-90 30 30)"/></svg><b>${v}</b><small>/100</small></div>`;};
const meter=s=>`<div class="meter"><i style="left:${pos(s)}%"></i></div><div class="scale"><span>-100 vendi</span><span>finale <b style="color:var(--ink)">${fmt(s)}</b></span><span>compra +100</span></div>`;
function fd(s){if(!s)return"";const m=["gen","feb","mar","apr","mag","giu","lug","ago","set","ott","nov","dic"];if(s.length==7)return m[+s.slice(5,7)-1]+" "+s.slice(0,4);return s.slice(8,10)+"/"+s.slice(5,7)+"/"+s.slice(0,4);}

/* ---------- PROTEZIONE ANTI-CROLLO ----------
   Ogni sezione qui sotto e' racchiusa in try { ... } catch: se una sezione ha un errore (bug o dati strani)
   al suo posto compare un riquadro "Sezione non disponibile" e TUTTE le altre continuano a funzionare.
   Gli errori imprevisti (anche dentro i clic) mostrano un avviso rosso in alto invece di una pagina bianca.
   DEBUG: F12 -> Console: ogni errore e' stampato con il nome della sezione. window.__errori li elenca tutti. */
window.__errori=[];
function fail(sezione,contenitore,e){
 window.__errori.push({sezione,errore:String(e&&e.stack||e)});
 try{window.ebStat&&ebStat.ev("errore",{sezione:sezione});}catch(_){}   // statistiche: quali sezioni si rompono ai visitatori
 console.error("[BoardEdge] sezione '"+sezione+"' non disponibile:",e);
 const box=`<div class="alert red"><b>Sezione "${sezione}" non disponibile.</b> Errore: ${esc(e&&e.message||e)}. Le altre sezioni funzionano normalmente.</div>`;
 const el=contenitore&&document.getElementById(contenitore);
 if(el)el.insertAdjacentHTML("afterbegin",box);else{const a=document.getElementById("alerts");if(a)a.insertAdjacentHTML("beforeend",box);}
}
function bannerErrore(msg){const a=document.getElementById("alerts");if(a&&!a.querySelector(".js-err"))a.insertAdjacentHTML("afterbegin",`<div class="alert red js-err"><b>Errore imprevisto nella pagina:</b> ${esc(msg)}. Ricarica la pagina.</div>`);}
/* "ResizeObserver loop..." e' un avviso innocuo del browser (zoom, rotazione dello schermo): non e' un errore della pagina */
window.addEventListener("error",ev=>{if(/ResizeObserver loop/i.test(ev.message||""))return;
 window.__errori.push({sezione:"pagina",errore:String(ev.message)});bannerErrore(ev.message);});
/* ---------- ETICHETTE INFORMATIVE (i) ----------
   Le spiegazioni lunghe (<p class="sub"> subito dopo un titolo <h2>, e le note tra parentesi dei sottotitoli
   <h3 class="vft"> della Verifica) restano nascoste: accanto al titolo compare
   un pulsante "i" che le apre e chiude. La pagina resta pulita e i comandi si notano subito.
   Vale per tutte le schede, anche per quelle ridisegnate dopo un clic (MutationObserver). Una spiegazione aperta
   resta aperta quando la sua sezione si ridisegna (es. cambio di strumento): la ricordiamo per titolo in infoAperte.
   DEBUG: se un titolo non ha la "i", controlla che il paragrafo abbia class="sub" e venga SUBITO dopo l'<h2>. */
const infoAperte=new Set();
function etichetteInfo(root){
 // sottotitoli delle schede di Verifica: "Titolo <span class=small>(spiegazione)</span>" -> titolo pulito + paragrafo
 root.querySelectorAll("h3.vft>span.small").forEach(sp=>{const h=sp.parentNode,t=sp.textContent.trim().replace(/^\(|\)$/g,"");
  sp.remove();const p=document.createElement("p");p.className="sub";p.textContent=t.charAt(0).toUpperCase()+t.slice(1)+".";
  h.after(p);});
 root.querySelectorAll("p.sub:not(.infotesto)").forEach(p=>{const h=p.previousElementSibling;
  if(!h||!(h.tagName=="H2"||h.matches("h3.vft")))return;
  const k=h.textContent.trim(),ap=infoAperte.has(k);
  p.classList.add("infotesto");p.classList.toggle("aperta",ap);
  const b=document.createElement("button");
  Object.assign(b,{type:"button",className:"info",textContent:"i",title:"Spiegazione"});
  b.dataset.k=k;b.setAttribute("aria-label","Mostra o nascondi la spiegazione");b.setAttribute("aria-expanded",ap);
  h.appendChild(b);});}
document.addEventListener("click",e=>{const b=e.target.closest&&e.target.closest("button.info");if(!b)return;
 const p=b.dataset.apri?document.getElementById(b.dataset.apri):b.closest("h2,h3")&&b.closest("h2,h3").nextElementSibling;if(!p||!p.classList.contains("infotesto"))return;
 const ap=p.classList.toggle("aperta");b.setAttribute("aria-expanded",ap);
 if(ap)infoAperte.add(b.dataset.k);else infoAperte.delete(b.dataset.k);});
(()=>{const w=document.querySelector(".wrap");if(!w)return;etichetteInfo(w);
 new MutationObserver(()=>etichetteInfo(w)).observe(w,{childList:true,subtree:true});})();
/* VERSIONE NUOVA? Il browser (o GitHub Pages, ~10 minuti) puo' tenere in memoria la pagina vecchia.
   Ogni 10 minuti leggiamo stato.json "fresco": se e' piu' recente dei dati di questa pagina, compare
   un avviso con il pulsante per ricaricare. Solo sul sito (http/https), non sul file aperto dal PC. */
function controllaVersione(){if(!/^https?:/.test(location.protocol)||!D.stato||!D.stato.creato)return;
 fetch("stato.json?v="+Date.now(),{cache:"no-store"}).then(r=>r.ok?r.json():null).then(s=>{
  if(!s||!s.creato||s.creato<=D.stato.creato||s.esito=="scartato"||document.getElementById("nuovaversione"))return;
  const d=document.createElement("div");d.id="nuovaversione";d.className="alert";
  d.style.cssText="position:fixed;left:50%;bottom:16px;transform:translateX(-50%);z-index:60;display:flex;gap:12px;align-items:center;box-shadow:0 6px 24px rgba(0,0,0,.18)";
  d.innerHTML=`<span>&Egrave; disponibile una versione pi&ugrave; recente della dashboard.</span><button class="tvbtn" onclick="location.reload()">Aggiorna</button>`;
  document.body.appendChild(d);}).catch(()=>{});}   // senza rete: nessun avviso, nessun errore
controllaVersione();setInterval(controllaVersione,10*60*1000);
window.addEventListener("unhandledrejection",ev=>{window.__errori.push({sezione:"pagina",errore:String(ev.reason)});bannerErrore(ev.reason);});

