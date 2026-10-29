/* ---------- INVITO A ISCRIVERSI AL CANALE TELEGRAM (v6.48) ----------
   Dopo un po' di utilizzo (tocchi/clic + tempo sulla pagina) compare UNA volta un piccolo invito in basso:
   "Iscriviti su Telegram" (apre il canale), "Mostrami dove" (apre la barra laterale e fa pulsare la card Telegram,
   per chi non l'ha notata) e "Non ora" (non torna per 14 giorni; dopo 2 inviti non compare piu').
   Regole di buona educazione:
   - mai sopra il consenso legale, il popup di manutenzione, la guida o la scheda di un titolo;
   - mai se l'utente ha gia' toccato la card/il link Telegram (si ricorda in localStorage "ebTg");
   - non blocca la pagina: e' un foglio in basso, non una finestra a tutto schermo. */
try{(function(){
 const SOGLIA_TOCCHI=15,SOGLIA_SECONDI=60,RINVIO_GIORNI=14,MAX_INVITI=2;       // quando mostrarlo
 const leggi=()=>{try{return JSON.parse(localStorage.getItem("ebTg")||"{}");}catch(e){return {};}};
 const salva=o=>{try{localStorage.setItem("ebTg",JSON.stringify(o));}catch(e){}};
 const st=leggi();st.tocchi=st.tocchi||0;st.inviti=st.inviti||0;
 const link=()=>{const a=document.querySelector(".stg");return a?a.href:"";};
 const stat=a=>{try{window.ebStat&&ebStat.ev("telegram_invito",{azione:a});}catch(e){}};
 // chi ha gia' aperto il canale (dalla card o dalla barra alta) non va disturbato
 document.addEventListener("click",e=>{if(e.target.closest(".stg,.tgtop")){const o=leggi();o.fatto=1;salva(o);chiudi();}},true);
 if(st.fatto||st.inviti>=MAX_INVITI||(st.rinvio&&Date.now()<st.rinvio)||!link())return;

 // conta i tocchi (clic) e il tempo con la pagina visibile
 let secondi=0,tocchi=0;
 document.addEventListener("click",()=>{tocchi++;},true);
 setInterval(()=>{if(!document.hidden)secondi++;},1000);

 // c'e' gia' qualcosa sopra la pagina? (consenso, manutenzione, guida, dettaglio titolo)
 const occupato=()=>{
  if(document.documentElement.classList.contains("sideon"))return true;            // barra laterale aperta (telefono): l'utente sta gia' guardando li'
  return !!document.querySelector(".cmodal:not([hidden]),.pmodal,.azdett.on,#guida.on");};

 let box=null,fine=0;
 function chiudi(){if(!box)return;box.classList.remove("on");const b=box;box=null;setTimeout(()=>b.remove(),300);}
 function mostra(){
  if(box)return;
  box=document.createElement("div");box.className="tginv";box.setAttribute("role","dialog");box.setAttribute("aria-label","Iscriviti al canale Telegram");
  box.innerHTML=`<button class="tgx" aria-label="Chiudi">&times;</button>
   <div class="tgt"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M21.5 3.5L2.8 10.7c-.9.4-.9 1.6.1 1.9l4.6 1.5 1.8 5.6c.3.8 1.3 1 1.9.4l2.6-2.5 4.7 3.5c.7.5 1.7.1 1.9-.7l3.1-15c.2-1.1-.9-1.9-2-1.4z"/><path d="M8 14l10-7.5"/></svg>
    <div><b>Ti piace BoardEdge?</b><span>Ricevi l'analisi gratis su Telegram: il riepilogo ogni venerdì e il briefing del lunedì.</span></div></div>
   <div class="tgb"><a class="tgp" href="${link()}" target="_blank" rel="noopener">Iscriviti su Telegram</a><button class="tgd" type="button">Dove lo trovo?</button><button class="tgn" type="button">Non ora</button></div>`;
  document.body.appendChild(box);requestAnimationFrame(()=>box&&box.classList.add("on"));
  const o=leggi();o.inviti=(o.inviti||0)+1;o.rinvio=Date.now()+RINVIO_GIORNI*864e5;salva(o);stat("mostrato");
  box.querySelector(".tgx").onclick=box.querySelector(".tgn").onclick=()=>{stat("non_ora");chiudi();};
  box.querySelector(".tgp").onclick=()=>{stat("iscriviti");};                       // il clic sul link lo segna come "fatto" (listener sopra)
  box.querySelector(".tgd").onclick=()=>{stat("mostra_dove");chiudi();evidenzia();};}

 // apre la barra laterale (telefono) o la allarga (PC a barra ridotta) e fa pulsare la card Telegram per qualche secondo
 function evidenzia(){const h=document.documentElement,card=document.querySelector(".stg");if(!card)return;
  const mob=matchMedia("(max-width:900px)").matches,eraRidotta=h.classList.contains("ridotta");
  if(mob){h.classList.add("sideon");const s=document.getElementById("sombra");if(s)s.hidden=false;}
  else if(eraRidotta)h.classList.remove("ridotta");                                    // solo per ora: non cambia la scelta salvata
  card.classList.add("tgevid");
  clearTimeout(fine);fine=setTimeout(()=>{card.classList.remove("tgevid");if(!mob&&eraRidotta)h.classList.add("ridotta");},9000);
  card.addEventListener("pointerdown",()=>{card.classList.remove("tgevid");},{once:true});}

 // controllo ogni 4 secondi: appena ci sono abbastanza tocchi e tempo, e la pagina e' libera, compare l'invito
 const t=setInterval(()=>{
  if(box){return;}
  const tot=(st.tocchi||0)+tocchi;
  if(tot>=SOGLIA_TOCCHI&&secondi>=SOGLIA_SECONDI&&!document.hidden&&!occupato()){clearInterval(t);mostra();}
  // salva i tocchi accumulati (sommati tra una visita e l'altra)
  const o=leggi();o.tocchi=tot>(o.tocchi||0)?tot:o.tocchi;salva(o);st.tocchi=o.tocchi;tocchi=0;},4000);
 document.addEventListener("keydown",e=>{if(e.key=="Escape"&&box)chiudi();});
})();}catch(e){try{fail("Invito Telegram",null,e);}catch(_){}}
