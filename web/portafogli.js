
/* ---------- portafogli modello ----------
   Dati da D.port (vedi cot_radar/portafogli.py): tre profili (conservativo, moderato, aggressivo), solo acquisti,
   rotazione il primo giorno di borsa di ogni mese. Per il profilo scelto la scheda mostra:
     1. la composizione del mese (ciambella + righe con peso, motivo e strumento da comprare);
     2. "cosa puo' andare contro": drawdown massimo storico, peggior mese e anno, esempio su 10.000 euro;
     3. la curva del capitale: storico, fuori campione (dal 2016) e live (dalla prima rotazione pubblicata),
        con il confronto 60/40; passando il mouse si leggono data e valore;
     4. tabella dei periodi, ultime rotazioni (entrati / usciti / tenuti) e mercati esclusi con il motivo.
   Il profilo scelto resta salvato nel browser (localStorage "ebProfilo"). */
try{(function(){const P=D.port,el=$("port");if(!el)return;
 if(!P||!P.profili||!P.profili.length){el.innerHTML=`<h2>Portafogli modello</h2><p class="sub">I prezzi storici degli ETF non sono disponibili in questo aggiornamento: la scheda torna al prossimo giro.</p>`;return;}
 const CL={azioni:"var(--c1)",obbligazioni:"var(--c4)",metalli:"var(--warn)","materie prime":"var(--c2)",crypto:"var(--c5)",liquidita:"var(--c3)"};
 const LIV={conservativo:1,moderato:2,aggressivo:3};
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

 function riga(c){const col=CL[c.classe]||"var(--c3)";
  const mot=c.k=="CASH"?"Liquidit&agrave; fissa del profilo + pesi dei mercati in pausa, in Treasury a breve termine."
   :`trend ${pc(c.trend)} sopra la media a 200 giorni · volatilit&agrave; ${fx(c.vol,0)}% · COT ${c.score!=null?sg(c.score,0):"n/d"} (informativo)`;
  return `<div class="prow"><i style="background:${col}"></i><div class="pnome"><b>${esc(c.nome)}</b><span>${esc(c.strumento)}</span><em>${mot}</em></div>
   <div class="ppeso"><b>${fx(c.peso,1)}%</b><span class="pbar"><i style="width:${Math.min(100,c.peso*2.5)}%;background:${col}"></i></span></div></div>`;}

 function contro(p){const s=p.stat.totale||{},o=p.stat.oos||{},dd=Math.min(s.maxdd??0,o.maxdd??0);
  const oltre=-dd>p.dd_rif;
  return `<div class="card pcontro"><h3>Cosa pu&ograve; andare contro</h3>
   <div class="pdd"><span>Caduta massima nello storico</span><b>${pc(dd)}</b><em class="${oltre?"pko":"pok"}">${oltre?"oltre":"entro"} il riferimento del profilo (&minus;${p.dd_rif}%)</em></div>
   <div class="pesempio">Con <b>10.000 €</b> investiti, nel momento peggiore il conto sarebbe sceso a <b>${eur(10000*(1+dd/100))}</b> prima di risalire.</div>
   <div class="pmini"><div><span>Peggior mese</span><b>${s.peggior_mese?pc(s.peggior_mese[1]):"n/d"}</b><em>${s.peggior_mese?s.peggior_mese[0].split("-").reverse().join("/"):""}</em></div>
    <div><span>Peggior anno</span><b>${s.peggior_anno?pc(s.peggior_anno[1]):"n/d"}</b><em>${s.peggior_anno?s.peggior_anno[0]:""}</em></div>
    <div><span>Mesi positivi</span><b>${s.mesi_pos??"n/d"}%</b><em>dal ${(s.dal||"").slice(0,4)}</em></div>
    <div><span>Volatilit&agrave;</span><b>${fx(s.vol,1)}%</b><em>annua</em></div></div></div>`;}

 function tabella(p){const st=p.stat,b=(P.bench||{}).stat||{};
  const col=[["Storico",st.storico,`fino al 2015`],["Fuori campione",st.oos,`dal 2016`],["Live",st.live,p.live_dal?`dal ${gg(p.live_dal)}`:"dalla prima rotazione"],["60/40",b.oos,"dal 2016"]];
  const r=(t,f)=>`<tr><th>${t}</th>${col.map(c=>`<td>${c[1]?f(c[1]):'<span class="small">in arrivo</span>'}</td>`).join("")}</tr>`;
  return `<div class="tablewrap ptab"><table><tr><th></th>${col.map(c=>`<th>${c[0]}<span>${c[2]}</span></th>`).join("")}</tr>
   ${r("Rendimento annuo",x=>x.cagr==null?pc(x.totale)+" tot.":pc(x.cagr))}${r("Volatilit&agrave;",x=>fx(x.vol,1)+"%")}
   ${r("Caduta massima",x=>`<b class="down">${pc(x.maxdd)}</b>`)}${r("Peggior mese",x=>x.peggior_mese?pc(x.peggior_mese[1]):"n/d")}${r("Mesi positivi",x=>(x.mesi_pos??"n/d")+"%")}</table></div>`;}

 function rotazioni(p){const ch=k=>`<span class="pchip" title="${esc(nomeK(k))}">${esc(nomeK(k))}</span>`;
  return `<div class="prot${tutteRot?" aperta":""}">${p.rotazioni.map((r,i)=>`<div class="protr${i>=6?" pextra":""}"><b>${gg(r.data)}</b><div>
   ${r.entrati.length?`<div class="pin">+ ${r.entrati.map(ch).join("")}</div>`:""}${r.usciti.length?`<div class="pout">&minus; ${r.usciti.map(ch).join("")}</div>`:""}
   ${r.tenuti.length?`<div class="pten">= ${r.tenuti.map(ch).join("")}</div>`:""}${!r.entrati.length&&!r.usciti.length&&!r.tenuti.length?'<div class="small">tutto in liquidit&agrave;</div>':""}</div>
   <span class="small">${r.liquidita?`liquidit&agrave; ${r.liquidita}%`:""}</span></div>`).join("")}
   ${p.rotazioni.length>6?`<button class="ptutte">${tutteRot?"Mostra meno":`Mostra tutte (${p.rotazioni.length})`}</button>`:""}</div>`;}

 function disegna(){const p=P.profili.find(x=>x.id==sel);
  el.innerHTML=`<h2>Portafogli modello</h2><p class="sub">Tre profili di rischio, solo acquisti, controllo ogni mese. Ogni profilo ha una base fissa di mercati e pesi; un mercato resta in portafoglio finch&eacute; il prezzo &egrave; sopra la media a 200 giorni, altrimenti il suo peso va in pausa nella liquidit&agrave; fino a quando torna sopra. Nei test sullo storico questo filtro di trend ha ridotto molto le cadute, mentre il posizionamento COT non migliorava i risultati: per questo il COT &egrave; mostrato accanto a ogni mercato solo come informazione. Regole decise sullo storico fino al 2015, verificate fuori campione dal 2016; la linea live parte dalla prima rotazione pubblicata. Prezzi in dollari di ETF ed ETC equivalenti (il cambio euro/dollaro non &egrave; incluso), costi 0,10% a ogni rotazione.</p>
   <div class="pdate"><span><i></i>Rotazione del <b>${gg(P.rotazione)}</b></span><span>Prossima rotazione: <b>${gg(P.prossima)}</b></span></div>
   <div class="pprof">${P.profili.map(x=>{const o=x.stat.oos||x.stat.totale||{};return `<button class="pcard${x.id==sel?" on":""}" data-p="${x.id}">
    <span class="plv">${[1,2,3].map(i=>`<i class="${i<=LIV[x.id]?"si":""}"></i>`).join("")}</span><b>${x.nome}</b><small>${esc(x.descr)}</small>
    <span class="pnum"><span><em>Rendimento annuo</em>${pc(o.cagr)}</span><span><em>Caduta max</em><span class="down">${pc(Math.min((x.stat.totale||{}).maxdd??0,o.maxdd??0))}</span></span></span></button>`;}).join("")}</div>
   <div class="pgrid"><div class="card pcomp"><div class="ptesta"><div><h3>Da tenere questo mese</h3><span class="small">${p.nome} &middot; ${p.composizione.filter(c=>c.k!="CASH").length} mercati</span></div>${ciambella(p.composizione)}</div>
    ${p.composizione.map(riga).join("")}</div>${contro(p)}</div>
   <h3 class="vft">Andamento del capitale <span class="small">(base 100, scala logaritmica: la stessa percentuale ha la stessa altezza in ogni periodo. Linea turchese = portafoglio, tratteggio = 60/40 di confronto, linea luminosa = live dalla prima rotazione pubblicata)</span></h3>
   <div class="vfswitch pper">${[["tutto","Tutto"],["oos","Fuori campione"],["live","Live"]].map(x=>`<button data-per="${x[0]}" class="${per==x[0]?"on":""}">${x[1]}</button>`).join("")}</div>
   <div class="card pgraf">${curva(p)}</div>
   ${tabella(p)}
   <div class="grid k2 pbasso"><div><h3 class="vft">Ultime rotazioni <span class="small">(+ entrati, &minus; usciti, = rimasti)</span></h3>${rotazioni(p)}</div>
    <div><h3 class="vft">In pausa questo mese <span class="small">(mercati della base sotto la media a 200 giorni: il loro peso &egrave; nella liquidit&agrave; e rientra quando il trend torna positivo)</span></h3>
    <div class="card pescl">${p.esclusi.length?p.esclusi.map(x=>`<div class="pesr"><b>${esc(nomeK(x.k))}</b><span>${x.motivo}</span><em>base ${fx(x.base,0)}% &middot; trend ${pc(x.trend)} &middot; COT ${x.score!=null?sg(x.score,0):"n/d"}</em></div>`).join(""):'<div class="small">Nessun mercato in pausa: tutta la base &egrave; investita.</div>'}</div></div></div>
   <p class="small pnota">Portafogli modello generici a scopo informativo e di studio, non personalizzati: non sono una raccomandazione d'investimento. Scegli sul tuo broker un ETF o ETC equivalente (UCITS) per ogni mercato. Risultati passati e simulati non garantiscono quelli futuri.</p>`;
  el.querySelectorAll(".pcard").forEach(b=>b.onclick=()=>{sel=b.dataset.p;try{localStorage.setItem("ebProfilo",sel);}catch(e){}disegna();});
  el.querySelectorAll(".pper button").forEach(b=>b.onclick=()=>{per=b.dataset.per;disegna();});
  const bt=el.querySelector(".ptutte");if(bt)bt.onclick=()=>{tutteRot=!tutteRot;disegna();};
  suggerimento(el.querySelector(".pgraf"),p);}

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
