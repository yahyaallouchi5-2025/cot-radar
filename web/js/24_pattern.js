
/* ---------- PATTERN DETECTOR: inversione a 3 candele con assorbimento (forex e materie prime) ----------
   Dati: pattern.json scritto ogni 4 ore da cot_radar/pattern.py nel ramo git "pattern" e letto DIRETTAMENTE da
   raw.githubusercontent.com (cosi' non serve ripubblicare il sito a ogni candela H4); se non risponde si usa la
   copia nel sito (../pattern/pattern.json).
   BUY  = candela 1 SELL, candele 2 e 3 BUY, chiusura della 3 sopra l'apertura della 1 (assorbimento).
   SELL = candela 1 BUY, candele 2 e 3 SELL, chiusura della 3 sotto l'apertura della 1.
   - si scarica solo all'apertura della scheda (scheletro di attesa) e si riaggiorna ogni 10 minuti finche' e' aperta;
   - timeframe H4 / Daily, filtro Forex / Materie prime, segnali freschi in evidenza;
   - clic su uno strumento: grafico a candele delle ultime 60 con i pattern evidenziati e le due linee
     (apertura della candela 1 e chiusura della candela 3), come nelle immagini di riferimento;
   - anomalia (Yahoo fermo) o file assente: popup comune di manutenzione con giorno e ora.
   DEBUG: F12 -> Console -> window.__pattern */
try{(function(){const el=$("pattern");if(!el)return;
 const RAW="https://raw.githubusercontent.com/yahyaallouchi5-2025/cot-radar/pattern/pattern.json",LOC="../pattern/pattern.json";
 const ST={d:null,tf:"h4",g:"tutti"};
 try{const s=JSON.parse(localStorage.getItem("ebPattern")||"{}");if(s.tf)ST.tf=s.tf;if(s.g)ST.g=s.g;}catch(e){}
 const salva=()=>{try{localStorage.setItem("ebPattern",JSON.stringify({tf:ST.tf,g:ST.g}));}catch(e){}};
 const z=x=>String(x).padStart(2,"0");
 // orario della CHIUSURA della candela, in ora italiana (H4: inizio + 4 ore; daily: solo la data)
 const quando=(t,tf)=>{const d=new Date((t+(tf=="h4"?4*3600:0))*1000);return tf=="h4"?`${z(d.getDate())}/${z(d.getMonth()+1)} ore ${z(d.getHours())}:${z(d.getMinutes())}`:`${z(d.getDate())}/${z(d.getMonth()+1)}/${d.getFullYear()}`;};
 const num=(v,c)=>v==null?"n/d":Number(v).toLocaleString("it-IT",{minimumFractionDigits:Math.min(c,5),maximumFractionDigits:c});
 const cifre=v=>{const s=String(v);return s.includes(".")?s.split(".")[1].length:0;};
 // variazione %: sotto lo 0,005% e' zero (evita il "-0,00%" quando il prezzo e' fermo)
 const pc=v=>{if(v==null)return "n/d";if(Math.abs(v)<0.005)v=0;return `<span class="${v>0?"up":v<0?"down":"flat"}">${v>0?"+":""}${fx(v,2)}%</span>`;};
 // "1 candela fa" al singolare, "N candele fa" al plurale
 const fa=n=>n==0?"ultima candela":n==1?"1 candela fa":n+" candele fa";
 const badge=l=>`<span class="ptb ${l=="BUY"?"buy":"sell"}">${l}</span>`;
 const sk=(w,h)=>`<i class="sk" style="width:${w};height:${h}px"></i>`;

 // mini schema del pattern (spiegazione visiva, sempre uguale)
 const schema=lato=>{const B=lato=="BUY",c=[[B?20:70,B?70:20],[B?70:20,B?50:45],[B?50:45,B?12:82]];
  const y=v=>8+v*0.9;return `<svg viewBox="0 0 120 96" class="ptschema" aria-hidden="true">
   <line x1="8" x2="112" y1="${y(c[0][0])}" y2="${y(c[0][0])}" class="lv"/>${c.map((k,i)=>{const s=k[1]<k[0];const top=Math.min(y(k[0]),y(k[1])),h=Math.abs(y(k[0])-y(k[1]));
   return `<rect x="${22+i*28}" y="${top}" width="16" height="${Math.max(2,h)}" rx="2" class="${(B?(i?"su":"giu"):(i?"giu":"su"))}"/>`;}).join("")}
   <circle cx="${22+2*28+8}" cy="${y(c[2][1])}" r="3.5" class="pt"/></svg>`;};

 function scheletro(){el.innerHTML=`<h2>Pattern Detector</h2><p class="sub">Caricamento dei segnali&hellip;</p>
  <div class="azbar">${sk("220px",38)}${sk("260px",38)}</div><div class="ptfresh">${Array(3).fill(`<div class="card">${sk("40%",14)}${sk("70%",24)}${sk("100%",60)}</div>`).join("")}</div>
  <div class="tablewrap" style="padding:14px">${Array(8).fill(`<div class="azskr">${sk("22%",14)}${sk("12%",14)}${sk("14%",14)}${sk("12%",14)}</div>`).join("")}</div>`;}

 let carico=null,timer=null;
 function scarica(){const v=Math.floor(Date.now()/300000);   // cambia ogni 5 minuti: niente copie vecchie in cache
  return fetch(RAW+"?v="+v,{cache:"no-cache"}).then(r=>{if(!r.ok)throw 0;return r.json();})
   .catch(()=>fetch(LOC,{cache:"no-cache"}).then(r=>{if(!r.ok)throw new Error("HTTP "+r.status);return r.json();}));}
 function carica(){if(carico)return carico;scheletro();
  return carico=scarica().then(d=>{ST.d=d;window.__pattern=d;disegna();
    if(d.anomalia)ebManutenzione({scheda:"pattern",codice:d.anomalia.codice,quando:d.anomalia.quando});
    clearInterval(timer);timer=setInterval(()=>{if(el.classList.contains("on")&&!document.hidden)scarica().then(n=>{if(n.generato_utc!=(ST.d||{}).generato_utc){ST.d=n;disegna();}}).catch(()=>{});},600000);})
   .catch(e=>{console.error("[BoardEdge] pattern non caricati:",e);carico=null;
    el.innerHTML=`<h2>Pattern Detector</h2><div class="card azvuoto"><span class="pav-i grande" aria-hidden="true">!</span><h3>Segnali momentaneamente non disponibili</h3><p class="small">La scheda torna appena il servizio &egrave; di nuovo regolare.</p></div>`;
    const n=new Date();ebManutenzione({scheda:"pattern",codice:"503",quando:`${n.getFullYear()}-${z(n.getMonth()+1)}-${z(n.getDate())} ${z(n.getHours())}:${z(n.getMinutes())}`});});}
 const nb=document.querySelector('#nav button[data-t=pattern]');if(nb)nb.addEventListener("click",()=>setTimeout(carica,0));
 setTimeout(()=>{if(el.classList.contains("on"))carica();},0);

 function disegna(){const d=ST.d,tf=ST.tf;
  const S=d.strumenti.filter(s=>ST.g=="tutti"||s.g==ST.g);
  const freschi=S.filter(s=>s[tf].ultimo&&s[tf].ultimo.fa==0);
  // statistica complessiva del timeframe (tutti gli strumenti filtrati)
  let n=0,v=0,m=0;S.forEach(s=>{const st=s[tf].stat;if(st&&st.n){n+=st.n;v+=st.vinti*st.n/100;m+=st.media*st.n;}});
  const tot=n?{v:Math.round(100*v/n),m:m/n}:null;
  el.innerHTML=`<h2>Pattern Detector</h2><p class="sub">Inversione a 3 candele con assorbimento: la candela 1 va in una direzione, le candele 2 e 3 nella direzione opposta e la candela 3 chiude oltre l'apertura della candela 1, &laquo;assorbendola&raquo; del tutto. Solo candele chiuse, ${S.length} strumenti tra forex e materie prime, aggiornamento ogni 4 ore.</p>
   <div class="ptspiega"><div>${schema("BUY")}<span>${badge("BUY")} candela 1 SELL, poi 2 candele BUY: la 3 chiude sopra l'apertura della 1</span></div>
    <div>${schema("SELL")}<span>${badge("SELL")} candela 1 BUY, poi 2 candele SELL: la 3 chiude sotto l'apertura della 1</span></div></div>
   <div class="azbar"><span class="azdata"><i></i>Aggiornato <b>${esc((d.generato||"").slice(8,10)+"/"+(d.generato||"").slice(5,7)+" ore "+(d.generato||"").slice(11,16))}</b></span>
    <div class="vfswitch pttf">${[["h4","H4"],["d1","Daily"]].map(x=>`<button data-tf="${x[0]}" class="${tf==x[0]?"on":""}">${x[1]}</button>`).join("")}</div>
    <div class="filters ptg">${[["tutti","Tutti"],["forex","Forex"],["materie","Materie prime"]].map(x=>`<button data-g="${x[0]}" class="${ST.g==x[0]?"on":""}">${x[1]}</button>`).join("")}</div></div>
   <h3 class="vft">Segnali freschi <span class="small">(pattern completato sull'ultima candela ${tf=="h4"?"H4":"giornaliera"} chiusa: ${freschi.length} su ${S.length} strumenti)</span></h3>
   ${freschi.length?`<div class="ptfresh">${freschi.map(s=>{const u=s[tf].ultimo,st=s[tf].stat;return `<button class="card ptc ${u.lato=="BUY"?"buy":"sell"}" data-id="${s.id}">
     <div class="ptct">${badge(u.lato)}<span class="small">chiusa ${quando(u.t,tf)}</span></div>
     <b class="ptn">${esc(s.n)}</b>
     <div class="ptlv"><span><em>Ingresso</em><b>${num(u.ingresso,cifre(u.ingresso))}</b></span><span><em>Apertura cand. 1</em><b>${num(u.livello,cifre(u.livello))}</b></span><span><em>${u.lato=="BUY"?"Minimo":"Massimo"} pattern</em><b>${num(u.estremo,cifre(u.estremo))}</b></span></div>
     <span class="small">Storico su ${esc(s.n)}: ${st.n?`${st.vinti}% nella direzione del segnale dopo ${st.dopo} candele (${st.n} casi, media ${st.media>0?"+":""}${fx(st.media,2)}%)`:"casi insufficienti"}</span></button>`;}).join("")}</div>`
    :`<div class="card small" style="padding:18px 20px">Nessun pattern sull'ultima candela ${tf=="h4"?"H4":"giornaliera"} chiusa. La tabella sotto mostra l'ultimo segnale di ogni strumento.</div>`}
   <h3 class="vft">Tutti gli strumenti <span class="small">(ultimo pattern di ciascuno &middot; clic per il grafico${tot?` &middot; storico complessivo ${tf=="h4"?"H4":"daily"}: ${tot.v}% nella direzione del segnale dopo ${d.dopo} candele, ${n} casi`:""})</span></h3>
   <div class="tablewrap"><table class="pttab"><tr><th>Strumento</th><th>Ultimo segnale</th><th>Chiusura candela 3</th><th class="num">Ingresso</th><th class="num">Ultimo prezzo</th><th class="num">Da ingresso</th><th class="num azh">Storico</th></tr>
    ${S.map(s=>{const u=s[tf].ultimo,st=s[tf].stat;return `<tr class="clic" data-id="${s.id}" tabindex="0"><td class="aznome"><b>${esc(s.n)}</b><span>${s.g=="forex"?"Forex":"Materie prime"}${s.copia?" &middot; dati del giro precedente":""}</span></td>
     <td>${u?`${badge(u.lato)} <span class="small">${fa(u.fa)}</span>`:'<span class="small">nessuno di recente</span>'}</td>
     <td>${u?quando(u.t,tf):""}</td><td class="num">${u?num(u.ingresso,cifre(u.ingresso)):""}</td><td class="num">${u?num(u.ora,cifre(u.ora)):""}</td><td class="num">${u?pc(u.mossa):""}</td>
     <td class="num azh">${st.n?`${st.vinti}% <span class="small">su ${st.n}</span>`:'<span class="small">n/d</span>'}</td></tr>`;}).join("")}</table></div>`;
  el.querySelectorAll(".pttf button").forEach(b=>b.onclick=()=>{ST.tf=b.dataset.tf;salva();disegna();});
  el.querySelectorAll(".ptg button").forEach(b=>b.onclick=()=>{ST.g=b.dataset.g;salva();disegna();});
  el.querySelectorAll("[data-id]").forEach(r=>{r.onclick=()=>apri(r.dataset.id);r.onkeydown=e=>{if(e.key=="Enter")apri(r.dataset.id);};});}

 // --- grafico a candele con i pattern evidenziati (pannello laterale, stesso stile del dettaglio Azionario)
 function apri(id){const s=ST.d.strumenti.find(x=>x.id==id);if(!s)return;const tf=ST.tf,a=s[tf],u=a.ultimo;
  let ov=document.querySelector(".azdett");if(!ov){ov=document.createElement("div");ov.className="azdett";document.body.appendChild(ov);}
  const chiudi=()=>{ov.classList.remove("on");document.removeEventListener("keydown",tasto);setTimeout(()=>{ov.innerHTML="";},250);};
  const tasto=e=>{if(e.key=="Escape")chiudi();};document.addEventListener("keydown",tasto);
  ov.onclick=e=>{if(e.target==ov||e.target.closest(".azx"))chiudi();};
  const C=a.candele,W=680,H=320,L=8,R=70,T=14,B=26;
  const lo=Math.min(...C.map(c=>c[3])),hi=Math.max(...C.map(c=>c[2])),Y=v=>T+(hi-v)/(hi-lo||1)*(H-T-B),bw=(W-L-R)/C.length,X=i=>L+i*bw+bw/2;
  const idx=new Map(C.map((c,i)=>[c[0],i]));
  let ultimaEt=-99;
  const bande=a.segnali.filter(p=>idx.has(p.t)&&idx.get(p.t)>=2).map(p=>{const i=idx.get(p.t),ult=u&&p.t==u.t,et=i-ultimaEt>=4||ult;if(et)ultimaEt=i;
   return `<rect x="${(L+(i-2)*bw).toFixed(1)}" y="${T}" width="${(3*bw).toFixed(1)}" height="${H-T-B}" class="ptband ${p.lato=="BUY"?"buy":"sell"}${ult?" ult":""}"/>${et?`<text x="${X(i).toFixed(1)}" y="${H-B-6}" text-anchor="middle" class="ptbl ${p.lato=="BUY"?"buy":"sell"}">${p.lato}</text>`:""}`;}).join("");
  const cand=C.map((c,i)=>{const su=c[4]>=c[1],top=Y(Math.max(c[1],c[4])),h=Math.max(1,Math.abs(Y(c[1])-Y(c[4])));
   return `<line x1="${X(i).toFixed(1)}" x2="${X(i).toFixed(1)}" y1="${Y(c[2]).toFixed(1)}" y2="${Y(c[3]).toFixed(1)}" class="ptw ${su?"su":"giu"}"/><rect x="${(X(i)-bw*0.36).toFixed(1)}" y="${top.toFixed(1)}" width="${(bw*0.72).toFixed(1)}" height="${h.toFixed(1)}" class="ptk ${su?"su":"giu"}"><title>${quando(c[0],tf)} · A ${c[1]} · M ${c[2]} · m ${c[3]} · C ${c[4]}</title></rect>`;}).join("");
  let linee="";if(u&&idx.has(u.t)){const i=idx.get(u.t);
   linee=`<line x1="${X(i-2)}" x2="${W-R}" y1="${Y(u.livello)}" y2="${Y(u.livello)}" class="ptl lv"/><text x="${W-R+4}" y="${Y(u.livello)+4}" class="ptlt lv">${num(u.livello,cifre(u.livello))}</text>
    <line x1="${X(i)}" x2="${W-R}" y1="${Y(u.ingresso)}" y2="${Y(u.ingresso)}" class="ptl in"/><text x="${W-R+4}" y="${Y(u.ingresso)+4}" class="ptlt in">${num(u.ingresso,cifre(u.ingresso))}</text>`;}
  const tick=[0,.25,.5,.75,1].map(k=>lo+(hi-lo)*k).map(v=>`<line x1="${L}" x2="${W-R}" y1="${Y(v)}" y2="${Y(v)}" class="pgr"/>`).join("");
  ov.innerHTML=`<aside class="azpan" role="dialog" aria-modal="true" aria-label="${esc(s.n)}"><button class="azx" aria-label="Chiudi">&times;</button>
   <div class="aztesta"><span class="small">${s.g=="forex"?"Forex":"Materie prime"} &middot; ${tf=="h4"?"H4":"Daily"} &middot; ultime ${C.length} candele chiuse</span><h3>${esc(s.n)}</h3>
    ${u?`<div class="azprz">${badge(u.lato)}<span class="small">pattern chiuso il ${quando(u.t,tf)} &middot; ${fa(u.fa)}</span></div>`:""}</div>
   <div class="azgraf"><svg viewBox="0 0 ${W} ${H}" class="ptsvg" preserveAspectRatio="none">${tick}${bande}${cand}${linee}</svg></div>
   ${u?`<div class="pleg ptleg"><span><i class="lv"></i>Apertura candela 1 (${num(u.livello,cifre(u.livello))})</span><span><i class="in"></i>Chiusura candela 3 = ingresso (${num(u.ingresso,cifre(u.ingresso))})</span></div>
   <div class="azmini"><div><span>Ingresso</span><b>${num(u.ingresso,cifre(u.ingresso))}</b></div><div><span>${u.lato=="BUY"?"Minimo":"Massimo"} del pattern</span><b>${num(u.estremo,cifre(u.estremo))}</b></div><div><span>Da ingresso</span>${pc(u.mossa)}</div></div>`:""}
   <h4 class="aztit">Pattern passati <span class="small">(esito dopo ${ST.d.dopo} candele nella direzione del segnale)</span></h4>
   <div class="tablewrap"><table class="compatta"><tr><th>Chiusura candela 3</th><th>Segnale</th><th class="num">Ingresso</th><th class="num">Esito</th></tr>
    ${[...a.segnali].reverse().map(p=>`<tr><td>${quando(p.t,tf)}</td><td>${badge(p.lato)}</td><td class="num">${num(p.ingresso,cifre(p.ingresso))}</td><td class="num">${p.esito==null?'<span class="small">in corso</span>':pc(p.esito)}</td></tr>`).join("")||'<tr><td colspan="4" class="small">Nessun pattern nel periodo.</td></tr>'}</table></div>
   <p class="small azfonte">${s.fonte&&s.fonte.endsWith("=F")?"Prezzi del future (approssimazione dello spot). ":""}Le candele H4 sono allineate alle ore UTC 00-04-08-12-16-20 e possono differire da quelle del proprio broker.</p></aside>`;
  requestAnimationFrame(()=>ov.classList.add("on"));ov.querySelector(".azx").focus({preventScroll:true});
  try{window.ebStat&&ebStat.ev("pattern",{strumento:id,tf:tf});}catch(e){}}
})();}catch(e){fail('Pattern Detector','pattern',e);}
