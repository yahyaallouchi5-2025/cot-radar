
/* ---------- VETRINA DELLA DASHBOARD: le azioni piu' forti di oggi (carosello) ----------
   Dati da ../azioni/top.json (cot_radar/azioni.py -> vetrina(), ricalcolati ogni sera, ~3 KB):
   al massimo 5 titoli, uno per settore, con punteggio alto E tutte le condizioni favorevoli
   (sopra la media a 200 giorni, 3 e 12 mesi positivi, mese in corso positivo in almeno il 60% degli anni,
   vicino ai massimi dell'anno). Solo lato acquisto.
   - cambia da sola ogni 6 secondi (barra di avanzamento); si ferma con il mouse sopra o con il focus;
   - frecce, pallini, tastiera (frecce sinistra/destra) e scorrimento col dito sul telefono;
   - "Apri grafico" porta alla scheda Azionario con il dettaglio del titolo (window.ebApriTitolo);
   - con "riduci movimento" attivo nel sistema non scorre da sola.
   DEBUG: F12 -> Console -> window.__top */
try{(function(){const el=$("topaz");if(!el)return;
 const DUR=6000,SIMB={USD:"$",EUR:"€",GBP:"£",CHF:"CHF ",JPY:"¥",HKD:"HK$",CNY:"CN¥",INR:"₹"};
 const MESI=["gennaio","febbraio","marzo","aprile","maggio","giugno","luglio","agosto","settembre","ottobre","novembre","dicembre"];
 const pc=(v,d=1)=>v==null?"n/d":(v>0?"+":"")+fx(v,d)+"%";
 const prezzo=(v,val)=>v==null?"n/d":(SIMB[val]||"")+Number(v).toLocaleString("it-IT",{minimumFractionDigits:2,maximumFractionDigits:2});
 const gg=d=>d?d.slice(8,10)+"/"+d.slice(5,7)+"/"+d.slice(0,4):"";
 const fermo=window.matchMedia&&matchMedia("(prefers-reduced-motion: reduce)").matches;
 // scheletro mentre arriva il file
 el.innerHTML=`<div class="card tz tzsk"><i class="sk" style="width:180px;height:14px"></i><i class="sk" style="width:55%;height:28px;margin-top:12px"></i><i class="sk" style="width:100%;height:120px;margin-top:16px;border-radius:14px"></i></div>`;
 fetch("../azioni/top.json",{cache:"no-cache"}).then(r=>{if(!r.ok)throw new Error("HTTP "+r.status);return r.json();}).then(d=>{window.__top=d;disegna(d);
   if(d.anomalia)ebManutenzione({scheda:"sig",codice:d.anomalia.codice,quando:d.anomalia.quando,dal:d.aggiornato});})
  .catch(e=>{console.error("[BoardEdge] vetrina azioni non caricata:",e);el.innerHTML="";});

 function spark(sp){if(!sp||sp.length<2)return "";const W=220,H=60;
  const p=sp.map((v,i)=>`${(i/(sp.length-1)*W).toFixed(1)},${(H-3-v/99*(H-6)).toFixed(1)}`).join(" ");
  return `<svg class="tzsp" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" aria-hidden="true"><defs><linearGradient id="tzg" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="currentColor" stop-opacity=".3"/><stop offset="1" stop-color="currentColor" stop-opacity="0"/></linearGradient></defs><polygon points="0,${H} ${p} ${W},${H}" fill="url(#tzg)"/><polyline points="${p}"/></svg>`;}
 function anello(v){const r=30,c=2*Math.PI*r;return `<div class="tzring" title="Punteggio ${v} su 100"><svg viewBox="0 0 76 76"><circle cx="38" cy="38" r="${r}" class="f"/><circle cx="38" cy="38" r="${r}" class="a" stroke-dasharray="${(c*v/100).toFixed(1)} ${c.toFixed(1)}" transform="rotate(-90 38 38)"/></svg><b>${v}</b><small>forza</small></div>`;}

 function disegna(d){const T=d.titoli||[];const mese=MESI[(d.mese||new Date().getMonth()+1)-1];
  if(!T.length){el.innerHTML=`<div class="card tz"><div class="tztesta"><div><span class="tzchip">Selezione di oggi</span><h3>Le azioni pi&ugrave; forti</h3></div></div><p class="small" style="margin:8px 0 0">Oggi nessun titolo supera tutti i filtri: la selezione torna appena trend, forza e stagionalit&agrave; si allineano.</p></div>`;return;}
  const slide=(t,i)=>`<article class="tzs${i?"":" on"}" data-i="${i}" aria-roledescription="slide" aria-label="${i+1} di ${T.length}">
   <div class="tzinfo"><span class="tzpos">#${i+1} di ${T.length} &middot; ${esc((d.settori||{})[t.s]||t.s)}</span>
    <h4>${esc(t.n)}</h4><span class="small">${esc(t.t)} &middot; ${t.l.map(x=>esc((d.listini||{})[x]||x)).join(", ")}</span>
    <div class="tzprz"><b>${prezzo(t.p,t.val)}</b><span class="${(t.v1g||0)>=0?"up":"down"}">${pc(t.v1g,2)}</span></div></div>
   <ul class="tzperche">
    <li><i class="ok"></i><span>Ultimi 12 mesi <b class="up">${pc(t.v1a)}</b>, ultimi 3 mesi <b class="up">${pc(t.v3m)}</b></span></li>
    <li><i class="ok"></i><span>Sopra la media a 200 giorni del <b>${fx(t.t200,1)}%</b>${t.dmax!=null?` &middot; ${t.dmax>-0.5?"sui massimi dell'anno":"a "+fx(-t.dmax,1)+"% dal massimo dell'anno"}`:""}</span></li>
    <li><i class="ok"></i><span>${mese[0].toUpperCase()+mese.slice(1)} positivo nel <b>${t.st_pos}%</b> degli anni (${t.st_n} anni, media <b>${pc(t.st_media)}</b>)</span></li></ul>
   <div class="tzdx">${anello(t.pt)}<div class="tzgraf">${spark(t.sp)}<span class="small">ultimo anno</span></div>
    <button class="tzapri" data-t="${esc(t.t)}">Apri grafico e stagionalit&agrave; <span aria-hidden="true">&rarr;</span></button></div></article>`;
  el.innerHTML=`<div class="card tz" tabindex="0" aria-roledescription="carosello" aria-label="Le azioni pi&ugrave; forti di oggi">
   <div class="tztesta"><div><span class="tzchip"><i></i>Selezione di oggi</span><h3>Le ${T.length} azioni pi&ugrave; forti</h3>
    <span class="small">Una per settore, solo lato acquisto &middot; dati al ${gg(d.aggiornato)}</span></div>
    <div class="tzcom"><button class="tzfr" data-v="-1" aria-label="Precedente">&lsaquo;</button><div class="tzdots">${T.map((t,i)=>`<button class="${i?"":"on"}" data-i="${i}" aria-label="${esc(t.n)}"><i></i></button>`).join("")}</div><button class="tzfr" data-v="1" aria-label="Successiva">&rsaquo;</button>
     <button class="tzvedi">Classifica completa</button></div></div>
   <div class="tzbox">${T.map(slide).join("")}</div></div>`;
  const box=el.querySelector(".tz"),sl=[...el.querySelectorAll(".tzs")],dots=[...el.querySelectorAll(".tzdots button")];
  let cur=0,tm=null,inizio=0,pausa=false;
  function vai(i){cur=(i+T.length)%T.length;sl.forEach((s,k)=>s.classList.toggle("on",k==cur));dots.forEach((b,k)=>{b.classList.toggle("on",k==cur);b.querySelector("i").style.animation="none";void b.offsetWidth;b.querySelector("i").style.animation="";});avvia();}
  function avvia(){clearTimeout(tm);if(fermo||pausa||T.length<2)return;inizio=Date.now();tm=setTimeout(()=>vai(cur+1),DUR);}
  box.style.setProperty("--tzdur",DUR+"ms");box.classList.toggle("fermo",fermo);
  box.addEventListener("mouseenter",()=>{pausa=true;box.classList.add("pausa");clearTimeout(tm);});
  box.addEventListener("mouseleave",()=>{pausa=false;box.classList.remove("pausa");vai(cur);});
  box.addEventListener("keydown",e=>{if(e.key=="ArrowRight")vai(cur+1);if(e.key=="ArrowLeft")vai(cur-1);});
  let x0=null;box.addEventListener("touchstart",e=>{x0=e.touches[0].clientX;},{passive:true});
  box.addEventListener("touchend",e=>{if(x0==null)return;const dx=e.changedTouches[0].clientX-x0;if(Math.abs(dx)>40)vai(cur+(dx<0?1:-1));x0=null;});
  el.querySelectorAll(".tzfr").forEach(b=>b.onclick=()=>vai(cur+ +b.dataset.v));
  dots.forEach(b=>b.onclick=()=>vai(+b.dataset.i));
  el.querySelectorAll(".tzapri").forEach(b=>b.onclick=()=>{try{window.ebStat&&ebStat.ev("vetrina",{ticker:b.dataset.t});}catch(e){}window.ebApriTitolo&&ebApriTitolo(b.dataset.t);});
  el.querySelector(".tzvedi").onclick=()=>{try{go("azioni");}catch(e){}};
  // la vetrina scorre solo quando e' visibile (Dashboard aperta e pagina in primo piano)
  document.addEventListener("visibilitychange",()=>{if(document.hidden)clearTimeout(tm);else avvia();});
  avvia();}
})();}catch(e){fail('Vetrina azioni','topaz',e);}
