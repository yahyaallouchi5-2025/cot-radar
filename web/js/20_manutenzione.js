
/* ---------- avviso di MANUTENZIONE (comune a tutte le schede) ----------
   ebManutenzione({scheda, codice, quando, dal}) mostra UN popup quando la scheda diventa visibile:
     "Manutenzione in corso · Errore server 503 · I dati non sono stati aggiornati.
      Anomalia rilevata il 26/10/2026 alle 22:15 · Ultimo aggiornamento disponibile: 23/10/2026"
   - una volta per sessione per ogni scheda e anomalia (sessionStorage "ebAvv:<scheda>:<quando>");
   - nessuna barra fissa: chiuso il popup la scheda resta pulita con gli ultimi dati validi;
   - si chiude con "Ho capito", clic fuori o Esc. Nelle statistiche anonime conta come evento "avviso".
   I dettagli tecnici (quali titoli, quale errore) restano nel registro admin e nella mail di GitHub. */
window.ebManutenzione=function(o){try{
 const el=document.getElementById(o.scheda);if(!el||!o)return;
 const gg=d=>d?d.slice(8,10)+"/"+d.slice(5,7)+"/"+d.slice(0,4):"";
 const quando=o.quando?`Anomalia rilevata il ${gg(o.quando.slice(0,10))}${o.quando.length>10?" alle "+o.quando.slice(11,16):""}`:"";
 const chiave="ebAvv:"+o.scheda+":"+(o.quando||o.dal||"1");
 function mostra(){
  try{if(sessionStorage.getItem(chiave))return;sessionStorage.setItem(chiave,"1");}catch(e){}
  if(document.querySelector(".pmodal"))return;                       // un popup alla volta
  const box=document.createElement("div");box.className="pmodal";
  box.innerHTML=`<div class="pmodal-box" role="alertdialog" aria-modal="true" aria-labelledby="pmt">
   <span class="pav-i grande" aria-hidden="true">!</span><h3 id="pmt">Manutenzione in corso</h3>
   <p>Errore server ${String(o.codice||"503").replace(/[^0-9A-Za-z-]/g,"")} &middot; I dati non sono stati aggiornati.</p>
   ${quando?`<p class="pmodal-q">${quando}</p>`:""}${o.dal?`<p class="small">Ultimo aggiornamento disponibile: ${gg(o.dal)}</p>`:""}
   <p class="small">Stiamo intervenendo: la scheda si aggiorna da sola appena il servizio torna regolare.</p>
   <button class="pmodal-ok">Ho capito</button></div>`;
  const chiudi=()=>{box.classList.remove("on");setTimeout(()=>box.remove(),220);document.removeEventListener("keydown",tasto);};
  const tasto=e=>{if(e.key=="Escape")chiudi();};
  box.addEventListener("click",e=>{if(e.target==box||e.target.classList.contains("pmodal-ok"))chiudi();});
  document.addEventListener("keydown",tasto);document.body.appendChild(box);
  requestAnimationFrame(()=>box.classList.add("on"));box.querySelector(".pmodal-ok").focus({preventScroll:true});
  try{window.ebStat&&ebStat.ev("avviso",{scheda:o.scheda});}catch(e){}}
 // il popup parte quando la scheda e' davvero visibile (non all'apertura della pagina su un'altra scheda)
 if(el.offsetParent!==null){mostra();return;}
 // la scheda diventa visibile con la classe "on" (navigazione): si osserva quella, non la geometria
 const mo=new MutationObserver(()=>{if(el.classList.contains("on")){mo.disconnect();mostra();}});
 mo.observe(el,{attributes:true,attributeFilter:["class"]});
}catch(e){console.error("[BoardEdge] avviso di manutenzione:",e);}};
