/* ==========================================================================
   app.js - disegna la dashboard a partire dai dati
   --------------------------------------------------------------------------
   I dati arrivano da Python nella costante D (vedi index.html):
     D.meta      impostazioni e ora di aggiornamento      D.sources   stato di ogni fonte
     D.assets    ogni strumento (punteggi, COT, mercato)   D.pairs     coppie di valute
     D.market    driver di mercato                         D.mortgage  mutui
     D.fed       liquidita' Fed                            D.corr      matrice delle correlazioni
   Ogni sezione qui sotto riempie un pezzo di pagina (gli id corrispondono a quelli di index.html).
   Si usano "template literal" `...${valore}...` per costruire l'HTML.
   DEBUG: F12 -> Console. Scrivi D per vedere i dati, D.assets.EUR per un singolo strumento.
          Un errore in rosso nella Console indica file e riga del problema.
   ========================================================================== */
const M=D.meta;            // impostazioni (pesi, soglie, ora di aggiornamento)

const COL={"STRONG BUY":"var(--sb)","BUY":"var(--b)","NEUTRO":"var(--n)","SELL":"var(--s)","STRONG SELL":"var(--ss)"};
const fmt=n=>{if(n==null||isNaN(n))return"n/d";const r=Math.round(n);return(r>0?"+":"")+(r==0?0:r).toLocaleString("it-IT");};
const fx=(n,d=2)=>n==null||isNaN(n)?"n/d":n.toLocaleString("it-IT",{minimumFractionDigits:d,maximumFractionDigits:d});
const sg=(n,d=2)=>n==null||isNaN(n)?"n/d":(n>0?"+":"")+fx(n,d);
const c2=v=>{const t=v.toFixed(2);return t=="-0.00"?"0.00":t;};const c1=v=>{const t=v.toFixed(1);return t=="-0.0"?"0.0":t;};
const verb=s=>s>=20?["COMPRANO","up","▲"]:s<=-20?["VENDONO","down","▼"]:["neutri","flat","■"];
const badge=l=>`<span class="badge" style="--bc:${COL[l]}">${l}</span>`;   // pillola: bordo e testo nel colore del segnale
const pos=s=>Math.max(0,Math.min(100,(s+100)/2));
const nm=k=>(D.assets[k]||{}).name||k;
const esc=t=>String(t).replace(/[&<>]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));
const lab=s=>Math.abs(s)>=M.strong?(s>0?"STRONG BUY":"STRONG SELL"):Math.abs(s)>=M.normal?(s>0?"BUY":"SELL"):"NEUTRO";
const $=id=>document.getElementById(id);


/* ---------- aiuti comuni a piu' sezioni ---------- */
const SEC=D.sectors,byS={};Object.values(D.assets).forEach(a=>{if(a.key!="USD")(byS[a.group]=byS[a.group]||[]).push(a);});
const NOTE={"Tassi USA":"Futures sui titoli di Stato: COMPRARE = scommettere su tassi in calo.","VIX":"Sul VIX comprare = aspettarsi piu' volatilita'."};
function mtag(cot,mac){if(mac==null)return`<span class="tag">mercato: n/d</span>`;if(Math.abs(mac)<25)return`<span class="tag">mercato: gia' scontato</span>`;
 if(Math.abs(cot)<10)return`<span class="tag">mercato ${mac>0?'rialzista':'ribassista'}</span>`;
 return (mac>0)==(cot>0)?`<span class="tag ok">Mercato conferma</span>`:`<span class="tag ko">Mercato contro</span>`;}
const split=(cot,mac)=>`<div class="split"><div>COT (${Math.round((1-M.mw)*100)}%)<b>${fmt(cot)}</b></div><div>Mercato (${Math.round(M.mw*100)}%)<b>${mac==null?'n/d':fmt(mac)}</b></div></div>`;
/* ANELLO del punteggio: il numero e' l'intensita' (0-100, senza segno), il colore la direzione
   (verde = acquisto, rosso = vendita, grigio = neutro). L'arco pieno = punteggio 100. */
const anello=s=>{const v=Math.min(100,Math.abs(Math.round(s||0))),r=24,c=2*Math.PI*r,
 col=s>=M.normal?"var(--b)":s<=-M.normal?"var(--s)":"var(--n)";
 return `<div class="anello" title="Punteggio finale ${fmt(s)} (intensita' ${v}/100)"><svg viewBox="0 0 60 60"><circle cx="30" cy="30" r="${r}" class="fondo"/>`+
  `<circle cx="30" cy="30" r="${r}" class="arco" style="stroke:${col}" stroke-dasharray="${(c*v/100).toFixed(1)} ${c.toFixed(1)}" transform="rotate(-90 30 30)"/></svg><b>${v}</b><small>/100</small></div>`;};
const meter=s=>`<div class="meter"><i style="left:${pos(s)}%"></i></div><div class="scale"><span>-100 vendi</span><span>finale <b style="color:var(--ink)">${fmt(s)}</b></span><span>compra +100</span></div>`;
function fd(s){if(!s)return"";const m=["gen","feb","mar","apr","mag","giu","lug","ago","set","ott","nov","dic"];if(s.length==7)return m[+s.slice(5,7)-1]+" "+s.slice(0,4);return s.slice(8,10)+"/"+s.slice(5,7)+"/"+s.slice(0,4);}

/* ---------- PROTEZIONE ANTI-CROLLO ----------
   Ogni sezione qui sotto e' racchiusa in try { ... } catch: se una sezione ha un errore (bug o dati strani)
   al suo posto compare un riquadro "Sezione non disponibile" e TUTTE le altre continuano a funzionare.
   Gli errori imprevisti (anche dentro i clic) mostrano un avviso rosso in alto invece di una pagina bianca.
   DEBUG: F12 -> Console: ogni errore e' stampato con il nome della sezione. window.__errori li elenca tutti. */
window.__errori=[];
function fail(sezione,contenitore,e){
 window.__errori.push({sezione,errore:String(e&&e.stack||e)});
 console.error("[Edge Board] sezione '"+sezione+"' non disponibile:",e);
 const box=`<div class="alert red"><b>Sezione "${sezione}" non disponibile.</b> Errore: ${esc(e&&e.message||e)}. Le altre sezioni funzionano normalmente.</div>`;
 const el=contenitore&&document.getElementById(contenitore);
 if(el)el.insertAdjacentHTML("afterbegin",box);else{const a=document.getElementById("alerts");if(a)a.insertAdjacentHTML("beforeend",box);}
}
function bannerErrore(msg){const a=document.getElementById("alerts");if(a&&!a.querySelector(".js-err"))a.insertAdjacentHTML("afterbegin",`<div class="alert red js-err"><b>Errore imprevisto nella pagina:</b> ${esc(msg)}. Ricarica la pagina.</div>`);}
/* "ResizeObserver loop..." e' un avviso innocuo del browser (zoom, rotazione dello schermo): non e' un errore della pagina */
window.addEventListener("error",ev=>{if(/ResizeObserver loop/i.test(ev.message||""))return;
 window.__errori.push({sezione:"pagina",errore:String(ev.message)});bannerErrore(ev.message);});
/* VERSIONE NUOVA? Il browser (o GitHub Pages, ~10 minuti) puo' tenere in memoria la pagina vecchia.
   Ogni 10 minuti leggiamo stato.json "fresco": se e' piu' recente dei dati di questa pagina, compare
   un avviso con il pulsante per ricaricare. Solo sul sito (http/https), non sul file aperto dal PC. */
function controllaVersione(){if(!/^https?:/.test(location.protocol)||!D.stato||!D.stato.creato)return;
 fetch("stato.json?v="+Date.now(),{cache:"no-store"}).then(r=>r.ok?r.json():null).then(s=>{
  if(!s||!s.creato||s.creato<=D.stato.creato||s.esito=="scartato"||document.getElementById("nuovaversione"))return;
  const d=document.createElement("div");d.id="nuovaversione";d.className="alert";
  d.style.cssText="position:fixed;left:50%;bottom:16px;transform:translateX(-50%);z-index:60;display:flex;gap:12px;align-items:center;box-shadow:0 6px 24px rgba(0,0,0,.18)";
  d.innerHTML=`<span>&Egrave; disponibile una versione pi&ugrave; recente della dashboard.</span><button class="tvbtn" onclick="location.reload()">Aggiorna</button>`;
  document.body.appendChild(d);}).catch(()=>{});}   // senza rete: nessun avviso, nessun errore
controllaVersione();setInterval(controllaVersione,10*60*1000);
window.addEventListener("unhandledrejection",ev=>{window.__errori.push({sezione:"pagina",errore:String(ev.reason)});bannerErrore(ev.reason);});

/* ---------- stato fonti e avvisi ----------
   Un riquadro per fonte (pallino verde/giallo/rosso) e, sotto, gli avvisi in chiaro.
   Se l'ora attuale supera la prossima uscita prevista (next_ms), la pagina avvisa che ci sono dati nuovi. */
try{
$("updated").innerHTML=`<span class="dataagg" title="Ultimo aggiornamento dei dati">${M.now}</span>`;
var DOT={ok:"var(--b)",cache:"var(--warn)",late:"var(--s)",err:"var(--s)"};
var STX={ok:"aggiornato",cache:"dati salvati (offline)",late:"IN RITARDO",err:"errore"};
/* stato delle fonti nella sidebar: pallino + nome, sotto data e prossimo aggiornamento (a barra ridotta resta il pallino) */
$("status").innerHTML=D.sources.filter(s=>s.st!="err").map(s=>`<div class="srow" title="${esc(s.name)}: ${esc(s.last)} (${STX[s.st]}) - prossimo: ${esc(s.next)}"><i style="background:${DOT[s.st]};color:${DOT[s.st]}"></i>
 <div class="stx"><b>${s.name}</b><small>${s.last} &middot; ${STX[s.st]}</small><small>Prossimo: ${s.next}</small></div></div>`).join("");
var al=[];D.sources.forEach(s=>{if(s.msg)al.push(`<div class="alert ${s.st=='late'||s.st=='err'?'red':''}"><b>${s.name}:</b> ${esc(s.msg)}</div>`);
 if(s.next_ms&&Date.now()>s.next_ms&&!/^https?:/.test(location.protocol))al.push(`<div class="alert red"><b>${s.name}:</b> sono usciti dati nuovi (${s.next}) dopo questo aggiornamento. ${/^https?:/.test(location.protocol)?"Il sito si aggiorna in automatico a breve.":"Riapri cot_radar.py per scaricarli."}</div>`);});
if(M.demo)al.unshift(`<div class="alert red"><b>DATI DIMOSTRATIVI:</b> pagina creata con --demo, i numeri sono finti.</div>`);
$("alerts").innerHTML=al.join("");
}catch(e){fail('Stato fonti e avvisi','alerts',e);}

/* ---------- navigazione ----------
   Le schede sono <section>: si mostra solo quella con la classe "on". */
try{
document.querySelectorAll("#nav button").forEach(b=>b.onclick=()=>{document.querySelectorAll("#nav button,section").forEach(x=>x.classList.remove("on"));
 b.classList.add("on");$(b.dataset.t).classList.add("on");window.scrollTo({top:0});});
var go=t=>document.querySelector(`#nav button[data-t=${t}]`).click();
}catch(e){fail('Navigazione','nav',e);}

/* ---------- grafici ----------
   spark(): mini linea senza assi.  lineChart(): grafico con assi, griglia e legenda.
   Entrambi producono SVG (grafica vettoriale): nitidi su qualsiasi schermo, nessuna libreria esterna. */
try{
function spark(v,col){v=v.filter(x=>x!=null);if(v.length<2)return"";const mn=Math.min(...v),mx=Math.max(...v),W=300,H=54;
 const p=v.map((y,i)=>`${(i/(v.length-1)*W).toFixed(1)},${(H-4-(y-mn)/((mx-mn)||1)*(H-8)).toFixed(1)}`).join(" ");
 return `<svg class="spark" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none"><polyline points="${p}" fill="none" stroke="${col}" stroke-width="2" vector-effect="non-scaling-stroke" stroke-linejoin="round"/></svg>`;}
function lineChart(x,series,unit){const W=760,H=280,L=48,R=16,T=14,B=30;const all=series.flatMap(s=>s.v.filter(v=>v!=null));
 if(!all.length)return"";let mn=Math.min(...all),mx=Math.max(...all);const pad=(mx-mn)*.08||.5;mn-=pad;mx+=pad;
 const X=i=>L+i/(x.length-1)*(W-L-R),Y=v=>T+(1-(v-mn)/(mx-mn))*(H-T-B);
 const ticks=[0,1,2,3,4].map(i=>mn+(mx-mn)*i/4);
 let g=ticks.map(t=>`<line x1="${L}" x2="${W-R}" y1="${Y(t)}" y2="${Y(t)}" stroke="var(--line)"/><text x="${L-8}" y="${Y(t)+4}" text-anchor="end" font-size="11" fill="var(--mute)">${t.toFixed(1)}${unit}</text>`).join("");
 const xi=[0,Math.floor((x.length-1)/2),x.length-1];g+=xi.map(i=>`<text x="${X(i)}" y="${H-8}" text-anchor="${i==0?'start':i==x.length-1?'end':'middle'}" font-size="11" fill="var(--mute)">${x[i]}</text>`).join("");
 series.forEach(s=>{let d="",pen=false;s.v.forEach((v,i)=>{if(v==null){pen=false;return;}d+=(pen?"L":"M")+X(i).toFixed(1)+","+Y(v).toFixed(1);pen=true;});
  g+=`<path d="${d}" fill="none" stroke="${s.c}" stroke-width="${s.w||2.2}" ${s.dash?'stroke-dasharray="5 4"':''} stroke-linejoin="round"/>`;
  const li=s.v.map((v,i)=>[v,i]).filter(p=>p[0]!=null).pop();if(li)g+=`<circle cx="${X(li[1])}" cy="${Y(li[0])}" r="3.5" fill="${s.c}"/>`;});
 return `<div class="legend">${series.map(s=>`<span><i style="background:${s.c}"></i>${s.n}</span>`).join("")}</div><svg class="chart" viewBox="0 0 ${W} ${H}">${g}</svg>`;}
}catch(e){fail('Grafici',null,e);}

/* ---------- segnali ----------
   Riepilogo in alto, settori, schede delle coppie (card) e degli altri strumenti (acard).
   mtag() decide l'etichetta "Mercato conferma / contro / gia' scontato" confrontando i segni di COT e Mercato. */
try{

(function kpis(){const strong=D.pairs.filter(p=>p.label.startsWith("STRONG")).length+Object.values(D.assets).filter(a=>a.key!="USD"&&a.group!="Valute"&&a.label.startsWith("STRONG")).length;
 const act=D.pairs.filter(p=>p.label!="NEUTRO").length+Object.values(D.assets).filter(a=>a.key!="USD"&&a.group!="Valute"&&a.label!="NEUTRO").length;
 const r=D.market?D.market.risk:null,rl=r==null?"n/d":r>=30?"FAVOREVOLE":r<=-30?"SFAVOREVOLE":"NEUTRO";   // in maiuscolo, come i verdetti delle card
 const mo=D.mortgage,pf=mo&&mo.proj_fix&&mo.proj_fix.points.length?mo.proj_fix.points.slice(-1)[0]:null;
 const cot=D.sources[0];
 $("kpis").innerHTML=`<div class="card kpi"><h3>Segnali attivi</h3><div class="big">${act}</div><div class="note">di cui <b>${strong}</b> STRONG</div></div>
 <div class="card kpi"><h3>Clima di rischio</h3><div class="big" style="color:${r>=30?'var(--b)':r<=-30?'var(--s)':'var(--ink)'}">${rl}</div><div class="note">VIX, spread e rendimenti reali, 4 settimane</div></div>
 <div class="card kpi"><h3>Mutuo fisso Italia</h3><div class="big">${mo&&mo.fix!=null?fx(mo.fix)+"%":"n/d"}</div><div class="note">${mo?fd(mo.last):""}${pf?` &middot; stima ${fd(pf.month)}: <b>${fx(pf.value)}%</b>`:""}</div></div>
 <div class="card kpi"><h3>Prossimo COT</h3><div class="big" style="font-size:20px;margin-top:12px">${cot.next}</div><div class="note">dati al ${cot.last}</div></div>`;})();

/* PROSSIMI EVENTI ad alto impatto (motore notizie): mini card come i settori.
   Colori: ambra = banca centrale (Fed, BCE), blu = dato macro (CPI, NFP); OGGI in rosso, DOMANI in ambra.
   Oltre 6 eventi compare "Mostra tutti". La spiegazione sta nel tasto (i). */
try{const ev=D.eventi||[],MAX=6;
 const GG=["dom","lun","mar","mer","gio","ven","sab"],oggi=new Date();oggi.setHours(0,0,0,0);
 const evc=e=>{const q=new Date(e.quando.replace(" ","T")),g=new Date(q);g.setHours(0,0,0,0);
  const diff=Math.round((g-oggi)/864e5),quando=diff<=0?"OGGI":diff==1?"DOMANI":`tra ${diff} giorni`;
  return `<div class="evc ${e.tipo=="banca"?"banca":"dato"}${diff<=0?" oggi":diff==1?" domani":""}"><div class="evt"><b>${esc(e.nome)}</b><span class="evv">${esc(e.valuta)}</span></div>
  <div class="evq">${GG[q.getDay()]} ${e.quando.slice(8,10)}/${e.quando.slice(5,7)} <b>${e.quando.slice(11)}</b></div><small>${quando} &middot; ${e.tipo=="banca"?"banca centrale":"dato macro"}</small></div>`;};
 $("eventi").innerHTML=ev.length?`<div class="card eventi"><div class="evhead"><h3>Prossimi eventi ad alto impatto</h3>
  <details class="info"><summary title="Come usarli" aria-label="Informazioni">i</summary><div>Il giorno del dato la volatilit&agrave; sale: per lo swing conviene valutare l'ingresso <b>dopo</b> l'uscita. Dopo il dato la riga "Notizie" delle card mostra se la sorpresa rafforza o penalizza il segnale.</div></details></div>
  <div class="evgrid">${ev.map((e,k)=>k<MAX?evc(e):evc(e).replace('class="evc','class="evc extra')).join("")}</div>
  ${ev.length>MAX?`<button class="tvbtn evtutti" id="evtutti">Mostra tutti (${ev.length})</button>`:""}</div>`:"";
 const bt=$("evtutti");if(bt)bt.onclick=()=>{const c=$("eventi").querySelector(".card").classList.toggle("aperto");bt.textContent=c?"Mostra meno":`Mostra tutti (${ev.length})`;};
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
   atag = affidabilita' storica: % di volte in cui, dopo un segnale, il prezzo e' andato nel verso giusto in 4 settimane */
function ctag(acc){return acc?`<span class="tag ${acc=="conferma"?"ok":"ko"}" title="Commercials (hedger) agli estremi">Commercials: ${acc}</span>`:"";}
/* stagtag = stagionalita' delle prossime 4 settimane: verde se va nel verso del segnale, arancio se contro */
function stagtag(st,score){if(!st||!st.robusto)return "";const su=st.score>0;
 return `<span class="tag ${Math.sign(st.score)==Math.sign(score)?"ok":"ko"}" title="Stagionalita': ${su?"salito":"sceso"} ${su?st.su:st.n-st.su} anni su ${st.n} nelle prossime 4 settimane">stagione ${su?"&uarr;":"&darr;"} ${su?st.su:st.n-st.su}/${st.n}</span>`;}
function atag(e){if(!e)return "";const c=e.pochi?"":e.hit>=60?"ok":e.hit<50?"ko":"";
 return `<span class="tag ${c}" title="Backtest: ${e.n} segnali passati, resa media ${e.resa>=0?"+":""}${fx(e.resa)}% in 4 settimane">storico ${e.hit}%${e.pochi?" (pochi dati)":""}</span>`;}
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
 <div class="tags">${p.div?'<span class="tag div">Divergenza</span>':''}${mtag(p.cot,p.macro)}${p.new?`<span class="tag new">Nuovo (prima ${p.prev})</span>`:''}${ctag(p.comm_acc)}${atag(p.affid)}</div>
 <div class="why">${why(p)}</div></div>`;}
var act=D.pairs.filter(p=>p.label!="NEUTRO");
$("cards").innerHTML=act.length?act.map(card).join(""):`<div class="card">Nessun segnale attivo sulle valute questa settimana.</div>`;
function acard(a){const v=verb(a.score),m=a.mkt;return `<div class="card clic" data-tv="a:${a.key}" title="Clic: grafico a candele"><div class="pairhead"><div><span class="pair" style="font-size:19px">${a.name}</span><div class="sotto">${badge(a.label)}</div></div>${anello(a.score)}</div>
 <div class="small" style="margin-top:8px">${a.it?esc(a.it)+" &middot; ":""}${a.group} &middot; ${a.key} &middot; COT Index ${a.idx}/100</div>${split(a.cot,a.macro)}
 <div class="tags">${mtag(a.cot,a.macro)}${a.new?`<span class="tag new">Nuovo (prima ${a.prev_label})</span>`:''}${a.crowded?'<span class="tag ko">affollato</span>':''}${ctag(a.comm_acc)}${atag(a.affid)}${stagtag(a.stag,a.score)}</div>
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
}catch(e){fail('Segnali','sig',e);}

/* ---------- coppie ----------
   Tabella completa con filtri; drawTable() la ridisegna a ogni clic su un filtro. */
try{
var F="Tutti";
function drawTable(){const rows=D.pairs.filter(p=>F=="Tutti"||(F=="Divergenze"?p.div:p.label.includes(F))).slice().sort((a,b)=>b.score-a.score);
 $("ptable").innerHTML=`<tr><th>Coppia</th><th>Segnale</th><th class="num">Finale</th><th></th><th class="num">COT</th><th class="num">Mercato</th><th>Base</th><th>Quotata</th><th>Divergenza</th><th class="num">Corr. flussi</th></tr>`+
 rows.map(p=>{const s=p.score,w=Math.abs(s)/2,vb=verb(D.assets[p.base].score),vq=verb(D.assets[p.quote].score);
 return `<tr class="clic" data-tv="p:${p.pair}"><td><b>${p.pair}</b>${p.new?' <span class="tag new">nuovo</span>':''}</td><td>${badge(p.label)}</td><td class="num"><b>${fmt(s)}</b></td>
 <td><div class="bar"><i style="left:${s<0?50-w:50}%;width:${w}%;background:${s<0?'var(--s)':'var(--b)'}"></i></div></td>
 <td class="num">${fmt(p.cot)}</td><td class="num">${p.macro==null?'n/d':fmt(p.macro)}</td>
 <td class="${vb[1]}">${vb[2]} ${p.base}</td><td class="${vq[1]}">${vq[2]} ${p.quote}</td><td>${p.div?'<span class="tag div">si\'</span>':'<span class="small">no</span>'}</td>
 <td class="num">${p.corr==null?'n/d':c2(p.corr)}</td></tr>`}).join("");}
$("filters").innerHTML=["Tutti","STRONG","BUY","SELL","NEUTRO","Divergenze"].map(x=>`<button class="${x==F?'on':''}">${x}</button>`).join("");
document.querySelectorAll("#filters button").forEach(b=>b.onclick=()=>{F=b.textContent;document.querySelectorAll("#filters button").forEach(x=>x.classList.toggle("on",x==b));drawTable();});
drawTable();
}catch(e){fail('Coppie','pairs',e);}

/* ---------- strumenti ----------
   Una riga per strumento, raggruppati per settore. selS(settore) filtra (usato anche dai riquadri dei settori). */
try{
var SF="Tutti";
function selS(g){SF=g;document.querySelectorAll("#sfilters button").forEach(x=>x.classList.toggle("on",x.textContent==g));drawAssets();}
$("sfilters").innerHTML=["Tutti",...SEC.filter(g=>byS[g])].map(g=>`<button class="${g==SF?'on':''}">${g}</button>`).join("");
document.querySelectorAll("#sfilters button").forEach(b=>b.onclick=()=>selS(b.textContent));
function drawAssets(){const groups={};D.order.forEach(k=>{const a=D.assets[k];if(a&&k!="DXY"&&(SF=="Tutti"||a.group==SF))(groups[a.group]=groups[a.group]||[]).push(a);});
 if(D.assets.DXY&&groups["Valute"])groups["Valute"].push(D.assets.DXY);
 $("alist").innerHTML=Object.entries(groups).map(([g,list])=>`<div class="group">${g}</div>`+list.sort((a,b)=>b.score-a.score).map(a=>{
  const s=a.score,w=Math.abs(s)/2;
  let t=a.composite?`Meta' indice del dollaro, meta' l'inverso di tutte le altre valute.`:
   `<b>Speculatori:</b> ${a.d_net==0?'nessuna variazione':(a.d_net>0?'comprato ':'venduto ')+fmt(Math.abs(a.d_net)).replace('+','')+' contratti netti'} in settimana, ${fmt(a.d_net4)} in 4 settimane; netto ${fmt(a.net)} (${a.pct_oi}% open interest), COT Index ${a.idx}/100.`;
  if(a.mkt)t+=` <b>Mercato:</b> ${a.mkt.status.toLowerCase()} (R² ${fx(a.mkt.r2)}).`;
  if(a.crowded)t+=` <b style="color:var(--warn)">Posizionamento affollato: rischio inversione.</b>`;
  if(a.comm)t+=` <b>Commercials:</b> ${a.comm.txt} (COT Index ${a.comm.idx}/100)${a.comm_acc?" &rarr; "+a.comm_acc+" del segnale":""}.`;
  if(a.oi4)t+=` <b>Open interest:</b> ${a.oi4.d_oi>=0?"+":""}${fx(a.oi4.d_oi,1)}% in 4 settimane, ${a.oi4.txt}.`;
  if(a.affid)t+=` <b>Storico:</b> ${a.affid.hit}% dei ${a.affid.n} segnali passati giusti a 4 settimane (resa media ${a.affid.resa>=0?"+":""}${fx(a.affid.resa)}%)${a.affid.pochi?", pochi dati":""}.`;
  return `<div class="asset clic" data-tv="a:${a.key}"><div class="nm"><b>${a.name}</b><small>${a.key}${a.it?" &middot; "+esc(a.it):""}</small></div>
  <div class="abar"><i style="left:${s<0?50-w:50}%;width:${w}%;background:${s<0?'var(--s)':'var(--b)'}"></i></div>
  <div style="text-align:right"><b style="font-size:17px">${fmt(s)}</b><br>${badge(a.label||lab(s))}</div><div class="txt">${t}</div></div>`}).join("")+
  (NOTE[g]?`<p class="small" style="margin:0 0 8px">${NOTE[g]}</p>`:'')).join("");}
drawAssets();
}catch(e){fail('Strumenti','assets',e);}

/* ---------- mercato e macro ----------
   Schede dei driver (valore, variazioni, forza del movimento) e tabella "quanto e' gia' scontato". */
try{
(function(){const X=D.market,el=$("mtop");
 if(!X){el.innerHTML=`<h2>Mercato e macro</h2><div class="card">Dati di mercato (FRED) non disponibili: i segnali usano solo il COT.</div>`;return;}
 const r=X.risk,env=r>=30?["FAVOREVOLE agli asset di rischio","var(--sb)"]:r<=-30?["SFAVOREVOLE agli asset di rischio","var(--ss)"]:["NEUTRO per gli asset di rischio","var(--n)"];
 const dcard=d=>{const u=d.unit=="pb"?" pb":"";const val=d.unit=="pb"?fx(d.value)+"%":fx(d.value,1);const bad=["vix","hy","real"].includes(d.key);
  const cls=d.d4==null?'flat':(d.d4>0)==bad?'down':'up';
  return `<div class="card"><h3>${d.name}</h3><div class="kpi"><div class="big">${val}</div></div>
  <div class="kv"><span>1 settimana</span><b>${sg(d.d1,1)}${u}</b><span>4 settimane</span><b class="${cls}">${sg(d.d4,1)}${u}</b><span>Forza del movimento</span><b>${Math.abs(d.z4)>=1.5?'forte':Math.abs(d.z4)>=.75?'media':'debole'} (z ${sg(d.z4,1)})</b></div>${spark(d.spark,"var(--c1)")}</div>`;};
 let h=`<h2>Il mercato in questo momento</h2><p class="sub">Solo indicatori prezzati ogni giorno dal mercato: anticipano le notizie invece di inseguirle. Ultimo dato: ${fd(X.anchor)}.</p>
 <div class="env" style="--bc:${env[1]}"><b>Clima ${env[0]}</b>Combina VIX, spread delle obbligazioni high yield e rendimenti reali delle ultime 4 settimane (punteggio ${fmt(r)}).</div>
 <div class="grid k3">${X.drivers.map(dcard).join("")}</div>
 <h2>Quanto e' gia' scontato nei prezzi</h2><p class="sub">Per ogni strumento con un prezzo pubblico: una regressione su ${M.regw} settimane stima quanto i driver qui sopra muovono il prezzo.
 Poi confronta la mossa che i driver <b>implicavano</b> nelle ultime 4 settimane con quella che il prezzo ha <b>fatto davvero</b>. Se coincidono la notizia e' gia' nel prezzo; se il prezzo e' rimasto indietro resta uno spazio, che diventa il punteggio "Mercato".</p>
 <div class="tablewrap"><table id="mtable"></table></div>`;
 const F=D.fed;
 if(F)h+=`<h2>Liquidita' della Fed (contesto, lento)</h2><p class="sub">QE e QT cambiano il quadro in mesi, non in giorni: per questo sono mostrati come contesto e non entrano nel punteggio.</p>
 <div class="grid k2"><div class="card"><h3>Bilancio Fed</h3><div class="kpi"><div class="big">${fx(F.bs/1e6)} mila mld $</div><div class="note">${F.regime} &middot; 3 mesi ${sg(F.bs13)}% &middot; dato del ${fd(F.date)}</div></div>${spark(F.spark_bs,"var(--ink)")}</div>
 <div class="card"><h3>Liquidita' netta</h3><div class="kpi"><div class="big">${fx(F.nl/1e6)} mila mld $</div><div class="note">Bilancio - conto del Tesoro - reverse repo &middot; 4 settimane ${sg(F.nl4)}%</div></div>${spark(F.spark_nl,F.nl4>0?"var(--b)":"var(--s)")}</div></div>`;
 el.innerHTML=h;
 const rows=Object.values(D.assets).filter(a=>a.mkt&&a.key!="USD").sort((a,b)=>Math.abs(b.mkt.score)-Math.abs(a.mkt.score));
 $("mtable").innerHTML=`<tr><th>Strumento</th><th class="num">R²</th><th>Driver principale</th><th class="num">Mossa implicita 4s</th><th class="num">Mossa reale 4s</th><th class="num">Differenza</th><th>Lettura</th><th class="num">Punteggio</th></tr>`+
 rows.map(a=>{const m=a.mkt,t=m.top[0];const st=m.r2<.05?'<span class="small">poco legato al macro</span>':Math.abs(m.gz)<.5?'<span class="tag">gia\' scontato</span>':m.gz>0?'<span class="tag ok">spazio al rialzo</span>':'<span class="tag ko">spazio al ribasso</span>';
 return `<tr class="clic" data-tv="a:${a.key}"><td><b>${a.name}</b> <span class="small">${a.key}</span></td><td class="num">${fx(m.r2)}</td><td class="wrap-ok">${t?`${t.name} <span class="${t.c>0?'up':'down'}">${sg(t.c)}%</span>`:''}</td>
 <td class="num">${sg(m.impl)}%</td><td class="num">${sg(m.act)}%</td><td class="num"><b>${sg(m.gap)}%</b></td><td>${st}</td><td class="num"><b class="${m.score>=25?'up':m.score<=-25?'down':'flat'}">${fmt(m.score)}</b></td></tr>`}).join("");
})();
}catch(e){fail('Mercato e macro','mkt',e);}

/* ---------- mutui ----------
   Tassi Italia, stime, grafico 5 anni, calcolatore della rata (ammortamento francese), confronto europeo.
   Formula della rata: R = C * i / (1 - (1+i)^-n) con i = tasso annuo/12/100 e n = numero di mesi. */
try{
(function(){const X=D.mortgage,el=$("mortgage");
 if(!X){el.innerHTML=`<h2>Mutui</h2><div class="card">Dati BCE sui mutui non disponibili in questo momento.</div>`;return;}
 const pf=X.proj_fix,pv=X.proj_var,lp=p=>p&&p.points.length?p.points[p.points.length-1]:null,lf=lp(pf),lv=lp(pv);
 const trend=(p,cur)=>{if(!p)return"n/d";const d=p.value-cur;return Math.abs(d)<.05?"stabile":d>0?"in SALITA":"in DISCESA";};
 const ycard=(t,v,d12,note)=>`<div class="card kpi"><h3>${t}</h3><div class="big">${v==null?'n/d':fx(v)+'%'}</div><div class="note">${note}${d12!=null?` &middot; 12 mesi <b class="${d12>0?'down':'up'}">${sg(d12)}</b>`:''}</div></div>`;
 const it=X.table.find(r=>r.code=="IT")||{};
 let h=`<h2>Mutui per la casa in Italia</h2><p class="sub">Tassi medi effettivamente applicati dalle banche sui nuovi mutui (statistica ufficiale BCE/Banca d'Italia). Ultimo mese disponibile: <b>${fd(X.last)}</b>; la BCE lo pubblica circa 5 settimane dopo la fine del mese.</p>
 <div class="grid k3">${ycard("Tasso fisso (oltre 10 anni)",X.fix,it.fix_d12,"Tasso medio nuovi mutui")}${ycard("Tasso variabile (fino a 1 anno)",X.var,it.var_d12,"Legato a Euribor / tasso BCE")}${ycard("Media di tutti i mutui",X.tot,it.tot_d12,"Fissi e variabili insieme")}</div>
 <h2>Dove stanno andando</h2><p class="sub">I tassi dei mutui seguono, con 1-2 mesi di ritardo, i tassi di mercato: il fisso segue il rendimento a 10 anni (proxy dell'IRS), il variabile segue l'ESTR/Euribor. Questi sono aggiornati ogni giorno, quindi permettono di stimare i mesi non ancora pubblicati.</p>
 <div class="grid k2">
 <div class="card"><h3>Stima tasso fisso</h3><div class="kpi"><div class="big">${lf?fx(lf.value)+'%':'n/d'}</div><div class="note">${lf?`stima per ${fd(lf.month)} (&plusmn;${fx(lf.err)}) &middot; tendenza <b>${trend(lf,X.fix)}</b>`:'dati insufficienti'}</div></div>
 <div class="kv"><span>Rendimento 10 anni area euro (AAA)</span><b>${X.y10.v!=null?fx(X.y10.v)+'%':'n/d'}</b><span>Margine banca sul fisso</span><b>${X.fix_spread!=null?fx(X.fix_spread)+' punti':'n/d'}</b><span>Affidabilita' del modello (R²)</span><b>${pf?fx(pf.r2):'n/d'}</b></div></div>
 <div class="card"><h3>Stima tasso variabile</h3><div class="kpi"><div class="big">${lv?fx(lv.value)+'%':'n/d'}</div><div class="note">${lv?`stima per ${fd(lv.month)} (&plusmn;${fx(lv.err)}) &middot; tendenza <b>${trend(lv,X.var)}</b>`:'dati insufficienti'}</div></div>
 <div class="kv"><span>ESTR (tasso overnight)</span><b>${X.estr.v!=null?fx(X.estr.v)+'%':'n/d'}</b><span>Euribor 3 mesi (${X.euribor?fd(X.euribor.month):''})</span><b>${X.euribor?fx(X.euribor.v,3)+'%':'n/d'}</b><span>Tasso BCE sui depositi</span><b>${X.dfr.v!=null?fx(X.dfr.v)+'%':'n/d'}</b></div></div></div>
 <div class="card" style="margin-top:20px"><h3 style="margin-bottom:12px">Cosa sconta il mercato sulla BCE</h3><p style="margin:0;color:var(--ink2)">${X.y2.v!=null&&X.dfr.v!=null?(X.y2.v<X.dfr.v-.1?`Il rendimento a 2 anni (${fx(X.y2.v)}%) e' <b>sotto</b> il tasso BCE (${fx(X.dfr.v)}%): il mercato si aspetta <b>tagli dei tassi</b> nei prossimi due anni, favorevole per i variabili.`:X.y2.v>X.dfr.v+.1?`Il rendimento a 2 anni (${fx(X.y2.v)}%) e' <b>sopra</b> il tasso BCE (${fx(X.dfr.v)}%): il mercato si aspetta <b>rialzi dei tassi</b>, sfavorevole per i variabili.`:`Il rendimento a 2 anni (${fx(X.y2.v)}%) e' vicino al tasso BCE (${fx(X.dfr.v)}%): il mercato non si aspetta grandi cambiamenti a breve.`):'Dati non disponibili.'}
 ${X.fix!=null&&X.var!=null?` Oggi il fisso costa <b>${sg(X.fix-X.var)}</b> punti rispetto al variabile.`:''}</p></div>
 <h2>Storico 5 anni</h2><p class="sub">Tassi sui nuovi mutui in Italia confrontati con i tassi di mercato che li guidano.</p>
 <div class="card">${lineChart(X.hist.months.map(fd),[{n:"Mutuo fisso >10a",v:X.hist.fix,c:"var(--c1)",w:2.6},{n:"Mutuo variabile",v:X.hist.var,c:"var(--c2)",w:2.6},{n:"Rendimento 10a (AAA)",v:X.hist.y10,c:"var(--c3)",dash:1},{n:"ESTR",v:X.hist.estr,c:"var(--c4)",dash:1}],"%")}</div>
 <h2>Calcolatore rata</h2><p class="sub">Rata mensile con ammortamento alla francese. I tassi sono precompilati con le medie attuali: la tua banca puo' offrire valori diversi.</p>
 <div class="card"><div class="calc"><div><label>Importo del mutuo (&euro;)</label><input id="cA" type="number" value="200000" step="5000"></div><div><label>Durata (anni)</label><input id="cN" type="number" value="30" min="5" max="40"></div>
 <div><label>Tasso fisso / variabile (%)</label><div style="display:flex;gap:8px"><input id="cF" type="number" step="0.05" value="${X.fix!=null?X.fix:3.5}"><input id="cV" type="number" step="0.05" value="${X.var!=null?X.var:3.3}"></div></div></div>
 <div class="grid k3" id="cOut"></div></div>
 <h2>Confronto europeo</h2><p class="sub">Stessa statistica BCE per i principali paesi dell'area euro.</p>
 <div class="tablewrap"><table><tr><th>Paese</th><th class="num">Fisso &gt;10a</th><th class="num">Variabile</th><th class="num">Media</th><th class="num">Media, 12 mesi</th><th>Mese</th></tr>
 ${X.table.map(r=>`<tr><td><b>${r.name}</b></td><td class="num">${r.fix!=null?fx(r.fix)+'%':'n/d'}</td><td class="num">${r.var!=null?fx(r.var)+'%':'n/d'}</td><td class="num">${r.tot!=null?fx(r.tot)+'%':'n/d'}</td><td class="num ${r.tot_d12>0?'down':'up'}">${r.tot_d12!=null?sg(r.tot_d12):'n/d'}</td><td>${fd(r.month)}</td></tr>`).join("")}</table></div>
 ${X.us30?`<h2>Stati Uniti</h2><div class="grid k2"><div class="card kpi"><h3>Mutuo USA 30 anni fisso</h3><div class="big">${fx(X.us30.v)}%</div><div class="note">Freddie Mac, settimana del ${fd(X.us30.date)} &middot; 4 settimane <b class="${X.us30.d4>0?'down':'up'}">${sg(X.us30.d4)}</b></div>${spark(X.us30.spark,"var(--c1)")}</div>
 <div class="card"><h3>Perche' guardarlo</h3><p style="color:var(--ink2);margin:10px 0 0">I tassi USA si muovono prima: un calo del mutuo USA e del Treasury 10 anni tende a trascinare in basso anche i rendimenti europei e quindi, con qualche settimana di ritardo, i mutui a tasso fisso in Italia.</p></div></div>`:''}`;
 el.innerHTML=h;
 function calc(){const A=+$("cA").value,n=+$("cN").value*12;const rata=t=>{const r=t/1200;return r?A*r/(1-Math.pow(1+r,-n)):A/n;};
  const f=rata(+$("cF").value),v=rata(+$("cV").value),eu=x=>x.toLocaleString("it-IT",{style:"currency",currency:"EUR",maximumFractionDigits:0});
  $("cOut").innerHTML=`<div class="card kpi" style="box-shadow:none;background:var(--soft);border:0"><h3>Rata fisso</h3><div class="big">${eu(f)}</div><div class="note">Interessi totali ${eu(f*n-A)}</div></div>
  <div class="card kpi" style="box-shadow:none;background:var(--soft);border:0"><h3>Rata variabile (oggi)</h3><div class="big">${eu(v)}</div><div class="note">Interessi totali ${eu(v*n-A)} se i tassi restano invariati</div></div>
  <div class="card kpi" style="box-shadow:none;background:var(--soft);border:0"><h3>Differenza al mese</h3><div class="big">${eu(f-v)}</div><div class="note">Con +1 punto il variabile diventa ${eu(rata(+$("cV").value+1))}</div></div>`;}
 ["cA","cN","cF","cV"].forEach(i=>$(i).oninput=calc);calc();
})();
}catch(e){fail('Mutui','mortg',e);}

/* ---------- correlazioni ----------
   Mappa di calore: verde = si muovono insieme, rosso = in direzioni opposte, intensita' = forza. */
try{
var KA=D.corr.keys,MA=D.corr.m;let K,Mx,CF="Valute";
function hcol(c){if(c==null)return"transparent";const a=Math.min(1,Math.abs(c));return c>0?`rgba(34,163,90,${a})`:`rgba(224,82,77,${a})`;}
function selC(g){CF=g;document.querySelectorAll("#cfilters button").forEach(x=>x.classList.toggle("on",x.textContent==g));
 const idx=KA.map((k,i)=>i).filter(i=>{const a=D.assets[KA[i]];return CF=="Tutto"||(a&&a.group==CF);});
 const extra=CF=="Valute"||CF=="Tutto"?[]:KA.map((k,i)=>i).filter(i=>["DXY","GOLD","SP500","US10Y"].includes(KA[i])&&!idx.includes(i));
 const use=idx.concat(extra);K=use.map(i=>KA[i]);Mx=use.map(i=>use.map(j=>MA[i][j]));drawCorr();}
$("cfilters").innerHTML=["Tutto",...SEC.filter(g=>byS[g])].map(g=>`<button class="${g==CF?'on':''}">${g}</button>`).join("");
document.querySelectorAll("#cfilters button").forEach(b=>b.onclick=()=>selC(b.textContent));
function drawCorr(){$("heat").innerHTML=`<tr><th></th>${K.map(k=>`<th>${k}</th>`).join("")}</tr>`+
 K.map((r,i)=>`<tr><th class="r">${r}</th>${K.map((c,j)=>{const v=Mx[i][j];return `<td title="${nm(r)} / ${nm(c)}" style="background:${i==j?'var(--soft)':hcol(v)};color:${v!=null&&Math.abs(v)>.55?'#fff':'var(--ink)'}">${i==j||v==null?'':c1(v)}</td>`}).join("")}</tr>`).join("");
 const pl=[];K.forEach((a,i)=>K.forEach((b,j)=>{if(j>i&&Mx[i][j]!=null)pl.push([a,b,Mx[i][j]])}));pl.sort((x,y)=>y[2]-x[2]);
 const li=l=>`<ol style="margin:12px 0 10px;padding-left:20px;line-height:1.9">${l.map(x=>`<li><b>${x[0]}</b> e <b>${x[1]}</b> <span class="small">${c2(x[2])}</span></li>`).join("")}</ol>`;
 $("together").innerHTML=`<h3>Si muovono insieme</h3>${li(pl.slice(0,6))}<div class="small">Quando gli speculatori comprano uno, comprano anche l'altro.</div>`;
 $("opposite").innerHTML=`<h3>Si muovono al contrario</h3>${li(pl.slice(-6).reverse())}<div class="small">Quando comprano uno vendono l'altro: qui nascono le divergenze.</div>`;}
selC("Valute");
}catch(e){fail('Correlazioni','corr',e);}

/* ---------- stagionalita' ----------
   Dati da D.stag (vedi cot_radar/stagionalita.py): per ogni coppia/strumento con storico lungo
   finestra = prossime 4 settimane, mesi = 12 mesi, mappa = anni x mesi, giorni = lunedi'..venerdi'.
   Un effetto e' "affidabile" solo se supera i filtri (anni d'accordo, stabile nel tempo e nelle date). */
try{(function(){const S=D.stag||{},el=$("stag"),M12=["Gen","Feb","Mar","Apr","Mag","Giu","Lug","Ago","Set","Ott","Nov","Dic"];
 const tutte=[...D.pairs.map(p=>p.pair),...D.order.filter(k=>D.assets[k])].filter((k,i,a)=>S[k]&&a.indexOf(k)==i);
 if(!tutte.length){el.innerHTML=`<h2>Stagionalit&agrave;</h2><p class="sub">L'archivio storico non e' ancora disponibile: si crea da solo al primo aggiornamento con FRED raggiungibile.</p>`;return;}
 const pc=(v,d=2)=>v==null?"n/d":(v>0?"+":"")+fx(v,d)+"%";
 const nome=k=>D.assets[k]?`${D.assets[k].name} (${k})`:k;
 const attive=tutte.filter(k=>S[k].finestra&&S[k].finestra.robusto).sort((a,b)=>Math.abs(S[b].finestra.score)-Math.abs(S[a].finestra.score));
 let sel=attive[0]||tutte[0];
 // colore di una cella della mappa: verde = mese in rialzo, rosso = in ribasso, piu' intenso = movimento piu' grande
 const cella=v=>v==null?"transparent":`rgba(${v>0?"79,214,163":"242,113,107"},${Math.min(.85,.12+Math.abs(v)/6)})`;
 function percorso(pp){if(!pp||!pp.some(x=>x!=null))return "";const W=600,H=150,P=24,v=pp.map(x=>x??0);
  const lo=Math.min(0,...v),hi=Math.max(0,...v),sc=y=>H-P-(y-lo)/((hi-lo)||1)*(H-2*P),xs=i=>P+i*(W-2*P)/(v.length-1);
  const col=v[v.length-1]>=0?"var(--b)":"var(--s)";
  return `<svg class="chart" viewBox="0 0 ${W} ${H}"><line x1="${P}" x2="${W-P}" y1="${sc(0)}" y2="${sc(0)}" stroke="var(--line)"/>
  <polyline fill="none" stroke="${col}" stroke-width="3" points="${v.map((y,i)=>xs(i)+","+sc(y)).join(" ")}"/>
  ${v.map((y,i)=>`<circle cx="${xs(i)}" cy="${sc(y)}" r="3.5" fill="${col}"/><text x="${xs(i)}" y="${H-4}" text-anchor="middle" font-size="11" fill="var(--mute)">${i?"+"+i+"s":"oggi"}</text>`).join("")}
  <text x="${W-P}" y="${sc(v[v.length-1])-8}" text-anchor="end" font-size="12" fill="${col}">${pc(v[v.length-1])}</text></svg>`;}
 function disegna(){const X=S[sel],f=X.finestra,mm=X.mesi||[],gg=X.giorni,ora=new Date().getMonth();
  const verd=!f?"n/d":f.robusto?(f.score>0?"RIALZO":"RIBASSO"):"NEUTRA";
  const fcard=`<div class="card"><h3>Prossime 4 settimane</h3><div class="kpi"><div class="big" style="color:${!f||!f.robusto?"var(--ink)":f.score>0?"var(--b)":"var(--s)"}">${verd}</div>
   <div class="note">${f?`salito <b>${f.su}</b> anni su <b>${f.n}</b> (dal ${f.da}) &middot; mediana ${pc(f.med)} &middot; senza trend ${pc(f.med_d)}`:"storico insufficiente"}</div>
   <div class="note">${f?(f.robusto?`<span class="tag ok">effetto affidabile</span> punteggio stagionale ${fmt(f.score)}`:`<span class="tag">non affidabile: ${esc(f.perche||"")}</span>`):""}</div></div>
   ${f?percorso(f.percorso):""}<div class="small">Percorso mediano degli anni passati da oggi alle prossime 8 settimane.</div></div>`;
  const gcard=`<div class="card"><h3>Giorni della settimana</h3>${gg?`<div class="tablewrap" style="box-shadow:none;margin-top:10px"><table class="compatta"><tr><th>Giorno</th><th class="num">In rialzo</th><th class="num">Media</th><th class="num">Mov. tipico</th><th class="num">Ultimi 10a</th><th>Effetto</th></tr>
   ${gg.map(g=>{const vmax=Math.max(...gg.map(x=>x.vol));return `<tr><td><b>${esc(g.giorno)}</b></td><td class="num">${g.su}%</td><td class="num ${g.media>0?"up":g.media<0?"down":""}">${pc(g.media,3)}</td>
   <td class="num">${fx(g.vol,2)}%${g.vol==vmax?' <b title="giorno piu\' mosso" style="color:var(--acc)">&#9679;</b>':""}</td><td class="num">${pc(g.rec,3)}</td><td>${g.robusto?`<span class="tag ${g.t>0?"ok":"ko"}">${g.t>0?"rialzo":"ribasso"} (t ${fx(g.t,1)})</span>`:'<span class="small">non significativo</span>'}</td></tr>`}).join("")}</table></div>
   <div class="small" style="margin-top:8px">&#9679; = giorno che si muove di piu'. ${gg[0].n+gg[1].n+gg[2].n+gg[3].n+gg[4].n} giorni dal ${X.da}. Cambi FRED rilevati alle 12:00 di New York: "mercoledi'" = da martedi' 12:00 a mercoledi' 12:00.</div>`:'<p class="small">Storico giornaliero insufficiente.</p>'}</div>`;
  const vmax=Math.max(0.01,...mm.map(m=>Math.abs(m.med||0)));
  const mcard=`<div class="card"><h3>Mesi</h3><div class="mesi">${mm.map((m,i)=>m.n>=10?`<div class="mese${i==ora?" ora":""}${m.robusto?" forte":""}" title="${M12[i]}: salito ${m.su}/${m.n} anni, mediana ${pc(m.med)}${m.robusto?" (affidabile)":""}">
   <div class="barra"><i style="height:${Math.round(Math.abs(m.med)/vmax*50)}%;${m.med>=0?"bottom:50%":"top:50%"};background:${m.med>=0?"var(--b)":"var(--s)"}"></i></div>
   <b>${M12[i]}</b><small>${pc(m.med,1)}</small><small>${m.su}/${m.n}</small></div>`:`<div class="mese"><div class="barra"></div><b>${M12[i]}</b><small>n/d</small></div>`).join("")}</div>
   <div class="small" style="margin-top:8px">Barra = rendimento mediano del mese; sotto, gli anni in rialzo. Bordo turchese = effetto affidabile; evidenziato il mese in corso.</div></div>`;
  const mp=X.mappa;
  const hcard=mp?`<div class="card"><h3>Mappa anni &times; mesi (ultimi ${mp.anni.length} anni)</h3><div class="tablewrap" style="box-shadow:none;margin-top:10px"><table class="mappa"><tr><th></th>${M12.map(m=>`<th>${m}</th>`).join("")}</tr>
   ${mp.anni.map((y,r)=>`<tr><th>${y}</th>${mp.v[r].map(v=>`<td style="background:${cella(v)}">${v==null?"":fx(v,1)}</td>`).join("")}</tr>`).reverse().join("")}</table></div></div>`:"";
  $("stagdett").innerHTML=`<div class="grid stag2">${fcard}${gcard}</div><div style="margin-top:20px">${mcard}</div><div style="margin-top:20px">${hcard}</div>`;}
 el.innerHTML=`<h2>Stagionalit&agrave;</h2><p class="sub">Come si e' comportato ogni strumento negli anni passati: nelle prossime 4 settimane, mese per mese e giorno per giorno. Conta solo cio' che supera i filtri anti-coincidenza (vedi Metodo).</p>
  <div class="card" style="margin-bottom:20px"><h3>Effetti affidabili adesso (prossime 4 settimane)</h3><div class="evlist">${attive.length?attive.map(k=>{const f=S[k].finestra;return `<button class="ev stagbtn" data-k="${esc(k)}"><b>${esc(k)}</b> ${f.score>0?"&uarr;":"&darr;"} ${f.score>0?f.su:f.n-f.su}/${f.n} anni &middot; ${pc(f.med,1)}</button>`}).join(""):'<span class="small">Nessun effetto affidabile in questo periodo dell\'anno.</span>'}</div></div>
  <div class="filters"><select id="stagsel" class="tvbtn">${tutte.map(k=>`<option value="${esc(k)}">${esc(nome(k))}</option>`).join("")}</select></div><div id="stagdett"></div>`;
 const scegli=k=>{sel=k;$("stagsel").value=k;disegna();};
 $("stagsel").onchange=e=>scegli(e.target.value);
 el.querySelectorAll(".stagbtn").forEach(b=>b.onclick=()=>scegli(b.dataset.k));
 scegli(sel);
})();}catch(e){fail("Stagionalita'","stag",e);}

/* ---------- metodo ----------
   Testo della guida: i numeri (pesi, soglie) arrivano da D.meta, cosi' restano allineati a config.py. */
try{
var w=M.w;
$("guide").innerHTML=`
<h3>1. Le tre fonti</h3><p><b>CFTC</b> (venerdi' 21:30 italiane, dati del martedi'): quanti contratti hanno in acquisto e in vendita i grandi speculatori. <b>FRED</b>, Fed di St. Louis (ogni giorno): tassi, rendimenti reali, inflazione attesa, VIX, spread high yield, cambi, indici, petrolio, bilancio Fed. Se FRED e' fermo, le serie principali arrivano dalle fonti originali (Tesoro USA, NY Fed, CBOE, Freddie Mac, BCE, Coinbase). <b>BCE</b> (ogni giorno i tassi di mercato, ogni mese i mutui): tassi sui nuovi mutui, Euribor, ESTR, curva dei rendimenti. Ogni fonte ha il suo stato in alto: verde aggiornato, giallo dati salvati, rosso in ritardo.</p>
<h3>2. Punteggio COT (${Math.round((1-M.mw)*100)}% del finale)</h3><ul><li><b>${w.posizione*100}% posizione</b>: COT Index a 3 anni (0 = mai cosi' short, 100 = mai cosi' long).</li><li><b>${w.flusso_1w*100}% flusso della settimana</b> e <b>${w.flusso_4w*100}% flusso a 4 settimane</b>, misurati in z-score a 52 settimane.</li><li>Se il posizionamento e' gia' estremo (oltre 95 o sotto 5) la forza viene ridotta del 30%.</li></ul>
<h3>3. Punteggio Mercato (${Math.round(M.mw*100)}% del finale)</h3><p>Il mercato sconta le notizie in anticipo, quindi non uso dati macro pubblicati in ritardo ma solo indicatori prezzati ogni giorno: tasso USA 2 anni (aspettative sulla Fed), rendimento reale 10 anni, inflazione attesa, VIX, spread high yield, differenziale 2 anni USA-Europa. Per ogni strumento con un prezzo pubblico una regressione (ridge, ${M.regw} settimane, stimata escludendo le ultime 4) misura quanto ogni driver muove il prezzo. Nelle ultime 4 settimane si confronta la mossa <b>implicita</b> con quella <b>reale</b>: differenza vicina a zero = gia' scontato (punteggio ~0); prezzo in ritardo = punteggio nella direzione dei driver, ridotto se il modello spiega poco (R² basso).</p>
<h3>4. Segnali</h3><p>Coppia = (finale base - finale quotata) / 2. Da ${M.normal} in su BUY/SELL, da ${M.strong} STRONG solo con divergenza (forza almeno ${M.divmin} da entrambi i lati, di segno opposto).</p>
<h3>5. Conferme del segnale</h3><p><b>Commercials</b> (hedger: produttori, banche, utilizzatori): stanno quasi sempre dalla parte opposta degli speculatori. Quando il loro COT Index e' a un estremo (molto long &ge;80, molto short &le;20) di solito il prezzo e' vicino a un minimo o a un massimo: se l'estremo va nel verso del segnale e' una <i>conferma</i>, altrimenti un <i>contrasto</i>. <b>Open interest</b> (4 settimane): se gli speculatori comprano e l'OI sale entrano nuovi long (trend sano); se l'OI scende stanno solo chiudendo short (spinta piu' debole); lo stesso al contrario per le vendite. <b>Storico</b>: per ogni settimana passata il punteggio COT e' ricalcolato con i soli dati di allora; se era BUY/SELL si guarda il prezzo 4 settimane dopo la pubblicazione. La percentuale e' quante volte il prezzo e' andato nel verso del segnale (50% = come tirare una moneta). E' calcolato solo dove esiste un prezzo storico gratuito (cambi, indici, petrolio, gas, cripto), non include costi e risultati passati non garantiscono quelli futuri.</p>
<h3>6. Stagionalit&agrave;</h3><p>Da un archivio permanente di prezzi giornalieri (fino a 50 anni, salvato su GitHub e mai riscritto) si misura come si e' mosso ogni strumento <b>nelle prossime 4 settimane</b> di ogni anno passato, in <b>ogni mese</b> e in <b>ogni giorno della settimana</b>. Prima si toglie il trend (il movimento medio dello strumento), poi un effetto conta solo se: almeno 10 anni di dati; almeno il 65% degli anni nello stesso verso (mesi: anche test t &ge; 2; giorni: test t &ge; 2,58 perche' si confrontano 5 giorni insieme); stesso verso nella prima e nella seconda meta' degli anni; per la finestra, stesso verso spostandola di una settimana avanti o indietro. Sul puro rumore questi filtri lasciano passare circa 1-3 casi su 100.</p>
<p><b>Peso deciso dal backtest</b>: i segnali COT passati sono stati divisi in "stagionalita' a favore" e "contraria", calcolata solo con gli anni precedenti a ogni segnale. ${D.stag_meta?`A favore: <b>${D.stag_meta.accordo.hit??"n/d"}%</b> di successi in 4 settimane (${D.stag_meta.accordo.n} segnali); contraria: <b>${D.stag_meta.contrasto.hit??"n/d"}%</b> (${D.stag_meta.contrasto.n}). Peso usato: <b>${Math.round(D.stag_meta.peso*100)}%</b> del punteggio stagionale${D.stag_meta.peso?"":" (nessun vantaggio dimostrato: la stagionalita' resta solo informativa)"}.`:"Backtest non disponibile."} I segnali di strumenti e coppie si sovrappongono nel tempo, quindi il numero di casi "indipendenti" e' piu' basso di quanto sembra. Il punteggio originale resta nell'anello; la correzione compare nella riga sotto i riquadri.</p>
<h3>7. Notizie (CPI, NFP, Fed, BCE)</h3><p>Il COT indica la direzione per le prossime settimane; una notizia ad alto impatto muove il prezzo per ore o pochi giorni e cambia soprattutto il <i>momento</i> giusto per entrare. Prima dell'evento la card mostra solo l'avviso &#9889;. Dopo l'evento la <b>sorpresa</b> e' misurata dal mercato: di quanto si e' mosso il tasso a 2 anni della valuta nel giorno del dato rispetto a una giornata normale (in deviazioni standard, &sigma;). Tassi su = valuta piu' forte. Il correttivo vale 10 punti per &sigma;, ha un tetto di &plusmn;30 per valuta e si dimezza ogni giorno (ogni 3 giorni per Fed e BCE). Il segnale COT non viene cambiato: accanto si vede il punteggio corretto.</p>
<h3>8. Verifica dei segnali</h3><p><b>Registro live</b>: ogni segnale viene salvato nel momento in cui nasce (data e ora vere), con l'ingresso alla <b>prima chiusura giornaliera successiva</b> (mai un prezzo gi&agrave; passato). Poi si misurano, nel verso del segnale, il risultato a 1, 2 e 4 settimane e fino al cambio di etichetta (massimo 12 settimane), con il guadagno massimo e il drawdown massimo lungo il percorso. Un segnale nasce quando l'etichetta passa da NEUTRO a BUY/SELL o si inverte; la stessa direzione la settimana dopo &egrave; una conferma; il passaggio a STRONG apre una "fase STRONG" misurata a parte. Gli eventi non si possono modificare: ognuno contiene l'impronta (hash SHA-256) del precedente, e il registro si aggiorna solo con dati completi.</p><p><b>Backtest</b> (marcato SIMULATO): le stesse regole applicate a tutte le settimane dal 1986, usando ogni volta solo i dati disponibili allora. Esclude la parte Mercato e macro, le notizie e la stagionalit&agrave;, sottrae costi stimati e tiene separati gli ultimi 2 anni (holdout) come controllo onesto. Tre modi di entrare: subito, con un ordine limite di ritracciamento, o met&agrave; e met&agrave;.</p><p><b>Orizzonte a scelta</b>: chi specula pu&ograve; chiudere dopo 1 settimana (5 sedute), chi investe dopo 4 (20 sedute). Il cursore mostra, seduta per seduta dall'uscita dei dati, risultato medio, guadagno massimo e drawdown massimo, anche solo sull'holdout. Accanto a ogni strumento ci sono volatilit&agrave; annua e mossa settimanale tipica: lo stesso drawdown pesa diversamente su un cambio tranquillo e su un mercato nervoso come il gas.</p>
<h3>9. Mutui</h3><p>Tassi medi sui nuovi mutui per acquisto casa (statistica BCE MIR, fonte Banca d'Italia per l'Italia). La stima dei mesi non ancora pubblicati usa una regressione delle variazioni mensili del tasso sulle variazioni del rendimento a 10 anni (fisso) o dell'ESTR (variabile), del mese stesso e di quello prima. L'intervallo &plusmn; e' l'errore tipico del modello.</p>
<h3>10. Aggiornamenti</h3><p>${/^https?:/.test(location.protocol)?"Il sito si aggiorna da solo: venerdi' sera dopo il COT, ogni mattina feriale (mercati e BCE) e ogni sera feriale a fine giornata (fino a 3 tentativi a 5 minuti di distanza). Se una fonte non risponde restano online gli ultimi dati validi.":"Ogni apertura scarica tutto. Aggiornamento automatico ogni venerdi': nel Prompt dei comandi <code>python cot_radar.py --pianifica</code>."}</p>
<h3>11. Limiti</h3><ul><li>Sono stime statistiche, non certezze: le relazioni cambiano nel tempo.</li><li>Il COT ha 3 giorni di ritardo; i mutui circa 5 settimane.</li><li>Oro, materie agricole e altri strumenti senza prezzo gratuito su FRED usano solo il COT.</li><li>Non e' una consulenza finanziaria.</li></ul>`;
/* AVVERTENZA LEGALE: testo fisso in fondo a ogni pagina (tutela: il sito e' informativo, non consulenza) */
$("foot").innerHTML=`<div class="legale"><b>Avvertenza importante.</b> Edge Board ha finalit&agrave; esclusivamente informative, didattiche e di studio.
 I contenuti (segnali, punteggi, statistiche, stagionalit&agrave;, analisi e qualsiasi altra informazione) <b>non costituiscono consulenza finanziaria,
 consulenza in materia di investimenti, raccomandazione personalizzata, sollecitazione o offerta</b> all'acquisto o alla vendita di strumenti finanziari,
 ai sensi della normativa vigente (tra cui D.Lgs. 58/1998 - TUF e direttiva MiFID II). L'autore non e' un consulente finanziario abilitato e non presta servizi di investimento.
 I dati provengono da fonti pubbliche di terzi e possono contenere errori, ritardi o omissioni; i modelli sono stime statistiche e i risultati passati non sono indicativi di quelli futuri.
 Il trading su futures, forex, CFD e criptovalute comporta un rischio elevato di perdita, anche superiore al capitale investito.
 Ogni decisione di investimento &egrave; presa in autonomia e sotto la propria esclusiva responsabilit&agrave;: l'autore declina ogni responsabilit&agrave; per perdite o danni, diretti o indiretti,
 derivanti dall'uso di queste informazioni. Prima di investire valuta la tua situazione e, se necessario, rivolgiti a un consulente abilitato.</div>
 <div>Fonti: CFTC Commitments of Traders (Legacy, Futures Only) &middot; FRED, Federal Reserve Bank of St. Louis &middot; Banca Centrale Europea, ECB Data Portal. Generato il ${M.now}.</div>`;
}catch(e){fail('Metodo','guide',e);}

/* ---------- sidebar ----------
   PC: il pulsante freccia la riduce a icone (classe "ridotta" su <html>, salvata in localStorage).
   Telefono (<900px): resta nascosta; il pulsante menu la apre sopra la pagina, un tocco fuori la chiude. */
try{(function(){const h=document.documentElement,mob=()=>matchMedia("(max-width:900px)").matches;
 try{if(localStorage.getItem("ebSide")=="ridotta")h.classList.add("ridotta");}catch(e){}
 $("scomprimi").onclick=()=>{if(mob())return chiudi();const r=h.classList.toggle("ridotta");try{localStorage.setItem("ebSide",r?"ridotta":"aperta");}catch(e){}};
 function apri(){h.classList.add("sideon");$("sombra").hidden=false;}
 function chiudi(){h.classList.remove("sideon");$("sombra").hidden=true;}
 $("smenu").onclick=apri;$("sombra").onclick=chiudi;
 $("gapri").addEventListener("click",()=>{if(mob())chiudi();});
})();}catch(e){fail("Barra laterale",null,e);}

/* ---------- guida laterale ----------
   La guida ("Come funziona") non e' piu' una scheda: si apre come pannello laterale dal pulsante "Guida" in alto.
   L'indice si costruisce da solo dai titoli <h3>: un clic porta alla sezione. Esc o clic fuori = chiude. */
try{(function(){const g=$("guida"),box=$("guide");
 const titoli=[...box.querySelectorAll("h3")];
 titoli.forEach((h,i)=>h.id="guida-"+i);
 $("gindice").innerHTML=titoli.map((h,i)=>`<a href="#guida-${i}" data-i="${i}">${esc(h.textContent)}</a>`).join("");
 $("gindice").onclick=ev=>{const a=ev.target.closest("a");if(!a)return;ev.preventDefault();
  const pan=g.querySelector(".gpannello"),h=$("guida-"+a.dataset.i);       // scorro solo il pannello, sotto la testata fissa
  pan.scrollTo({top:pan.scrollTop+h.getBoundingClientRect().top-pan.getBoundingClientRect().top-g.querySelector(".gtop").offsetHeight-12,behavior:"smooth"});};
 const apri=()=>{g.hidden=false;document.documentElement.classList.add("guidaon");setTimeout(()=>g.classList.add("on"),10);};
 const chiudi=()=>{g.classList.remove("on");document.documentElement.classList.remove("guidaon");setTimeout(()=>g.hidden=true,250);};
 $("gapri").onclick=apri;$("gchiudi").onclick=chiudi;
 g.onclick=ev=>{if(ev.target===g)chiudi();};
 document.addEventListener("keydown",ev=>{if(ev.key=="Escape"&&!g.hidden)chiudi();});
})();}catch(e){fail("Guida",null,e);}

/* ---------- grafico a candele (TradingView) ----------
   Clic su una scheda, una riga di tabella o uno strumento -> si apre un pannello con il grafico a candele.
   Il widget gratuito di TradingView si carica SOLO al primo clic (la dashboard resta veloce e funziona offline).
   Timeframe: D (giornaliero), H4, H1, W. Pulsante "Schermo intero" e link per aprire il grafico su tradingview.com.
   Simboli: config.py -> TV_SYMBOLS (strumenti) e TV_PAIRS (coppie speciali); le altre coppie usano "FX:NOME". */
try{
var TV={spec:null,iv:"D",caricato:null};
function tvInfo(spec){const t=spec.slice(0,1),k=spec.slice(2);
 if(t=="p"){const p=D.pairs.find(x=>x.pair==k)||{};return {sym:(D.tvp&&D.tvp[k])||("FX:"+k),nome:k,label:p.label,score:p.score,inv:false,sotto:p.base&&p.quote?`${nm(p.base)} / ${nm(p.quote)}`:""};}
 const a=D.assets[k]||{},tv=(D.tv&&D.tv[k])||{};return {sym:tv.s,nome:a.name||k,label:a.label,score:a.score,inv:!!tv.inv,sotto:`${a.it?a.it+" · ":""}${a.group||""} · ${k}`};}
function caricaTV(){if(TV.caricato)return TV.caricato;
 TV.caricato=new Promise((ok,ko)=>{const s=document.createElement("script");s.src="https://s3.tradingview.com/tv.js";s.async=true;
  s.onload=()=>window.TradingView?ok():ko(new Error("TradingView non disponibile"));s.onerror=()=>{TV.caricato=null;ko(new Error("impossibile caricare TradingView (sei offline?)"));};document.head.appendChild(s);});
 return TV.caricato;}
function disegnaTV(){const info=tvInfo(TV.spec),box=$("tvchart");box.innerHTML="";
 if(!info.sym){box.innerHTML=`<div class="tvmsg">Nessun grafico associato a questo strumento.</div>`;return;}
 const scuro=true;   // tema unico blu notte: grafico sempre scuro
 caricaTV().then(()=>{new TradingView.widget({container_id:"tvchart",autosize:true,symbol:info.sym,interval:TV.iv,
   // "range" = periodo visibile. ATTENZIONE: TradingView adatta il timeframe al range (3M->1h, 12M->D, 60M->W),
   // quindi lo abbiniamo solo dove coincide; per H4 nessun range (mostra le ultime ~300 candele).
   ...({"60":{range:"3M"},"D":{range:"12M"},"W":{range:"60M"}}[TV.iv]||{}),
   timezone:"Europe/Rome",theme:scuro?"dark":"light",style:"1",locale:"it",allow_symbol_change:true,withdateranges:true,hide_side_toolbar:false,save_image:true,
   /* telefono: niente barra in alto di TradingView (timeframe doppi), grafico piu' alto */ hide_top_toolbar:matchMedia("(max-width:600px)").matches});})
 .catch(e=>{box.innerHTML=`<div class="tvmsg">${esc(e.message)}. <a href="https://www.tradingview.com/chart/?symbol=${encodeURIComponent(info.sym)}" target="_blank" rel="noopener">Apri il grafico su TradingView</a></div>`;console.error("[Edge Board] grafico:",e);});}
/* Pannello COT sotto il grafico: per ogni settimana la variazione del netto Non Commercial (% open interest).
   Coppia = flusso della valuta base MENO quello della quotata: verde = flussi a favore della coppia in SALITA.
   Strumento quotato al contrario (es. JPY -> grafico USDJPY): il segno viene girato per seguire il grafico.
   La data e' il MARTEDI' di riferimento: il dato esce il venerdi' dopo (21:30 italiane). */
function flussiDi(spec){const t=spec.slice(0,1),k=spec.slice(2);
 if(t=="a"){const f=(D.assets[k]||{}).flussi||[],inv=!!((D.tv||{})[k]||{}).inv;return f.map(([d,v])=>[d,inv?-v:v]);}
 const p=D.pairs.find(x=>x.pair==k)||{},fb=new Map((D.assets[p.base]||{}).flussi||[]),fq=new Map((D.assets[p.quote]||{}).flussi||[]);
 return [...fb.keys()].filter(d=>fq.has(d)).sort().map(d=>[d,+(fb.get(d)-fq.get(d)).toFixed(2)]);}
/* Lettura delle ultime 3 settimane (swing): somma dei flussi e quante settimane vanno nella stessa direzione.
   3 su 3 nello stesso verso = flusso CONCENTRATO (posizionamento che si sta costruendo), 2 su 3 = prevalente. */
function tre(f){const u=f.slice(-3),tot=u.reduce((s,x)=>s+x[1],0),su=u.filter(x=>x[1]>0).length,giu=u.filter(x=>x[1]<0).length;
 const n=Math.max(su,giu),verso=tot>=0?"acquisti":"vendite";
 const forza=n==3?(tot>=0?"concentrati":"concentrate"):n==2?"prevalenti":"misti";   // accordo: acquisti concentrati / vendite concentrate
 return {u,tot,txt:n<2?"flussi misti, nessuna direzione chiara":`${verso} ${forza} (${n} su 3)`,col:n<2?"var(--ink2)":tot>=0?"var(--sb)":"var(--ss)"};}
/* posizione netta attuale in % dell'open interest: >0 net long, <0 net short */
function netto(k,inv){const a=D.assets[k]||{};if(a.pct_oi==null)return "";const v=inv?-a.pct_oi:a.pct_oi;
 return `${esc(k)} <b style="color:${v>=0?"var(--sb)":"var(--ss)"}">net ${v>=0?"long":"short"} ${fx(Math.abs(v),1)}%</b>`;}
/* riga "Conferme" del pannello: Commercials, open interest, affidabilita' storica */
function conferme(k,p){const parti=[],col=v=>v=="conferma"?"var(--sb)":v=="contrasto"?"var(--ss)":"var(--ink)";
 const gambe=p?[p.base,p.quote]:[k];
 const cm=gambe.map(g=>{const c=(D.assets[g]||{}).comm;return c?`${esc(g)} ${c.idx>=80?"molto long":c.idx<=20?"molto short":"neutri"} (${c.idx})`:null;}).filter(Boolean);
 const acc=p?p.comm_acc:(D.assets[k]||{}).comm_acc;
 if(cm.length)parti.push(`<b>Commercials:</b> ${cm.join(" &middot; ")}${acc?` &rarr; <b style="color:${col(acc)}">${acc}</b>`:""}`);
 const oi=gambe.map(g=>{const o=(D.assets[g]||{}).oi4;return o?`${esc(g)} ${o.d_oi>=0?"+":""}${fx(o.d_oi,1)}% <span class="lungo">(${esc(o.txt)})</span>`:null;}).filter(Boolean);
 if(oi.length)parti.push(`<b>Open interest 4 sett.:</b> ${oi.join(" &middot; ")}`);
 if(p&&p.news){const n=p.news,ev=(n.eventi||[]).filter(x=>x.z!=null).map(x=>`${esc(x.nome)} ${x.z>=0?"+":""}${fx(x.z,1)}&sigma; (${x.pb>=0?"+":""}${fx(x.pb,1)} pb)`);
  parti.push(`<b>Notizie:</b> ${n.oggi.length?"&#9889; "+n.oggi.map(esc).join(", ")+" ":""}${ev.join(" &middot; ")}${ev.length?` &rarr; <b style="color:${n.effetto=="rafforza"?"var(--sb)":n.effetto=="penalizza"?"var(--ss)":"var(--ink)"}">${n.effetto}</b> (${n.adj>=0?"+":""}${fx(n.adj,0)}, punteggio ${fmt(n.score)})`:""}`);}
 const st=p?p.stag:(D.assets[k]||{}).stag,sc=p?p.score:(D.assets[k]||{}).score;
 if(st)parti.push(`<b>Stagionalit&agrave;:</b> ${st.robusto?`${st.score>0?"salito":"sceso"} ${st.score>0?st.su:st.n-st.su}/${st.n} anni nelle prossime 4 sett. (mediana ${st.med>=0?"+":""}${fx(st.med)}%) &rarr; <b style="color:${Math.sign(st.score)==Math.sign(sc)?"var(--sb)":"var(--ss)"}">${Math.sign(st.score)==Math.sign(sc)?"conferma":"contrasto"}</b>${st.adj?` (${st.adj>0?"+":""}${fx(st.adj,0)})`:""}`:"nessun effetto affidabile in questo periodo"}`);
 const e=p?p.affid:(D.assets[k]||{}).affid;
 if(e)parti.push(`<b>Storico:</b> <b style="color:${e.pochi?"var(--ink)":e.hit>=60?"var(--sb)":e.hit<50?"var(--ss)":"var(--ink)"}">${e.hit}%</b> su ${e.n} segnali <span class="lungo">(resa media ${e.resa>=0?"+":""}${fx(e.resa)}% a 4 sett.)</span>`);
 return parti.length?`<div class="riga tre">${parti.map(x=>`<span>${x}</span>`).join("")}</div>`:"";}
/* SINTESI DEI FLUSSI COT in una riga (al posto delle barre, che si aprono con un clic):
   quante settimane in acquisto/vendita, da quante settimane di fila nello stesso verso,
   e se la spinta sta crescendo o calando (media delle ultime 3 settimane contro le 3 prima). */
function sintesiFlussi(f){const n=f.length,su=f.filter(x=>x[1]>0).length,giu=f.filter(x=>x[1]<0).length;
 const ult=Math.sign(f[n-1][1]);let fila=0;for(let i=n-1;i>=0&&Math.sign(f[i][1])==ult&&ult!=0;i--)fila++;
 const media=a=>a.reduce((x,y)=>x+Math.abs(y[1]),0)/(a.length||1),m1=media(f.slice(-3)),m0=media(f.slice(-6,-3));
 const spinta=m1>m0*1.25?"spinta in aumento":m1<m0*0.8?"spinta in calo":"spinta stabile";
 const col=ult>0?"var(--sb)":ult<0?"var(--ss)":"var(--ink)";
 return `<b>${n} settimane:</b> ${su} in acquisto &middot; ${giu} in vendita &middot; <b style="color:${col}">${ult>0?"acquisti":ult<0?"vendite":"fermi"} da ${fila} ${fila==1?"settimana":"settimane di fila"}</b> &middot; ${spinta}`;}
function disegnaCOT(spec){const box=$("tvcot");try{
 const f=flussiDi(spec);if(!f.length){box.innerHTML=`<div class="riga">Nessun dato COT per questo strumento.</div>`;return;}
 const max=Math.max(...f.map(x=>Math.abs(x[1])),0.01),W=600,H=100,bw=W/f.length;
 const barre=f.map(([d,v],i)=>{const h=Math.abs(v)/max*(H/2-2),y=v>=0?H/2-h:H/2,recente=i>=f.length-3;   // le ultime 3 piene
  return `<rect x="${(i*bw+bw*0.15).toFixed(1)}" y="${y.toFixed(1)}" width="${(bw*0.7).toFixed(1)}" height="${Math.max(h,0.8).toFixed(1)}" rx="1.5"
   fill="${v>=0?"var(--sb)":"var(--ss)"}" opacity="${recente?1:0.45}"><title>martedi' ${fd(d)}: ${v>=0?"+":""}${fx(v)}% open interest</title></rect>`;}).join("");
 // fascia chiara dietro le ultime 3 settimane
 const fascia=`<rect x="${((f.length-3)*bw).toFixed(1)}" y="0" width="${(3*bw).toFixed(1)}" height="${H}" fill="var(--soft)" opacity=".6"/>`;
 const [ud,uv]=f[f.length-1],ven=new Date(ud);ven.setDate(ven.getDate()+3),t=tre(f);
 const k=spec.slice(2),p=spec[0]=="p"?D.pairs.find(x=>x.pair==k)||{}:null,inv=!!((D.tv||{})[k]||{}).inv;
 const pos=p?[netto(p.base),netto(p.quote)].filter(Boolean).join(" &middot; "):netto(k,inv);
 box.innerHTML=`<div class="riga"><span><b>COT Non Commercial</b><span class="lungo"> &middot; variazione settimanale del netto (% open interest) &middot; ultime ${f.length} settimane</span></span>
  <span>Ultimo: <b style="color:${uv>=0?"var(--sb)":"var(--ss)"}">${uv>=0?"acquisti":"vendite"} ${uv>=0?"+":""}${fx(uv)}%</b> &middot; <span class="lungo">dato di marted&igrave; ${fd(ud)}, pubblicato venerd&igrave; ${fd(ven.toISOString().slice(0,10))}</span><span class="corto">mar ${fd(ud).slice(0,5)}</span></span></div>
  <div class="riga tre"><span><b><span class="lungo">Ultime 3 settimane:</span><span class="corto">3 sett.:</span></b> ${t.u.map(x=>`<span style="color:${x[1]>=0?"var(--sb)":"var(--ss)"}">${x[1]>=0?"+":""}${fx(x[1])}</span>`).join(" &middot; ")}
   = <b style="color:${t.col}">${t.tot>=0?"+":""}${fx(t.tot)}%</b> &rarr; <b style="color:${t.col}">${t.txt}</b></span>${pos?`<span>Posizione: ${pos}</span>`:""}</div>
  ${conferme(k,p)}
  <button class="sintesi" id="cotsint" title="Mostra / nascondi le barre settimanali">${sintesiFlussi(f)} <span class="freccia">&#9662;</span></button>
  <div class="barre"><svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img" aria-label="Flussi COT settimanali">${fascia}<line x1="0" x2="${W}" y1="${H/2}" y2="${H/2}" stroke="var(--line)"/>${barre}</svg>
  <div class="assi"><span>${fd(f[0][0])}</span><span class="lungo">verde = comprano &middot; rosso = vendono${p?" (base contro quotata)":""} &middot; fascia = ultime 3 settimane</span><span>${fd(ud)}</span></div></div>`;
 // barre aperte/chiuse: su telefono partono chiuse (piu' spazio al grafico); la scelta resta salvata
 const pan=$("tvpannello");let chiuse=matchMedia("(max-width:600px)").matches;
 try{const v=localStorage.getItem("cotBarre");if(v)chiuse=v=="chiuse";}catch(e){}
 pan.classList.toggle("barrechiuse",chiuse);
 $("cotsint").onclick=()=>{const c=pan.classList.toggle("barrechiuse");try{localStorage.setItem("cotBarre",c?"chiuse":"aperte");}catch(e){}};
 }catch(e){box.innerHTML="";console.error("[Edge Board] pannello COT:",e);}}   // se si rompe sparisce il pannello, non il grafico
/* MANIGLIA: trascinando la barretta tra grafico e pannello COT si allarga o si schiaccia il pannello.
   Doppio clic = misura iniziale. La misura scelta resta salvata in questo browser (se il browser lo permette). */
(function(){const man=$("tvmaniglia"),pan=$("tvpannello");if(!man||!pan)return;
 const MIN=30,MAX=420,STD=72;
 const imposta=h=>{h=Math.round(Math.min(MAX,Math.max(MIN,h)));pan.style.setProperty("--cotH",h+"px");try{localStorage.setItem("cotH",h);}catch(e){}};
 try{const h=+localStorage.getItem("cotH");if(h)pan.style.setProperty("--cotH",Math.min(MAX,Math.max(MIN,h))+"px");}catch(e){}
 let y0=0,h0=0;
 man.addEventListener("pointerdown",ev=>{ev.preventDefault();y0=ev.clientY;h0=parseFloat(getComputedStyle(pan).getPropertyValue("--cotH"))||STD;
  man.setPointerCapture(ev.pointerId);pan.classList.add("trascino");});        // durante il trascinamento il grafico non "ruba" il mouse
 man.addEventListener("pointermove",ev=>{if(pan.classList.contains("trascino"))imposta(h0+(y0-ev.clientY));});   // su = piu' alto
 const fine=()=>pan.classList.remove("trascino");man.addEventListener("pointerup",fine);man.addEventListener("pointercancel",fine);
 man.addEventListener("dblclick",()=>imposta(STD));})();
/* AFFIDABILITA' DEL SEGNALE (etichetta in testa al pannello del grafico): somma di tre conferme
   storico (>=60% +1, <50% -1, "pochi dati" non conta) + Commercials (conferma +1, contrasto -1)
   + stagionalita' affidabile (stesso verso del segnale +1, contrario -1).  >=2 ALTA, <=-1 BASSA, altrimenti MEDIA. */
function affidabilitaSegnale(spec){const[t,id]=spec.split(":"),o=t=="p"?D.pairs.find(x=>x.pair==id):D.assets[id];
 if(!o||o.label=="NEUTRO")return "";
 let v=0;const perche=[],e=o.affid,st=o.stag,acc=o.comm_acc;
 if(e&&!e.pochi){if(e.hit>=60){v++;perche.push(`storico ${e.hit}%`);}else if(e.hit<50){v--;perche.push(`storico solo ${e.hit}%`);}}
 if(acc=="conferma"){v++;perche.push("Commercials a favore");}else if(acc=="contrasto"){v--;perche.push("Commercials contrari");}
 if(st&&st.robusto){if(Math.sign(st.score)==Math.sign(o.score)){v++;perche.push("stagionalita' a favore");}else{v--;perche.push("stagionalita' contraria");}}
 const liv=v>=2?["ALTA","var(--sb)"]:v<=-1?["BASSA","var(--ss)"]:["MEDIA","var(--warn)"];
 return `<span class="badge" style="--bc:${liv[1]}" title="${esc(perche.join(", ")||"nessuna conferma o contrasto")}">AFFIDABILIT&Agrave; ${liv[0]}</span>`;}
function apriGrafico(spec){TV.spec=spec;const info=tvInfo(spec),m=$("tvmodal");disegnaCOT(spec);
 $("tvtitolo").innerHTML=`<span class="pair">${esc(info.nome)}</span> ${info.label?badge(info.label):""} ${affidabilitaSegnale(spec)} <span class="small">punteggio ${fmt(info.score)}</span>`;
 $("tvsotto").innerHTML=`${esc(info.sotto)} &middot; simbolo <b>${esc(info.sym||"n/d")}</b>`+(info.inv?` &middot; <b style="color:var(--warn)">grafico quotato al contrario: BUY sul segnale = grafico che SCENDE</b>`:"");
 $("tvlink").href="https://www.tradingview.com/chart/?symbol="+encodeURIComponent(info.sym||"");
 document.querySelectorAll("#tviv button").forEach(b=>b.classList.toggle("on",b.dataset.iv==TV.iv));
 m.hidden=false;bloccaPagina(true);disegnaTV();}
function chiudiGrafico(){const m=$("tvmodal");if(document.fullscreenElement)document.exitFullscreen().catch(()=>{});
 if($("tvpannello").classList.contains("pieno"))schermoPieno();m.hidden=true;bloccaPagina(false);$("tvchart").innerHTML="";}
/* BLOCCO DELLA PAGINA mentre il grafico e' aperto (soprattutto iPhone).
   Su iOS "overflow:hidden" non basta: trascinando sul grafico (es. per disegnare una zona) Safari muoveva
   anche la pagina sotto, o la ingrandiva. Qui: 1) la pagina viene "fissata" nella sua posizione (position:fixed)
   e poi rimessa dov'era alla chiusura; 2) lo zoom con le dita della pagina e' disattivato solo finche' il
   grafico e' aperto (il grafico TradingView continua a zoomare da solo). */
var BLOCCO={y:0,vp:null};
function bloccaPagina(on){const b=document.body,h=document.documentElement,vp=document.querySelector('meta[name="viewport"]');
 if(on){if(h.classList.contains("bloccato"))return;BLOCCO.y=window.scrollY;h.classList.add("bloccato");
  Object.assign(b.style,{position:"fixed",top:-BLOCCO.y+"px",left:"0",right:"0",width:"100%",overflow:"hidden"});
  if(vp){BLOCCO.vp=vp.content;vp.content=BLOCCO.vp+",maximum-scale=1,user-scalable=no";}}
 else{if(!h.classList.contains("bloccato"))return;h.classList.remove("bloccato");
  Object.assign(b.style,{position:"",top:"",left:"",right:"",width:"",overflow:""});window.scrollTo({top:BLOCCO.y,behavior:"instant"});
  if(vp&&BLOCCO.vp)vp.content=BLOCCO.vp;}}
document.addEventListener("click",ev=>{const el=ev.target.closest("[data-tv]");if(el&&!ev.target.closest("button,a,input")){try{apriGrafico(el.dataset.tv);}catch(e){fail("Grafico",null,e);}}});
$("tvchiudi").onclick=chiudiGrafico;
$("tvmodal").addEventListener("click",ev=>{if(ev.target.id=="tvmodal")chiudiGrafico();});
document.addEventListener("keydown",ev=>{if(ev.key=="Escape"&&!$("tvmodal").hidden)chiudiGrafico();});
/* SCHERMO INTERO. iPhone (Safari e Chrome su iOS) NON permette lo schermo intero vero sugli elementi della pagina
   (solo sui video): li' usiamo un "finto" schermo intero via CSS (classe .pieno = pannello su tutta la finestra).
   Sugli altri browser si prova quello vero; se il browser lo rifiuta si ripiega sullo stesso metodo CSS. */
function schermoPieno(){const p=$("tvpannello"),on=p.classList.toggle("pieno");$("tvfull").classList.toggle("on",on);}   // la pagina e' gia' bloccata dal grafico aperto
$("tvfull").onclick=()=>{const p=$("tvpannello"),fs=document.fullscreenElement||document.webkitFullscreenElement;
 if(p.classList.contains("pieno"))return schermoPieno();                 // esco dal finto schermo intero
 if(fs){(document.exitFullscreen||document.webkitExitFullscreen).call(document);return;}
 const vero=p.requestFullscreen||p.webkitRequestFullscreen;
 if(!vero)return schermoPieno();                                          // iPhone: niente API -> CSS
 try{const r=vero.call(p);if(r&&r.catch)r.catch(()=>schermoPieno());}catch(e){schermoPieno();}};
document.querySelectorAll("#tviv button").forEach(b=>b.onclick=()=>{TV.iv=b.dataset.iv;document.querySelectorAll("#tviv button").forEach(x=>x.classList.toggle("on",x==b));disegnaTV();});
}catch(e){fail('Grafico',null,e);}

/* ---------- VERIFICA DEI SEGNALI: registro live + backtest simulato ----------
   Due finestre separate e mai mescolate:
     LIVE     = segnali veri, con data e ora di generazione, salvati per sempre con una catena di hash (D.reg)
     BACKTEST = segnali SIMULATI sulle settimane passate dal 1986 con le stesse regole (D.bt)
   Calcoli in cot_radar/motore.py; qui solo la presentazione. Ingresso = prima chiusura dopo il segnale. */
try{(function(){const el=$("verifica"),R=D.reg,B=D.bt;if(!el)return;
 const V={fin:"live",d:5,per:"tutti"};   // finestra, sedute di uscita (1..20 o "fine"), periodo del backtest
 try{const s=JSON.parse(localStorage.getItem("ebVerifica")||"{}");if(s.fin)V.fin=s.fin;if(s.d=="fine"||(s.d>=1&&s.d<=20))V.d=s.d;if(s.per)V.per=s.per;}catch(e){}
 const salva=()=>{try{localStorage.setItem("ebVerifica",JSON.stringify(V));}catch(e){}};
 const pc=(x,d=2)=>x==null||isNaN(x)?"n/d":(x>0?"+":x<0?"−":"")+Math.abs(x).toLocaleString("it-IT",{minimumFractionDigits:d,maximumFractionDigits:d})+"%";
 const col=x=>x==null?"":x>0?"up":x<0?"down":"flat";
 const prezzo=p=>{if(p==null)return"n/d";const d=p>=1000?2:p>=100?3:p>=10?3:4;return p.toLocaleString("it-IT",{minimumFractionDigits:d,maximumFractionDigits:d});};
 const oraIt=u=>{if(!u)return"";const t=new Date(u.replace("Z",":00Z"));
  return t.toLocaleDateString("it-IT",{timeZone:"Europe/Rome",day:"2-digit",month:"2-digit",year:"numeric"})+" ore "+t.toLocaleTimeString("it-IT",{timeZone:"Europe/Rome",hour:"2-digit",minute:"2-digit"});};
 const sett=(a,b)=>Math.max(1,Math.round((new Date(b)-new Date(a))/864e5/7));
 const AFC={ALTA:"var(--sb)",MEDIA:"var(--warn)",BASSA:"var(--ss)"};
 const aff=l=>l?`<span class="badge" style="--bc:${AFC[l]||"var(--n)"}">AFFIDABILIT&Agrave; ${l}</span>`:"";
 const MOT={neutro:"tornato NEUTRO",inversione:"segnale invertito",indebolito:"tornato da STRONG a normale","12 settimane":"limite di 12 settimane"};

 /* tabellina dei risultati: periodo, risultato, guadagno massimo e drawdown massimo lungo il percorso */
 function cella(t){return t?`<td class="num"><b class="${col(t.res)}">${pc(t.res)}</b></td><td class="num up">${pc(t.mfe)}</td><td class="num down">${pc(t.mae)}</td><td>${t.provvisorio?'<span class="vfic" title="ancora in corso">&#9719;</span>':t.vinto?'<span class="vfok">&#10003;</span>':'<span class="vfko">&#10007;</span>'}</td>`
  :`<td class="num small" colspan="4">in attesa</td>`;}

 /* scheda di un segnale nel formato approvato */
 function scheda(s,sim){const m=s.m||{},A=m.A||{},ing=m.ingresso;
  const testa=`<div class="vfh"><span class="pair">${esc(s.strumento)}</span> ${badge(s.etichetta)} ${aff(s.affid)}${s.iniziale?' <span class="tag" title="Era gia\' attivo quando il registro e\' partito: escluso dalle statistiche">gi&agrave; attivo all\'avvio</span>':''}${s.padre?' <span class="tag" title="Fase STRONG di un segnale gia\' aperto">fase STRONG</span>':''}</div>`;
  let h=`<div class="vfr"><span>Segnale generato</span><b>${esc(s.generato_it)}</b></div>`+
   (ing?`<div class="vfr"><span>Ingresso</span><b>${prezzo(ing.prezzo)} <span class="small">&middot; ${oraIt(ing.utc)}</span></b></div>`
       :`<div class="vfr"><span>Ingresso</span><span class="small">${esc(m.stato||"prezzo non disponibile")}</span></div>`);
  if(ing){const f=A.fine,fm=m.fine||{},chiuso=!!(s.chiuso||fm.motivo);
   const nf=f?`${chiuso?"Al cambio":"Finora"}<small class="vfsett">${sett(ing.data,f.data)} sett.</small>`:"Al cambio";
   h+=`<table class="vftab"><tr><th></th><th class="num">Risultato</th><th class="num">Max</th><th class="num">Min</th><th></th></tr>
    <tr><td>1 settimana</td>${cella(A["1s"])}</tr><tr><td>2 settimane</td>${cella(A["2s"])}</tr><tr><td>4 settimane</td>${cella(A["4s"])}</tr>
    <tr class="vffine"><td>${nf}</td>${f?cella(f):'<td class="num small" colspan="4">in attesa del prezzo</td>'}</tr></table>`;
   if(chiuso){const quando=s.chiuso&&fm.motivo!="12 settimane"?s.chiuso.quando_it:(f?fd(f.data):"");
    h+=`<div class="small vfnota">${s.chiuso?"Chiuso il "+esc(quando):"Misura conclusa"} &middot; ${esc(MOT[fm.motivo]||MOT[(s.chiuso||{}).motivo]||"")}</div>`;}
   const b=m.B||{};const bt=b.esito=="eseguito"?`eseguito a ${prezzo(b.limite)} il ${fd(b.data)}`:b.esito=="non eseguito"?`non eseguito (limite ${prezzo(b.limite)})`:b.esito=="in attesa"?`limite a ${prezzo(b.limite)} in attesa`:"n/d";
   h+=`<div class="small vfnota">Ingresso B (ritracciamento): ${bt}</div>`;}
  const perche=(s.perche||[]).length?`<div class="small vfp">Affidabilit&agrave;: ${esc(s.perche.join(", "))}</div>`:"";
  return `<div class="card vfcard${sim?" vfsim":""}">${testa}<div class="vfrighe">${h}</div>${perche}</div>`;}

 /* ---- ORIZZONTE DI USCITA scelto da chi guarda ----
    Uno speculatore chiude in settimana (5 sedute), un investitore tiene 4 settimane (20 sedute):
    V.d = numero di sedute dopo l'ingresso (1..20) oppure "fine" (= fino al cambio di etichetta).
    I dati arrivano compatti da Python (motore.giorni_stat): per ogni seduta [segnali, vinti, somme di
    risultato, guadagno massimo e drawdown massimo]. Qui si calcolano medie, % vinti e intervallo di Wilson. */
 function wilson(k,n){if(!n)return null;const z=1.96,p=k/n,den=1+z*z/n,c=(p+z*z/(2*n))/den,m=z*Math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den;
  return [Math.round(100*Math.max(0,c-m)),Math.round(100*Math.min(1,c+m))];}
 function st(R){if(!R)return null;
  if(V.d=="fine")return R.fine||null;
  const a=(R.g||[])[V.d-1];if(!a||!a[0])return null;
  const n=a[0],v=a[1],mfe=a[3]/n,mae=a[4]/n;
  return {n:n,vinti:v,hit:Math.round(100*v/n),ic:wilson(v,n),resa:a[2]/n,mfe:mfe,mae:mae,rapporto:mae<0?Math.round(100*mfe/Math.abs(mae))/100:null};}
 const nomeD=()=>V.d=="fine"?"fino al cambio di etichetta":`dopo ${V.d} ${V.d==1?"seduta":"sedute"}${V.d%5==0?` (${V.d/5} ${V.d==5?"settimana":"settimane"})`:""}`;

 /* riquadri riassuntivi per l'orizzonte scelto */
 function kpi(R,nota){const x=st(R);
  if(!x)return `<div class="vfvuoto small">Nessun segnale con questo orizzonte ancora concluso.${nota?" "+nota:""}</div>`;
  return `<div class="grid k4 vfkpi">
   <div class="card kpi"><h3>Segnali misurati</h3><div class="big">${x.n.toLocaleString("it-IT")}</div><div class="note">${x.vinti.toLocaleString("it-IT")} vinti &middot; ${(x.n-x.vinti).toLocaleString("it-IT")} persi</div></div>
   <div class="card kpi"><h3>Vinti</h3><div class="big">${x.hit}%</div><div class="note" title="Intervallo di confidenza al 95% (Wilson): con pochi segnali e' largo">probabile tra ${x.ic[0]}% e ${x.ic[1]}%</div></div>
   <div class="card kpi"><h3>Resa media</h3><div class="big ${col(x.resa)}">${pc(x.resa)}</div><div class="note">per segnale, al netto dei costi stimati</div></div>
   <div class="card kpi"><h3>Guadagno / drawdown max</h3><div class="big" style="font-size:22px;margin-top:12px"><span class="up">${pc(x.mfe)}</span> / <span class="down">${pc(x.mae)}</span></div><div class="note">medie separate &middot; rapporto ${x.rapporto==null?"n/d":x.rapporto.toLocaleString("it-IT")}</div></div></div>`;}

 /* PERCORSO MEDIO dal segnale: seduta per seduta, risultato medio (linea chiara), guadagno massimo medio
    raggiunto fino a quel giorno (verde) e drawdown massimo medio (rosso). La linea verticale = uscita scelta. */
 function percorso(R){const g=(R&&R.g)||[];if(g.length<2)return "";
  const pts=g.map((a,i)=>({d:i+1,r:a[2]/a[0],mx:a[3]/a[0],mn:a[4]/a[0],n:a[0]}));
  const mob=matchMedia("(max-width:600px)").matches,W=mob?400:760,H=mob?280:250,L=mob?40:46,Rr=mob?10:16,T=16,Bm=30,lo=Math.min(0,...pts.map(p=>p.mn)),hi=Math.max(0,...pts.map(p=>p.mx));
  const X=d=>L+(d-1)/(20-1)*(W-L-Rr),Y=v=>T+(hi-v)/((hi-lo)||1)*(H-T-Bm);
  const linea=(k,c,w)=>`<path d="${pts.map((p,i)=>(i?"L":"M")+X(p.d).toFixed(1)+" "+Y(p[k]).toFixed(1)).join(" ")}" fill="none" stroke="${c}" stroke-width="${w}" stroke-linejoin="round"/>`;
  const area=`<path d="${pts.map((p,i)=>(i?"L":"M")+X(p.d).toFixed(1)+" "+Y(p.mx).toFixed(1)).join(" ")} ${pts.slice().reverse().map(p=>"L"+X(p.d).toFixed(1)+" "+Y(p.mn).toFixed(1)).join(" ")} Z" fill="var(--soft)" opacity=".55"/>`;
  const tick=[];const passo=(hi-lo)>6?2:(hi-lo)>3?1:0.5;for(let v=Math.ceil(lo/passo)*passo;v<=hi+1e-9;v+=passo)tick.push(v);
  const sel=V.d=="fine"?null:pts[V.d-1];
  return `<h3 class="vft">Percorso medio dal segnale <span class="small">(ingresso alla prima chiusura dopo l'uscita dei dati)</span></h3>
  <div class="card vfgraf"><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Percorso medio dei segnali seduta per seduta">
   ${tick.map(v=>`<line x1="${L}" x2="${W-Rr}" y1="${Y(v)}" y2="${Y(v)}" stroke="var(--line)" ${Math.abs(v)<1e-9?'stroke-width="1.5"':'stroke-dasharray="3 4"'}/><text x="${L-8}" y="${Y(v)+4}" text-anchor="end" class="vfax">${v>0?"+":""}${String(Math.round(v*10)/10).replace(".",",")}%</text>`).join("")}
   ${(mob?[5,10,15,20]:[1,5,10,15,20]).map(d=>`<text x="${X(d)}" y="${H-8}" text-anchor="${d==20&&mob?"end":"middle"}" class="vfax">${d==1?"1 seduta":d%5==0?d/5+" sett.":d}</text>`).join("")}
   ${area}${linea("mx","var(--b)",2)}${linea("mn","var(--s)",2)}${linea("r","var(--ink)",2.6)}
   ${sel?`<line x1="${X(sel.d)}" x2="${X(sel.d)}" y1="${T}" y2="${H-Bm}" stroke="var(--acc)" stroke-width="1.5"/>
    <circle cx="${X(sel.d)}" cy="${Y(sel.r)}" r="4.5" fill="var(--ink)"/><circle cx="${X(sel.d)}" cy="${Y(sel.mx)}" r="4" fill="var(--b)"/><circle cx="${X(sel.d)}" cy="${Y(sel.mn)}" r="4" fill="var(--s)"/>`:""}
  </svg><div class="vfleg small"><span><i style="background:var(--ink)"></i>risultato medio</span><span><i style="background:var(--b)"></i>guadagno massimo medio</span><span><i style="background:var(--s)"></i>drawdown massimo medio</span><span>(fino a quel giorno)</span></div></div>`;}

 /* tabella per gruppo (etichetta, affidabilita', periodo, strumento): gr = {nome: riassunto} */
 function tabella(titolo,gr,ordine,min,prof){const ks=(ordine||Object.keys(gr||{})).filter(k=>gr&&gr[k]&&st(gr[k])&&st(gr[k]).n>=(min||1));
  if(!ks.length)return "";
  return `<h3 class="vft">${titolo}</h3><div class="tablewrap"><table class="compatta"><tr><th></th><th class="num">Segnali</th><th class="num">Vinti</th><th class="num">Probabile tra</th><th class="num">Resa media</th><th class="num">Guadagno max</th><th class="num">Drawdown max</th><th class="num">Rapporto</th>${prof?`<th class="num" title="Volatilita' annua dell'ultimo anno">Volatilit&agrave; annua</th><th class="num" title="Movimento tipico in una settimana (mediana), ultimo anno">Mossa tipica sett.</th><th class="num" title="Drawdown medio diviso la mossa settimanale tipica: sotto 1 = drawdown nella norma per quel mercato, sopra 1 = il segnale soffre piu' del normale rumore">Drawdown / mossa</th>`:""}</tr>
   ${ks.map(k=>{const x=st(gr[k]),p=prof&&prof[k];return `<tr><td><b>${esc(k)}</b></td><td class="num">${x.n.toLocaleString("it-IT")}</td><td class="num"><b>${x.hit}%</b></td><td class="num small">${x.ic[0]}&ndash;${x.ic[1]}%</td><td class="num ${col(x.resa)}">${pc(x.resa)}</td><td class="num up">${pc(x.mfe)}</td><td class="num down">${pc(x.mae)}</td><td class="num">${x.rapporto==null?"n/d":x.rapporto.toLocaleString("it-IT")}</td>${prof?(p?`<td class="num">${fx(p.ann,1)}%</td><td class="num">${fx(p.sett,2)}%</td><td class="num ${Math.abs(x.mae)/p.sett>1.5?"down":""}">${fx(Math.abs(x.mae)/p.sett,2)}&times;</td>`:'<td class="num small" colspan="3">n/d</td>'):""}</tr>`;}).join("")}</table></div>${prof?`<p class="small">Drawdown e volatilit&agrave; raccontano la <b>natura del mercato</b>: lo stesso drawdown del 2% &egrave; tanto su un cambio che si muove dell'1% a settimana e poco su un mercato che si muove dell'8%. "Drawdown / mossa" sopra 1,5 = il segnale soffre pi&ugrave; del normale rumore di quello strumento.</p>`:""}`;}

 /* confronto dei tre modi di entrare: calcolato a 1, 2 e 4 settimane (5, 10, 20 sedute) */
 function varianti(R){const h={5:"1s",10:"2s",20:"4s"}[V.d],x=h&&R&&R.var&&R.var[h];
  if(!x)return `<h3 class="vft">Tre modi di entrare</h3><p class="small">Il confronto tra ingresso subito, ritracciamento e met&agrave; e met&agrave; &egrave; calcolato a 1, 2 e 4 settimane: scegli 5, 10 o 20 sedute per vederlo.</p>`;
  return `<h3 class="vft">Tre modi di entrare <span class="small">(valore medio per segnale, ${nomeD()})</span></h3><div class="grid k3 vfvar">
   <div class="card"><b>A &middot; subito</b><div class="big ${col(x.resa)}">${pc(x.resa)}</div><div class="small">alla prima chiusura dopo il segnale</div></div>
   <div class="card"><b>B &middot; ritracciamento</b><div class="big ${col(x.B.valore)}">${pc(x.B.valore)}</div><div class="small">ordine limite a 0,5&times; il movimento settimanale tipico, valido 5 giorni: eseguito ${x.B.fill==null?"n/d":x.B.fill+"%"} delle volte${x.B.resa_eseguiti!=null?`, resa quando eseguito ${pc(x.B.resa_eseguiti)}`:""}</div></div>
   <div class="card"><b>C &middot; met&agrave; e met&agrave;</b><div class="big ${col(x.C.valore)}">${pc(x.C.valore)}</div><div class="small">met&agrave; subito, met&agrave; con l'ordine limite</div></div></div>
   <p class="small">Valore per segnale = percentuale di esecuzione &times; resa media: un ingresso "migliore" che scatta di rado pu&ograve; valere meno.</p>`;}

 /* comandi: uscita (sedute o fino al cambio) e, solo nel backtest, il periodo */
 function comandi(){const per=V.fin=="bt"?`<div class="vfriga"><span class="vfetich">Periodo</span><div class="filters vfper">${[["tutti","Tutto"],["sviluppo","Sviluppo"],["holdout","Holdout (ultimi 2 anni)"]].map(([k,t])=>`<button data-p="${k}" class="${V.per==k?"on":""}">${t}</button>`).join("")}</div></div>`:"";
  return `<div class="card vfcomandi">${per}<div class="vfriga"><span class="vfetich">Chiudo</span><div class="filters vforz">${[[5,"1 settimana"],[10,"2 settimane"],[15,"3 settimane"],[20,"4 settimane"],["fine","al cambio di etichetta"]].map(([k,t])=>`<button data-h="${k}" class="${V.d==k?"on":""}">${t}</button>`).join("")}</div></div>
   <div class="vfriga vfslider"><span class="vfetich">oppure</span><input type="range" id="vfgiorni" min="1" max="20" step="1" value="${V.d=="fine"?20:V.d}" aria-label="Sedute dopo l'ingresso"><b id="vfgtesto">${V.d=="fine"?"al cambio":V.d+(V.d==1?" seduta":" sedute")}</b></div>
   <p class="small" style="margin:6px 0 0">Seduta = giorno di mercato (5 per settimana). Risultati, guadagno e drawdown sono misurati <b>${nomeD()}</b> dall'ingresso.</p></div>`;}

 function datiLive(){const P=R.stat,ap=R.aperti||[],ch=R.chiusi||[];
  return kpi(P.riass,"I segnali già attivi all'avvio sono esclusi.")+percorso(P.riass)+
   `<h2>Segnali aperti <span class="small">(${ap.length})</span></h2><div class="grid vfgrid">${ap.map(s=>scheda(s)).join("")||'<div class="small">Nessun segnale aperto.</div>'}</div>
   <h2>Segnali chiusi <span class="small">(${R.n_chiusi})</span></h2><div class="grid vfgrid" id="vfchiusi">${ch.slice(0,12).map(s=>scheda(s)).join("")||'<div class="small">Ancora nessuno.</div>'}</div>
   ${ch.length>12?`<button class="vfaltro" id="vfaltro">Mostra tutti (${ch.length})</button>`:""}
   ${tabella("Per etichetta",P.etichetta,["STRONG BUY","BUY","SELL","STRONG SELL"])}${tabella("Per affidabilit&agrave;",P.affid,["ALTA","MEDIA","BASSA"])}${varianti(P.riass)}${tabella("Per strumento",P.strumento,null,1,R.profilo)}`;}

 function datiBt(){const P=B.periodi[V.per]||B.periodi.tutti,nomeP={tutti:"tutto il periodo",sviluppo:"sviluppo",holdout:"holdout"}[V.per];
  const per={"Tutto il periodo":B.periodi.tutti.riass,"Sviluppo":B.periodi.sviluppo.riass,"Holdout (ultimi 2 anni)":B.periodi.holdout.riass};
  const anni=Object.entries(B.anni||{}).map(([a,R])=>[a,st(R)]).filter(([a,x])=>x),mx=Math.max(0.5,...anni.map(([a,x])=>Math.abs(x.resa)));
  const barre=anni.length?`<h3 class="vft">Anno per anno <span class="small">(resa media ${nomeD()})</span></h3><div class="vfanni">${anni.map(([a,x])=>{const h=Math.round(Math.abs(x.resa)/mx*100),hold=a>=B.holdout_dal.slice(0,4);
   return `<div class="vfanno${hold?" vfhold":""}" title="${a}: ${x.n} segnali, vinti ${x.hit}%, resa media ${pc(x.resa)}"><div class="vfmeta">${x.resa>=0?`<i class="su" style="height:${h}%"></i>`:""}</div><div class="vfmeta giu">${x.resa<0?`<i class="giu" style="height:${h}%"></i>`:""}</div><span>${a.slice(2)}</span></div>`;}).join("")}</div>`:"";
  const ordS=Object.keys(P.strumento||{}).sort((a,b)=>((st(P.strumento[b])||{}).resa??-99)-((st(P.strumento[a])||{}).resa??-99));
  return kpi(P.riass)+percorso(P.riass)+tabella("Sviluppo e holdout a confronto",per,Object.keys(per))+
   `<p class="small">Il periodo di <b>holdout</b> (ultimi 2 anni) non va mai usato per tarare pesi o soglie: &egrave; il controllo onesto. Se sviluppo e holdout dicono cose molto diverse, il risultato del passato non &egrave; affidabile.</p>
   ${tabella(`Per affidabilit&agrave; <span class="small">(${nomeP})</span>`,P.affid,["ALTA","MEDIA","BASSA"])}${tabella(`Per etichetta <span class="small">(${nomeP})</span>`,P.etichetta,["STRONG BUY","BUY","SELL","STRONG SELL"])}${varianti(P.riass)}${barre}
   ${tabella(`Per strumento <span class="small">(${nomeP}, almeno ${V.per=="holdout"?5:20} segnali)</span>`,P.strumento,ordS,V.per=="holdout"?5:20,B.profilo)}`;}

 function live(){if(!R)return `<div class="card vfvuoto">Registro non disponibile in questo aggiornamento.</div>`;
  const cat=R.integra?`<span class="vfok">&#10003;</span> catena integra`:`<b class="vfko">&#10007; catena NON integra</b>`;
  const testa=`<div class="vfstato small">${R.dal?`Registro attivo dal <b>${esc(R.dal)}</b> &middot; `:""}${R.eventi} eventi &middot; ${cat}${R.ultimo_hash?` <code title="Impronta SHA-256 dell'ultimo evento: se un evento passato venisse modificato, non corrisponderebbe piu'">${R.ultimo_hash.slice(0,12)}&hellip;</code>`:""}${R.completi?"":" &middot; <b style='color:var(--warn)'>ultimo aggiornamento con dati incompleti: registro non aggiornato</b>"}</div>`;
  if(!R.eventi)return testa+`<div class="card vfvuoto"><b>Il registro parte con il prossimo aggiornamento completo.</b><p class="small">Da quel momento ogni segnale viene salvato con data e ora, prezzo d'ingresso e risultati. Gli eventi non si possono modificare: ognuno contiene l'impronta del precedente.</p></div>`;
  return testa+comandi()+`<div id="vfdati">${datiLive()}</div>`;}

 function backtest(){if(!B)return `<div class="card vfvuoto">Backtest non disponibile in questo aggiornamento.</div>`;
  return `<div class="vfsimulato"><b>SIMULATO</b> &middot; risultati ricostruiti sul passato, non segnali reali. Servono a capire se il metodo ha un vantaggio, non promettono risultati futuri.</div>
   <div class="vfstato small">Dal <b>${fd(B.dal)}</b> al <b>${fd(B.al)}</b> &middot; ${B.n.toLocaleString("it-IT")} segnali (pi&ugrave; ${B.n_strong.toLocaleString("it-IT")} fasi STRONG) &middot; sviluppo ${(B.n_svil||0).toLocaleString("it-IT")} &middot; holdout dal ${fd(B.holdout_dal)}: ${(B.n_hold||0).toLocaleString("it-IT")}</div>
   ${comandi()}<div id="vfdati">${datiBt()}</div>
   <details class="vfdett"><summary>Come &egrave; costruito (e cosa manca rispetto al live)</summary><ul class="small">
    <li>Ogni settimana il punteggio COT &egrave; ricalcolato con i <b>soli report disponibili allora</b>; il segnale nasce alla pubblicazione (venerd&igrave; 15:30 di New York, 21:30 in Italia) ed entra alla prima chiusura successiva: da l&igrave; partono il percorso e i risultati.</li>
    <li>Stesse regole del sito per etichette, divergenza, dollaro composito, nascita/conferma/chiusura dei segnali e affidabilit&agrave; (storico e Commercials di allora).</li>
    <li>Non incluse: la parte <b>Mercato e macro</b> (30% del punteggio live), le notizie e la stagionalit&agrave;.</li>
    <li>Costi stimati andata e ritorno sottratti: cambi principali ${B.costi.major}%, incroci ${B.costi.cross}%, emergenti ${B.costi.em}%, indici ${B.costi.indici}%, petrolio ${B.costi.energia}%, gas ${B.costi.NATGAS}%, crypto ${B.costi.crypto}%. Swap e rollover esclusi.</li>
    <li>Prezzi solo di chiusura giornaliera (FRED): guadagno e drawdown massimi sono misurati sulle chiusure.</li></ul></details>
   <h2>Ultimi segnali simulati conclusi</h2><div class="grid vfgrid">${(B.ultimi||[]).slice(0,12).map(s=>scheda(s,true)).join("")}</div>`;}

 /* aggiorna SOLO i numeri (non i comandi): cosi' il cursore delle sedute si puo' trascinare senza scatti */
 function aggiorna(){const box=$("vfdati");if(!box)return;box.innerHTML=V.fin=="live"?datiLive():datiBt();
  el.querySelectorAll(".vforz button").forEach(b=>b.classList.toggle("on",b.dataset.h==String(V.d)));
  const t=$("vfgtesto");if(t)t.textContent=V.d=="fine"?"al cambio":V.d+(V.d==1?" seduta":" sedute");
  const alt=$("vfaltro");if(alt)alt.onclick=()=>{$("vfchiusi").innerHTML=R.chiusi.map(s=>scheda(s)).join("");alt.remove();};}

 function disegna(){el.innerHTML=`<h2>Verifica dei segnali</h2><p class="sub">Ogni segnale misurato con prezzi veri dall'uscita dei dati: ingresso alla prima chiusura dopo il segnale, poi risultato, guadagno massimo e drawdown massimo per l'orizzonte che scegli tu (da 1 seduta a 4 settimane, oppure fino al cambio di etichetta).</p>
  <div class="vfswitch"><button data-f="live" class="${V.fin=="live"?"on":""}">Registro live</button><button data-f="bt" class="${V.fin=="bt"?"on":""}">Backtest <span class="vfsimtag">SIMULATO</span></button></div>
  <div class="vfcorpo">${V.fin=="live"?live():backtest()}</div>`;
  el.querySelectorAll(".vfswitch button").forEach(b=>b.onclick=()=>{V.fin=b.dataset.f;salva();disegna();});
  el.querySelectorAll(".vforz button").forEach(b=>b.onclick=()=>{V.d=b.dataset.h=="fine"?"fine":+b.dataset.h;const r=$("vfgiorni");if(r&&V.d!="fine")r.value=V.d;salva();aggiorna();});
  el.querySelectorAll(".vfper button").forEach(b=>b.onclick=()=>{V.per=b.dataset.p;el.querySelectorAll(".vfper button").forEach(x=>x.classList.toggle("on",x==b));salva();aggiorna();});
  const r=$("vfgiorni");if(r){r.oninput=()=>{V.d=+r.value;aggiorna();};r.onchange=salva;}
  aggiorna();}
 disegna();})();}catch(e){fail('Verifica dei segnali','verifica',e);}

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

