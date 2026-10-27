/* ---------- registro (SOLO AMMINISTRATORE) ----------
   Il sito e' pubblico, quindi il registro completo NON e' in chiaro nella pagina:
   - sul PC (pagina locale) D.admin = {chiaro:{...}} -> scheda "Registro" visibile;
   - sul sito D.admin = {salt,iv,ct,iter} cifrato con la password admin (Secret ADMIN_PASSWORD, vedi cot_radar/admin.py):
     la scheda compare solo aprendo l'indirizzo con  #admin  in fondo, e si legge solo con la password;
   - D.admin = null (nessuna password impostata) -> nessuna scheda.
   La password non viene mai inviata da nessuna parte: la decifratura avviene nel browser (Web Crypto). */
try{
(function(){const A=D.admin,el=$("registro"),bt=document.querySelector('nav button[data-t="registro"]');
 const mostra=on=>{if(bt)bt.style.display=on?"":"none";};
 function disegna(S){
  const colE={ok:"var(--sb)",avvisi:"var(--warn)",errori:"var(--s)",critico:"var(--ss)",fallito:"var(--ss)"}[S.esito]||"var(--n)";
  const colL={WARNING:"var(--warn)",ERROR:"var(--s)",CRITICAL:"var(--ss)"};
  const fonti=Object.entries(S.fonti||{}).map(([k,v])=>k=="fred_riserva"   // serie FRED prese da Tesoro USA, NY Fed, BCE...
    ?`<span class="tag ok">RISERVA FRED: ${v} serie</span>`:`<span class="tag ${v=="online"?"ok":"ko"}">${k.toUpperCase()}: ${v}</span>`).join(" ");
  const crit=(S.critici||[]).map(c=>`<tr><td class="small">paracadute</td><td><b style="color:var(--ss)">CRITICAL</b></td><td class="small">fonti</td><td style="white-space:normal">${esc(c)}</td></tr>`).join("");
  const voci=(S.voci||[]).map(v=>`<tr><td class="small">${esc(v.ora||"")}</td><td><b style="color:${colL[v.livello]||"var(--ink)"}">${esc(v.livello)}</b></td><td class="small">${esc(v.modulo||"")}</td><td style="white-space:normal">${esc(v.messaggio)}</td></tr>`).join("");
  const brow=window.__errori.map(v=>`<tr><td class="small">browser</td><td><b style="color:var(--s)">ERROR</b></td><td class="small">${esc(v.sezione)}</td><td style="white-space:normal">${esc(v.errore).slice(0,400)}</td></tr>`).join("");
  el.innerHTML=`<h2>Registro di monitoraggio <span class="tag ko">solo admin</span></h2><p class="sub">Esito dell'ultimo aggiornamento, fonti, avvisi ed errori. Il dettaglio completo e' in <code>dati/registro.log</code> sul PC.</p>
  <div class="grid k4"><div class="card kpi"><h3>Esito</h3><div class="big" style="color:${colE}">${esc((S.esito||"n/d").toUpperCase())}</div><div class="note">${esc(S.creato||"")}</div></div>
  <div class="card kpi"><h3>Errori</h3><div class="big" style="color:${S.errori?"var(--s)":"var(--ink)"}">${S.errori??"n/d"}</div><div class="note">parti non calcolate o dati impossibili</div></div>
  <div class="card kpi"><h3>Avvisi</h3><div class="big" style="color:${S.avvisi?"var(--warn)":"var(--ink)"}">${S.avvisi??"n/d"}</div><div class="note">dati vecchi, fonti non raggiunte</div></div>
  <div class="card kpi"><h3>Durata</h3><div class="big">${S.durata_s??"n/d"} s</div><div class="note">${S.strumenti??"?"} strumenti, ${S.coppie??"?"} coppie</div></div></div>
  <h2>Fonti</h2><div class="card">${fonti||"n/d"}</div>
  <h2>Avvisi ed errori di questa esecuzione</h2><div class="tablewrap"><table><tr><th>Ora</th><th>Livello</th><th>Modulo</th><th>Messaggio</th></tr>${crit+voci+brow||'<tr><td colspan="4">Nessun avviso: tutto regolare.</td></tr>'}</table></div>`;}
 // decifra con la password: PBKDF2-SHA256 -> chiave AES-GCM 256 (stessi parametri di admin.py)
 async function decifra(pw){const b=x=>Uint8Array.from(atob(x),c=>c.charCodeAt(0));
  const base=await crypto.subtle.importKey("raw",new TextEncoder().encode(pw),"PBKDF2",false,["deriveKey"]);
  const k=await crypto.subtle.deriveKey({name:"PBKDF2",salt:b(A.salt),iterations:A.iter,hash:"SHA-256"},base,{name:"AES-GCM",length:256},false,["decrypt"]);
  return JSON.parse(new TextDecoder().decode(await crypto.subtle.decrypt({name:"AES-GCM",iv:b(A.iv)},k,b(A.ct))));}
 function chiedi(){el.innerHTML=`<h2>Registro di monitoraggio</h2><p class="sub">Area riservata all'amministratore.</p>
  <form id="admform" class="card admin"><label for="admpw">Password</label><input id="admpw" type="password" autocomplete="current-password">
  <button type="submit" class="tvbtn">Apri</button><div id="admmsg" class="small"></div></form>`;
  $("admform").onsubmit=ev=>{ev.preventDefault();const pw=$("admpw").value;$("admmsg").textContent="Verifica...";
   decifra(pw).then(S=>{try{sessionStorage.setItem("cotAdmin",pw);}catch(e){}disegna(S);})
   .catch(()=>{$("admmsg").textContent="Password errata.";});};}
 function admin(){if(!A||A.chiaro||location.hash!="#admin")return;
  mostra(true);let pw=null;try{pw=sessionStorage.getItem("cotAdmin");}catch(e){}
  if(pw)decifra(pw).then(disegna).catch(chiedi);else chiedi();go("registro");}
 if(!A){mostra(false);el.remove();return;}           // nessun registro pubblicato
 if(A.chiaro){disegna(A.chiaro);return;}             // pagina locale sul PC
 mostra(false);admin();window.addEventListener("hashchange",admin);
})();
}catch(e){fail('Registro','registro',e);}

