
/* ---------- portafogli modello ----------
   Dati da D.port (vedi cot_radar/portafogli.py): tre profili (conservativo, moderato, aggressivo), solo acquisti,
   rotazione il primo giorno di borsa di ogni mese. In alto un selettore a segmenti (Conservativo / Moderato /
   Aggressivo: "stesso motore, rischio diverso") e la CARD PRINCIPALE del profilo: rischio, descrizione, rendimento
   annuo, caduta massima, 10.000 euro dall'inizio dello storico, composizione per classe, le 5 azioni scelte del mese
   e la spiegazione apribile della rotazione. Sotto, per il profilo scelto:
     1. la composizione del mese (ciambella + righe con peso, motivo e strumento da comprare);
     2. il rischio del MESE della rotazione (es. ottobre): la composizione di oggi tenuta in ogni ottobre dello
        storico, con rendimento e caduta massima dentro il mese anno per anno, esempio su 10.000 euro e
        stagionalita' del mese per ogni mercato (nessuna statistica per anno solare);
     3. la curva del capitale: storico, fuori campione (dal 2016) e live (dalla prima rotazione pubblicata),
        con il confronto 60/40; passando il mouse si leggono data e valore;
     4. tabella dei periodi, ultime rotazioni (entrati / usciti / tenuti) e mercati esclusi con il motivo.
   Il profilo scelto resta salvato nel browser (localStorage "ebProfilo"). */
try{(function(){const P=D.port,el=$("port");if(!el)return;
 if(!P||!P.profili||!P.profili.length){el.innerHTML=`<h2>Portafogli modello</h2><p class="sub">Scegli un profilo: stesso motore, rischio diverso. Solo acquisti, controllo una volta al mese.</p>`;return;}
 const CL={azioni:"var(--c1)","azioni singole":"var(--acc)",obbligazioni:"var(--c4)",metalli:"var(--warn)","materie prime":"var(--c2)",crypto:"var(--c5)",liquidita:"var(--c3)"};
 // nomi delle classi per la "composizione per classe" della card principale (ordine fisso di lettura)
 const CLN=[["azioni","Azioni (ETF indici)"],["azioni singole","Azioni scelte"],["obbligazioni","Obbligazioni"],["metalli","Oro e metalli"],["materie prime","Materie prime"],["crypto","Cripto"],["liquidita","Liquidità"]];
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

 function riga(c){const col=CL[c.classe]||"var(--c3)";
  const mot=c.k=="CASH"?"Liquidit&agrave; fissa del profilo + pesi dei mercati in pausa, in Treasury a breve termine."
   :c.k=="AZ"?`${c.titoli&&c.titoli.length?`${fx(c.peso_titolo,1)}% per titolo`:"i 5 titoli arrivano con la prossima rotazione"} &middot; S&amp;P 500 ${pc(c.trend)} sopra la media a 200 giorni (filtro di mercato)`
   :`trend ${pc(c.trend)} sopra la media a 200 giorni · volatilit&agrave; ${fx(c.vol,0)}% · COT ${c.score!=null?sg(c.score,0):"n/d"} (informativo)`;
  const tit=c.k=="AZ"&&c.titoli&&c.titoli.length?`<span class="ptit">${c.titoli.map(x=>`<button class="pchip clic" data-az="${esc(x.t)}" title="${esc(x.n)}">${esc(x.t)} <small>${esc(x.n.length>22?x.n.slice(0,21)+"…":x.n)}</small></button>`).join("")}</span>`:"";
  return `<div class="prow"><i style="background:${col}"></i><div class="pnome"><b>${esc(c.nome)}</b><span>${esc(c.strumento)}</span><em>${mot}</em>${tit}</div>
   <div class="ppeso"><b>${fx(c.peso,1)}%</b><span class="pbar"><i style="width:${Math.min(100,c.peso*2.5)}%;background:${col}"></i></span></div></div>`;}

 // --- rischio del MESE della rotazione: la composizione di oggi tenuta nello stesso mese di ogni anno
 function contro(p){const m=p.mese,s=p.stat.totale||{},o=p.stat.oos||{},ddTot=Math.min(s.maxdd??0,o.maxdd??0);
  if(!m)return `<div class="card pcontro"><h3>Il rischio del mese</h3><div class="small">Storico non ancora sufficiente.</div></div>`;
  const Mese=m.mese[0].toUpperCase()+m.mese.slice(1),peg=m.anni.reduce((a,x)=>x.dd<a.dd?x:a,m.anni[0]);
  const oltre=-m.dd_max>p.dd_rif;
  // barre per anno: altezza = rendimento del mese, puntino = caduta massima dentro il mese
  const W=420,H=120,mx=Math.max(4,...m.anni.map(x=>Math.max(Math.abs(x.r),Math.abs(x.dd)))),Y=v=>H/2-v/mx*(H/2-6),bw=W/m.anni.length;
  const bar=m.anni.map((x,i)=>`<g class="pmb"><rect x="${(i*bw+1).toFixed(1)}" width="${Math.max(1,bw-2).toFixed(1)}" y="${Math.min(Y(0),Y(x.r)).toFixed(1)}" height="${Math.max(1,Math.abs(Y(x.r)-Y(0))).toFixed(1)}" class="${x.r>=0?"su":"giu"}"/>
   <circle cx="${(i*bw+bw/2).toFixed(1)}" cy="${Y(x.dd).toFixed(1)}" r="2"/><rect x="${(i*bw).toFixed(1)}" width="${bw.toFixed(1)}" y="0" height="${H}" class="pmh"><title>${Mese} ${x.a}: ${pc(x.r)} · caduta nel mese ${pc(x.dd)}</title></rect></g>`).join("");
  return `<div class="card pcontro"><h3>Il rischio di ${m.mese}</h3>
   <div class="small">Questa composizione tenuta in ogni ${m.mese} dal ${m.anni[0].a} (${m.n} anni), dal primo giorno di borsa al primo del mese dopo.</div>
   <div class="pdd"><span>Caduta massima dentro il mese</span><b>${pc(m.dd_max)}</b><em class="${oltre?"pko":"pok"}">${m.mese} ${peg.a} &middot; ${oltre?"oltre":"entro"} il riferimento del profilo (&minus;${p.dd_rif}%)</em></div>
   <div class="pesempio">Con <b>10.000 €</b>, ${/^[aeiou]/.test(m.mese)?"nell'":"nel "}${m.mese} peggiore il conto sarebbe sceso a <b>${eur(10000*(1+m.dd_max/100))}</b> nel corso del mese.</div>
   <svg viewBox="0 0 ${W} ${H}" class="pmesi" preserveAspectRatio="none" role="img" aria-label="Rendimento di ${m.mese} anno per anno"><line x1="0" x2="${W}" y1="${Y(0)}" y2="${Y(0)}" class="pm0"/>${bar}</svg>
   <div class="pmasse"><span>${m.anni[0].a}</span><span><i class="su"></i>rendimento del mese <i class="pt"></i>caduta nel mese</span><span>${m.anni[m.anni.length-1].a}</span></div>
   <div class="pmini"><div><span>${Mese} peggiore</span><b>${pc(m.peggiore[1])}</b><em>${m.peggiore[0]}</em></div>
    <div><span>${Mese} medio</span><b>${pc(m.media)}</b><em>su ${m.n} anni</em></div>
    <div><span>Anni positivi</span><b>${m.positivi} su ${m.n}</b><em>${Math.round(100*m.positivi/m.n)}%</em></div>
    <div><span>Caduta del metodo</span><b>${pc(ddTot)}</b><em>tutto lo storico</em></div></div>
   ${m.mercati.length?`<div class="pstag"><span class="small">Stagionalit&agrave; di ${m.mese} per mercato (informativa):</span>${m.mercati.map(x=>`<span class="pchip ${x.media>=0?"pos":"neg"}" title="${x.n} anni">${esc(nomeK(x.k))} <b>${pc(x.media)}</b> &middot; ${x.pos}% positivi</span>`).join("")}</div>`:""}</div>`;}

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
    <div><em>Caduta massima</em><b class="down">${pc(t.maxdd)}</b><span>il momento peggiore</span></div>
    <div><em>10.000 € nel ${anno}</em><b>${eur(finale)}</b><span>valore di oggi</span></div>
    <div><em>Mesi positivi</em><b>${t.mesi_pos??"n/d"}%</b><span>su tutti i mesi</span></div></div>
   <div class="phcomp"><h4>Composizione del mese</h4>${CLN.filter(x=>cl[x[0]]).map(x=>`<div class="phbar"><span>${x[1]}</span><b>${fx(cl[x[0]],1)}%</b><i><s style="width:${Math.min(100,cl[x[0]])}%;background:${CL[x[0]]}"></s></i></div>`).join("")}</div>
   <div class="phaz"><h4>Le 5 azioni del mese <span class="small">(${p.az}% del portafoglio${az&&az.titoli&&az.titoli.length?`, ${fx(az.peso_titolo,1)}% ciascuna`:""})</span></h4>
    ${pausa?`<div class="small">${esc(pausa.motivo)}.</div>`:az&&az.titoli&&az.titoli.length?`<div class="ptit">${az.titoli.map(x=>`<button class="pchip clic" data-az="${esc(x.t)}" title="Apri nell'Azionario">${esc(x.t)} <small>${esc(x.n)}</small></button>`).join("")}</div>`
     :`<div class="small">I titoli vengono scelti l'ultimo giorno di borsa del mese, dopo la chiusura, e entrano con la rotazione del ${gg(P.prossima)}.</div>`}</div>
   <details class="phcome"><summary>Come funziona la rotazione di ogni mese</summary><ol>
    <li><b>Primo giorno di borsa del mese</b>: per ogni ETF della base si controlla il trend. Se il prezzo &egrave; sotto la media a 200 giorni il suo peso va in pausa nella liquidit&agrave;.</li>
    <li><b>Azioni scelte (${p.az}%)</b>: i 5 titoli dell'Azionario con il punteggio pi&ugrave; alto che hanno trend positivo (sopra la media a 200 giorni, 3 e 12 mesi in guadagno), non pi&ugrave; del 15% sotto il massimo dell'anno e il mese che entra positivo in almeno il 60% degli anni (minimo 8). Al massimo uno per settore, a pari peso.</li>
    <li><b>Filtro di mercato</b>: se l'S&amp;P 500 &egrave; sotto la sua media a 200 giorni tutta la quota azioni va in liquidit&agrave; (nel 2008, senza filtro, questa quota perdeva il 55%).</li>
    <li><b>Durante il mese non si tocca nulla</b>. Al mese dopo chi resta tra i migliori rimane, chi esce si vende, chi entra si compra. Costi inclusi: 0,10% sugli ETF, 0,20% sulle azioni.</li>
    <li><b>Registro</b>: ogni rotazione e ogni scelta di titoli vengono salvate e non si modificano pi&ugrave;: la linea live non si pu&ograve; aggiustare dopo.</li></ol>
    <p class="small">${esc((P.azioni||{}).nota||"")} Storico fino al 2015, fuori campione dal 2016. Prezzi in dollari di ETF ed ETC equivalenti e azioni in valuta locale (cambi non inclusi).</p></details></div>`;}

 function disegna(){const p=P.profili.find(x=>x.id==sel);
  el.innerHTML=`<h2>Portafogli modello</h2><p class="sub">Tre profili di rischio, solo acquisti, controllo ogni mese. Ogni profilo ha una base fissa di mercati e pesi; un mercato resta in portafoglio finch&eacute; il prezzo &egrave; sopra la media a 200 giorni, altrimenti il suo peso va in pausa nella liquidit&agrave; fino a quando torna sopra. Nei test sullo storico questo filtro di trend ha ridotto molto le cadute, mentre il posizionamento COT non migliorava i risultati: per questo il COT &egrave; mostrato accanto a ogni mercato solo come informazione. Regole decise sullo storico fino al 2015, verificate fuori campione dal 2016; la linea live parte dalla prima rotazione pubblicata. Il rischio si legge mese per mese: a ogni rotazione la scheda mostra come si &egrave; comportata la composizione del mese nello stesso mese di tutti gli anni dello storico. Prezzi in dollari di ETF ed ETC equivalenti (il cambio euro/dollaro non &egrave; incluso), costi 0,10% a ogni rotazione.</p>
   <div class="pdate"><span><i></i>Rotazione del <b>${gg(P.rotazione)}</b></span><span>Prossima rotazione: <b>${gg(P.prossima)}</b></span></div>
   <div class="pseg" role="tablist" aria-label="Scegli il portafoglio">${P.profili.map(x=>`<button role="tab" aria-selected="${x.id==sel}" class="${x.id==sel?"on":""}" data-p="${x.id}">${x.nome}</button>`).join("")}</div>
   ${hero(p)}
   <div class="pgrid"><div class="card pcomp"><div class="ptesta"><div><h3>Da tenere questo mese</h3><span class="small">${p.nome} &middot; ${p.composizione.filter(c=>c.k!="CASH").length} mercati</span></div>${ciambella(p.composizione)}</div>
    ${p.composizione.map(riga).join("")}</div>${contro(p)}</div>
   <h3 class="vft">Andamento del capitale <span class="small">(base 100, scala logaritmica: la stessa percentuale ha la stessa altezza in ogni periodo. Linea turchese = portafoglio, tratteggio = 60/40 di confronto, linea luminosa = live dalla prima rotazione pubblicata)</span></h3>
   <div class="vfswitch pper">${[["tutto","Tutto"],["oos","Fuori campione"],["live","Live"]].map(x=>`<button data-per="${x[0]}" class="${per==x[0]?"on":""}">${x[1]}</button>`).join("")}</div>
   <div class="card pgraf">${curva(p)}</div>
   ${tabella(p)}
   <div class="grid k2 pbasso"><div><h3 class="vft">Ultime rotazioni <span class="small">(+ entrati, &minus; usciti, = rimasti)</span></h3>${rotazioni(p)}</div>
    <div><h3 class="vft">In pausa questo mese <span class="small">(mercati della base sotto la media a 200 giorni: il loro peso &egrave; nella liquidit&agrave; e rientra quando il trend torna positivo)</span></h3>
    <div class="card pescl">${p.esclusi.length?p.esclusi.map(x=>`<div class="pesr"><b>${esc(nomeK(x.k))}</b><span>${x.motivo}</span><em>base ${fx(x.base,0)}% &middot; trend ${pc(x.trend)} &middot; COT ${x.score!=null?sg(x.score,0):"n/d"}</em></div>`).join(""):'<div class="small">Nessun mercato in pausa: tutta la base &egrave; investita.</div>'}</div></div></div>`;
  el.querySelectorAll(".pseg button").forEach(b=>b.onclick=()=>{sel=b.dataset.p;try{localStorage.setItem("ebProfilo",sel);}catch(e){}disegna();});
  // clic su un titolo delle azioni scelte: apre la sua scheda nell'Azionario (azioni.js)
  el.querySelectorAll("[data-az]").forEach(b=>b.onclick=()=>{if(window.ebApriTitolo)window.ebApriTitolo(b.dataset.az);});
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
