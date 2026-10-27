
/* ---------- VOTO A STELLE (popup discreto dopo un po' di navigazione) ----------
   Chiede un voto da 1 a 5 stelle (+ commento facoltativo) SOLO a chi usa davvero la dashboard, mai all'apertura:
   - si contano i clic "utili" (schede, pulsanti, righe cliccabili) anche tra una visita e l'altra (localStorage "eb_clic");
   - compare quando: almeno CLIC_MIN clic in totale E almeno SECONDI_MIN secondi in questa visita E consenso legale gia' dato
     E nessun'altra finestra aperta E l'utente non sta scrivendo. Parte 1,5 s dopo l'ultimo clic, per non interromperlo.
   - Una volta votato non torna MAI piu'. Se l'utente chiude o sceglie "Piu' tardi" torna dopo RIPROVA_GIORNI giorni,
     al massimo VOLTE_MAX volte in tutto: poi basta (eventuale voto resta possibile dal pulsante Feedback).
   - E' una scheda in basso a destra (su telefono un pannello in basso a tutta larghezza), NON blocca la pagina.
   Invio con Web3Forms, la stessa chiave del modulo Feedback (26_feedback.js): il voto arriva solo all'email dell'admin.
   Senza chiave il popup non compare proprio. Statistiche anonime: evento "voto" con il solo numero di stelle. */
(function(){try{
 const CHIAVE="__FEEDBACK_KEY__".indexOf("__")===0?"":"__FEEDBACK_KEY__";
 if(!CHIAVE||!document.getElementById("nav"))return;
 const CLIC_MIN=25,SECONDI_MIN=120,RIPROVA_GIORNI=21,VOLTE_MAX=2;
 const ETICHETTE=["Scarso","Così così","Buono","Molto buono","Ottimo"];
 const inizio=Date.now();
 const leggi=(k,d)=>{try{return JSON.parse(localStorage.getItem(k))??d;}catch(e){return d;}};
 const scrivi=(k,v)=>{try{localStorage.setItem(k,JSON.stringify(v));}catch(e){}};
 const stato=()=>leggi("eb_voto",{});
 function puoMostrare(){
  const s=stato();
  if(s.votato||(s.volte||0)>=VOLTE_MAX)return false;
  if(s.rimandato&&Date.now()-s.rimandato<RIPROVA_GIORNI*864e5)return false;
  if(leggi("eb_clic",0)<CLIC_MIN||Date.now()-inizio<SECONDI_MIN*1000)return false;
  const c=leggi("eb_consenso",null);if(!(c&&c.versione)&&window.__ebConsenso!==true)return false;
  if(document.querySelector(".cmodal:not([hidden]),.tvmodal:not([hidden]),.ebvoto"))return false;   // altre finestre aperte (grafico, consenso, feedback)
  const a=document.activeElement;if(a&&/^(INPUT|TEXTAREA|SELECT)$/.test(a.tagName))return false;  // sta scrivendo
  return true;}
 let timer=0;
 document.addEventListener("click",e=>{
  if(!e.target.closest("button,a,[role=tab],.clic,.sec,summary")||e.target.closest(".ebvoto"))return;
  scrivi("eb_clic",leggi("eb_clic",0)+1);
  clearTimeout(timer);timer=setTimeout(()=>{if(puoMostrare())mostra();},1500);},true);

 function mostra(){
  const s=stato();s.volte=(s.volte||0)+1;scrivi("eb_voto",s);
  let voto=0;
  const box=document.createElement("section");box.className="ebvoto";box.setAttribute("role","dialog");box.setAttribute("aria-labelledby","evt");
  box.innerHTML=`<button type="button" class="evx" aria-label="Chiudi">&#x2715;</button>
   <h3 id="evt">Ti sta piacendo BoardEdge?</h3><p class="evsub">Un voto da 1 a 5 stelle: ci vogliono 5 secondi e ci aiuta molto.</p>
   <div class="evstelle" role="radiogroup" aria-label="Voto da 1 a 5 stelle">${ETICHETTE.map((t,i)=>`<button type="button" role="radio" aria-checked="false" aria-label="${i+1} stell${i?"e":"a"}: ${t}" data-v="${i+1}" tabindex="${i?-1:0}"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2.8l2.8 5.9 6.4.8-4.7 4.4 1.2 6.4L12 17.2l-5.7 3.1 1.2-6.4-4.7-4.4 6.4-.8z"/></svg></button>`).join("")}</div>
   <div class="evetic" aria-live="polite">&nbsp;</div>
   <div class="evaltro" hidden><textarea rows="3" maxlength="1000" aria-label="Commento facoltativo"></textarea>
    <div class="evbtn"><button type="button" class="evdopo">Più tardi</button><button type="button" class="evinvia">Invia voto</button></div>
    <div class="evesito" role="status"></div></div>`;
  document.body.appendChild(box);requestAnimationFrame(()=>box.classList.add("on"));
  try{window.ebStat&&ebStat.ev("voto_mostrato");}catch(_){}
  const stelle=[...box.querySelectorAll(".evstelle button")],etic=box.querySelector(".evetic"),altro=box.querySelector(".evaltro"),
        ta=altro.querySelector("textarea"),invia=box.querySelector(".evinvia"),esito=box.querySelector(".evesito");
  const accendi=n=>stelle.forEach((b,i)=>b.classList.toggle("on",i<n));
  const chiudi=(rimanda)=>{if(rimanda){const s=stato();s.rimandato=Date.now();scrivi("eb_voto",s);}
   box.classList.remove("on");setTimeout(()=>box.remove(),260);document.removeEventListener("keydown",esc);};
  const esc=e=>{if(e.key=="Escape")chiudi(true);};document.addEventListener("keydown",esc);
  function scegli(n,focus){voto=n;accendi(n);etic.textContent=ETICHETTE[n-1];
   stelle.forEach((b,i)=>{b.setAttribute("aria-checked",i==n-1);b.tabIndex=i==n-1?0:-1;});
   if(focus)stelle[n-1].focus();
   ta.placeholder=n<=3?"Cosa possiamo migliorare? (facoltativo)":"Cosa ti è più utile? (facoltativo)";
   if(altro.hidden){altro.hidden=false;box.classList.add("aperto");}}
  stelle.forEach((b,i)=>{
   b.onmouseenter=()=>{accendi(i+1);etic.textContent=ETICHETTE[i];};
   b.onclick=()=>scegli(i+1,false);
   b.onkeydown=e=>{const d={ArrowRight:1,ArrowUp:1,ArrowLeft:-1,ArrowDown:-1}[e.key];
    if(d){e.preventDefault();scegli(Math.min(5,Math.max(1,(voto||i+1)+(voto?d:0))),true);}};});
  box.querySelector(".evstelle").onmouseleave=()=>{accendi(voto);etic.innerHTML=voto?ETICHETTE[voto-1]:"&nbsp;";};
  box.querySelector(".evx").onclick=()=>chiudi(true);box.querySelector(".evdopo").onclick=()=>chiudi(true);
  invia.onclick=async()=>{if(!voto)return;
   invia.disabled=true;invia.textContent="Invio…";esito.textContent="";esito.className="evesito";
   const b=document.querySelector("#nav button.on");
   try{const r=await fetch("https://api.web3forms.com/submit",{method:"POST",headers:{"Content-Type":"application/json",Accept:"application/json"},
     body:JSON.stringify({access_key:CHIAVE,subject:`BoardEdge · Voto ${"★".repeat(voto)}${"☆".repeat(5-voto)} (${voto}/5)`,from_name:"BoardEdge voto",
      stelle:voto,giudizio:ETICHETTE[voto-1],commento:ta.value.trim()||"(nessun commento)",scheda:b?b.textContent.trim():"",
      versione:(typeof D!="undefined"&&D.meta&&D.meta.version)||"",botcheck:false})});
    const j=await r.json().catch(()=>({}));if(!r.ok||j.success===false)throw new Error(j.message||("HTTP "+r.status));
    const s=stato();s.votato=Date.now();s.stelle=voto;scrivi("eb_voto",s);
    try{window.ebStat&&ebStat.ev("voto",{stelle:voto});}catch(_){}
    box.classList.add("fatto");
    box.innerHTML=`<div class="evgrazie"><span aria-hidden="true">&#10003;</span><div><b>Grazie del voto!</b><small>${voto>=4?"Ci fa piacere: continueremo così.":"Lo useremo per migliorare."}</small></div></div>`;
    setTimeout(()=>chiudi(false),2600);}
   catch(err){console.warn("[BoardEdge] voto:",err);invia.disabled=false;invia.textContent="Invia voto";
    esito.className="evesito ko";esito.textContent="Invio non riuscito, riprova tra poco.";}};
  }
}catch(e){console.error("[BoardEdge] voto:",e);}})();
