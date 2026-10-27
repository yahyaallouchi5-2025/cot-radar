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

