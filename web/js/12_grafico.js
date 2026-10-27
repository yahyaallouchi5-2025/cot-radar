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
 .catch(e=>{box.innerHTML=`<div class="tvmsg">${esc(e.message)}. <a href="https://www.tradingview.com/chart/?symbol=${encodeURIComponent(info.sym)}" target="_blank" rel="noopener">Apri il grafico su TradingView</a></div>`;console.error("[BoardEdge] grafico:",e);});}
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
 if(st)parti.push(`<b>Stagionalit&agrave;:</b> ${st.robusto?`${st.score>0?"salito":"sceso"} ${st.score>0?st.su:st.n-st.su}/${st.n} anni nelle 4 sett. dal COT (mediana ${st.med>=0?"+":""}${fx(st.med)}%) &rarr; <b style="color:${Math.sign(st.score)==Math.sign(sc)?"var(--sb)":"var(--ss)"}">${Math.sign(st.score)==Math.sign(sc)?"favorevole":"non favorevole"}</b>${st.adj?` (${st.adj>0?"+":""}${fx(st.adj,0)})`:""}`:`<b style="color:var(--warn)">neutra</b> (nessuna tendenza costante)`}`);
 const e=p?p.affid:(D.assets[k]||{}).affid;
 if(e)parti.push(`<b>Storico:</b> <b style="color:${e.pochi?"var(--ink)":e.hit>=60?"var(--sb)":e.hit<50?"var(--ss)":"var(--ink)"}">${e.hit}%</b> su ${e.n} segnali <span class="lungo">(resa media ${e.resa>=0?"+":""}${fx(e.resa)}% a 4 sett.)</span>`);
 return parti.length?`<div class="riga tre">${parti.map(x=>`<span>${x}</span>`).join("")}</div>`:"";}
/* RIEPILOGO SEMPLICE sotto il grafico (richiudibile): una riga riassuntiva sempre visibile e, aprendola,
   poche frasi in italiano semplice. Niente doppioni: i numeri tecnici restano nelle schede di approfondimento.
   Ordine: speculatori -> Commercials -> contratti aperti -> notizie -> storico -> prossima settimana (stagionalita'). */
function lettura(spec,f,p,k,inv){
 const pc1=x=>`${x>=0?"+":"&minus;"}${fx(Math.abs(x),1)}%`,verde="var(--sb)",rosso="var(--ss)";
 const t=tre(f),[ud,uv]=f[f.length-1],ven=new Date(ud);ven.setDate(ven.getDate()+3);
 const o=p||D.assets[k]||{},nome=p?p.pair:(o.name||k),gambe=p?[p.base,p.quote]:[k];
 const n3=Math.max(t.u.filter(x=>x[1]>0).length,t.u.filter(x=>x[1]<0).length),compra=t.tot>=0;
 // --- speculatori
 const dir=n3<2?"nessuna direzione chiara":`${compra?"comprano":"vendono"} (${n3==3?"3 settimane su 3":"2 su 3"}, ${pc1(t.tot)})`;
 const pos=p?[netto(p.base),netto(p.quote)].filter(Boolean).join(" &middot; "):netto(k,inv);
 const righe=[`<b>Speculatori</b> (grandi fondi): nell'ultima settimana hanno <b style="color:${uv>=0?verde:rosso}">${uv>=0?"comprato":"venduto"}</b> (${pc1(uv)} dei contratti aperti).
  Nelle ultime 3 settimane ${n3<2?"la direzione &egrave; mista":`hanno ${compra?"comprato":"venduto"} ${n3==3?"tutte e 3 le settimane":"2 settimane su 3"} (<b style="color:${compra?verde:rosso}">${pc1(t.tot)}</b> in totale)`}.
  ${pos?`Oggi: ${pos}.`:""} <span class="small">Dato di marted&igrave; ${fd(ud)}, uscito venerd&igrave; ${fd(ven.toISOString().slice(0,10))}.</span>`];
 // --- Commercials (chi produce o usa davvero il sottostante e si copre)
 const acc=o.comm_acc,cm=gambe.map(g=>{const c=(D.assets[g]||{}).comm;return c&&(c.idx>=80||c.idx<=20)?`molto in ${c.idx>=80?"acquisto":"vendita"} su ${esc(g)}`:null;}).filter(Boolean);
 righe.push(`<b>Commercials</b> (produttori e banche che si coprono): ${cm.length?cm.join(" &middot; ")+(acc?` &rarr; <b style="color:${acc=="conferma"?verde:rosso}">${acc=="conferma"?"sono dalla parte del segnale":"vanno contro il segnale"}</b>`:""):"nella norma, nessuna indicazione"}.`);
 // --- contratti aperti
 const oi=gambe.map(g=>{const x=(D.assets[g]||{}).oi4;return x&&Math.abs(x.d_oi)>=2?`${esc(g)} ${pc1(x.d_oi)} (${esc(x.txt)})`:null;}).filter(Boolean);
 if(oi.length)righe.push(`<b>Contratti aperti</b> nelle ultime 4 settimane: ${oi.join(" &middot; ")}.`);
 // --- notizie (solo se cambiano qualcosa)
 const nw=p&&p.news;if(nw&&nw.effetto!="neutro"){const ev=[...(nw.oggi||[]),...(nw.eventi||[]).map(x=>x.nome)].filter(Boolean);
  righe.push(`<b>Notizie</b>: ${ev.length?esc(ev.join(", "))+" &rarr; ":""}<b style="color:${nw.effetto=="rafforza"?verde:rosso}">${nw.effetto=="rafforza"?"rafforzano il segnale":"vanno contro il segnale"}</b>.`);}
 // --- storico del segnale
 const e=o.affid;if(e)righe.push(`<b>Storico</b>: su ${e.n} segnali simili in passato ha funzionato <b style="color:${e.pochi?"var(--ink)":e.hit>=60?verde:e.hit<50?rosso:"var(--ink)"}">${e.hit}% delle volte</b> (resa media ${pc1(e.resa)} dopo 4 settimane)${e.pochi?", pochi casi: da prendere con le pinze":""}.`);
 // --- stagionalita' (v6.18): la settimana parte dal VENERDI' DI USCITA DEL COT (s1.giorno), cosi' segue il ciclo
 //     settimanale del segnale. Giudizio rispetto al segnale: FAVOREVOLE (stessa direzione), NON FAVOREVOLE
 //     (direzione opposta), NEUTRA (nessuna tendenza costante negli anni passati). Colori: verde / rosso / ambra.
 const s1=o.stag1s,st4=o.stag,vs=(o.label||"").includes("BUY")?1:(o.label||"").includes("SELL")?-1:0;
 const giudizio=(robusto,m)=>!robusto?["neutra","var(--warn)"]:!vs?[m>0?"tende al rialzo":"tende al ribasso",m>0?verde:rosso]
  :Math.sign(m)==vs?["favorevole",verde]:["non favorevole",rosso];
 const g1=s1?giudizio(s1.robusto,s1.med):null;
 if(s1){const giu=s1.n-s1.su,g0=s1.giorno?new Date(s1.giorno):null,g7=g0?new Date(g0.getTime()+7*864e5):null;
  let stg=`<b>Stagionalit&agrave; della settimana</b>${g0?` (da venerd&igrave; ${fd(s1.giorno)}, uscita del COT, a venerd&igrave; ${fd(g7.toISOString().slice(0,10))})`:""}: dal ${s1.dal} ${esc(nome)} &egrave; salito in <b>${s1.su} anni su ${s1.n}</b> e sceso in ${giu}${s1.robusto?`, variazione tipica ${pc1(s1.med)}`:""} &rarr; <b style="color:${g1[1]}">${g1[0].toUpperCase()}</b>${vs?` al segnale ${esc(o.label)}`:""}${s1.robusto?"":" (quasi testa o croce)"}.`;
  if(st4){const g4=giudizio(st4.robusto,st4.score);stg+=` Sulle 4 settimane: <b style="color:${g4[1]}">${g4[0]}</b>${st4.robusto?` (${st4.score>0?st4.su:st4.n-st4.su} anni su ${st4.n})`:""}.`;}
  stg+=` <a href="#stag" data-vai="stag">Approfondisci nella scheda Stagionalit&agrave;</a>`;righe.push(stg);}
 // --- riga riassuntiva (sempre visibile)
 const pezzi=[`Speculatori: <b style="color:${n3<2?"var(--ink)":compra?verde:rosso}">${dir}</b>`];
 if(acc)pezzi.push(`Commercials: <b style="color:${acc=="conferma"?verde:rosso}">${acc=="conferma"?"a favore":"contrari"}</b>`);
 if(nw&&nw.effetto=="penalizza")pezzi.push(`<b style="color:${rosso}">notizia contraria</b>`);
 if(g1)pezzi.push(`Stagionalit&agrave;: <b style="color:${g1[1]}">${g1[0]}</b>`);
 return `<button class="sintesi" id="cotinfo" title="Mostra / nascondi il riepilogo"><b>Riepilogo:</b> ${pezzi.join(" &middot; ")} <span class="freccia">&#9662;</span></button>
  <div class="cotinfo">${righe.map(r=>`<p>${r}</p>`).join("")}</div>`;}
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
 box.innerHTML=lettura(spec,f,p,k,inv)+`
  <button class="sintesi" id="cotsint" title="Mostra / nascondi le barre settimanali">${sintesiFlussi(f)} <span class="freccia">&#9662;</span></button>
  <div class="barre"><svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img" aria-label="Flussi COT settimanali">${fascia}<line x1="0" x2="${W}" y1="${H/2}" y2="${H/2}" stroke="var(--line)"/>${barre}</svg>
  <div class="assi"><span>${fd(f[0][0])}</span><span class="lungo">verde = comprano &middot; rosso = vendono${p?" (base contro quotata)":""} &middot; fascia = ultime 3 settimane</span><span>${fd(ud)}</span></div></div>`;
 // barre aperte/chiuse: su telefono partono chiuse (piu' spazio al grafico); la scelta resta salvata
 const pan=$("tvpannello");let chiuse=matchMedia("(max-width:600px)").matches;
 try{const v=localStorage.getItem("cotBarre");if(v)chiuse=v=="chiuse";}catch(e){}
 pan.classList.toggle("barrechiuse",chiuse);
 let infoChiuse=true;try{const v=localStorage.getItem("cotInfo");if(v)infoChiuse=v=="chiuse";}catch(e){}
 pan.classList.toggle("infochiuse",infoChiuse);
 $("cotinfo").onclick=()=>{const c=pan.classList.toggle("infochiuse");try{localStorage.setItem("cotInfo",c?"chiuse":"aperte");}catch(e){}};
 /* i link [data-vai] (es. "Approfondisci nella scheda Stagionalita'") sono gestiti da un unico ascoltatore globale (vedi navigazione) */
 $("cotsint").onclick=()=>{const c=pan.classList.toggle("barrechiuse");try{localStorage.setItem("cotBarre",c?"chiuse":"aperte");}catch(e){}};
 }catch(e){box.innerHTML="";console.error("[BoardEdge] pannello COT:",e);}}   // se si rompe sparisce il pannello, non il grafico
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
/* AVVISO NOTIZIA nel pannello del grafico: compare SOLO quando una notizia (es. CPI, Fed) va contro il
   segnale, perche' cambia il "quando" entrare. Nessun voto di affidabilita' (tolto in v6.16). */
function avvisoNotizia(spec){const[t,id]=spec.split(":");if(t!="p")return "";const p=D.pairs.find(x=>x.pair==id);
 if(!p||!p.news||p.news.effetto!="penalizza"||p.label=="NEUTRO")return "";
 const ev=[...(p.news.oggi||[]),...(p.news.eventi||[]).map(x=>x.nome)].filter(Boolean);
 return `<span class="badge" style="--bc:var(--ss)" title="${esc("Notizia contraria al segnale: "+(ev.join(", ")||"vedi riepilogo"))}">NOTIZIA CONTRARIA</span>`;}
function apriGrafico(spec){TV.spec=spec;const info=tvInfo(spec),m=$("tvmodal");disegnaCOT(spec);
 $("tvtitolo").innerHTML=`<span class="pair">${esc(info.nome)}</span> ${info.label?badge(info.label):""} ${avvisoNotizia(spec)} <span class="small">punteggio ${fmt(info.score)}</span>`;
 $("tvsotto").innerHTML=`${esc(info.sotto)}`+   /* simbolo TradingView tolto: si vede gia' nel grafico */(info.inv?` &middot; <b style="color:var(--warn)">grafico quotato al contrario: BUY sul segnale = grafico che SCENDE</b>`:"");
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

