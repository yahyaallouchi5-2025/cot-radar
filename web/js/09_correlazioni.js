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


/* ---------- correlazioni dei PREZZI (D.corr_px, da cot_radar/correlazioni.py) ----------
   Vista predefinita della scheda: rendimenti GIORNALIERI di indici, settori USA, obbligazioni, metalli, energia,
   agricole, cripto e dollaro. +1 = salgono e scendono insieme, -1 = quando uno sale l'altro scende.
   Tre liste (insieme / al contrario / stanno cambiando), il legame di ogni strumento con l'S&P 500 con la sua
   mini linea degli ultimi ~3 anni, e la mappa di calore per gruppo o per singolo strumento.
   Il pulsante "Flussi COT" mostra la vista settimanale degli speculatori (codice qui sopra). */
try{(function(){const C=D.corr_px,el=$("cpx");if(!el)return;
 // switch tra le due viste della scheda
 document.querySelectorAll(".cvista button").forEach(b=>b.onclick=()=>{
  document.querySelectorAll(".cvista button").forEach(x=>x.classList.toggle("on",x===b));
  $("cpx").hidden=b.dataset.cv!="px";$("ccot").hidden=b.dataset.cv!="cot";});
 if(!C||!C.asset||!C.asset.length){el.innerHTML=`<div class="card small" style="padding:18px 20px">I prezzi non sono disponibili in questo aggiornamento: la vista torna al prossimo giro. Intanto c'&egrave; la vista dei flussi COT.</div>`;return;}
 let fin="m63",vista="gruppi";
 const A=C.asset,idx={};A.forEach((a,i)=>idx[a.k]=i);
 const nome=k=>idx[k]!=null?A[idx[k]].nome:k,grp=k=>idx[k]!=null?A[idx[k]].g:"";
 const GC={"Indici":"var(--c1)","Settori USA":"var(--acc)","Obbligazioni":"var(--c4)","Metalli":"var(--warn)","Energia":"var(--c2)","Agricole":"#a3e635","Cripto":"var(--c5)","Dollaro":"var(--c3)"};
 const cv=v=>v==null?"n/d":(v>0?"+":v<0?"&minus;":"")+fx(Math.abs(v),2);
 const sfondo=v=>{if(v==null)return"transparent";const a=Math.min(1,Math.abs(v));return v>0?`rgba(34,163,90,${a})`:`rgba(224,82,77,${a})`;};
 const pall=g=>`<i class="cpall" style="background:${GC[g]||"var(--c3)"}"></i>`;
 // barra divergente: centro = 0, verso destra verde (insieme), verso sinistra rosso (al contrario)
 const barra=v=>v==null?`<span class="cbar"></span>`:`<span class="cbar"><s class="${v>=0?"su":"giu"}" style="${v>=0?"left:50%":"right:50%"};width:${Math.min(50,Math.abs(v)*50)}%"></s></span>`;
 // mini linea della correlazione mobile a 3 mesi con l'S&P 500 (linea dello zero tratteggiata)
 function mini(s){const v=(s||[]).filter(x=>x!=null);if(v.length<3)return "";const W=120,H=30,n=s.length;
  const Y=x=>(H/2-x*(H/2-2)).toFixed(1),X=i=>(i/(n-1)*W).toFixed(1);let d="",su=false;
  s.forEach((x,i)=>{if(x==null){su=false;return;}d+=(su?"L":"M")+X(i)+" "+Y(x);su=true;});
  const u=v[v.length-1];
  return `<svg viewBox="0 0 ${W} ${H}" class="cmini" preserveAspectRatio="none" aria-hidden="true"><line x1="0" x2="${W}" y1="${H/2}" y2="${H/2}" class="c0"/><path d="${d}" class="${u>=0?"su":"giu"}"/></svg>`;}
 function coppia(x,tipo){const del=tipo=="cambio";
  // i due nomi su due righe (il secondo preceduto dal simbolo: frecce parallele = insieme, opposte = al contrario)
  return `<div class="crow"><span class="cpair"><span><span class="ce" aria-hidden="true" style="visibility:hidden">&#8644;</span>${pall(grp(x.a))}<b>${esc(nome(x.a))}</b></span><span><span class="ce">${tipo=="giu"?"&#8646;":"&#8644;"}</span>${pall(grp(x.b))}<b>${esc(nome(x.b))}</b></span></span>
   <span class="cval ${x.c63>=0?"up":"down"}">${cv(x.c63)}</span>${barra(x.c63)}
   <em>${del?`un anno fa ${cv(x.c252)} &rarr; oggi ${cv(x.c63)}`:`ultimo anno ${cv(x.c252)}`}</em></div>`;}
 function heat(){const g=vista=="gruppi",K=g?C.gruppi:A.map(a=>a.k),M=g?C["g"+fin]:C[fin];
  const et=k=>g?k:nome(k);
  return `<table class="heat cheat${g?" cgr":""}"><tr><th></th>${K.map(k=>`<th title="${esc(et(k))}">${esc(et(k))}</th>`).join("")}</tr>${K.map((r,i)=>`<tr><th class="r">${g?pall(r):pall(grp(r))}${esc(et(r))}</th>${K.map((c,j)=>{const v=M[i][j];const diag=!g&&i==j;
   return `<td title="${esc(et(r))} / ${esc(et(c))}: ${diag?"":cv(v)}" style="background:${diag?"var(--soft)":sfondo(v)};color:${v!=null&&Math.abs(v)>.55?"#fff":"var(--ink)"}">${diag||v==null?"":cv(v)}</td>`;}).join("")}</tr>`).join("")}</table>`;}
 function disegna(){const op=C.opposti[0],ins=C.insieme[0];
  const sp=[...C.spx].sort((a,b)=>(b[fin=="m63"?"c63":"c252"]??-2)-(a[fin=="m63"?"c63":"c252"]??-2));
  el.innerHTML=`<div class="azbar"><span class="azdata"><i></i>Prezzi al <b>${fd(C.aggiornato)}</b></span>
    <div class="vfswitch cfin">${[["m63","3 mesi"],["m252","1 anno"]].map(x=>`<button data-f="${x[0]}" class="${fin==x[0]?"on":""}">${x[1]}</button>`).join("")}</div>
    <div class="filters cvis">${[["gruppi","Per gruppo"],["tutti","Per strumento"]].map(x=>`<button data-v="${x[0]}" class="${vista==x[0]?"on":""}">${x[1]}</button>`).join("")}</div></div>
   ${op?`<div class="card cnota"><b>In breve.</b> Oggi il legame contrario pi&ugrave; forte &egrave; tra <b>${esc(nome(op.a))}</b> e <b>${esc(nome(op.b))}</b> (${cv(op.c63)}): quando uno sale, l'altro tende a scendere. Il pi&ugrave; stretto tra mondi diversi &egrave; <b>${esc(nome(ins.a))}</b> con <b>${esc(nome(ins.b))}</b> (${cv(ins.c63)}). Le correlazioni cambiano nel tempo: guarda la colonna "stanno cambiando".</div>`:""}
   <div class="cgrid"><div class="card"><h3>Si muovono insieme</h3><span class="small">ultimi 3 mesi, tra mondi diversi</span>${C.insieme.map(x=>coppia(x,"su")).join("")}</div>
    <div class="card"><h3>Si muovono al contrario</h3><span class="small">quando uno sale l'altro scende</span>${C.opposti.map(x=>coppia(x,"giu")).join("")}</div>
    <div class="card"><h3>Stanno cambiando</h3><span class="small">legami di oggi diversi dall'ultimo anno</span>${C.cambiati.map(x=>coppia(x,"cambio")).join("")}</div></div>
   <h3 class="vft">Rispetto all'S&amp;P 500 <span class="small">(${fin=="m63"?"ultimi 3 mesi":"ultimo anno"} &middot; la mini linea mostra il legame a 3 mesi negli ultimi ~3 anni: sopra la riga tratteggiata si muove con la borsa USA, sotto va al contrario)</span></h3>
   <div class="card cspx">${sp.map(x=>{const v=x[fin=="m63"?"c63":"c252"];return `<div class="csr"><span class="cnomi">${pall(grp(x.k))}<b>${esc(nome(x.k))}</b><small>${esc(grp(x.k))}</small></span>${barra(v)}<span class="cval ${v>=0?"up":"down"}">${cv(v)}</span>${mini(x.serie)}</div>`;}).join("")}</div>
   <h3 class="vft">Mappa di calore <span class="small">(${vista=="gruppi"?"media tra gli strumenti di ogni gruppo":"ogni strumento con ogni altro"}, ${fin=="m63"?"ultimi 3 mesi":"ultimo anno"}: verde = insieme, rosso = al contrario)</span></h3>
   <div class="tablewrap" style="padding:16px">${heat()}</div>
   <div class="cleg">${C.gruppi.map(g=>`<span>${pall(g)}${esc(g)}</span>`).join("")}</div>`;
  el.querySelectorAll(".cfin button").forEach(b=>b.onclick=()=>{fin=b.dataset.f;disegna();});
  el.querySelectorAll(".cvis button").forEach(b=>b.onclick=()=>{vista=b.dataset.v;disegna();});}
 disegna();
})();}catch(e){fail('Correlazioni dei prezzi','corr',e);}
