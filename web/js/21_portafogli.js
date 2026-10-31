
/* ---------- portafogli modello ----------
   Dati da D.port (vedi cot_radar/portafogli.py): tre profili (conservativo, moderato, aggressivo), solo acquisti,
   rotazione il primo giorno di borsa di ogni mese. In alto un selettore a segmenti (Conservativo / Moderato /
   Aggressivo: "stesso motore, rischio diverso") e la CARD PRINCIPALE del profilo: rischio, descrizione, rendimento
   annuo, max drawdown, 10.000 euro dall'inizio dello storico, composizione per classe, le 5 azioni scelte del mese
   e la spiegazione apribile della rotazione. Sotto, per il profilo scelto:
     1. "Portafoglio di <mese>" del profilo scelto: righe raggruppate per classe (Azionario, Obbligazionario,
        Materie prime, Cripto, Liquidita'), per ogni mercato lo strumento UCITS/ETC/ETP da comprare in Europa con
        ISIN copiabile, peso e importo in euro sul capitale scritto dall'utente; le 5 azioni scelte elencate una per
        una (o l'ANTEPRIMA provvisoria del mese prossimo); esposizione al dollaro stimata;
        in alto il CONTO ALLA ROVESCIA al prossimo ribilanciamento (giorno di rotazione, 09:00 ora italiana);
     2. il rischio del MESE della rotazione (es. ottobre): la composizione di oggi tenuta in ogni ottobre dello
        storico, con rendimento e max drawdown dentro il mese anno per anno, esempio su 10.000 euro e
        stagionalita' del mese per ogni mercato (nessuna statistica per anno solare);
     3. la curva del capitale: storico, fuori campione (dal 2016) e live (dalla prima rotazione pubblicata),
        con il confronto 60/40; passando il mouse si leggono data e valore;
     4. tabella dei periodi, ultime rotazioni (entrati / usciti / tenuti) e mercati esclusi con il motivo.
   Il profilo scelto resta salvato nel browser (localStorage "ebProfilo"). */
try{(function(){const P=D.port,el=$("port");if(!el)return;
 if(!P||!P.profili||!P.profili.length){el.innerHTML=`<h2>Portafogli modello</h2><p class="sub">Scegli un profilo: stesso motore, rischio diverso. Solo acquisti, controllo una volta al mese.</p>`;return;}
 const CL={azioni:"var(--c1)","azioni singole":"var(--acc)",obbligazioni:"var(--c4)",metalli:"var(--warn)","materie prime":"var(--c2)",crypto:"var(--c5)",liquidita:"var(--c3)"};
 // nomi delle classi per la "composizione per classe" della card principale (ordine fisso di lettura)
 const CLN=[["azioni","Azionario (ETF)"],["azioni singole","Azioni singole"],["obbligazioni","Obbligazionario"],["metalli","Metalli preziosi"],["materie prime","Materie prime"],["crypto","Cripto"],["liquidita","Liquidità"]];
 // macro-classi per raggruppare le righe del portafoglio (azioni singole stanno nell'Azionario)
 const MACRO=[["Azionario",["azioni","azioni singole"]],["Obbligazionario",["obbligazioni"]],["Materie prime",["metalli","materie prime"]],["Cripto",["crypto"]],["Liquidità",["liquidita"]]];
 // borsa dal suffisso del ticker Yahoo; "ue:false" = di solito NON acquistabile dai broker europei per privati
 const BORSE={T:["Tokyo",1],NS:["India (NSE)",0],BO:["India (BSE)",0],SS:["Shanghai",0],SZ:["Shenzhen",0],HK:["Hong Kong",1],MI:["Milano",1],DE:["Xetra",1],PA:["Parigi",1],AS:["Amsterdam",1],L:["Londra",1],SW:["Svizzera",1],MC:["Madrid",1],BR:["Bruxelles",1],KS:["Corea",0],TW:["Taiwan",0],AX:["Australia",1],TO:["Toronto",1]};
 const borsa=t=>{const m=/\.([A-Z]+)$/.exec(t);return m?(BORSE[m[1]]||[m[1],1]):["USA",1];};
 const MESI=["gennaio","febbraio","marzo","aprile","maggio","giugno","luglio","agosto","settembre","ottobre","novembre","dicembre"];
 const SETT={tech:["Tecnologia"],tlc:["Comunicazione"],cdis:["Beni voluttuari"],cstap:["Prima necessità"],salute:["Salute"],fin:["Finanza"],ind:["Industria"],mat:["Materiali"],ener:["Energia"],util:["Servizi pubblici"],imm:["Immobiliare"]};
 // capitale per calcolare gli importi in euro di ogni riga (salvato nel browser)
 let capitale=10000;try{const c=+localStorage.getItem("ebCapitale");if(c>0)capitale=c;}catch(e){}
 const RISK={conservativo:["Basso","r1"],moderato:["Medio","r2"],aggressivo:["Alto","r3"]};
 const pc=(v,d=1)=>v==null?"n/d":(v>0?"+":"")+fx(v,d)+"%";
 const eur=v=>v==null?"n/d":Math.round(v).toLocaleString("it-IT")+" €";
 const gg=d=>d?d.slice(8,10)+"/"+d.slice(5,7)+"/"+d.slice(0,4):"";
 const nomeK=k=>{for(const p of P.profili){const c=p.composizione.find(x=>x.k==k);if(c)return c.nome;const a=p.ammessi.find(x=>x.k==k);if(a)return a.nome;}return k;};
 let sel=P.profili[1].id,per="tutto",tutteRot=false;
 try{const s=localStorage.getItem("ebProfilo");if(s&&P.profili.some(p=>p.id==s))sel=s;}catch(e){}

 // --- ciambella dei pesi (SVG): un arco per mercato, colore = classe
 function ciambella(comp){const R=62,C=2*Math.PI*R;let off=0;
  const archi=comp.map(c=>{const l=C*c.peso/100,s=`<circle r="${R}" cx="80" cy="80" fill="none" stroke="${CL[c.classe]||"var(--c3)"}" stroke-width="22" stroke-dasharray="${Math.max(0,l-2)} ${C}" stroke-dashoffset="${-off}" transform="rotate(-90 80 80)"><title>${esc(c.nome)}: ${fx(c.peso,1)}%</title></circle>`;off+=l;return s;}).join("");
  const n=comp.filter(c=>c.k!="CASH").length;
  return `<svg viewBox="0 0 160 160" class="ptorta" role="img" aria-label="Composizione del portafoglio">${archi}<text x="80" y="76" text-anchor="middle" class="ptn">${n}</text><text x="80" y="96" text-anchor="middle" class="ptl">${n==1?"mercato":"mercati"}</text></svg>`;}

 // --- curva del capitale (SVG, scala logaritmica: le percentuali hanno la stessa altezza in ogni epoca)
 function curva(p){const W=900,H=300,L=52,Rm=14,T=16,B=30;
  let pts=p.curva,bench=(P.bench||{}).curva||[];
  const dal=per=="oos"?P.oos_dal:per=="live"?(p.live_dal||P.oos_dal):null;
  if(dal){pts=pts.filter(x=>x[0]>=dal);bench=bench.filter(x=>x[0]>=dal);}
  if(pts.length<2)return `<div class="small" style="padding:30px;text-align:center">Dati non ancora sufficienti per questo periodo.</div>`;
  const b0=pts[0][1],bb0=(bench[0]||[0,1])[1];
  const s=pts.map(x=>[x[0],x[1]/b0*100]),sb=bench.map(x=>[x[0],x[1]/bb0*100]);
  const t0=+new Date(s[0][0]),t1=+new Date(s[s.length-1][0]);
  const tutti=s.concat(sb).map(x=>x[1]),lo=Math.log(Math.min(...tutti)*.97),hi=Math.log(Math.max(...tutti)*1.03);
  const X=d=>L+(+new Date(d)-t0)/(t1-t0||1)*(W-L-Rm),Y=v=>T+(hi-Math.log(v))/(hi-lo||1)*(H-T-B);
  const path=a=>a.map((x,i)=>(i?"L":"M")+X(x[0]).toFixed(1)+" "+Y(x[1]).toFixed(1)).join("");
  // griglia orizzontale: valori "tondi" del capitale (base 100)
  const passi=[25,50,75,100,150,200,300,400,600,800,1000,1500,2000,3000,5000];
  const righe=passi.filter(v=>Math.log(v)>lo&&Math.log(v)<hi).map(v=>`<line x1="${L}" x2="${W-Rm}" y1="${Y(v)}" y2="${Y(v)}" class="pgr"/><text x="${L-8}" y="${Y(v)+4}" text-anchor="end" class="pax">${v}</text>`).join("");
  const anni=[];for(let a=+s[0][0].slice(0,4)+1;a<=+s[s.length-1][0].slice(0,4);a++){const d=a+"-01-01";anni.push(a);}
  const passoA=Math.ceil(anni.length/10)||1;
  const etA=anni.filter((a,i)=>i%passoA==0).map(a=>`<text x="${X(a+"-01-01")}" y="${H-8}" text-anchor="middle" class="pax">${a}</text>`).join("");
  // fasce: fuori campione e live
  const fascia=(d,cls,et)=>d&&d>s[0][0]?`<rect x="${X(d)}" y="${T}" width="${W-Rm-X(d)}" height="${H-T-B}" class="${cls}"/><text x="${X(d)+8}" y="${T+14}" class="pfet">${et}</text>`:"";
  const live=p.live_dal?s.filter(x=>x[0]>=p.live_dal):[];
  return `<svg viewBox="0 0 ${W} ${H}" class="pcurva" data-t0="${t0}" data-t1="${t1}" preserveAspectRatio="none">
   ${righe}${fascia(P.oos_dal,"pfoos","FUORI CAMPIONE")}${p.live_dal?fascia(p.live_dal,"pflive","LIVE"):""}${etA}
   ${sb.length?`<path d="${path(sb)}" class="pbench"/>`:""}<path d="${path(s)}" class="plinea"/>${live.length>1?`<path d="${path(live)}" class="plive"/>`:""}
   <line class="pcur" x1="0" x2="0" y1="${T}" y2="${H-B}" style="display:none"/><circle class="pcurp" r="4.5" style="display:none"/></svg>
   <div class="ptip" hidden></div>
   <div class="pleg"><span><i class="lp"></i>Portafoglio ${esc(p.nome.toLowerCase())}</span><span><i class="lb"></i>${esc((P.bench||{}).nome||"60/40")}</span>${p.live_dal?'<span><i class="ll"></i>Live</span>':'<span class="small">La linea live parte con la prima rotazione pubblicata</span>'}</div>`;}

 // --- una riga del portafoglio: nome, strumento UCITS da comprare (ISIN copiabile), motivo, peso, importo in euro.
 //     Per "Azioni scelte": elenco dei 5 titoli (registrati, oppure ANTEPRIMA provvisoria del mese prossimo).
 function riga(c,p){const col=CL[c.classe]||"var(--c3)";
  const mot=c.k=="CASH"?"Liquidit&agrave; fissa del profilo + pesi dei mercati in pausa."
   :c.k=="AZ"?`filtro di mercato: S&amp;P 500 ${pc(c.trend)} sopra la media a 200 giorni`
   :`trend ${pc(c.trend)} sopra la media a 200 giorni · volatilit&agrave; ${fx(c.vol,0)}% · COT ${c.score!=null?sg(c.score,0):"n/d"} (informativo)`;
  const ue=c.ue?`<div class="pue"><span class="pue-n">${esc(c.ue.nome)}</span><button class="pisin" data-isin="${esc(c.ue.isin)}" title="Copia l'ISIN da cercare nell'app del broker"><code>${esc(c.ue.isin)}</code><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/></svg></button></div>${c.ue.nota?`<em class="pue-nota">${esc(c.ue.nota)}</em>`:""}`
   :`<span>${esc(c.strumento)}</span>`;
  let tit="";
  if(c.k=="AZ"){const reg=c.titoli&&c.titoli.length,an=c.anteprima,lista=reg?c.titoli:(an&&an.titoli)||[];
   const quota=lista.length?c.peso/lista.length:0;
   if(lista.length)tit=`<div class="paz">${reg?"":`<div class="paz-ante"><b>Anteprima per ${MESI[+an.mese.slice(5,7)-1]}</b> &middot; calcolata il ${gg(an.al)} con i prezzi di oggi. La lista definitiva si fissa l'ultimo giorno di borsa dopo la chiusura ed entra il ${gg(P.prossima)}.</div>`}
    ${lista.map(x=>{const b=borsa(x.t),sett=(SETT[x.s]||[x.s||""])[0];return `<button class="paz-r clic" data-az="${esc(x.t)}" title="Apri nell'Azionario">
     <span class="paz-id"><b>${esc(x.t)}</b><span class="paz-n">${esc(x.n)}</span></span><span class="paz-s">${esc(sett)}</span><span class="paz-b${b[1]?"":" no"}" title="${b[1]?"Borsa di quotazione":"Di solito non acquistabile dai broker europei per privati"}">${b[0]}</span><span class="paz-p"><b>${fx(quota,1)}%</b><em data-peso="${quota}">${eur(capitale*quota/100)}</em></span></button>`;}).join("")}</div>`;
   else tit=`<div class="small paz-vuoto">I 5 titoli si scelgono l'ultimo giorno di borsa del mese, dopo la chiusura, ed entrano con la rotazione del ${gg(P.prossima)}.</div>`;}
  // l'elenco dei titoli sta su una riga a parte della griglia, a tutta larghezza (leggibile anche su telefono)
  return `<div class="prow${c.k=="AZ"?" prow-az":""}"><i style="background:${col}"></i><div class="pnome"><b>${esc(c.nome)}</b>${ue}<em>${mot}</em></div>
   <div class="ppeso"><b>${fx(c.peso,1)}%</b><span class="peur">${eur(capitale*c.peso/100)}</span><span class="pbar"><i style="width:${Math.min(100,c.peso*2.5)}%;background:${col}"></i></span></div>${tit}</div>`;}

 // --- composizione del mese raggruppata per macro-classe (Azionario, Obbligazionario, Materie prime, Cripto, Liquidita')
 function composizione(p){const mesi=MESI[+P.rotazione.slice(5,7)-1];
  const gruppi=MACRO.map(g=>({n:g[0],r:p.composizione.filter(c=>g[1].includes(c.classe))})).filter(g=>g.r.length);
  // esposizione al dollaro: mercati quotati in USD (indici USA, Treasury, oro, Bitcoin) + azioni USA tra le scelte
  const USD=["SP500","NASDAQ","DOW","RUSSELL","US10Y","USBOND","GOLD","SILVER","PLATINUM","BTC","ETH"];
  let usd=p.composizione.filter(c=>USD.includes(c.k)).reduce((a,c)=>a+c.peso,0);
  const az=p.composizione.find(c=>c.k=="AZ");if(az){const l=(az.titoli&&az.titoli.length?az.titoli:(az.anteprima||{}).titoli)||[];if(l.length)usd+=az.peso*l.filter(x=>borsa(x.t)[0]=="USA").length/l.length;}
  return `<div class="card pcomp"><div class="ptesta"><div><h3>Portafoglio di ${mesi} <span class="pbprof">${esc(p.nome)}</span></h3>
    <span class="small">${p.composizione.filter(c=>c.k!="CASH").length} mercati &middot; ribilanciamento ${gg(P.rotazione)} &rarr; prossimo ${gg(P.prossima)}</span>
    <label class="pcap">Capitale <input type="text" inputmode="numeric" value="${capitale.toLocaleString("it-IT")}" aria-label="Capitale da investire in euro"> &euro;</label></div>${ciambella(p.composizione)}</div>
   ${gruppi.map(g=>`<div class="pgrp"><div class="pgrp-t"><span>${g.n}</span><b>${fx(g.r.reduce((a,c)=>a+c.peso,0),1)}%</b></div>${g.r.map(c=>riga(c,p)).join("")}</div>`).join("")}
   <div class="pfx"><span>Valute: nessuna posizione diretta. Esposizione al dollaro stimata <b>${fx(usd,0)}%</b> (gli strumenti UCITS in euro seguono comunque il cambio EUR/USD).</span></div>
   <p class="small pnota-ue">Strumenti UCITS / ETC / ETP acquistabili da un conto europeo: cerca l'ISIN nell'app del tuo broker. Gli ETF USA usati nei calcoli (SPY, QQQ…) non sono acquistabili dai privati in Europa. Informazione, non consulenza.</p></div>`;}

 // --- RISCHIO DEL MESE della rotazione (v6.41): la composizione di oggi tenuta nello stesso mese di ogni anno dello storico.
 //     1) TERMOMETRO: drawdown peggiore del mese contro il limite del profilo (tacca bianca), verdetto in parole;
 //     2) HEAT MAP: una casella per anno con la %, verde = guadagno, rosso = perdita (piu' intenso = piu' grande);
 //        interruttore "Risultato del mese" / "Scenario peggiore" (drawdown dentro il mese); fumetto con i dettagli;
 //     3) quattro numeri chiave allineati (titoli su piu' righe non spostano i valori: CSS subgrid).
 let hmModo="r";                                         // modo della heat map, ricordato cambiando profilo
 function hmCelle(m,modo){const peg=m.anni.reduce((a,x)=>x.dd<a.dd?x:a,m.anni[0]),per={};m.anni.forEach(x=>per[x.a]=x);
  const d0=Math.floor(m.anni[0].a/10)*10,d1=Math.floor(m.anni[m.anni.length-1].a/10)*10;
  const col=x=>{const t=Math.min(1,Math.abs(x)/(modo=="dd"?6:5));return modo=="dd"||x<0?`rgba(242,113,107,${(.12+.78*t).toFixed(2)})`:`rgba(79,214,163,${(.12+.78*t).toFixed(2)})`;};
  let h="";
  for(let d=d0;d<=d1;d+=10){h+=`<div class="phmdec">${d==1990?"anni '90":"anni "+d}</div>`;
   for(let y=d;y<d+10;y++){const x=per[y];
    if(!x){h+=`<div class="phmc vuota" aria-hidden="true"></div>`;continue;}
    const v=modo=="r"?x.r:x.dd;
    h+=`<div class="phmc${x.a==peg.a?" peg":""}" tabindex="0" data-a="${y}" style="background:${col(v)}"><span>${y}</span><b>${pc(v)}</b></div>`;}}
  return h;}
 function hmLeg(modo){return modo=="r"
  ?`<span>perdita</span><i style="background:linear-gradient(90deg,rgba(242,113,107,.9),rgba(242,113,107,.12) 48%,rgba(79,214,163,.12) 52%,rgba(79,214,163,.9))"></i><span>guadagno</span>`
  :`<span>drawdown piccolo</span><i style="background:linear-gradient(90deg,rgba(242,113,107,.12),rgba(242,113,107,.9))"></i><span>drawdown grande</span>`;}
 function contro(p){const m=p.mese,s=p.stat.totale||{},o=p.stat.oos||{},ddTot=Math.min(s.maxdd??0,o.maxdd??0);
  if(!m)return `<div class="card pcontro"><h3>Rischio del mese</h3><div class="small">Storico non ancora sufficiente.</div></div>`;
  const peg=m.anni.reduce((a,x)=>x.dd<a.dd?x:a,m.anni[0]),lim=-p.dd_rif,oltre=m.dd_max<lim,wr=Math.round(100*m.positivi/m.n);
  const altri=Math.min(...m.anni.filter(x=>x!==peg).map(x=>x.dd));
  // termometro: 0% a sinistra, fondo scala poco oltre il peggiore tra drawdown e limite
  const fondo=Math.min(m.dd_max,lim)*1.18,pos=v=>(v/fondo*100).toFixed(1);
  const k=(t,v,sub,cls="")=>`<div><span>${t}</span><b class="${cls}">${v}</b><em>${sub}</em></div>`;
  return `<div class="card pcontro"><div class="pctesta"><h3>Rischio di ${m.mese}</h3><span class="pbprof">${esc(p.nome)}</span></div>
   <div class="small">Questo portafoglio tenuto in ogni ${m.mese} dal ${m.anni[0].a} (${m.n} anni), dal primo giorno di borsa al primo del mese dopo.</div>
   <div class="ptermo-t"><span>Drawdown peggiore di ${m.mese}</span><em class="${oltre?"pko":"pok"}">${oltre?`Oltre il limite di ${fx(Math.abs(m.dd_max-lim),1)} punti`:"Dentro il limite del profilo"}</em></div>
   <div class="ptermo"><div class="ptermo-r" style="width:${pos(m.dd_max)}%"></div><span class="ptermo-l" style="left:${pos(lim)}%"></span>
    <span class="ptermo-e su" style="left:${pos(lim)}%">limite ${pc(lim,0)}</span><span class="ptermo-e giu" style="left:0;transform:none">0%</span>
    <span class="ptermo-e giu" style="left:${pos(m.dd_max)}%">${pc(m.dd_max)}</span></div>
   <div class="small pdd-quando">Peggior caso: ${m.mese} ${peg.a}. Con <b>10.000 €</b> il conto sarebbe sceso fino a <b>${eur(10000*(1+m.dd_max/100))}</b> durante il mese. Negli altri ${m.n-1} anni il drawdown non ha mai superato il ${pc(altri)}.</div>
   <div class="phmtesta"><span>${m.mese[0].toUpperCase()+m.mese.slice(1)} anno per anno</span>
    <div class="phmsw" role="tablist"><button type="button" data-m="r" class="${hmModo=="r"?"on":""}" role="tab" aria-selected="${hmModo=="r"}">Risultato del mese</button><button type="button" data-m="dd" class="${hmModo=="dd"?"on":""}" role="tab" aria-selected="${hmModo=="dd"}">Scenario peggiore</button></div></div>
   <div class="phmbox"><div class="phm">${hmCelle(m,hmModo)}</div><div class="phmtip" hidden></div></div>
   <div class="phmleg">${hmLeg(hmModo)}</div>
   <div class="pmini">${k("Peggior "+m.mese,pc(m.peggiore[1]),String(m.peggiore[0]),"down")}${k(m.mese[0].toUpperCase()+m.mese.slice(1)+" medio",pc(m.media),`su ${m.n} anni`,m.media>=0?"up":"down")}
    ${k("Anni positivi",`${m.positivi} su ${m.n}`,`win rate ${wr}%`)}${k("Max drawdown storico",pc(ddTot),"intero backtest del profilo","down")}</div>
   ${m.mercati.length?`<div class="pstag"><div class="pstag-t">Stagionalit&agrave; di ${m.mese} per mercato <span class="small">(informativa)</span></div>${m.mercati.map(x=>`<div class="pstag-r"><span>${esc(nomeK(x.k))}</span><i><s class="${x.media>=0?"su":"giu"}" style="width:${Math.min(100,Math.abs(x.media)*8)}%"></s></i><b class="${x.media>=0?"up":"down"}">${pc(x.media)}</b><em>${x.pos}% positivi</em></div>`).join("")}</div>`:""}</div>`;}


 // --- MESE IN CORSO (v6.43): come sta andando adesso il portafoglio del profilo scelto, dalla rotazione a oggi.
 //     Prezzi a fine giornata (EOD), ingresso alla chiusura del giorno di rotazione (come nello storico e nel registro).
 //     Il risultato e' provvisorio fino a fine mese; i mesi chiusi dal live restano nel registro (chiusure_v3.json).
 function corso(p){const c=p.corrente;if(!c)return "";
  const z=v=>v==null?v:(Math.abs(v)<0.05?0:v);                       // niente "-0,0%": sotto 0,05 punti e' zero
  const r=z(c.r),rr=z(c.rr),m=p.mese,cl=r>0?"up":r<0?"down":"flat",MES=x=>x[0].toUpperCase()+x.slice(1);
  const chiusi=(P.chiusure||[]).filter(x=>x.profili&&x.profili[p.id]).slice(-6).reverse();
  let termo="";
  if(m&&m.anni&&m.anni.length){const rs=m.anni.map(x=>x.r),lo=Math.min(...rs,c.r),hi=Math.max(...rs,c.r),sp=(hi-lo)||1,pos=v=>Math.max(3,Math.min(97,(v-lo)/sp*100)).toFixed(1);
   termo=`<div class="pmc-f"><span class="pmc-pt" style="left:${pos(c.r)}%"></span><span class="pmc-e" style="left:3%;transform:none">${pc(lo)}</span><span class="pmc-e" style="left:${pos(m.media)}%">media ${pc(m.media)}</span><span class="pmc-e" style="left:97%;transform:translateX(-100%)">${pc(hi)}</span></div>
    <p class="pmc-fr">Rispetto ai <b>${m.n}</b> ${m.mese} passati con questa composizione, il mese va <b>${c.r>=m.media?"sopra":"sotto"}</b> la media storica.</p>`;}
  const wr=m&&m.n?Math.round(100*m.positivi/m.n):null;
  const k=(t,v,cls="")=>`<div><small>${t}</small><b class="${cls}">${v}</b></div>`;
  return `<div class="card pmc"><div class="pmc-t"><h3>${MES(c.mese)} in corso <span class="pbprof">${esc(p.nome)}</span></h3>
    <span class="pmc-b${c.live?"":" sim"}">${c.live?"Provvisorio &middot; si chiude a fine mese":"Simulazione &middot; il live parte il "+gg(P.prossima)}</span></div>
   <div class="pmc-g"><b class="${cl}">${pc(r)}</b><span>da inizio mese &middot; ingresso alla chiusura del ${gg(c.dal)}</span></div>
   <div><div class="pmc-bar"><i style="width:${Math.min(100,c.gg/c.tot*100).toFixed(0)}%"></i></div><div class="pmc-bl"><span>Giorno ${c.gg} di ${c.tot} di borsa</span><span>fine mese</span></div></div>
   <div class="pmc-k">${k("Drawdown peggiore",pc(c.dd),"down")}${k("Rendimento / rischio",rr==null?"n/d":fx(rr,1))}${k("Mesi storici in positivo",wr==null?"n/d":wr+"%")}</div>
   ${termo}
   ${chiusi.length?`<div class="pmc-h"><div class="pmc-ht">Mesi chiusi (live)</div>${chiusi.map(x=>{const r=x.profili[p.id];return `<div class="pmc-hr"><span>${MES(MESI[+x.mese.slice(5)-1])} ${x.mese.slice(0,4)}</span><b class="${r.r>=0?"up":"down"}">${pc(r.r)}</b><em>drawdown ${pc(r.dd)}</em></div>`;}).join("")}</div>`:""}
   <p class="pmc-n">Prezzi a fine giornata (EOD), ingresso alla chiusura del giorno di rotazione.</p></div>`;}

 function tabella(p){const st=p.stat,b=(P.bench||{}).stat||{};
  // v6.52: la colonna Live compare solo quando ci sono dati live (prima era una colonna di "in arrivo")
  const col=[["Storico",st.storico,`fino al 2015`],["Fuori campione",st.oos,`dal 2016`]].concat(st.live?[["Live",st.live,p.live_dal?`dal ${gg(p.live_dal)}`:"dall'avvio"]]:[]).concat([["60/40",b.oos,"dal 2016"]]);
  const r=(t,f)=>`<tr><th>${t}</th>${col.map(c=>`<td>${c[1]?f(c[1]):'<span class="small">n/d</span>'}</td>`).join("")}</tr>`;
  return `<div class="tablewrap ptab"><table><tr><th class="ptab0">Risultati<span>per periodo</span></th>${col.map(c=>`<th>${c[0]}<span>${c[2]}</span></th>`).join("")}</tr>
   ${r("Rendimento annuo",x=>x.cagr==null?pc(x.totale)+" tot.":pc(x.cagr))}${r("Volatilit&agrave;",x=>fx(x.vol,1)+"%")}
   ${r("Max drawdown",x=>`<b class="down">${pc(x.maxdd)}</b>`)}${r("Peggior mese",x=>x.peggior_mese?pc(x.peggior_mese[1]):"n/d")}${r("Win rate mensile",x=>(x.mesi_pos??"n/d")+"%")}</table></div>
   ${st.live?"":`<p class="small">La colonna <b>Live</b> compare dopo la prima rotazione con le regole attuali (${gg(P.prossima)}).</p>`}`;}

 /* v6.52: ogni rotazione mostra com'e' andato il mese (netto e drawdown) e, aprendo "Dettaglio", ogni mercato con
    peso, rendimento, contributo al totale (punti %) e drawdown; per le Azioni scelte anche i singoli titoli. */
 function dettMese(m){if(!m)return `<div class="prisul small">mese in corso</div>`;
  const riga=a=>`<tr><td>${esc(a.nome)}${a.titoli&&a.titoli.length?`<div class="ptit">${a.titoli.map(t=>`<span>${esc(t.n)} <em class="${t.r==null?"":t.r>=0?"up":"down"}">${t.r==null?"in corso":pc(t.r)}</em></span>`).join("")}</div>`:""}</td>
   <td class="num">${fx(a.w,0)}%</td><td class="num ${a.r>=0?"up":"down"}">${pc(a.r)}</td><td class="num ${a.c>=0?"up":"down"}">${a.c>0?"+":""}${fx(a.c,2)}</td><td class="num down">${pc(a.dd)}</td></tr>`;
  const peg=[...m.asset].sort((x,y)=>x.c-y.c)[0];
  return `<div class="prisul"><span>Risultato <b class="${m.r>=0?"up":"down"}">${pc(m.r)}</b></span><span>drawdown <b class="down">${pc(m.dd)}</b></span></div>
   <details class="pdet"><summary>Dettaglio del mese</summary>
    ${peg&&peg.c<0?`<p class="small">Ha pesato di pi&ugrave;: <b>${esc(peg.nome)}</b> (${fx(peg.c,2)} punti sul totale).</p>`:""}
    <div class="tablewrap"><table class="compatta pdett"><tr><th>Mercato</th><th class="num">Peso</th><th class="num">Rend.</th><th class="num">Contributo</th><th class="num">Drawdown</th></tr>${m.asset.map(riga).join("")}</table></div>
    <p class="small">Contributo = peso &times; rendimento, in punti percentuali: la somma (meno i costi) d&agrave; il risultato del mese.</p></details>`;}
 function rotazioni(p){const ch=k=>`<span class="pchip" title="${esc(nomeK(k))}">${esc(nomeK(k))}</span>`;
  const perMese={};(p.mesi_chiusi||[]).forEach(m=>perMese[m.mese]=m);
  return `<div class="prot${tutteRot?" aperta":""}">${p.rotazioni.map((r,i)=>`<div class="protr${i>=6?" pextra":""}"><b>${gg(r.data)}</b><div>
   ${r.entrati.length?`<div class="pin">+ ${r.entrati.map(ch).join("")}</div>`:""}${r.usciti.length?`<div class="pout">&minus; ${r.usciti.map(ch).join("")}</div>`:""}
   ${r.tenuti.length?`<div class="pten">= ${r.tenuti.map(ch).join("")}</div>`:""}${!r.entrati.length&&!r.usciti.length&&!r.tenuti.length?'<div class="small">tutto in liquidit&agrave;</div>':""}</div>
   <span class="small">${r.liquidita?`liquidit&agrave; ${r.liquidita}%`:""}</span>${dettMese(perMese[r.data.slice(0,7)])}</div>`).join("")}
   ${p.rotazioni.length>6?`<button class="ptutte">${tutteRot?"Mostra meno":`Mostra tutte (${p.rotazioni.length})`}</button>`:""}</div>`;}

 // --- AVVISO DATI NON AGGIORNATI (P.avviso dal backend): solo il popup comune di manutenzione (manutenzione.js),
 //     nessuna barra fissa. Data e ora dell'anomalia arrivano dal backend (P.avviso.quando).
 if(P.avviso)ebManutenzione({scheda:"port",codice:P.avviso.codice,quando:P.avviso.quando,dal:P.avviso.dal});

 // --- CARD PRINCIPALE del profilo scelto: rischio, descrizione, numeri chiave, composizione per classe, 5 azioni
 function hero(p){const t=p.stat.totale||{},rk=RISK[p.id]||["",""];
  const cl={};p.composizione.forEach(c=>{cl[c.classe]=(cl[c.classe]||0)+c.peso;});
  const finale=t.totale!=null?10000*(1+t.totale/100):null,anno=(t.dal||"").slice(0,4);
  const az=p.composizione.find(c=>c.k=="AZ"),pausa=p.esclusi.find(x=>x.k=="AZ");
  return `<div class="card phero"><div class="phtesta"><h3>${esc(p.nome)}</h3><span class="prisk ${rk[1]}">Rischio ${rk[0].toLowerCase()}</span></div>
   <p class="phdesc">${esc(p.descr)}</p>
   <div class="phnum"><div><em>Rendimento annuo</em><b class="up">${pc(t.cagr)}</b><span>media dal ${anno}</span></div>
    <div><em>Max drawdown</em><b class="down">${pc(t.maxdd)}</b><span>dal picco al minimo</span></div>
    <div><em>10.000 € nel ${anno}</em><b>${eur(finale)}</b><span>valore di oggi</span></div>
    <div><em>Mesi positivi</em><b>${t.mesi_pos??"n/d"}%</b><span>su tutti i mesi</span></div></div>
   <div class="phcomp"><h4>Composizione del mese</h4>${CLN.filter(x=>cl[x[0]]).map(x=>`<div class="phbar"><span>${x[1]}</span><b>${fx(cl[x[0]],1)}%</b><i><s style="width:${Math.min(100,cl[x[0]])}%;background:${CL[x[0]]}"></s></i></div>`).join("")}</div>
   <div class="phaz"><h4>Le 5 azioni del mese <span class="small">(${p.az}% del portafoglio${az&&az.titoli&&az.titoli.length?`, ${fx(az.peso_titolo,1)}% ciascuna`:""})</span></h4>
    ${pausa?`<div class="small">${esc(pausa.motivo)}.</div>`:az&&az.titoli&&az.titoli.length?`<div class="ptit">${az.titoli.map(x=>`<button class="pchip clic" data-az="${esc(x.t)}" title="Apri nell'Azionario">${esc(x.t)} <small>${esc(x.n)}</small></button>`).join("")}</div>`
     :`<div class="small">I titoli vengono scelti l'ultimo giorno di borsa del mese, dopo la chiusura, e entrano con la rotazione del ${gg(P.prossima)}.</div>`}</div>
   <details class="phcome"><summary>Come funziona la rotazione di ogni mese</summary><ol>
    <li><b>Primo giorno di borsa del mese</b>: per gli ETF azionari e Bitcoin si controlla il trend. Se il prezzo &egrave; sotto la media a 200 giorni il suo peso va in pausa nella liquidit&agrave;. <b>Treasury e oro restano sempre</b>: sono la difesa del portafoglio.</li>
    <li><b>Si compra e si vende solo se serve</b>: se nessun mercato entra o esce il portafoglio resta com'&egrave;; a inizio trimestre (gennaio, aprile, luglio, ottobre) si riportano i pesi al loro valore. Meno scambi = meno costi e meno tasse.</li>
    <li><b>Azioni scelte (${p.az}%)</b>: i 5 titoli dell'Azionario con il punteggio pi&ugrave; alto che hanno trend positivo (sopra la media a 200 giorni, 3 e 12 mesi in guadagno), non pi&ugrave; del 15% sotto il massimo dell'anno e il mese che entra positivo in almeno il 60% degli anni (minimo 8). Al massimo uno per settore, a pari peso.</li>
    <li><b>Filtro di mercato</b>: se l'S&amp;P 500 &egrave; sotto la sua media a 200 giorni tutta la quota azioni va in liquidit&agrave; (nel 2008, senza filtro, questa quota perdeva il 55%).</li>
    <li><b>Durante il mese non si tocca nulla</b>. Al mese dopo chi resta tra i migliori rimane, chi esce si vende, chi entra si compra. Costi inclusi: 0,10% sugli ETF, 0,20% sulle azioni.</li>
    <li><b>Registro</b>: ogni rotazione e ogni scelta di titoli vengono salvate e non si modificano pi&ugrave;: la linea live non si pu&ograve; aggiustare dopo.</li></ol>
    <p class="small">${esc((P.azioni||{}).nota||"")} Storico fino al 2015, fuori campione dal 2016. Prezzi in dollari di ETF ed ETC equivalenti e azioni in valuta locale (cambi non inclusi).</p></details></div>`;}

 // ridisegna mantenendo la posizione della pagina (v6.52: prima ogni tocco riportava in cima)
 function ridisegna(){const y=window.scrollY;disegna();window.scrollTo(0,y);}
 function disegna(){const p=P.profili.find(x=>x.id==sel);
  el.innerHTML=`<h2>Portafogli modello</h2><p class="sub">Tre profili di rischio, solo acquisti, controllo ogni mese. Ogni profilo ha una base fissa di mercati e pesi; un mercato azionario resta in portafoglio finch&eacute; il prezzo &egrave; sopra la media a 200 giorni, altrimenti il suo peso va in pausa nella liquidit&agrave; fino a quando torna sopra; Treasury e oro restano sempre come difesa. Nei test sullo storico questo filtro di trend ha ridotto molto i drawdown, mentre il posizionamento COT non migliorava i risultati: per questo il COT &egrave; mostrato accanto a ogni mercato solo come informazione. Regole di base decise sullo storico fino al 2015 e verificate dal 2016; la revisione di ottobre 2026 (meno azioni singole, difesa sempre presente, meno scambi) ha guardato tutto lo storico, quindi la prova davvero pulita &egrave; la linea live, che riparte dalla rotazione del 2 novembre 2026. Il rischio si legge mese per mese: a ogni rotazione la scheda mostra come si &egrave; comportata la composizione del mese nello stesso mese di tutti gli anni dello storico. Prezzi in dollari di ETF ed ETC equivalenti (il cambio euro/dollaro non &egrave; incluso), costi 0,10% a ogni rotazione.</p>
   <div class="pdate"><span><i></i>Rotazione del <b>${gg(P.rotazione)}</b></span><span class="pcount" data-t="${P.prossima||""}" title="Prossimo ribilanciamento: ${gg(P.prossima)} all'apertura delle borse europee (09:00 ora italiana)">Prossimo ribilanciamento <b class="pcd">${gg(P.prossima)}</b></span></div>
   <div class="pseg" role="tablist" aria-label="Scegli il portafoglio">${P.profili.map(x=>`<button role="tab" aria-selected="${x.id==sel}" class="${x.id==sel?"on":""}" data-p="${x.id}">${x.nome}</button>`).join("")}</div>
   ${hero(p)}
   ${corso(p)}
   <div class="pgrid">${composizione(p)}${contro(p)}</div>
   <h3 class="vft">Andamento del capitale <span class="small">(base 100, scala logaritmica: la stessa percentuale ha la stessa altezza in ogni periodo. Linea turchese = portafoglio, tratteggio = 60/40 di confronto, linea luminosa = live dalla prima rotazione pubblicata)</span></h3>
   <div class="vfswitch pper">${[["tutto","Tutto"],["oos","Fuori campione"],["live","Live"]].map(x=>`<button data-per="${x[0]}" class="${per==x[0]?"on":""}">${x[1]}</button>`).join("")}</div>
   <div class="card pgraf">${curva(p)}</div>
   ${tabella(p)}
   <div class="grid k2 pbasso"><div><h3 class="vft">Ultime rotazioni <span class="small">(+ entrati, &minus; usciti, = rimasti)</span></h3>${rotazioni(p)}</div>
    <div><h3 class="vft">In pausa questo mese <span class="small">(mercati della base sotto la media a 200 giorni: il loro peso &egrave; nella liquidit&agrave; e rientra quando il trend torna positivo)</span></h3>
    <div class="card pescl">${p.esclusi.length?p.esclusi.map(x=>`<div class="pesr"><b>${esc(nomeK(x.k))}</b><span>${x.motivo}</span><em>base ${fx(x.base,0)}% &middot; trend ${pc(x.trend)} &middot; COT ${x.score!=null?sg(x.score,0):"n/d"}</em></div>`).join(""):'<div class="small">Nessun mercato in pausa: tutta la base &egrave; investita.</div>'}</div></div></div>`;
  el.querySelectorAll(".pseg button").forEach(b=>b.onclick=()=>{sel=b.dataset.p;try{localStorage.setItem("ebProfilo",sel);}catch(e){}ridisegna();});
  // clic su un titolo delle azioni scelte: apre la sua scheda nell'Azionario (azioni.js)
  el.querySelectorAll("[data-az]").forEach(b=>b.onclick=()=>{if(window.ebApriTitolo)window.ebApriTitolo(b.dataset.az);});
  el.querySelectorAll(".pper button").forEach(b=>b.onclick=()=>{per=b.dataset.per;ridisegna();});
  const bt=el.querySelector(".ptutte");if(bt)bt.onclick=()=>{tutteRot=!tutteRot;ridisegna();};
  // copia dell'ISIN: feedback "Copiato" per 1,5 secondi
  el.querySelectorAll(".pisin").forEach(b=>b.onclick=async()=>{try{await navigator.clipboard.writeText(b.dataset.isin);}catch(e){}
   b.classList.add("ok");b.querySelector("code").textContent="Copiato";setTimeout(()=>{b.classList.remove("ok");b.querySelector("code").textContent=b.dataset.isin;},1500);});
  // capitale: ricalcola gli importi in euro mentre si scrive (solo cifre), salvato nel browser
  const ci=el.querySelector(".pcap input");if(ci){ci.oninput=()=>{const v=+ci.value.replace(/\D/g,"");capitale=v||0;
   aggiornaEuro(p);};ci.onblur=()=>{ci.value=capitale.toLocaleString("it-IT");try{localStorage.setItem("ebCapitale",capitale);}catch(e){}};}
  tipMesi(el.querySelector(".pcontro"),p);
  conto();
  suggerimento(el.querySelector(".pgraf"),p);}
 // --- CONTO ALLA ROVESCIA al prossimo ribilanciamento: primo giorno di borsa del mese alle 09:00 ora italiana
 //     (apertura di Xetra/Borsa Italiana, dove si comprano gli strumenti UCITS). Un solo timer per tutta la pagina,
 //     fermo quando la scheda del browser non e' visibile; se la data manca o e' passata mostra un testo fisso.
 let timer=0;
 function oraRoma(ymd,h){// Date per "ymd hh:00" a Roma, con ora legale/solare corretta (senza librerie)
  const [y,m,d]=ymd.split("-").map(Number),g=Date.UTC(y,m-1,d,h);
  const parti=new Intl.DateTimeFormat("en-GB",{timeZone:"Europe/Rome",hour:"2-digit",hourCycle:"h23"}).formatToParts(new Date(g));
  const hr=+parti.find(x=>x.type=="hour").value;return new Date(g-((hr-h+24)%24)*3600e3);}
 function conto(){clearInterval(timer);const box=el.querySelector(".pcount");if(!box||!box.dataset.t)return;
  let fine;try{fine=oraRoma(box.dataset.t,9);}catch(e){return;}
  const out=box.querySelector(".pcd"),z=n=>String(n).padStart(2,"0");
  const tick=()=>{if(!document.body.contains(box)){clearInterval(timer);return;}
   const ms=fine-Date.now();
   if(ms<=0){out.textContent="oggi";box.classList.add("ora");clearInterval(timer);return;}
   const t=Math.floor(ms/1000),gi=Math.floor(t/86400),o=Math.floor(t%86400/3600),mi=Math.floor(t%3600/60),se=t%60;
   out.innerHTML=`${gi?`<u>${gi}</u>g `:""}<u>${z(o)}</u>h <u>${z(mi)}</u>m <u>${z(se)}</u>s`;};
  tick();timer=setInterval(()=>{if(!document.hidden)tick();},1000);}
 // importi in euro senza ridisegnare tutto (il campo resta a fuoco mentre si scrive)
 function aggiornaEuro(p){const pesi=[];MACRO.forEach(g=>p.composizione.filter(c=>g[1].includes(c.classe)).forEach(c=>pesi.push(c.peso)));
  el.querySelectorAll(".pcomp .peur").forEach((e,i)=>{e.textContent=eur(capitale*(pesi[i]||0)/100);});
  el.querySelectorAll(".paz-p em").forEach(e=>{e.textContent=eur(capitale*(+e.dataset.peso||0)/100);});}
 // tooltip del grafico del rischio del mese: anno, rendimento, max drawdown
 function tipMesi(card,p){if(!card||!p.mese)return;const m=p.mese,box=card.querySelector(".phmbox"),tip=card.querySelector(".phmtip");if(!box)return;
  // interruttore Risultato del mese / Scenario peggiore: ridisegna solo la griglia
  card.querySelectorAll(".phmsw button").forEach(b=>b.onclick=()=>{hmModo=b.dataset.m;
   card.querySelectorAll(".phmsw button").forEach(x=>{x.classList.toggle("on",x===b);x.setAttribute("aria-selected",x===b);});
   box.querySelector(".phm").innerHTML=hmCelle(m,hmModo);card.querySelector(".phmleg").innerHTML=hmLeg(hmModo);tip.hidden=true;});
  // fumetto: mouse, tastiera e tocco
  const mostra=e=>{const c=e.target.closest(".phmc[data-a]");if(!c){tip.hidden=true;return;}
   const x=m.anni.find(q=>q.a==c.dataset.a),r=box.getBoundingClientRect(),cb=c.getBoundingClientRect();
   tip.innerHTML=`<b>${m.mese[0].toUpperCase()+m.mese.slice(1)} ${x.a}</b><span>Risultato del mese <b class="${x.r>=0?"up":"down"}">${pc(x.r)}</b></span><span>Scenario peggiore <b class="down">${pc(x.dd)}</b></span><span>10.000 € &rarr; ${eur(10000*(1+x.r/100))} a fine mese</span>`;
   tip.hidden=false;const w=tip.offsetWidth,h=tip.offsetHeight;
   tip.style.left=Math.max(0,Math.min(r.width-w,cb.left-r.left+cb.width/2-w/2))+"px";
   tip.style.top=(cb.top-r.top-h-8<0?cb.bottom-r.top+8:cb.top-r.top-h-8)+"px";};
  box.addEventListener("mouseover",mostra);box.addEventListener("focusin",mostra);box.addEventListener("click",mostra);
  box.addEventListener("mouseleave",()=>tip.hidden=true);}

 // --- passando il mouse sulla curva: linea verticale, punto e valore della settimana
 function suggerimento(box,p){const svg=box&&box.querySelector("svg.pcurva");if(!svg)return;const tip=box.querySelector(".ptip");
  const lin=svg.querySelector(".pcur"),pt=svg.querySelector(".pcurp"),path=svg.querySelector(".plinea");
  const dal=per=="oos"?P.oos_dal:per=="live"?(p.live_dal||P.oos_dal):null;
  const s=p.curva.filter(x=>!dal||x[0]>=dal),b0=s.length?s[0][1]:1;
  svg.addEventListener("mousemove",e=>{const r=svg.getBoundingClientRect(),fx_=(e.clientX-r.left)/r.width;
   const vb=svg.viewBox.baseVal,x=fx_*vb.width;if(x<52||x>vb.width-14)return;
   const t0=+svg.dataset.t0,t1=+svg.dataset.t1,t=t0+(x-52)/(vb.width-66)*(t1-t0);
   let i=s.findIndex(q=>+new Date(q[0])>=t);if(i<0)i=s.length-1;
   const len=path.getTotalLength();let a=0,z=len,P2=null;
   for(let k=0;k<22;k++){const m=(a+z)/2;P2=path.getPointAtLength(m);if(P2.x<x)a=m;else z=m;}
   lin.setAttribute("x1",x);lin.setAttribute("x2",x);lin.style.display="";pt.setAttribute("cx",P2.x);pt.setAttribute("cy",P2.y);pt.style.display="";
   tip.hidden=false;tip.innerHTML=`<b>${gg(s[i][0])}</b> ${fx(s[i][1]/b0*100,1)} <span>(${pc(s[i][1]/b0*100-100)})</span>`;
   tip.style.left=Math.min(r.width-170,Math.max(0,e.clientX-r.left+12))+"px";});
  svg.addEventListener("mouseleave",()=>{lin.style.display="none";pt.style.display="none";tip.hidden=true;});}
 disegna();
})();}catch(e){fail('Portafogli','port',e);}
