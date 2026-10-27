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

