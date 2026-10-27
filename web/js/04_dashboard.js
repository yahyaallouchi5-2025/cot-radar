/* ---------- segnali ----------
   Riepilogo in alto, settori, schede delle coppie (card) e degli altri strumenti (acard).
   mtag() decide l'etichetta "Mercato conferma / contro / gia' scontato" confrontando i segni di COT e Mercato. */
try{

(function kpis(){const strong=D.pairs.filter(p=>p.label.startsWith("STRONG")).length+Object.values(D.assets).filter(a=>a.key!="USD"&&a.group!="Valute"&&a.label.startsWith("STRONG")).length;
 const act=D.pairs.filter(p=>p.label!="NEUTRO").length+Object.values(D.assets).filter(a=>a.key!="USD"&&a.group!="Valute"&&a.label!="NEUTRO").length;
 const r=D.market?D.market.risk:null,rl=r==null?"n/d":r>=30?"FAVOREVOLE":r<=-30?"SFAVOREVOLE":"NEUTRO";   // in maiuscolo, come i verdetti delle card
 const po=D.port;                                        // portafogli modello (al posto del vecchio riquadro mutui)
 const cot=D.sources[0];
 $("kpis").innerHTML=`<div class="card kpi"><h3>Segnali attivi</h3><div class="big">${act}</div><div class="note">di cui <b>${strong}</b> STRONG</div></div>
 <div class="card kpi"><h3>Clima di rischio</h3><div class="big" style="color:${r>=30?'var(--b)':r<=-30?'var(--s)':'var(--ink)'}">${rl}</div><div class="note">VIX, spread e rendimenti reali, 4 settimane</div></div>
 <div class="card kpi clic" data-vai="port" title="Apri i Portafogli"><h3>Prossima rotazione</h3><div class="big" style="font-size:20px;margin-top:12px">${po&&po.prossima?fd(po.prossima):"n/d"}</div><div class="note">portafogli modello &middot; 5 azioni scelte</div></div>
 <div class="card kpi"><h3>Prossimo COT</h3><div class="big" style="font-size:20px;margin-top:12px">${cot.next}</div><div class="note">dati al ${cot.last}</div></div>`;})();

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
 function monta(){if(!track)return;
  if(matchMedia("(prefers-reduced-motion: reduce)").matches){track.innerHTML=base;nastro.classList.add("fermo");return;}
  track.style.animation="none";track.innerHTML=`<span class="evmeta">${base}</span>`;
  const meta=track.firstChild,W=nastro.clientWidth||800;let n=1;
  while(meta.scrollWidth<W&&n<30){meta.insertAdjacentHTML("beforeend",base);n++;}   // riempi la larghezza
  track.insertAdjacentHTML("beforeend",`<span class="evmeta" aria-hidden="true">${meta.innerHTML}</span>`);
  const L=meta.getBoundingClientRect().width;
  track.style.setProperty("--evdur",Math.max(12,L/VEL).toFixed(1)+"s");void track.offsetWidth;track.style.animation="";}
 monta();let rt=0;addEventListener("resize",()=>{clearTimeout(rt);rt=setTimeout(monta,250);});
 // tocco su telefono: ferma / riparte
 if(nastro)nastro.addEventListener("click",e=>{if(!e.target.closest("a"))nastro.classList.toggle("pausa");});
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

