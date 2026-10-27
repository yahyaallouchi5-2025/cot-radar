
/* ---------- FEEDBACK UTENTI (pulsante "Feedback" nella sidebar) ----------
   Un modulo semplice: tipo (Suggerimento, Errore, Domanda, Altro), messaggio, email facoltativa.
   Invio con Web3Forms (servizio gratuito, nessun server nostro): il messaggio arriva SOLO alla casella email
   dell'admin collegata alla chiave, non viene pubblicato da nessuna parte.
   - La chiave pubblica del modulo arriva da Python (pagina.py: Secret WEB3FORMS_KEY o config.FEEDBACK_CHIAVE).
     Senza chiave il modulo si apre lo stesso e dice che e' in attivazione (niente invii persi in silenzio).
   - Al messaggio si aggiungono in automatico la scheda aperta e la versione del sito (aiutano a capire il contesto).
   - Protezione anti-spam: campo nascosto "botcheck" (i robot lo compilano, le persone no) + limite di 1 invio al minuto.
   Nelle statistiche anonime conta come evento "feedback" (solo il tipo, mai il testo). */
(function(){try{
 const CHIAVE="__FEEDBACK_KEY__".indexOf("__")===0?"":"__FEEDBACK_KEY__";
 const apri=document.getElementById("fbapri");if(!apri)return;
 const TIPI=[["suggerimento","Suggerimento"],["errore","Errore"],["domanda","Domanda"],["altro","Altro"]];
 let tipo="suggerimento",ultimo=0;
 function scheda(){const b=document.querySelector("#nav button.on");return b?b.textContent.trim():"";}
 function mostra(){
  if(document.querySelector(".fbmodal"))return;
  const box=document.createElement("div");box.className="cmodal fbmodal";
  box.innerHTML=`<form class="cmodal-box fbbox" role="dialog" aria-modal="true" aria-labelledby="fbt" novalidate>
    <div class="cmodal-testa"><span class="cmodal-ico" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M4 5h16v11H8l-4 4z"/></svg></span>
     <div><h3 id="fbt">Aiutaci a migliorare</h3><p>Idee, errori, domande: leggiamo tutto. Il messaggio arriva solo al team BoardEdge.</p></div>
     <button type="button" class="fbx" aria-label="Chiudi">&#x2715;</button></div>
    <div class="fbtipi" role="radiogroup" aria-label="Tipo di messaggio">${TIPI.map(t=>`<button type="button" role="radio" aria-checked="${t[0]==tipo}" class="${t[0]==tipo?"on":""}" data-t="${t[0]}">${t[1]}</button>`).join("")}</div>
    <label class="fbcampo"><span>Messaggio</span><textarea name="messaggio" rows="5" maxlength="2000" required placeholder="Scrivi qui (almeno 10 caratteri)"></textarea><small class="fbconta">0 / 2000</small></label>
    <label class="fbcampo"><span>Email <em>(facoltativa, solo se vuoi una risposta)</em></span><input type="email" name="email" autocomplete="email" placeholder="nome@esempio.it"></label>
    <input type="checkbox" name="botcheck" class="fbbot" tabindex="-1" autocomplete="off" aria-hidden="true">
    <div class="fbesito" role="status" aria-live="polite"></div>
    <div class="cmodal-btn"><button type="button" class="cno fbannulla">Annulla</button><button type="submit" class="csi fbinvia">Invia</button></div>
    <p class="small fbpriv">Inviando accetti che il messaggio (ed eventuale email) sia trattato solo per rispondere e migliorare il servizio. <a href="../legale/" target="_blank" rel="noopener">Privacy</a></p></form>`;
  document.body.appendChild(box);requestAnimationFrame(()=>box.classList.add("on"));
  const f=box.querySelector("form"),ta=f.querySelector("textarea"),esito=f.querySelector(".fbesito"),invia=f.querySelector(".fbinvia");
  const chiudi=()=>{box.classList.remove("on");setTimeout(()=>box.remove(),220);document.removeEventListener("keydown",tasto);apri.focus({preventScroll:true});};
  const tasto=e=>{if(e.key=="Escape")chiudi();};document.addEventListener("keydown",tasto);
  box.addEventListener("mousedown",e=>{if(e.target==box)chiudi();});
  f.querySelector(".fbx").onclick=chiudi;f.querySelector(".fbannulla").onclick=chiudi;
  f.querySelectorAll(".fbtipi button").forEach(b=>b.onclick=()=>{tipo=b.dataset.t;f.querySelectorAll(".fbtipi button").forEach(x=>{x.classList.toggle("on",x===b);x.setAttribute("aria-checked",x===b);});});
  ta.addEventListener("input",()=>{f.querySelector(".fbconta").textContent=ta.value.length+" / 2000";});
  setTimeout(()=>ta.focus(),60);
  if(!CHIAVE){esito.className="fbesito avv";esito.textContent="Il modulo è in attivazione: tra poco potrai inviare il tuo messaggio.";invia.disabled=true;}
  f.onsubmit=async e=>{e.preventDefault();
   const msg=ta.value.trim(),mail=f.email.value.trim();
   if(msg.length<10){esito.className="fbesito ko";esito.textContent="Scrivi almeno 10 caratteri.";ta.focus();return;}
   if(mail&&!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(mail)){esito.className="fbesito ko";esito.textContent="L'email non sembra valida (oppure lasciala vuota).";f.email.focus();return;}
   if(Date.now()-ultimo<60000){esito.className="fbesito ko";esito.textContent="Hai appena inviato un messaggio: riprova tra un minuto.";return;}
   invia.disabled=true;invia.textContent="Invio…";esito.className="fbesito";esito.textContent="";
   try{const r=await fetch("https://api.web3forms.com/submit",{method:"POST",headers:{"Content-Type":"application/json",Accept:"application/json"},
     body:JSON.stringify({access_key:CHIAVE,subject:`BoardEdge · ${TIPI.find(t=>t[0]==tipo)[1]}`,from_name:"BoardEdge feedback",
      tipo,messaggio:msg,email:mail||undefined,scheda:scheda(),versione:(D.meta&&D.meta.version)||"",botcheck:f.botcheck.checked})});
    const j=await r.json().catch(()=>({}));
    if(!r.ok||j.success===false)throw new Error(j.message||("HTTP "+r.status));
    ultimo=Date.now();try{window.ebStat&&ebStat.ev("feedback",{tipo});}catch(_){}
    f.innerHTML=`<div class="fbgrazie"><span class="cmodal-ico ok" aria-hidden="true">&#10003;</span><h3>Grazie!</h3><p>Messaggio ricevuto.${mail?" Se serve, ti rispondiamo all'email indicata.":""}</p><button type="button" class="csi">Chiudi</button></div>`;
    f.querySelector(".csi").onclick=chiudi;f.querySelector(".csi").focus();}
   catch(err){console.warn("[BoardEdge] feedback:",err);invia.disabled=false;invia.textContent="Invia";
    esito.className="fbesito ko";esito.textContent="Invio non riuscito (connessione o servizio). Riprova tra poco.";}};}
 apri.onclick=mostra;
}catch(e){console.error("[BoardEdge] feedback:",e);}})();
