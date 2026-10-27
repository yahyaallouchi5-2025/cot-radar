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

