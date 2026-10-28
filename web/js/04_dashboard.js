/* ---------- segnali ----------
   Riepilogo in alto, settori, schede delle coppie (card) e degli altri strumenti (acard).
   mtag() decide l'etichetta "Mercato conferma / contro / gia' scontato" confrontando i segni di COT e Mercato. */
try{

/* RIQUADRI IN ALTO (v6.40): ognuno risponde a UNA domanda semplice con un disegno che si capisce a colpo d'occhio:
   1) segnali attivi = barra verde/rossa rialzo-ribasso + etichetta STRONG;  2) clima = tachimetro PAURA -> FIDUCIA;
   3) prossima rotazione e 4) nuovi dati COT = conto alla rovescia (giorni/ore/min) + barra del tempo gia' passato.
   Il conto alla rovescia si aggiorna ogni 30 s e si ferma da solo se i riquadri spariscono dalla pagina. */
(function kpis(){
 const altri=Object.values(D.assets).filter(a=>a.key!="USD"&&a.group!="Valute");
 const tutti=D.pairs.map(p=>p.label).concat(altri.map(a=>a.label));
 const su=tutti.filter(l=>l.includes("BUY")).length,giu=tutti.filter(l=>l.includes("SELL")).length,strong=tutti.filter(l=>l.startsWith("STRONG")).length;
 const r=D.market?D.market.risk:null;                       // -100 (paura) ... +100 (fiducia)
 const [rl,rc]=r==null?["n/d","var(--mute)"]:r>=30?["FIDUCIA","var(--b)"]:r<=-30?["PAURA","var(--s)"]:["NEUTRO","var(--warn)"];
 const po=D.port,cot=D.sources[0]||{};
 const GG=["domenica","lunedì","martedì","mercoledì","giovedì","venerdì","sabato"],MM=["gennaio","febbraio","marzo","aprile","maggio","giugno","luglio","agosto","settembre","ottobre","novembre","dicembre"];
 const roma=(ymd,h)=>{const [y,m,d]=ymd.split("-").map(Number),g=Date.UTC(y,m-1,d,h);   // "ymd hh:00" a Roma (ora legale/solare)
  const hr=+new Intl.DateTimeFormat("en-GB",{timeZone:"Europe/Rome",hour:"2-digit",hourCycle:"h23"}).formatToParts(new Date(g)).find(x=>x.type=="hour").value;
  return new Date(g-((hr-h+24)%24)*3600e3);};
 let rotA=null,rotDa=null;try{if(po&&po.prossima){rotA=roma(po.prossima,9);rotDa=po.rotazione?roma(po.rotazione,9):new Date(rotA-30*864e5);}}catch(e){}
 const cotA=cot.next_ms?new Date(cot.next_ms):null,cotDa=cotA?new Date(cotA-7*864e5):null;
 const ico={seg:'<path d="M3 17l6-6 4 4 8-8"/><path d="M15 7h6v6"/>',clima:'<path d="M12 3v2M5.6 5.6l1.4 1.4M3 12h2M19 12h2M17 7l1.4-1.4"/><circle cx="12" cy="14" r="5"/>',
  rot:'<path d="M21 12a9 9 0 1 1-3-6.7"/><path d="M21 4v5h-5"/>',cot:'<rect x="3" y="5" width="18" height="16" rx="3"/><path d="M3 10h18M8 3v4M16 3v4"/>'};
 const testa=(k,t,q)=>`<div class="kzt"><span class="kzico"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">${ico[k]}</svg></span><h3>${t}</h3><span class="kzvai" aria-hidden="true">&rsaquo;</span></div><p class="kzq">${q}</p>`;
 const tot=su+giu||1,ang=r==null?0:Math.max(-1,Math.min(1,r/100))*80;
 const rd=rotA?`${GG[rotA.getDay()]} ${rotA.getDate()} ${MM[rotA.getMonth()]}`:"n/d";
 $("kpis").className="kzg";
 $("kpis").innerHTML=`<a class="kz kz1" href="#cards" data-scorri="cards" title="Vai ai segnali">${testa("seg","Segnali attivi","Quante occasioni vede oggi il radar?")}
   <div class="kzb"><div class="kzbig">${su+giu}</div>${strong?`<span class="kzchip" title="I segnali più forti">&#9733; ${strong} STRONG</span>`:""}</div>
   <div class="kzsplit"><i class="su" style="width:${su/tot*100}%"></i><i class="giu" style="width:${giu/tot*100}%"></i></div>
   <div class="kzleg"><span><b class="up">&#9650; ${su}</b> al rialzo</span><span>al ribasso <b class="dn">&#9660; ${giu}</b></span></div></a>
  <a class="kz kz2" href="#mkt" data-vai="mkt" title="Vai al clima di mercato" style="--clima:${rc}">${testa("clima","Clima del mercato","Gli investitori hanno paura o fiducia?")}
   <div class="kzb kzbc"><div class="kzgauge" aria-hidden="true"><svg viewBox="0 0 132 74"><defs><linearGradient id="kzarco" x1="0" x2="1"><stop offset="0" stop-color="#f2716b"/><stop offset=".5" stop-color="#e9b44c"/><stop offset="1" stop-color="#4fd6a3"/></linearGradient></defs>
     <path d="M12 66 A54 54 0 0 1 120 66" fill="none" stroke="#121d31" stroke-width="12" stroke-linecap="round"/><path d="M12 66 A54 54 0 0 1 120 66" fill="none" stroke="url(#kzarco)" stroke-width="12" stroke-linecap="round" opacity=".9"/>
     <g class="kzago" style="transform:rotate(${ang}deg)"><line x1="66" y1="66" x2="66" y2="22" stroke="#f1f5fb" stroke-width="3.5" stroke-linecap="round"/></g><circle cx="66" cy="66" r="6" fill="#f1f5fb"/></svg>
     <div class="kzestremi"><span class="p">PAURA</span><span class="f">FIDUCIA</span></div></div><div class="kzstato">${rl}</div></div>
   <div class="kzn">Misurato su paura (VIX), rischio delle obbligazioni e tassi, ultime 4 settimane</div></a>
  <a class="kz kz3" href="#port" data-vai="port" title="Apri i Portafogli">${testa("rot","Prossima rotazione","Quando si aggiornano i portafogli?")}
   <div class="kzcd" data-cd="rot"></div><div class="kzprog"><i data-pr="rot"></i></div><div class="kzquando"><b>${rd}</b>${rotA?" &middot; ore 9:00":""}</div></a>
  <a class="kz kz4" href="#assets" data-vai="assets" title="Vedi la forza di ogni strumento">${testa("cot","Nuovi dati COT","Quando arrivano i dati nuovi?")}
   <div class="kzcd" data-cd="cot"></div><div class="kzprog"><i data-pr="cot"></i></div><div class="kzquando"><b>${esc(cot.next||"n/d")}</b>${cot.last?` &middot; ora i dati sono del ${esc(String(cot.last).replace(/^\w+ /,"").slice(0,5))}`:""}</div></a>`;
 // clic su "Segnali attivi": scorre alle card dei segnali nella stessa scheda
 const s1=$("kpis").querySelector("[data-scorri]");if(s1)s1.onclick=e=>{e.preventDefault();const t=$("cards");if(t)t.scrollIntoView({behavior:"smooth",block:"start"});};
 const z=n=>String(n).padStart(2,"0");
 function cd(k,da,a){const box=$("kpis").querySelector(`[data-cd=${k}]`),bar=$("kpis").querySelector(`[data-pr=${k}]`);if(!box)return false;
  if(!a){box.innerHTML='<span class="small">data non disponibile</span>';return true;}
  const ms=Math.max(0,a-Date.now()),g=Math.floor(ms/864e5),h=Math.floor(ms/36e5)%24,m=Math.floor(ms/6e4)%60;
  box.innerHTML=[[g,"giorni"],[h,"ore"],[m,"min"]].map(([v,l])=>`<div><b>${z(v)}</b><small>${l}</small></div>`).join("");
  bar.style.width=Math.min(100,Math.max(0,(Date.now()-da)/(a-da)*100))+"%";return true;}
 const giro=()=>{if(!cd("rot",rotDa,rotA)||!cd("cot",cotDa,cotA))clearInterval(t);};
 const t=setInterval(giro,30000);giro();})();

/* PROSSIMI EVENTI ad alto impatto (motore notizie): BANNER A SCORRIMENTO LENTO (ticker).
   Ogni evento e' una "pillola": valuta, nome, giorno e ora, quanto manca. Colori: ambra = banca centrale (Fed, BCE),
   blu = dato macro (CPI, NFP); OGGI in rosso, DOMANI in ambra.
   - Scorre da destra a sinistra a velocita' costante (VEL px al secondo), all'infinito senza salti: la lista e'
     ripetuta finche' riempie la larghezza e poi duplicata, l'animazione sposta il nastro di meta' della sua lunghezza.
   - Si ferma passando il mouse o toccando (per leggere), riparte uscendo. Ai bordi sfuma.
   - Chi ha chiesto "riduci animazioni" nel sistema operativo vede le pillole ferme, una accanto all'altra (a capo).
   - Si ricalcola quando cambia la larghezza della finestra. La spiegazione sta nel tasto (i). */
try{const ev=D.eventi||[],VEL=38;
 const GG=["dom","lun","mar","mer","gio","ven","sab"],oggi=new Date();oggi.setHours(0,0,0,0);
 const pill=e=>{const q=new Date(e.quando.replace(" ","T")),g=new Date(q);g.setHours(0,0,0,0);
  const diff=Math.round((g-oggi)/864e5),quando=diff<=0?"OGGI":diff==1?"DOMANI":`tra ${diff} giorni`;
  return `<span class="evp ${e.tipo=="banca"?"banca":"dato"}${diff<=0?" oggi":diff==1?" domani":""}" title="${e.tipo=="banca"?"Banca centrale":"Dato macro"}">
   <span class="evv">${esc(e.valuta)}</span><b>${esc(e.nome)}</b><span class="evq">${GG[q.getDay()]} ${e.quando.slice(8,10)}/${e.quando.slice(5,7)} <b>${e.quando.slice(11)}</b></span><em>${quando}</em></span>`;};
 $("eventi").innerHTML=ev.length?`<div class="card eventi"><div class="evhead"><h3>Prossimi eventi ad alto impatto</h3>
  <details class="info"><summary title="Come usarli" aria-label="Informazioni">i</summary><div>Il giorno del dato la volatilit&agrave; sale: per lo swing conviene valutare l'ingresso <b>dopo</b> l'uscita. Dopo il dato la riga "Notizie" delle card mostra se la sorpresa rafforza o penalizza il segnale.</div></details>
  ${D.agenda&&String(D.agenda.fonte||"").startsWith("financecalendar")?`<span class="small evfonte">Calendario: <a href="https://www.financecalendar.com" target="_blank" rel="noopener">financecalendar.com</a></span>`:""}</div>
  <div class="evnastro" role="marquee" aria-label="Prossimi eventi"><div class="evtrack"></div></div></div>`:"";
 const nastro=$("eventi").querySelector(".evnastro"),track=nastro&&nastro.querySelector(".evtrack");
 const base=ev.map(pill).join("");
 // Nastro a scorrimento lento CONTROLLATO DA JS (non piu' da CSS): si puo' trascinare avanti e indietro con dito o mouse,
 // al rilascio prosegue per inerzia e poi torna dolcemente alla velocita' di crociera (mai "inchiodato").
 // x = spostamento corrente in px (0 .. -L, ciclico), vel = velocita' istantanea px/s, crociera = -VEL.
 let x=0,vel=-VEL,L=1,trascina=false,sopra=false,ultimoT=0,rafId=0,mosso=0,px0=0,pt=0,vm=0;
 const applica=()=>{track.style.transform=`translate3d(${x.toFixed(2)}px,0,0)`;};
 const cicla=()=>{if(L>1){x=x%L;if(x>0)x-=L;}};
 function giro(t){rafId=requestAnimationFrame(giro);
  const dt=Math.min(0.05,(t-(ultimoT||t))/1000);ultimoT=t;if(trascina||!L)return;
  const meta=sopra?0:-VEL;                          // col mouse sopra rallenta fino a fermarsi (si legge), senza scatti
  vel+=(meta-vel)*Math.min(1,dt*(sopra?5:1.6));      // ritorno morbido alla crociera dopo il rilascio
  x+=vel*dt;cicla();applica();}
 function monta(){if(!track)return;
  if(matchMedia("(prefers-reduced-motion: reduce)").matches){track.innerHTML=base;nastro.classList.add("fermo");cancelAnimationFrame(rafId);return;}
  nastro.classList.remove("fermo");track.innerHTML=`<span class="evmeta">${base}</span>`;
  const meta=track.firstChild,W=nastro.clientWidth||800;let n=1;
  while(meta.scrollWidth<W&&n<30){meta.insertAdjacentHTML("beforeend",base);n++;}   // riempi la larghezza
  track.insertAdjacentHTML("beforeend",`<span class="evmeta" aria-hidden="true">${meta.innerHTML}</span>`);
  L=meta.getBoundingClientRect().width;cicla();applica();
  cancelAnimationFrame(rafId);ultimoT=0;rafId=requestAnimationFrame(giro);}
 monta();let rt=0;addEventListener("resize",()=>{clearTimeout(rt);rt=setTimeout(monta,250);});
 if(nastro&&track){
  nastro.addEventListener("pointerdown",e=>{if(e.pointerType=="mouse"&&e.button!==0)return;
   trascina=true;mosso=0;px0=e.clientX;pt=performance.now();vm=0;nastro.classList.add("presa");
   try{nastro.setPointerCapture(e.pointerId);}catch(_){}});
  nastro.addEventListener("pointermove",e=>{if(!trascina)return;
   const dx=e.clientX-px0,now=performance.now(),dtm=Math.max(1,now-pt);px0=e.clientX;pt=now;
   mosso+=Math.abs(dx);x+=dx;cicla();applica();
   vm=vm*0.6+(dx/dtm*1000)*0.4;});                   // velocita' del gesto (media mobile) per l'inerzia
  const rilascia=()=>{if(!trascina)return;trascina=false;nastro.classList.remove("presa");
   vel=Math.max(-1400,Math.min(1400,vm));ultimoT=0;};
  nastro.addEventListener("pointerup",rilascia);nastro.addEventListener("pointercancel",rilascia);
  nastro.addEventListener("pointerenter",e=>{if(e.pointerType=="mouse")sopra=true;});
  nastro.addEventListener("pointerleave",e=>{if(e.pointerType=="mouse")sopra=false;});
  nastro.addEventListener("click",e=>{if(mosso>6){e.preventDefault();e.stopPropagation();}},true);   // un trascinamento non e' un clic
  nastro.addEventListener("keydown",e=>{if(e.key=="ArrowLeft"||e.key=="ArrowRight"){x+=(e.key=="ArrowLeft"?1:-1)*140;cicla();applica();e.preventDefault();}});
  nastro.tabIndex=0;
  document.addEventListener("visibilitychange",()=>{ultimoT=0;});}
}catch(e){fail("Prossimi eventi","eventi",e);}
$("sectors").innerHTML=SEC.filter(g=>byS[g]).map(g=>{const l=byS[g],avg=l.reduce((x,a)=>x+a.score,0)/l.length;
 const up=l.filter(a=>a.score>=M.normal).length,dn=l.filter(a=>a.score<=-M.normal).length;
 return `<div class="sec" data-g="${g}" style="--bc:${COL[lab(avg*1.6)]}"><b>${g}</b><span>${fmt(avg)}</span><small>${up} in acquisto &middot; ${dn} in vendita</small></div>`}).join("");
document.querySelectorAll(".sec").forEach(x=>x.onclick=()=>{go("assets");selS(x.dataset.g);});
var L5=["STRONG BUY","BUY","NEUTRO","SELL","STRONG SELL"];
$("summary").innerHTML=L5.map(l=>`<div class="sum" style="--bc:${COL[l]}"><b>${D.pairs.filter(p=>p.label==l).length}</b><small>${l}</small></div>`).join("");
function sideRow(k){const a=D.assets[k]||{score:0};const v=verb(a.score);return `<div class="r"><span>${k} <span class="small">${nm(k)}</span></span><span class="${v[1]}">${v[2]} ${v[0]} (${fmt(a.score)})</span></div>`;}
function why(p){const b=verb(D.assets[p.base].score)[0],q=verb(D.assets[p.quote].score)[0];
 const dir=p.score>=M.normal?"tende a SALIRE":p.score<=-M.normal?"tende a SCENDERE":"non ha una direzione chiara";
 if(p.div)return `Speculatori: ${b} ${p.base} e ${q} ${p.quote}. Spingono in direzioni opposte, quindi ${p.pair} ${dir}.`;
 const st=x=>x=="neutri"?"sono neutri":x.toLowerCase();   // "vendono"/"comprano"/"sono neutri"
 return `Su ${p.base} gli speculatori ${st(b)}, su ${p.quote} ${st(q)}: nessuna divergenza netta, ${p.pair} ${dir} (segnale meno forte).`;}
/* TAG DI CONFERMA (vedi cot_radar/conferme.py):
   ctag = i Commercials (hedger) agli estremi confermano o contrastano il segnale
   (v6.16: tolto il tag "storico %" e ogni voto di AFFIDABILITA': il backtest ha mostrato che non ordina i
   risultati, BASSA andava meglio di MEDIA. Il dato grezzo "Storico" resta solo nel pannello sotto il grafico.) */
function ctag(acc){return acc?`<span class="tag ${acc=="conferma"?"ok":"ko"}" title="Commercials (hedger) agli estremi">Commercials: ${acc}</span>`:"";}
/* stagtag = stagionalita' delle prossime 4 settimane: verde se va nel verso del segnale, arancio se contro */
function stagtag(st,score){if(!st||!st.robusto)return "";const su=st.score>0;
 return `<span class="tag ${Math.sign(st.score)==Math.sign(score)?"ok":"ko"}" title="Stagionalita': ${su?"salito":"sceso"} ${su?st.su:st.n-st.su} anni su ${st.n} nelle prossime 4 settimane">stagione ${su?"&uarr;":"&darr;"} ${su?st.su:st.n-st.su}/${st.n}</span>`;}
/* CARD A 3 RIGHE: Smart money (COT) / Macro (modello di mercato) / Notizie (motore notizie).
   Verde = spinge la coppia su, rosso = giu', grigio = neutro. Il dettaglio resta nel pannello sotto il grafico. */
function riga(nome,txt,v,breve){const c=v>0?"up":v<0?"down":"flat";
 return `<div class="r3 ${c}"><span><i></i>${nome}</span><b class="${c}">${txt}</b><small>${breve||"&nbsp;"}</small></div>`;}
function flussi3(p){const fb=new Map((D.assets[p.base]||{}).flussi||[]),fq=new Map((D.assets[p.quote]||{}).flussi||[]);
 const d=[...fb.keys()].filter(x=>fq.has(x)).sort().slice(-3).map(x=>fb.get(x)-fq.get(x));
 if(d.length<3)return "";const su=d.filter(x=>x>0).length;return su==3?"flussi 3/3 in acquisto":su==0?"flussi 3/3 in vendita":`flussi ${Math.max(su,3-su)}/3`;}
/* TRE RIQUADRI affiancati (Smart money / Macro / Notizie): etichetta, verdetto, valore breve.
   Le spiegazioni lunghe vanno nella riga "det" sotto, cosi' i riquadri restano leggibili anche stretti. */
function trio(p){const n=p.news,cot=p.cot,mac=p.macro,det=[];
 const sm=riga("Smart money",cot>=M.normal?"LONG":cot<=-M.normal?"SHORT":"NEUTRO",cot>=M.normal?1:cot<=-M.normal?-1:0,`COT ${fmt(cot)}`);
 const f3=flussi3(p);if(f3)det.push(f3);
 const mtop=((D.assets[p.base]||{}).mkt||{}).top;
 const ma=mac==null?riga("Macro","n/d",0,"non disponibile"):riga("Macro",Math.abs(mac)<25?"SCONTATO":mac>0?"LONG":"SHORT",Math.abs(mac)<25?0:mac,fmt(mac));
 if(mac!=null&&mtop&&mtop[0])det.push("driver macro: "+esc(mtop[0].name));
 let ne;
 if(!n)ne=riga("Notizie","&mdash;",0,"nessun evento");
 else{const ultimo=(n.eventi||[]).filter(e=>e.z!=null).slice(-1)[0];
  const txt=n.oggi.length?"&#9889; OGGI":ultimo?n.effetto.toUpperCase():"&mdash;";
  const breve=ultimo?`${ultimo.z>=0?"+":""}${fx(ultimo.z,1)}&sigma; &middot; ${n.adj>=0?"+":""}${fx(n.adj,0)}`:"";
  if(ultimo)det.push(`${esc(ultimo.nome.split(" ").slice(0,-2).join(" ")||ultimo.nome)}: punteggio corretto ${fmt(n.score)}`);
  if(n.oggi.length)det.push(`${esc(n.oggi[0])}: valuta l'ingresso dopo il dato`);
  ne=riga("Notizie",txt,n.oggi.length?0:n.effetto=="rafforza"?Math.sign(p.score):n.effetto=="penalizza"?-Math.sign(p.score):0,breve||"nessun evento");}
 const st=p.stag;let sa;                                   // STAGIONALITA' (prossime 4 settimane, vedi stagionalita.py)
 if(!st)sa=riga("Stagionalit&agrave;","n/d",0,"storico corto");
 else if(!st.robusto)sa=riga("Stagionalit&agrave;","NEUTRA",0,"non affidabile");
 else{sa=riga("Stagionalit&agrave;",st.score>0?"RIALZO":"RIBASSO",st.score,`${st.score>0?st.su:st.n-st.su}/${st.n} anni`);
  det.push(`stagionalit&agrave;: ${st.score>0?"salito":"sceso"} ${st.score>0?st.su:st.n-st.su} anni su ${st.n} nelle prossime 4 settimane (mediana ${st.med>=0?"+":""}${fx(st.med)}%)`);}
 if(p.corretto!=null&&Math.round(p.corretto)!=Math.round(p.score))det.push(`<b>punteggio corretto ${fmt(p.score)} &rarr; ${fmt(p.corretto)}</b>`);
 return `<div class="trio">${sm}${ma}${ne}${sa}</div>${det.length?`<div class="det">${det.join(" &middot; ")}</div>`:""}`;}
function card(p){return `<div class="card clic" data-tv="p:${p.pair}" title="Clic: grafico a candele"><div class="pairhead"><div><span class="pair">${p.pair}</span><div class="sotto">${badge(p.label)}</div></div>${anello(p.score)}</div>${trio(p)}
 <div class="rows">${sideRow(p.base)}${sideRow(p.quote)}</div>
 <div class="tags">${p.div?'<span class="tag div">Divergenza</span>':''}${mtag(p.cot,p.macro)}${p.new?`<span class="tag new">Nuovo (prima ${p.prev})</span>`:''}${ctag(p.comm_acc)}</div>
 <div class="why">${why(p)}</div></div>`;}
var act=D.pairs.filter(p=>p.label!="NEUTRO");
$("cards").innerHTML=act.length?act.map(card).join(""):`<div class="card">Nessun segnale attivo sulle valute questa settimana.</div>`;
function acard(a){const v=verb(a.score),m=a.mkt;return `<div class="card clic" data-tv="a:${a.key}" title="Clic: grafico a candele"><div class="pairhead"><div><span class="pair" style="font-size:19px">${a.name}</span><div class="sotto">${badge(a.label)}</div></div>${anello(a.score)}</div>
 <div class="small" style="margin-top:8px">${a.it?esc(a.it)+" &middot; ":""}${a.group} &middot; ${a.key} &middot; COT Index ${a.idx}/100</div>${split(a.cot,a.macro)}
 <div class="tags">${mtag(a.cot,a.macro)}${a.new?`<span class="tag new">Nuovo (prima ${a.prev_label})</span>`:''}${a.crowded?'<span class="tag ko">affollato</span>':''}${ctag(a.comm_acc)}${stagtag(a.stag,a.score)}</div>
 <div class="why">Speculatori: <b class="${v[1]}">${v[0]}</b>, ${fmt(a.d_net)} contratti in settimana, ${fmt(a.d_net4)} in 4 settimane.${m?` Mercato: ${m.status.toLowerCase()}.`:''}${NOTE[a.key]||NOTE[a.group]?' '+(NOTE[a.key]||NOTE[a.group]):''}</div></div>`;}
var oth=Object.values(D.assets).filter(a=>a.group!="Valute"&&a.label!="NEUTRO").sort((x,y)=>Math.abs(y.score)-Math.abs(x.score));
$("acards").innerHTML=oth.length?oth.map(acard).join(""):`<div class="card">Nessun segnale attivo.</div>`;
/* ANELLI ALLINEATI: il diametro dell'anello = altezza del blocco a sinistra (nome + pillola).
   ResizeObserver ricalcola quando la scheda diventa visibile, cambia larghezza o il nome va a capo. */
(function(){const allinea=sx=>{const a=sx.parentElement.querySelector(".anello"),h=Math.round(sx.getBoundingClientRect().height);
  if(a&&h>=40){a.style.width=a.style.height=h+"px";}};      // h<40: scheda nascosta o misura non pronta
 // requestAnimationFrame: la misura si applica al fotogramma dopo, cosi' il browser non entra in un ciclo di ridimensionamenti
 const ro=window.ResizeObserver?new ResizeObserver(v=>requestAnimationFrame(()=>v.forEach(x=>allinea(x.target)))):null;
 document.querySelectorAll(".pairhead").forEach(h=>{const sx=h.firstElementChild;if(!sx||!h.querySelector(".anello"))return;allinea(sx);if(ro)ro.observe(sx);});})();
}catch(e){fail('Dashboard','sig',e);}

