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
 // R = margine a destra riservato al valore finale: l'etichetta sta ACCANTO all'ultimo punto, in una "pillola"
 // scura, cosi' la linea non ci passa mai sopra (prima era sopra il punto e la linea la attraversava).
 function percorso(pp){if(!pp||!pp.some(x=>x!=null))return "";const W=600,H=150,P=24,R=78,v=pp.map(x=>x??0);
  const lo=Math.min(0,...v),hi=Math.max(0,...v),sc=y=>H-P-(y-lo)/((hi-lo)||1)*(H-2*P),xs=i=>P+i*(W-P-R)/(v.length-1);
  const col=v[v.length-1]>=0?"var(--b)":"var(--s)",xf=xs(v.length-1),yf=sc(v[v.length-1]),txt=pc(v[v.length-1]);
  return `<svg class="chart" viewBox="0 0 ${W} ${H}"><line x1="${P}" x2="${xf}" y1="${sc(0)}" y2="${sc(0)}" stroke="var(--line)"/>
  <polyline fill="none" stroke="${col}" stroke-width="3" points="${v.map((y,i)=>xs(i)+","+sc(y)).join(" ")}"/>
  ${v.map((y,i)=>`<circle cx="${xs(i)}" cy="${sc(y)}" r="3.5" fill="${col}"/><text x="${xs(i)}" y="${H-4}" text-anchor="middle" font-size="11" fill="var(--mute)">${i?"+"+i+"s":"oggi"}</text>`).join("")}
  <rect x="${xf+9}" y="${yf-11}" width="${txt.length*7.4+12}" height="22" rx="11" fill="var(--card2)" stroke="${col}" stroke-opacity=".55"/>
  <text x="${xf+15}" y="${yf+4.5}" font-size="12.5" font-weight="700" fill="${col}">${txt}</text></svg>`;}
 function disegna(){const X=S[sel],f=X.finestra,mm=X.mesi||[],gg=X.giorni,ora=new Date().getMonth();
  const verd=!f?"n/d":f.robusto?(f.score>0?"RIALZO":"RIBASSO"):"NEUTRA";
  const fcard=`<div class="card"><h3>Prossime 4 settimane</h3><div class="kpi"><div class="big" style="color:${!f||!f.robusto?"var(--ink)":f.score>0?"var(--b)":"var(--s)"}">${verd}</div>
   <div class="note">${f?`salito <b>${f.su}</b> anni su <b>${f.n}</b> (dal ${f.da}) &middot; mediana ${pc(f.med)} &middot; senza trend ${pc(f.med_d)}`:"storico insufficiente"}</div>
   <div class="note">${f?(f.robusto?`<span class="tag ok">effetto affidabile</span> punteggio stagionale ${fmt(f.score)}`:`<span class="tag">non affidabile: ${esc(f.perche||"")}</span>`):""}</div></div>
   ${f?percorso(f.percorso):""}<div class="small">Percorso mediano degli anni passati dal venerd&igrave; di uscita del COT alle 8 settimane successive.</div></div>`;
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

