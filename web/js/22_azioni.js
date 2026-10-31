
/* ---------- AZIONI per settore ----------
   Dati da ../azioni/indice.json (scritto ogni sera da cot_radar/azioni.py, ramo "azioni"): ~630 titoli di
   S&P 500, Nasdaq-100, FTSE MIB, DAX 40 ed Euro Stoxx 50, divisi negli 11 settori GICS.
   - il file si scarica SOLO quando si apre la scheda (il terminale resta leggero), con lo scheletro di attesa;
   - il dettaglio di un titolo (grafico + stagionalita') arriva da ../azioni/titoli/<TICKER>.json al clic;
   - filtri: listino, settore (le card), ricerca per nome o ticker; colonne ordinabili;
   - se l'aggiornamento della sera non e' riuscito (indice.anomalia) o il file non arriva: popup comune di
     manutenzione (manutenzione.js) con giorno e ora dell'anomalia, e la scheda mostra gli ultimi dati validi.
   DEBUG: F12 -> Console -> window.__azioni (dati caricati). */
try{(function(){const el=$("azioni");if(!el)return;
 const BASE="../azioni/",PAG=50;                       // titoli per pagina della tabella
 const ST={dati:null,list:"tutti",set:"tutti",ord:"pt",dir:-1,cerca:"",pag:1,per:"1a",tit:null};
 try{const s=JSON.parse(localStorage.getItem("ebAzioni2")||"{}");if(s.list)ST.list=s.list;if(s.ord){ST.ord=s.ord;ST.dir=s.dir||-1;}}catch(e){}
 const salva=()=>{try{localStorage.setItem("ebAzioni2",JSON.stringify({list:ST.list,ord:ST.ord,dir:ST.dir}));}catch(e){}};
 const gg=d=>d?d.slice(8,10)+"/"+d.slice(5,7)+"/"+d.slice(0,4):"";
 const pc=(v,d=1)=>v==null?'<span class="flat">n/d</span>':`<span class="${v>0?"up":v<0?"down":"flat"}">${v>0?"+":""}${fx(v,d)}%</span>`;
 const SIMB={USD:"$",EUR:"€",GBP:"£",CHF:"CHF ",JPY:"¥",HKD:"HK$",CNY:"CN¥",INR:"₹"};
 const prezzo=(v,val)=>v==null?"n/d":(SIMB[val]||"")+Number(v).toLocaleString("it-IT",{minimumFractionDigits:2,maximumFractionDigits:2});
 // dove e' quotato il titolo, dal suffisso del ticker di Yahoo (senza suffisso = Stati Uniti)
 const BORSE={MI:"Borsa italiana (Milano)",DE:"Borsa tedesca (Xetra)",PA:"Borsa di Parigi",AS:"Borsa di Amsterdam",MC:"Borsa di Madrid",BR:"Borsa di Bruxelles",HE:"Borsa di Helsinki",T:"Borsa di Tokyo",HK:"Borsa di Hong Kong",SS:"Borsa di Shanghai",SZ:"Borsa di Shenzhen",NS:"Borsa indiana (NSE)"};
 const borsa=tk=>{const m=String(tk).match(/\.([A-Z]+)$/);return m?(BORSE[m[1]]||"Borsa estera"):"Borsa USA";};
 const nomeSet=id=>((ST.dati&&ST.dati.settori.find(s=>s.id==id))||{}).nome||id;
 const nomeList=id=>((ST.dati&&ST.dati.listini.find(s=>s.id==id))||{}).nome||id;

 // --- scheletro di attesa (blocchi grigi che "respirano" al posto dei contenuti)
 const sk=(w,h,extra="")=>`<i class="sk" style="width:${w};height:${h}px;${extra}"></i>`;
 function scheletro(){el.innerHTML=`<h2>Azionario per settore</h2><p class="sub">Caricamento dei titoli in corso&hellip;</p>
  <div class="azbar">${sk("240px",38,"border-radius:99px")}${sk("320px",38,"border-radius:99px")}</div>
  <div class="azidx">${Array(6).fill(`<div class="card azsk">${sk("60%",14)}${sk("80%",26)}${sk("50%",12)}</div>`).join("")}</div>
  <div class="azset">${Array(11).fill(`<div class="azsc azsk">${sk("70%",14)}${sk("45%",24)}${sk("100%",6)}</div>`).join("")}</div>
  <div class="tablewrap" style="padding:14px">${Array(8).fill(`<div class="azskr">${sk("28%",14)}${sk("12%",14)}${sk("10%",14)}${sk("10%",14)}${sk("18%",22)}</div>`).join("")}</div>`;}

 // --- caricamento (una sola volta, quando la scheda diventa visibile)
 let caricato=null;
 function carica(){if(caricato)return caricato;scheletro();
  return caricato=fetch(BASE+"indice.json",{cache:"no-cache"}).then(r=>{if(!r.ok)throw new Error("HTTP "+r.status);return r.json();})
   .then(d=>{ST.dati=d;window.__azioni=d;disegna();
    if(d.anomalia)ebManutenzione({scheda:"azioni",codice:d.anomalia.codice,quando:d.anomalia.quando,dal:d.aggiornato});})
   .catch(e=>{console.error("[BoardEdge] azioni non caricate:",e);
    el.innerHTML=`<h2>Azionario per settore</h2><div class="card azvuoto"><span class="pav-i grande" aria-hidden="true">!</span><h3>Dati azionari momentaneamente non disponibili</h3><p class="small">La scheda torna appena il servizio &egrave; di nuovo regolare.</p></div>`;
    if(/^https?:/.test(location.protocol)){const n=new Date(),z=x=>String(x).padStart(2,"0");
     ebManutenzione({scheda:"azioni",codice:"503",quando:`${n.getFullYear()}-${z(n.getMonth()+1)}-${z(n.getDate())} ${z(n.getHours())}:${z(n.getMinutes())}`});}});}
 // la sezione vuota e' alta 0 px (l'IntersectionObserver non sempre la vede): si carica al clic sulla scheda
 // o subito se la pagina si apre gia' su "Azioni" (link #azioni)
 const nb=document.querySelector('#nav button[data-t=azioni]');if(nb)nb.addEventListener("click",()=>setTimeout(carica,0));
 setTimeout(()=>{if(el.classList.contains("on")||el.offsetParent!==null)carica();},0);

 // --- titoli dopo i filtri (listino + ricerca); il settore si applica alla tabella, non alle card
 function filtrati(conSettore){const q=ST.cerca.trim().toLowerCase();
  return ST.dati.titoli.filter(t=>(ST.list=="tutti"||t.l.includes(ST.list))&&(!conSettore||ST.set=="tutti"||t.s==ST.set)
   &&(!q||t.t.toLowerCase().includes(q)||(t.n||"").toLowerCase().includes(q)));}
 const media=a=>{const x=a.filter(v=>v!=null);return x.length?x.reduce((s,v)=>s+v,0)/x.length:null;};

 function spark(sp,cls){if(!sp||sp.length<2)return "";const W=96,H=28;
  const pts=sp.map((v,i)=>`${(i/(sp.length-1)*W).toFixed(1)},${(H-2-v/99*(H-4)).toFixed(1)}`).join(" ");
  return `<svg class="azsp ${cls}" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" aria-hidden="true"><polyline points="${pts}"/></svg>`;}

 // pulsanti delle pagine: 1 2 3 ... 12 (sempre prima, ultima e le due vicine a quella aperta)
 function pagine(tot){const n=Math.ceil(tot/PAG);if(n<2)return "";const p=ST.pag,v=[];
  for(let i=1;i<=n;i++)if(i==1||i==n||Math.abs(i-p)<=2)v.push(i);else if(v[v.length-1]!="…")v.push("…");
  return `<nav class="azpag" aria-label="Pagine"><button data-pg="${p-1}" ${p<=1?"disabled":""} aria-label="Pagina precedente">&lsaquo;</button>
   ${v.map(i=>i=="…"?`<span>&hellip;</span>`:`<button data-pg="${i}" class="${i==p?"on":""}" ${i==p?'aria-current="page"':""}>${i}</button>`).join("")}
   <button data-pg="${p+1}" ${p>=n?"disabled":""} aria-label="Pagina successiva">&rsaquo;</button><em>${(p-1)*PAG+1}&ndash;${Math.min(tot,p*PAG)} di ${tot}</em></nav>`;}
 // punteggio 0-100 come barra + numero (verde forte sopra 75)
 const forza=v=>v==null?"n/d":`<span class="azpt${v>=75?" alto":v<40?" basso":""}" title="Punteggio ${v} su 100"><span class="azptb"><i style="width:${v}%"></i></span><b>${v}</b></span>`;
 const MESI=["gennaio","febbraio","marzo","aprile","maggio","giugno","luglio","agosto","settembre","ottobre","novembre","dicembre"];

 function disegna(){const d=ST.dati,base=filtrati(false),righe=filtrati(true),mese=MESI[new Date().getMonth()];
  const COL=[["rk","#",1],["n","Titolo",0],["pt","Punteggio",0],["p","Prezzo",1],["v1g","1G",1],["v1m","1M",1],["v3m","3M",1,"azh"],["vytd","Da gennaio",1,"azh"],["v1a","1 anno",1],["st_pos",mese[0].toUpperCase()+mese.slice(1),1,"azh"],["t200","vs media 200g",1,"azh azh3"],["sp","Ultimo anno",0,"azh2"]];
  const ord=[...righe].sort((a,b)=>{const k=ST.ord;if(k=="n")return ST.dir*String(a.n).localeCompare(String(b.n));
   const x=a[k],y=b[k];if(x==null)return 1;if(y==null)return -1;return ST.dir*(x-y);});
  const np=Math.max(1,Math.ceil(ord.length/PAG));if(ST.pag>np)ST.pag=np;
  const vis=ord.slice((ST.pag-1)*PAG,ST.pag*PAG);
  el.innerHTML=`<h2>Azionario per settore</h2><p class="sub">${d.titoli.length} titoli di Stati Uniti, Europa, Giappone, Hong Kong, Cina e India nei 11 settori, in classifica per punteggio. Il punteggio (0-100) si ricalcola ogni sera: forza degli ultimi 12 e 3 mesi, posizione rispetto alla media a 200 giorni e stagionalit&agrave; di ${mese} (rendimento medio e anni positivi), confrontati tra tutti i titoli. Clicca un settore per filtrare la tabella, un titolo per grafico e stagionalit&agrave;.</p>
   <div class="azbar"><span class="azdata"><i></i>Dati al <b>${gg(d.aggiornato)}</b></span>
    <div class="azcw"><label class="azcerca"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/></svg><input type="search" placeholder="Cerca titolo o ticker" value="${esc(ST.cerca)}" aria-label="Cerca titolo o ticker" autocomplete="off" autocapitalize="off" spellcheck="false" role="combobox" aria-expanded="false" aria-controls="azsg"></label><div class="azsg" id="azsg" role="listbox" hidden></div></div>
    <div class="filters azlist">${[["tutti","Tutti"]].concat(d.listini.map(l=>[l.id,l.nome])).map(x=>`<button data-l="${x[0]}" class="${ST.list==x[0]?"on":""}">${x[1]}</button>`).join("")}</div></div>
   <div class="azidx">${d.indici.map(i=>`<div class="card azi${ST.list==i.l?" on":""}" data-l="${i.l}" role="button" tabindex="0"><span>${esc(i.n)}</span><b>${Number(i.p).toLocaleString("it-IT",{maximumFractionDigits:0,useGrouping:"always"})}</b>
    <em><span>oggi ${pc(i.v1g,2)}</span><span>anno ${pc(i.vytd)}</span></em>${spark(i.sp,(i.v1a||0)>=0?"su":"giu")}</div>`).join("")}</div>
   <h3 class="vft">Settori <span class="small">(media dei titoli${ST.list!="tutti"?" del "+esc(nomeList(ST.list)):""}: rendimento da inizio anno, ultimo mese e quota sopra la media a 200 giorni)</span></h3>
   <div class="azset"><button class="azsc${ST.set=="tutti"?" on":""}" data-s="tutti"><span>Tutti i settori</span><b>${base.length}</b><em>titoli</em></button>
    ${d.settori.map(s=>{const t=base.filter(x=>x.s==s.id);if(!t.length)return "";const y=media(t.map(x=>x.vytd)),m=media(t.map(x=>x.v1m)),
     sopra=Math.round(100*t.filter(x=>x.t200!=null&&x.t200>0).length/Math.max(1,t.filter(x=>x.t200!=null).length));
     return `<button class="azsc${ST.set==s.id?" on":""}" data-s="${s.id}"><span>${esc(s.nome)} <small>${t.length}</small></span><b class="${y>=0?"up":"down"}">${y==null?"n/d":(y>0?"+":"")+fx(y,1)+"%"}</b>
      <em>1 mese ${m==null?"n/d":(m>0?"+":"")+fx(m,1)+"%"}</em><span class="azbr" title="${sopra}% dei titoli sopra la media a 200 giorni"><i style="width:${sopra}%"></i></span><small class="azbrt">${sopra}% sopra media 200g</small></button>`;}).join("")}</div>
   <h3 class="vft azcl">${ST.set=="tutti"?"Classifica":esc(nomeSet(ST.set))} <span class="small">(${righe.length} titoli${ST.cerca?" per &laquo;"+esc(ST.cerca)+"&raquo;":""} &middot; clic sulle colonne per ordinare)</span></h3>
   <div class="tablewrap"><table class="aztab"><tr>${COL.map(c=>`<th class="${c[2]?"num":""} ${c[3]||""}${c[0]!="sp"?" azo":""}${ST.ord==c[0]?" on":""}" ${c[0]!="sp"?`data-o="${c[0]}"`:""}${c[0]=="st_pos"?` title="Stagionalit&agrave; di ${mese}: quota di anni positivi e rendimento medio del mese"`:""}>${c[1]}${ST.ord==c[0]?(ST.dir>0?" &uarr;":" &darr;"):""}</th>`).join("")}</tr>
    ${vis.map(t=>`<tr class="clic" data-t="${esc(t.t)}" tabindex="0"><td class="num azrk">${t.rk}</td><td class="aznome"><b>${esc(t.n)}</b><span>${esc(t.t)} &middot; ${t.l.map(nomeList).join(", ")}</span></td>
     <td>${forza(t.pt)}</td><td class="num">${prezzo(t.p,t.val)}</td><td class="num">${pc(t.v1g,2)}</td><td class="num">${pc(t.v1m)}</td><td class="num azh">${pc(t.v3m)}</td><td class="num azh">${pc(t.vytd)}</td>
     <td class="num">${pc(t.v1a)}</td><td class="num azh azst">${t.st_pos==null?'<span class="flat">n/d</span>':`<b>${t.st_pos}%</b> ${pc(t.st_media)}`}</td><td class="num azh azh3">${pc(t.t200)}</td><td class="azh2">${spark(t.sp,(t.v1a||0)>=0?"su":"giu")}</td></tr>`).join("")}
    ${!righe.length?`<tr><td colspan="12" class="small" style="text-align:center;padding:28px">Nessun titolo con questi filtri.</td></tr>`:""}</table></div>
   ${pagine(ord.length)}`;
  // eventi
  /* SUGGERIMENTI MENTRE SCRIVI: da 1 lettera, per nome o ticker (senza maiuscole/accenti), massimo 6 righe.
     Ordine: ticker esatto > ticker che inizia > nome che inizia > una parola del nome che inizia > contiene.
     Tocco/Invio su una riga = si apre direttamente la scheda del titolo (la stessa del clic in tabella).
     L'ultima riga "Mostra tutti" applica il filtro alla tabella. Frecce su/giu', Invio, Esc dalla tastiera. */
  const inp=el.querySelector(".azcerca input"),sg=el.querySelector(".azsg");let lis=[],sel=-1,tot=0;
  const nz=x=>String(x||"").normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLowerCase();
  const evid=(x,k)=>{const i=nz(x).indexOf(k);return i<0?esc(x):esc(x.slice(0,i))+"<em>"+esc(x.slice(i,i+k.length))+"</em>"+esc(x.slice(i+k.length));};
  const chiudiSg=()=>{sg.hidden=true;inp.setAttribute("aria-expanded","false");};
  const trova=k=>{const r=[];for(const t of ST.dati.titoli){const n=nz(t.n),tk=nz(t.t),tb=tk.split(".")[0];let p=0;
    if(tb==k||tk==k)p=100;else if(tk.startsWith(k))p=80;else if(n.startsWith(k))p=70;else if(n.split(/[\s,.()&-]+/).some(w=>w.startsWith(k)))p=60;else if(n.includes(k)||tk.includes(k))p=30;
    if(p)r.push([p-(t.rk||0)/1e4,t]);}
   r.sort((a,b)=>b[0]-a[0]);tot=r.length;return r.slice(0,6).map(x=>x[1]);};
  const mostra=()=>{const k=nz(inp.value.trim());if(!k){chiudiSg();return;}lis=trova(k);sel=-1;
   sg.innerHTML=lis.length?lis.map((t,i)=>`<div class="azsr" role="option" data-i="${i}"><span class="n">${evid(t.n,k)}<span class="t">${esc(t.t)}</span></span>
     <span class="p">${prezzo(t.p,t.val)}<small class="${t.v1g>0?"up":t.v1g<0?"down":"flat"}">${t.v1g==null?"":(t.v1g>0?"+":"")+fx(t.v1g,2)+"%"}</small></span>
     <span class="d">${esc(nomeSet(t.s))} &middot; ${t.l.map(nomeList).map(esc).join(", ")} &middot; ${esc(borsa(t.t))}</span></div>`).join("")
     +(tot>lis.length?`<div class="azsr azpiu" role="option" data-i="tutti">Mostra tutti i ${tot} risultati in tabella</div>`:""):`<div class="aznulla">Nessun titolo trovato per &laquo;${esc(inp.value.trim())}&raquo;.</div>`;
   sg.hidden=false;inp.setAttribute("aria-expanded","true");};
  const scegli=i=>{if(i=="tutti"){chiudiSg();ST.cerca=inp.value;ST.pag=1;disegna();return;}
   const t=lis[i];if(!t)return;chiudiSg();inp.value="";inp.blur();if(ST.cerca){ST.cerca="";ST.pag=1;disegna();}apri(t.t);};
  inp.addEventListener("input",()=>{if(!inp.value&&ST.cerca){ST.cerca="";ST.pag=1;disegna();return;}mostra();});
  inp.addEventListener("focus",()=>{if(inp.value.trim())mostra();
   if(innerWidth<760)setTimeout(()=>{try{el.querySelector(".azcw").scrollIntoView({block:"start",behavior:"smooth"});}catch(e){}},300);});   // su telefono: il campo sale in alto, la tendina resta sopra la tastiera
  inp.addEventListener("keydown",e=>{const n=lis.length+(tot>lis.length?1:0);
   if(e.key=="Escape"){chiudiSg();return;}
   if(sg.hidden||!n){if(e.key=="Enter"&&inp.value.trim()){ST.cerca=inp.value;ST.pag=1;disegna();}return;}
   if(e.key=="ArrowDown"){sel=(sel+1)%n;e.preventDefault();}else if(e.key=="ArrowUp"){sel=(sel-1+n)%n;e.preventDefault();}
   else if(e.key=="Enter"){scegli(sel<0?0:sel>=lis.length?"tutti":sel);e.preventDefault();return;}else return;
   sg.querySelectorAll(".azsr").forEach((r,i)=>r.classList.toggle("on",i==sel));const o=sg.querySelector(".azsr.on");if(o)o.scrollIntoView({block:"nearest"});});
  sg.addEventListener("mousedown",e=>{const r=e.target.closest(".azsr");if(r){e.preventDefault();scegli(r.dataset.i=="tutti"?"tutti":+r.dataset.i);}});   // mousedown: scatta prima che il campo perda il fuoco
  document.addEventListener("click",e=>{if(!e.target.closest(".azcw"))chiudiSg();});
  el.querySelectorAll(".azlist button,.azi").forEach(b=>{const f=()=>{ST.list=ST.list==b.dataset.l&&b.classList.contains("azi")?"tutti":b.dataset.l;ST.pag=1;salva();disegna();};b.onclick=f;b.onkeydown=e=>{if(e.key=="Enter")f();};});
  el.querySelectorAll(".azsc").forEach(b=>b.onclick=()=>{ST.set=b.dataset.s;ST.pag=1;disegna();el.querySelector(".azcl").scrollIntoView({behavior:"smooth",block:"start"});});
  el.querySelectorAll("th.azo").forEach(h=>h.onclick=()=>{const k=h.dataset.o;if(ST.ord==k)ST.dir=-ST.dir;else{ST.ord=k;ST.dir=(k=="n"||k=="rk")?1:-1;}ST.pag=1;salva();disegna();});
  el.querySelectorAll(".aztab tr[data-t]").forEach(r=>{r.onclick=()=>apri(r.dataset.t);r.onkeydown=e=>{if(e.key=="Enter")apri(r.dataset.t);};});
  el.querySelectorAll(".azpag button[data-pg]").forEach(b=>b.onclick=()=>{ST.pag=+b.dataset.pg;disegna();el.querySelector(".azcl").scrollIntoView({behavior:"smooth",block:"start"});});}

 // ingresso dalla vetrina della Dashboard: apre la scheda e il dettaglio del titolo
 window.ebApriTitolo=tk=>{try{go("azioni");}catch(e){}const p=carica();(p&&p.then?p:Promise.resolve()).then(()=>{if(ST.dati)apri(tk);});};

 // --- DETTAGLIO di un titolo (pannello laterale): grafico 1 anno / 2 anni / storico mensile + stagionalita'
 function apri(tk){const t=ST.dati.titoli.find(x=>x.t==tk);if(!t)return;
  let ov=document.querySelector(".azdett");if(!ov){ov=document.createElement("div");ov.className="azdett";document.body.appendChild(ov);
   ov.addEventListener("click",e=>{if(e.target==ov||e.target.closest(".azx"))chiudi();});}
  const chiudi=()=>{ov.classList.remove("on");document.removeEventListener("keydown",tasto);setTimeout(()=>{ov.innerHTML="";},250);};
  const tasto=e=>{if(e.key=="Escape")chiudi();};document.addEventListener("keydown",tasto);
  ov.innerHTML=`<aside class="azpan" role="dialog" aria-modal="true" aria-label="${esc(t.n)}"><button class="azx" aria-label="Chiudi">&times;</button>
   <div class="aztesta"><span class="small">${esc(nomeSet(t.s))} &middot; ${t.l.map(nomeList).join(", ")}</span><h3>${esc(t.n)} <small>${esc(t.t)}</small></h3>
    <div class="azprz"><b>${prezzo(t.p,t.val)}</b>${pc(t.v1g,2)}<span class="small">al ${gg(t.data)}</span></div></div>
   <div class="azcorpo">${sk("100%",230,"border-radius:14px")}<div class="azmini">${Array(6).fill(`<div>${sk("60%",11)}${sk("70%",18)}</div>`).join("")}</div>${sk("100%",150,"border-radius:14px;margin-top:18px")}</div></aside>`;
  requestAnimationFrame(()=>ov.classList.add("on"));ov.querySelector(".azx").focus({preventScroll:true});
  try{window.ebStat&&ebStat.ev("azione",{ticker:tk});}catch(e){}
  fetch(BASE+"titoli/"+encodeURIComponent(tk.replace("^","_"))+".json",{cache:"no-cache"}).then(r=>{if(!r.ok)throw new Error("HTTP "+r.status);return r.json();})
   .then(x=>{if(!ov.querySelector(".azcorpo"))return;ST.tit=x;corpo(ov,t,x);})
   .catch(e=>{const c=ov.querySelector(".azcorpo");if(c)c.innerHTML=`<div class="card azvuoto"><h3>Dettaglio non disponibile</h3><p class="small">Riprova tra qualche minuto.</p></div>`;});}

 function corpo(ov,t,x){const c=ov.querySelector(".azcorpo");
  const PER=[["1a","1 anno"],["2a","2 anni"],["max","Storico"]];
  const serie=()=>{if(ST.per=="max")return x.m.map(p=>[p[0]+"-01",p[1]]);const lim=new Date(x.d[x.d.length-1][0]);lim.setFullYear(lim.getFullYear()-(ST.per=="1a"?1:2));
   const l=lim.toISOString().slice(0,10);return x.d.filter(p=>p[0]>=l);};
  const MESI=["Gen","Feb","Mar","Apr","Mag","Giu","Lug","Ago","Set","Ott","Nov","Dic"],mc=new Date().getMonth();
  const stag=x.stag?(()=>{const v=x.stag.mesi,mx=Math.max(1,...v.filter(Boolean).map(m=>Math.abs(m.media)));
   return `<h4 class="aztit">Stagionalit&agrave; mensile <span class="small">(rendimento medio di ogni mese dal ${x.stag.dal}; in evidenza il mese in corso)</span></h4>
    <div class="azstag">${v.map((m,i)=>`<div class="${i==mc?"cur":""}" title="${m?`${MESI[i]}: media ${m.media>0?"+":""}${fx(m.media,2)}% · mediana ${m.mediana>0?"+":""}${fx(m.mediana,2)}% · positivo ${m.pos}% (${m.n} anni)`:"n/d"}">
     <span class="azsb"><i class="${m&&m.media>=0?"su":"giu"}" style="height:${m?Math.max(2,Math.abs(m.media)/mx*50):0}%;${m&&m.media<0?"top:50%":"bottom:50%"}"></i></span>
     <b class="${m&&m.media>=0?"up":"down"}">${m?(m.media>0?"+":"")+fx(m.media,1):"–"}</b><small>${m?m.pos+"%":""}</small><em>${MESI[i]}</em></div>`).join("")}</div>
    <p class="small">Numero in alto: rendimento medio del mese. Sotto: quota di anni in cui il mese &egrave; stato positivo. La stagionalit&agrave; &egrave; una statistica del passato, non una previsione.</p>`;})():"";
  c.innerHTML=`<div class="vfswitch azper">${PER.map(p=>`<button data-p="${p[0]}" class="${ST.per==p[0]?"on":""}">${p[1]}</button>`).join("")}</div>
   <div class="azgraf">${grafico(serie(),ST.per=="max",t.val)}</div>
   <div class="azmini"><div><span>1 mese</span>${pc(t.v1m)}</div><div><span>3 mesi</span>${pc(t.v3m)}</div><div><span>Da inizio anno</span>${pc(t.vytd)}</div>
    <div><span>1 anno</span>${pc(t.v1a)}</div><div><span>Dal massimo 52 sett.</span>${pc(t.dmax)}</div><div><span>Rispetto media 200g</span>${pc(t.t200)}</div></div>
   <div class="azbil">${sk("40%",16)}${sk("100%",140,"border-radius:14px;margin-top:10px")}</div>
   <div class="azprof">${sk("30%",16)}${sk("100%",14,"margin-top:12px")}${sk("90%",14,"margin-top:8px")}<div class="azmini">${Array(4).fill(`<div>${sk("60%",11)}${sk("70%",16)}</div>`).join("")}</div></div>
   ${stag}<p class="small azfonte">${esc(x.borsa||"")}${x.val?" &middot; prezzi in "+esc(x.val):""}</p>`;
  c.querySelectorAll(".azper button").forEach(b=>b.onclick=()=>{ST.per=b.dataset.p;corpo(ov,t,x);});
  bilancio(c.querySelector(".azbil"),t);profilo(c.querySelector(".azprof"),t);
  tooltip(c.querySelector(".azgraf"),serie(),t.val,ST.per=="max");}

 // --- BILANCIO (aziende USA, fonte SEC: vedi cot_radar/fondamentali.py): ricavi, utile, anni in perdita, debito netto
 //     e giudizio SOLIDA / NELLA MEDIA / INDEBITATA. File pubblico/bilanci/<T>.json; assente = azienda non USA.
 const GIU={"SOLIDA":["ok","Solida"],"NELLA MEDIA":["med","Nella media"],"INDEBITATA":["ko","Indebitata"]};
 function dollari(v){if(v==null)return "n/d";const a=Math.abs(v),s=v<0?"&minus;":"";
  return a>=1e9?s+fx(a/1e9,a>=1e11?0:1)+" mld $":a>=1e6?s+fx(a/1e6,0)+" mln $":s+fx(a,0)+" $";}
 function bilancio(box,t){if(!box)return;
  fetch(BASE+"bilanci/"+encodeURIComponent(t.t.replace("^","_"))+".json",{cache:"no-cache"}).then(r=>r.ok?r.json():null).catch(()=>null).then(b=>{
   if(!box.isConnected)return;
   if(!b||!b.anni||!b.anni.length){box.innerHTML=`<h4 class="aztit">Bilancio e trimestrali</h4><p class="small">Bilanci annuali e risultati trimestrali sono disponibili per le aziende USA (S&amp;P 500 e Nasdaq-100), fonte SEC. Gratuiti, ma la SEC copre solo le societ&agrave; americane.</p>`;return;}
   const A=b.anni,u=A[A.length-1],g=GIU[b.giudizio]||["med",b.giudizio];
   const mx=Math.max(1,...A.map(y=>Math.abs(y.ricavi||0))),W=440,H=150,T=10,B=22,bw=(W/A.length);
   const Y0=T+(H-T-B)*0.78,Ys=v=>Math.min(Y0-T,(Math.abs(v)/mx)*(Y0-T)),Yn=v=>Math.min(H-B-Y0-4,(Math.abs(v)/mx)*(Y0-T));   // zero al 78%: le perdite scendono sotto
   const barre=A.map((y,i)=>{const x=i*bw,r=Ys(y.ricavi||0),uu=y.utile>=0?Ys(y.utile):Yn(y.utile);
    return `<rect x="${(x+bw*.16).toFixed(1)}" y="${(Y0-r).toFixed(1)}" width="${(bw*.32).toFixed(1)}" height="${r.toFixed(1)}" rx="3" class="bric"><title>${y.a}: ricavi ${dollari(y.ricavi).replace("&minus;","-")}</title></rect>
     <rect x="${(x+bw*.52).toFixed(1)}" y="${(y.utile>=0?Y0-uu:Y0).toFixed(1)}" width="${(bw*.32).toFixed(1)}" height="${Math.max(1,uu).toFixed(1)}" rx="3" class="${y.utile>=0?"butu":"bper"}"><title>${y.a}: utile ${dollari(y.utile).replace("&minus;","-")}</title></rect>
     <text x="${(x+bw/2).toFixed(1)}" y="${H-6}" text-anchor="middle" class="pax">${y.a}</text>`;}).join("");
   box.innerHTML=`<h4 class="aztit">Bilancio <span class="small">(ultimi ${A.length} anni fiscali, fonte SEC)</span>
     <details class="info"><summary title="Da dove arrivano i dati" aria-label="Informazioni">i</summary><div>Bilanci annuali (10-K) depositati alla SEC: arrivano 2-3 mesi dopo la chiusura dell'anno fiscale e qui si aggiornano ogni settimana. Giudizio automatico e semplificato, non una valutazione di investimento.</div></details></h4>
    <div class="bgiu ${g[0]}"><b>${g[1]}</b><span>${esc(b.motivo||"")}</span></div>
    <div class="azmini bmini"><div><span>Ricavi ${u.a}</span><b>${dollari(u.ricavi)}</b>${b.crescita!=null?`<em class="${b.crescita>=0?"up":"down"}">${b.crescita>0?"+":""}${fx(b.crescita,1)}% l'anno</em>`:""}</div>
     <div><span>Utile netto ${u.a}</span><b class="${u.utile>=0?"up":"down"}">${dollari(u.utile)}</b><em>margine ${u.ricavi?fx(u.utile/u.ricavi*100,1)+"%":"n/d"}</em></div>
     <div><span>Anni in perdita</span><b class="${b.perdite?"down":"up"}">${b.perdite} su ${A.length}</b></div>
     <div><span>${u.dn!=null&&u.dn<0?"Liquidit&agrave; netta":"Debito netto"}</span><b>${u.dn==null?"n/d":dollari(Math.abs(u.dn))}</b><em>${u.dn!=null&&u.utile>0&&u.dn>0?fx(u.dn/u.utile,1)+" anni di utile":""}</em></div></div>
    <div class="bbox"><svg viewBox="0 0 ${W} ${H}" class="bsvg" preserveAspectRatio="none" role="img" aria-label="Ricavi e utile per anno"><line x1="0" x2="${W}" y1="${Y0}" y2="${Y0}" class="pm0"/>${barre}
     ${A.map((y,i)=>`<rect x="${(i*bw).toFixed(1)}" y="0" width="${bw.toFixed(1)}" height="${H}" class="bzona" data-i="${i}"/>`).join("")}</svg><div class="btip" hidden></div></div>
    <div class="pmasse bleg"><span><i class="bric"></i>ricavi</span><span><i class="butu"></i>utile</span><span><i class="bper"></i>perdita</span></div>${trimestrali(b)}`;
   /* v6.52: tocco (telefono) o passaggio del mouse su un anno = fumetto con ricavi, utile e margine di quell'anno */
   const bb=box.querySelector(".bbox"),tip=bb.querySelector(".btip");
   const mostra=e=>{const z=e.target.closest(".bzona");if(!z)return;const y=A[+z.dataset.i];
    bb.querySelectorAll(".bzona").forEach(q=>q.classList.toggle("on",q===z));
    tip.innerHTML=`<b>${y.a}</b><span>Ricavi <b>${dollari(y.ricavi)}</b></span><span>${y.utile>=0?"Utile":"Perdita"} <b class="${y.utile>=0?"up":"down"}">${dollari(y.utile)}</b></span>${y.ricavi?`<span>Margine <b>${fx(y.utile/y.ricavi*100,1)}%</b></span>`:""}`;
    tip.hidden=false;const r=bb.getBoundingClientRect(),zr=z.getBoundingClientRect(),w=tip.offsetWidth;
    tip.style.left=Math.max(0,Math.min(r.width-w,zr.left-r.left+zr.width/2-w/2))+"px";};
   bb.addEventListener("pointerover",mostra);bb.addEventListener("click",mostra);
   bb.addEventListener("pointerleave",e=>{if(e.pointerType=="mouse"){tip.hidden=true;bb.querySelectorAll(".bzona").forEach(q=>q.classList.remove("on"));}});});}

 // --- RISULTATI TRIMESTRALI (v6.54, cot_radar/fondamentali.py): ultimi 4 trimestri dai 10-Q/10-K della SEC con la
 //     variazione sullo stesso trimestre dell'anno prima, data degli ultimi conti e stima dei prossimi (dagli 8-K).
 const MB=["gen","feb","mar","apr","mag","giu","lug","ago","set","ott","nov","dic"];
 const dataIt=d=>{const x=new Date(d+"T12:00:00");return x.getDate()+" "+MB[x.getMonth()]+" "+x.getFullYear();};
 const nomeTrim=q=>{const a=new Date(q.ini+"T12:00:00"),b=new Date(q.fine+"T12:00:00");      // es. "Lug–Set 2026"
  const M=m=>MB[m][0].toUpperCase()+MB[m].slice(1);return M(a.getMonth())+"&ndash;"+M(b.getMonth())+" "+b.getFullYear();};
 function trimestrali(b){const T=b.trim||[];if(!T.length)return "";
  const prima=q=>T.find(z=>{const g=(new Date(q.fine)-new Date(z.fine))/864e5;return g>=350&&g<=380;});   // stesso trimestre, anno prima
  const var_=(v,o)=>v==null||o==null||!o?"":(v<0)!=(o<0)?(v<0?`<em class="down">in perdita</em>`:`<em class="up">torna in utile</em>`):(()=>{const p=(v-o)/Math.abs(o)*100;return `<em class="${p>=0?"up":"down"}">${p>0?"+":""}${fx(p,1)}%</em>`;})();
  /* var_: se cambia segno (utile -> perdita) la percentuale non ha senso: si scrive a parole */
  const eps=v=>v==null?"n/d":(v<0?"&minus;":"")+fx(Math.abs(v),2)+" $";
  const righe=T.slice(-4).reverse().map(q=>{const o=prima(q)||{};
   return `<tr><td>${nomeTrim(q)}${q.r4?"<sup>*</sup>":""}</td><td><b>${dollari(q.ricavi)}</b>${var_(q.ricavi,o.ricavi)}</td>
    <td class="tut"><b class="${q.utile>=0?"up":"down"}">${dollari(q.utile)}</b>${var_(q.utile,o.utile)}</td><td><b>${eps(q.eps)}</b>${var_(q.eps,o.eps)}</td></tr>`;}).join("");
  const c=b.conti,oggi=new Date().toISOString().slice(0,10);
  const pross=c?(c.prossimo<=oggi?`<b>attesi a breve</b>`:`<b>~ ${dataIt(c.prossimo)}</b>`):"";
  return `<h4 class="aztit tritit">Risultati trimestrali <span class="small">(ultimi 4 trimestri, fonte SEC)</span>
    <details class="info"><summary title="Come leggere la tabella" aria-label="Informazioni">i</summary><div>Ricavi, utile netto e utile per azione (EPS diluito) dai bilanci trimestrali depositati alla SEC (10-Q), con la variazione rispetto allo stesso trimestre dell'anno prima. Il 4&deg; trimestre non viene depositato da solo: &egrave; calcolato come anno intero meno i primi tre (*). La data dei prossimi conti &egrave; una stima basata sul calendario dell'anno precedente. Dati gratuiti con qualche giorno di ritardo; le stime degli analisti non sono incluse.</div></details></h4>
   ${c?`<div class="tconti"><span>Ultimi conti <b>${dataIt(c.ultimo)}</b></span><span class="prox">Prossimi conti (stima) ${pross}</span></div>`:""}
   <div class="ttab"><table><thead><tr><th>Trimestre</th><th>Ricavi</th><th class="tut">Utile netto</th><th>EPS</th></tr></thead><tbody>${righe}</tbody></table></div>
   ${T.slice(-4).some(q=>q.r4)?`<p class="small">* 4&deg; trimestre calcolato: anno intero meno i primi tre trimestri.</p>`:""}`;}

 // --- PROFILO DELL'AZIENDA (v6.52, cot_radar/profili.py): cosa fa, fondazione, sede, CEO, dipendenti, borse,
 //     eventuale acquisizione negli ultimi 10 anni. Fonti: Wikidata e Wikipedia. File pubblico/profili/<T>.json.
 function profilo(box,t){if(!box)return;
  fetch(BASE+"profili/"+encodeURIComponent(t.t.replace("^","_"))+".json",{cache:"no-cache"}).then(r=>r.ok?r.json():null).catch(()=>null).then(p=>{
   if(!box.isConnected)return;
   if(!p){box.innerHTML=`<h4 class="aztit">L'azienda</h4><p class="small">Scheda dell'azienda in preparazione: arriva con i prossimi aggiornamenti.</p>`;return;}
   if(p.vuoto){box.innerHTML=`<h4 class="aztit">L'azienda</h4><div class="azmini azfatti"><div><span>Settore</span><b>${esc(nomeSet(t.s))}</b></div><div><span>Quotata su</span><b>${esc(t.l.map(nomeList).join(", "))}</b></div></div>
    <p class="small azfonte">Descrizione non disponibile: il titolo non ha una voce su Wikidata.</p>`;return;}   // v6.54: titolo senza voce
   const f=(et,v)=>v?`<div><span>${et}</span><b>${v}</b></div>`:"";
   const dip=p.dipendenti?Number(p.dipendenti.n).toLocaleString("it-IT")+(p.dipendenti.anno?` <em>(${p.dipendenti.anno})</em>`:""):"";
   const acq=(p.acquisita_da||[])[0];
   box.innerHTML=`<h4 class="aztit">L'azienda</h4>
    ${p.desc?`<p class="azdesc">${esc(p.desc.testo)}${p.desc.lingua!="it"?' <span class="small">(da Wikipedia in inglese)</span>':""}</p>`:""}
    <div class="azmini azfatti">${f("Settore",esc(nomeSet(t.s)))}${f("Fondata",esc(p.fondata||""))}${f("Sede",esc([p.sede,p.paese].filter(Boolean).join(", ")))}
     ${f((p.ceo||[]).length>1?"Amministratori delegati":"Amministratore delegato",esc((p.ceo||[]).join(", ")))}${f("Dipendenti",dip)}
     ${f("Quotata su",esc((p.borse||[]).join(", ")||t.l.map(nomeList).join(", ")))}${acq?f("Acquisita da",esc(acq.nome)+` <em>(${acq.anno})</em>`):""}</div>
    <p class="small azfonte">Fonte: Wikidata e Wikipedia${p.desc&&p.desc.url?` &middot; <a href="${esc(p.desc.url)}" target="_blank" rel="noopener">voce completa</a>`:""}${p.sito?` &middot; <a href="${esc(p.sito)}" target="_blank" rel="noopener">sito ufficiale</a>`:""}.</p>`;});}

 function grafico(s,logar,val){if(s.length<2)return `<div class="small" style="padding:40px;text-align:center">Dati insufficienti.</div>`;
  const W=640,H=240,L=8,R=58,T=12,B=26,v=s.map(p=>p[1]),f=logar?Math.log:(z=>z),lo=f(Math.min(...v)),hi=f(Math.max(...v));
  const X=i=>L+i/(s.length-1)*(W-L-R),Y=z=>T+(hi-f(z))/(hi-lo||1)*(H-T-B);
  const path=s.map((p,i)=>(i?"L":"M")+X(i).toFixed(1)+" "+Y(p[1]).toFixed(1)).join("");
  const su=v[v.length-1]>=v[0],tick=[0,.25,.5,.75,1].map(k=>logar?Math.exp(lo+(hi-lo)*k):lo+(hi-lo)*k);
  const anni=[];let ult="";s.forEach((p,i)=>{const k=logar?p[0].slice(0,4):p[0].slice(0,7);if(k!=ult&&(logar?+k%5==0:+p[0].slice(5,7)%3==1)&&i>0)anni.push([i,logar?k:p[0].slice(5,7)+"/"+p[0].slice(2,4)]);ult=k;});
  return `<svg viewBox="0 0 ${W} ${H}" class="azsvg ${su?"su":"giu"}" preserveAspectRatio="none">
   <defs><linearGradient id="azgr" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="currentColor" stop-opacity=".28"/><stop offset="1" stop-color="currentColor" stop-opacity="0"/></linearGradient></defs>
   ${tick.map(z=>`<line x1="${L}" x2="${W-R}" y1="${Y(z)}" y2="${Y(z)}" class="pgr"/><text x="${W-R+6}" y="${Y(z)+4}" class="pax">${Number(z).toLocaleString("it-IT",{maximumFractionDigits:z<10?2:0})}</text>`).join("")}
   ${anni.map(a=>`<text x="${X(a[0])}" y="${H-7}" text-anchor="middle" class="pax">${a[1]}</text>`).join("")}
   <path d="${path}L${X(s.length-1)} ${H-B}L${L} ${H-B}Z" fill="url(#azgr)"/><path d="${path}" class="azlin"/>
   <line class="pcur" x1="0" x2="0" y1="${T}" y2="${H-B}" style="display:none"/><circle class="pcurp" r="4" style="display:none"/></svg><div class="ptip" hidden></div>`;}

 function tooltip(box,s,val,mensile){const svg=box&&box.querySelector("svg");if(!svg||s.length<2)return;const tip=box.querySelector(".ptip"),lin=svg.querySelector(".pcur"),pt=svg.querySelector(".pcurp");
  const W=640,L=8,R=58;
  svg.addEventListener("mousemove",e=>{const r=svg.getBoundingClientRect(),x=(e.clientX-r.left)/r.width*W,i=Math.max(0,Math.min(s.length-1,Math.round((x-L)/(W-L-R)*(s.length-1))));
   const X=L+i/(s.length-1)*(W-L-R);
   const path=svg.querySelector(".azlin").getAttribute("d").split(/[ML]/).filter(Boolean)[i].trim().split(" ");
   lin.setAttribute("x1",X);lin.setAttribute("x2",X);lin.style.display="";pt.setAttribute("cx",path[0]);pt.setAttribute("cy",path[1]);pt.style.display="";
   tip.hidden=false;tip.innerHTML=`<b>${mensile?fd(s[i][0].slice(0,7)):gg(s[i][0])}</b> ${prezzo(s[i][1],val)} <span>(${(s[i][1]/s[0][1]-1)>0?"+":""}${fx((s[i][1]/s[0][1]-1)*100,1)}%)</span>`;
   tip.style.left=Math.min(r.width-190,Math.max(0,e.clientX-r.left+12))+"px";});
  svg.addEventListener("mouseleave",()=>{lin.style.display="none";pt.style.display="none";tip.hidden=true;});}
})();}catch(e){fail('Azioni','azioni',e);}
