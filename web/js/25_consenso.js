
/* ---------- CONSENSO LEGALE prima di usare la dashboard ----------
   Al primo accesso (e a ogni nuova versione del testo) un popup a tutto schermo mostra le condizioni d'uso.
   - Il pulsante "Accetto" si attiva solo dopo aver fatto scorrere il testo FINO IN FONDO (barra di avanzamento).
   - "Accetto": si salva nel browser (localStorage "eb_consenso" + cookie tecnico di 1 anno + sessione) e il popup
     non torna piu' a ogni accesso,
     finche' non cambia CONSENSO_VERSIONE (cambiando il testo, alzare la versione: tutti devono riaccettare).
   - "Non accetto": la dashboard resta coperta con un messaggio e il pulsante "Rileggi le condizioni".
   - Se il browser non permette di salvare (navigazione privata) il consenso vale per la sessione aperta.
   Il testo completo sta nelle Note legali (/legale/), qui c'e' la sintesi che l'utente deve accettare.
   Nelle statistiche anonime conta come evento "consenso" (accettato / rifiutato). */
(function(){try{
 const CONSENSO_VERSIONE="2026-10-27";
 // Il consenso si ricorda in TRE posti (come fanno i grandi siti), cosi' non viene richiesto a ogni accesso anche
 // se un browser ne cancella uno: archiviazione locale (principale), cookie tecnico di 1 anno (alcuni browser e le
 // app tipo Telegram/Instagram svuotano l'archiviazione locale ma tengono i cookie) e archiviazione di sessione
 // (navigazione privata: vale finche' la finestra resta aperta). Basta che UNO dei tre abbia la versione giusta.
 const COOKIE="eb_consenso",GIORNI=365;
 const leggiCookie=()=>{try{const m=document.cookie.match(/(?:^|;\s*)eb_consenso=([^;]+)/);return m?decodeURIComponent(m[1]):null;}catch(e){return null;}};
 function ricorda(){const ora=new Date().toISOString();
  try{localStorage.setItem("eb_consenso",JSON.stringify({versione:CONSENSO_VERSIONE,data:ora}));}catch(e){}
  try{document.cookie=`${COOKIE}=${encodeURIComponent(CONSENSO_VERSIONE)}; Max-Age=${GIORNI*86400}; Path=/; SameSite=Lax; Secure`;}catch(e){}
  try{sessionStorage.setItem("eb_consenso",CONSENSO_VERSIONE);}catch(e){}
  window.__ebConsenso=true;}
 const salvato=()=>{
  try{const v=JSON.parse(localStorage.getItem("eb_consenso")||"null");if(v&&v.versione==CONSENSO_VERSIONE){
   if(leggiCookie()!=CONSENSO_VERSIONE)ricorda();          // chi ha accettato prima di v6.37: aggiunge il cookie di riserva
   return true;}}catch(e){}
  if(leggiCookie()==CONSENSO_VERSIONE){try{localStorage.setItem("eb_consenso",JSON.stringify({versione:CONSENSO_VERSIONE,data:new Date().toISOString()}));}catch(e){}return true;}
  try{if(sessionStorage.getItem("eb_consenso")==CONSENSO_VERSIONE)return true;}catch(e){}
  return window.__ebConsenso===true;};
 if(salvato())return;
 const TESTO=`
  <h4>1. Che cos'&egrave; BoardEdge</h4>
  <p>BoardEdge &egrave; uno strumento di <b>informazione, studio e didattica</b> sui mercati finanziari. Mostra dati pubblici (CFTC, FRED, BCE, Yahoo Finance, SEC) elaborati con modelli statistici: segnali COT, punteggi, stagionalit&agrave;, correlazioni, pattern, portafogli modello e selezioni di azioni.</p>
  <h4>2. Non &egrave; consulenza finanziaria</h4>
  <p>Nessun contenuto costituisce consulenza in materia di investimenti, raccomandazione personalizzata, sollecitazione o offerta all'acquisto o alla vendita di strumenti finanziari (D.Lgs. 58/1998 &ndash; TUF, direttiva MiFID II). Espressioni come &laquo;BUY&raquo;, &laquo;SELL&raquo;, &laquo;strong BUY&raquo;, &laquo;le 5 azioni pi&ugrave; forti&raquo; o &laquo;portafoglio aggressivo&raquo; sono <b>etichette di un modello</b>, generiche e uguali per tutti: non tengono conto della tua situazione, dei tuoi obiettivi o della tua tolleranza al rischio.</p>
  <h4>3. Rischi</h4>
  <p>Investire comporta il rischio di perdere in parte o del tutto il capitale. Il trading su futures, forex, CFD e criptovalute, soprattutto con leva, pu&ograve; generare perdite <b>superiori al capitale investito</b>.</p>
  <h4>4. Risultati passati e simulazioni</h4>
  <p>Backtest, statistiche storiche e simulazioni (compreso lo storico delle azioni scelte, calcolato con le aziende presenti oggi negli indici) <b>non garantiscono risultati futuri</b>. Contano come verifica solo i registri live, che non vengono mai modificati.</p>
  <h4>5. Dati</h4>
  <p>I dati arrivano da fonti esterne e possono contenere ritardi, errori o interruzioni. BoardEdge segnala le anomalie che rileva ma non pu&ograve; garantire completezza, esattezza o disponibilit&agrave; continua del servizio.</p>
  <h4>6. Responsabilit&agrave;</h4>
  <p>Ogni decisione di investimento &egrave; presa da te, in autonomia e sotto la tua esclusiva responsabilit&agrave;. BoardEdge e i suoi autori non rispondono di perdite o danni, diretti o indiretti, derivanti dall'uso delle informazioni pubblicate. Prima di investire valuta di rivolgerti a un consulente finanziario abilitato.</p>
  <h4>7. Uso dei contenuti</h4>
  <p>I contenuti sono per uso personale. Non &egrave; consentito copiarli, ripubblicarli o rivenderli senza autorizzazione scritta (diritto d'autore e banca dati, L. 633/1941).</p>
  <h4>8. Privacy</h4>
  <p>Niente cookie pubblicitari o di profilazione. Statistiche di visita anonime senza cookie (Umami). Il browser ricorda l'accesso e questo consenso (archiviazione locale). I messaggi inviati con &laquo;Feedback&raquo; arrivano solo al team BoardEdge via email e non vengono pubblicati.</p>
  <p class="small">Testo completo: <a href="../legale/" target="_blank" rel="noopener">Note legali</a>. Versione del ${CONSENSO_VERSIONE.split("-").reverse().join("/")}.</p>`;
 const box=document.createElement("div");box.className="cmodal";
 box.innerHTML=`<div class="cmodal-box" role="dialog" aria-modal="true" aria-labelledby="cmt">
   <div class="cmodal-testa"><span class="cmodal-ico" aria-hidden="true">&sect;</span><div><h3 id="cmt">Prima di entrare</h3><p>Leggi le condizioni d'uso fino in fondo per continuare.</p></div></div>
   <div class="cmodal-avanz" aria-hidden="true"><i></i></div>
   <div class="cmodal-testo" tabindex="0">${TESTO}</div>
   <div class="cmodal-piede"><span class="cmodal-hint">Scorri fino in fondo per attivare &laquo;Accetto&raquo;</span>
    <div class="cmodal-btn"><button class="cno">Non accetto</button><button class="csi" disabled>Accetto</button></div></div></div>`;
 const blocco=document.createElement("div");blocco.className="cmodal cblocco";blocco.hidden=true;
 blocco.innerHTML=`<div class="cmodal-box cmodal-picc" role="alertdialog" aria-modal="true"><span class="cmodal-ico" aria-hidden="true">&sect;</span>
   <h3>Accesso non disponibile</h3><p>Per usare la dashboard &egrave; necessario accettare le condizioni d'uso.</p>
   <div class="cmodal-btn"><a class="cno" href="../">Torna alla home</a><button class="csi crileggi">Rileggi le condizioni</button></div></div>`;
 document.documentElement.classList.add("cbloccato");                    // niente scorrimento della pagina sotto
 document.body.appendChild(box);document.body.appendChild(blocco);
 requestAnimationFrame(()=>box.classList.add("on"));
 const testo=box.querySelector(".cmodal-testo"),si=box.querySelector(".csi"),barra=box.querySelector(".cmodal-avanz i"),hint=box.querySelector(".cmodal-hint");
 // avanzamento della lettura: "Accetto" si attiva arrivati in fondo (con 8px di tolleranza)
 function controlla(){const max=testo.scrollHeight-testo.clientHeight,p=max<=0?1:Math.min(1,testo.scrollTop/max);
  barra.style.width=(p*100).toFixed(1)+"%";
  if(p>=0.995||max-testo.scrollTop<=8){si.disabled=false;hint.textContent="Grazie per aver letto. Puoi accettare.";hint.classList.add("ok");}}
 testo.addEventListener("scroll",controlla,{passive:true});setTimeout(controlla,50);
 const stat=(esito)=>{try{window.ebStat&&ebStat.ev("consenso",{esito});}catch(e){}};
 si.onclick=()=>{ricorda();
  stat("accettato");box.classList.remove("on");setTimeout(()=>box.remove(),220);blocco.remove();document.documentElement.classList.remove("cbloccato");};
 box.querySelector(".cno").onclick=()=>{stat("rifiutato");box.classList.remove("on");setTimeout(()=>{box.hidden=true;blocco.hidden=false;requestAnimationFrame(()=>blocco.classList.add("on"));},200);};
 blocco.querySelector(".crileggi").onclick=()=>{blocco.classList.remove("on");blocco.hidden=true;box.hidden=false;requestAnimationFrame(()=>box.classList.add("on"));testo.focus({preventScroll:true});};
}catch(e){console.error("[BoardEdge] consenso:",e);}})();
