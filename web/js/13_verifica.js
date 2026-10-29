/* ---------- VERIFICA DEI SEGNALI: registro live + backtest simulato ----------
   Due finestre separate e mai mescolate:
     LIVE     = segnali veri, con data e ora di generazione, salvati per sempre con una catena di hash (D.reg)
     BACKTEST = segnali SIMULATI sulle settimane passate dal 1986 con le stesse regole (D.bt)
   Calcoli in cot_radar/motore.py; qui solo la presentazione. Ingresso = prima chiusura dopo il segnale. */
function ebVerifica(){try{(function(){const el=$("verifica"),R=D.reg,B=D.bt;if(!el)return;
 // finestra, durata del trade (giorni di mercato 1..20 o "fine"), storico usato, strumento (volatilita' e drawdown),
 // unita' del grafico del drawdown ("pct" = in %, "vol" = in settimane tipiche di quel mercato)
 const V={fin:"live",d:5,per:"tutti",asset:"EURUSD",strum:"tutti",unita:"pct"};
 try{const s=JSON.parse(localStorage.getItem("ebVerifica")||"{}");if(s.fin)V.fin=s.fin;if(s.d=="fine"||(s.d>=1&&s.d<=20))V.d=s.d;if(s.per)V.per=s.per;if(s.asset)V.asset=s.asset;
  if(s.strum)V.strum=s.strum;if(s.unita=="vol")V.unita="vol";}catch(e){}
 const salva=()=>{try{localStorage.setItem("ebVerifica",JSON.stringify(V));}catch(e){}};
 const pc=(x,d=2)=>x==null||isNaN(x)?"n/d":(x>0?"+":x<0?"−":"")+Math.abs(x).toLocaleString("it-IT",{minimumFractionDigits:d,maximumFractionDigits:d})+"%";
 const col=x=>x==null?"":x>0?"up":x<0?"down":"flat";
 const prezzo=p=>{if(p==null)return"n/d";const d=p>=1000?2:p>=100?3:p>=10?3:4;return p.toLocaleString("it-IT",{minimumFractionDigits:d,maximumFractionDigits:d});};
 const oraIt=u=>{if(!u)return"";const t=new Date(u.replace("Z",":00Z"));
  return t.toLocaleDateString("it-IT",{timeZone:"Europe/Rome",day:"2-digit",month:"2-digit",year:"numeric"})+" ore "+t.toLocaleTimeString("it-IT",{timeZone:"Europe/Rome",hour:"2-digit",minute:"2-digit"});};
 const sett=(a,b)=>Math.max(1,Math.round((new Date(b)-new Date(a))/864e5/7));
 const MOT={neutro:"tornato NEUTRO",inversione:"segnale invertito",indebolito:"tornato da STRONG a normale","12 settimane":"limite di 12 settimane"};

 /* tabellina dei risultati: periodo, risultato, guadagno massimo e drawdown massimo lungo il percorso */
 function cella(t){return t?`<td class="num"><b class="${col(t.res)}">${pc(t.res)}</b></td><td class="num up">${pc(t.mfe)}</td><td class="num down">${pc(t.mae)}</td><td>${t.provvisorio?'<span class="vfic" title="ancora in corso">&#9719;</span>':t.vinto?'<span class="vfok">&#10003;</span>':'<span class="vfko">&#10007;</span>'}</td>`
  :`<td class="num small" colspan="4">in attesa</td>`;}

 /* scheda di un segnale nel formato approvato */
 function scheda(s,sim){const m=s.m||{},A=m.A||{},ing=m.ingresso;
  const testa=`<div class="vfh"><span class="pair">${esc(s.strumento)}</span> ${badge(s.etichetta)}${s.iniziale?' <span class="tag" title="Era gia\' attivo quando il registro e\' partito: escluso dalle statistiche">gi&agrave; attivo all\'avvio</span>':''}${s.padre?' <span class="tag" title="Fase STRONG di un segnale gia\' aperto">fase STRONG</span>':''}${volTag(s.vol)}</div>`;
  let h=`<div class="vfr"><span>Segnale generato</span><b>${esc(s.generato_it)}</b></div>`+
   (ing?`<div class="vfr"><span>Ingresso</span><b>${prezzo(ing.prezzo)} <span class="small">&middot; ${oraIt(ing.utc)}</span></b></div>`
       :`<div class="vfr"><span>Ingresso</span><span class="small">${esc(m.stato||"prezzo non disponibile")}</span></div>`);
  if(ing){const f=A.fine,fm=m.fine||{},chiuso=!!(s.chiuso||fm.motivo);
   const nf=f?`${chiuso?"Al cambio":"Finora"}<small class="vfsett">${sett(ing.data,f.data)} sett.</small>`:"Al cambio";
   h+=`<table class="vftab"><tr><th></th><th class="num">Risultato</th><th class="num">Max</th><th class="num">Min</th><th></th></tr>
    <tr><td>1 settimana</td>${cella(A["1s"])}</tr><tr><td>2 settimane</td>${cella(A["2s"])}</tr><tr><td>4 settimane</td>${cella(A["4s"])}</tr>
    <tr class="vffine"><td>${nf}</td>${f?cella(f):'<td class="num small" colspan="4">in attesa del prezzo</td>'}</tr></table>`;
   if(chiuso){const quando=s.chiuso&&fm.motivo!="12 settimane"?s.chiuso.quando_it:(f?fd(f.data):"");
    h+=`<div class="small vfnota">${s.chiuso?"Chiuso il "+esc(quando):"Misura conclusa"} &middot; ${esc(MOT[fm.motivo]||MOT[(s.chiuso||{}).motivo]||"")}</div>`;}
   const b=m.B||{};const bt=b.esito=="eseguito"?`eseguito a ${prezzo(b.limite)} il ${fd(b.data)}`:b.esito=="non eseguito"?`non eseguito (limite ${prezzo(b.limite)})`:b.esito=="in attesa"?`limite a ${prezzo(b.limite)} in attesa`:"n/d";
   h+=`<div class="small vfnota">Ingresso B (ritracciamento): ${bt}</div>`;}
  return `<div class="card vfcard${sim?" vfsim":""}">${testa}<div class="vfrighe">${h}</div></div>`;}

 /* ---- VOLATILITA' PER ASSET (D.vol, calcolata da cot_radar/volatilita.py) ----
    La "natura" di ogni mercato: quanto si muove per giorno della settimana, per settimana, per mese del
    calendario e anno per anno, e in che regime e' adesso. Volatilita' da chiusura a chiusura (FRED). */
 const VCOL={calma:"var(--c1)",normale:"var(--warn)",agitata:"var(--ss)"};
 const fp=(x,d=2)=>x==null?"n/d":x.toLocaleString("it-IT",{minimumFractionDigits:d,maximumFractionDigits:d})+"%";
 const volTag=v=>v?` <span class="tag vfvtag" style="--vc:${VCOL[v.nome]}" title="Volatilita' delle 4 settimane prima del segnale (${fp(v.vol,1)} annua) rispetto agli ultimi 5 anni">vol. ${v.nome} &middot; ${v.pct}&deg;</span>`:"";
 /* barre verticali semplici: items = [{et, v, v2?, evid?, tit?}]; v2 = seconda serie (ultimo anno) */
 function barre(items,dec,cls){const mx=Math.max(1e-9,...items.flatMap(x=>[x.v||0,x.v2||0]));
  return `<div class="vfbarre ${cls||""}">${items.map(x=>`<div class="vfb${x.evid?" evid":""}" title="${esc(x.tit||x.et+": "+fp(x.v,dec)+(x.v2!=null?" (ultimo anno "+fp(x.v2,dec)+")":""))}">
   <div class="vfbcol"><i style="height:${Math.round((x.v||0)/mx*100)}%"></i>${x.v2!=null?`<i class="b2" style="height:${Math.round(x.v2/mx*100)}%"></i>`:""}</div>
   ${cls=="fitte"?"":`<em>${fp(x.v,dec)}</em>`}<span>${esc(x.et)}</span></div>`).join("")}</div>`;}
 function datiVol(){const P=(D.vol||{})[V.asset];if(!P)return `<div class="card vfvuoto">Volatilit&agrave; non disponibile per questo strumento.</div>`;
  const R=P.regime,S=P.settimane,o=P.oggi,mOra=new Date().getMonth(),aOra=String(new Date().getFullYear());
  const MESI=["gen","feb","mar","apr","mag","giu","lug","ago","set","ott","nov","dic"];
  const reg=R?`<div class="card vfregime" style="--vc:${VCOL[R.nome]}"><div><h3>Regime di adesso</h3><div class="big" style="color:var(--vc)">${R.nome.toUpperCase()}</div>
   <div class="note">ultime 4 settimane: <b>${fp(R.vol,1)}</b> di volatilit&agrave; annua, pi&ugrave; alta del <b>${R.pct}%</b> dei periodi degli ultimi 5 anni</div></div>
   <div class="vfpct"><div class="vfpbar"><i style="left:${R.pct}%"></i></div><div class="scale"><span>calma</span><span>normale</span><span>agitata</span></div></div></div>`:"";
  // movimento in PUNTI sull'ultimo prezzo: pip per i cambi (0,01 se la quotata e' lo yen), punti indice, dollari
  const u=/^[A-Z]{6}$/.test(V.asset)?["pip",V.asset.endsWith("JPY")?0.01:0.0001]:["SP500","NASDAQ","DOW"].includes(V.asset)?["punti",1]:["$",1];
  const inPt=x=>x!=null&&P.prezzo?" &middot; &asymp; "+fmtPt(x/100*P.prezzo/u[1],u[0]):"";
  const rng=S.media_anno!=null?S.media_anno*2:null;   // range tipico STIMATO: circa il doppio della mossa chiusura-chiusura
  return reg+`<h3 class="vft">Quanto si muove <span class="small">(Settimana media e P90 sono misurate DA CHIUSURA A CHIUSURA: quanto il prezzo si &egrave; spostato da un venerd&igrave; all'altro, in valore assoluto. Non sono il RANGE della candela (massimo &minus; minimo, stoppini compresi), che &egrave; sempre pi&ugrave; ampio: in media circa il doppio, per questo la scheda mostra anche un range tipico STIMATO. Il range vero richiede massimi e minimi (dati OHLC), che la fonte gratuita FRED non fornisce. Prezzi FRED: per i cambi &egrave; il fixing delle 12 di New York (18 in Italia), mentre il broker chiude alle 17 di New York (23 in Italia), e i cambi FRED possono arrivare con circa una settimana di ritardo: l'ultimo dato usato qui &egrave; del <b>${fd(P.al)}</b>, controlla che sia la stessa settimana che guardi sul grafico. Per verificare su TradingView: grafico settimanale, misura da chiusura a chiusura (corpo contro corpo) delle ultime 52 settimane e fai la media senza segno; per il range usa l'ATR(14) settimanale, da confrontare con il range stimato. I pip sono calcolati sull'ultimo prezzo disponibile)</span></h3>
   <div class="grid k4 vfkpi">
   ${kcard("vki1","Volatilit&agrave; annua",fp(P.ann_anno,1),"storia "+fp(P.ann_storia,1),`Quanto oscilla il prezzo in un anno, nell'ultimo anno: deviazione standard dei rendimenti giornalieri &times; &radic;252, da chiusura a chiusura. "Storia" = la stessa misura su tutto l'archivio, dal ${fd(P.dal)}.`)}
   ${kcard("vki2","Settimana media",fp(S.media_anno),[inPt(S.media_anno).replace(" &middot; ",""),"range &asymp; "+fp(rng)].filter(Boolean).join(" &middot; "),`Media dell'ultimo anno della variazione da una chiusura settimanale alla successiva, in valore assoluto${inPt(S.media_anno)} (storia: ${fp(S.media)}). Il <b>range</b> della candela (massimo &minus; minimo) &egrave; stimato a circa il doppio: ${fp(rng)}${inPt(rng)}. Il range vero richiede massimi e minimi, non disponibili con FRED.`)}
   ${kcard("vki3","Settimana P90",fp(S.brutta),[inPt(S.brutta).replace(" &middot; ",""),"ultima "+fp(S.ultima)].filter(Boolean).join(" &middot; "),`1 settimana su 10 si muove pi&ugrave; di cos&igrave; (90&deg; percentile, da chiusura a chiusura)${inPt(S.brutta)}. L'ultima settimana disponibile, al ${fd(P.al)}, si &egrave; mossa dello ${fp(S.ultima)}.`)}
   ${kcard("vki4","Ultima seduta",fp(o.mossa,2),fd(o.data)+" &middot; media "+fp(o.media_giorno),`Movimento dell'ultima seduta disponibile (${fd(o.data)}), da chiusura a chiusura${inPt(o.mossa)}, contro la media storica dello stesso giorno della settimana (${fp(o.media_giorno)}).`)}</div>
   <h3 class="vft">Giorno per giorno <span class="small">(movimento medio per giorno della settimana: colonna piena = storia, chiara = ultimo anno)</span></h3>
   <div class="card">${barre(P.giorni.map(g=>({et:g.g,v:g.storia,v2:g.anno})),2)}</div>
   <h3 class="vft">Mese per mese <span class="small">(volatilit&agrave; annua media in quel mese del calendario, dal ${fd(P.dal)})</span></h3>
   <div class="card">${barre(P.mesi.map((v,i)=>({et:MESI[i],v:v,evid:i==mOra})),1)}</div>
   <h3 class="vft">Anno per anno <span class="small">(volatilit&agrave; annua di ogni anno; l'anno in corso &egrave; parziale)</span></h3>
   <div class="card">${barre(Object.entries(P.anni).map(([a,v])=>({et:a.slice(2),v:v,evid:a==aOra,tit:a+": "+fp(v,1)+(a==aOra?" (in corso)":"")})),1,"fitte")}</div>
   <p class="small">Volatilit&agrave; misurata da chiusura a chiusura (FRED pubblica un prezzo al giorno): il range vero della giornata (massimo &minus; minimo) pu&ograve; essere pi&ugrave; ampio. Movimenti giornalieri e settimanali = media del valore assoluto della variazione; volatilit&agrave; annua = deviazione standard dei rendimenti giornalieri &times; &radic;252.</p>`;}
 function volatilitaVista(){const ks=Object.keys(D.vol||{});if(!ks.length)return `<div class="card vfvuoto">Volatilit&agrave; non disponibile in questo aggiornamento.</div>`;
  if(!ks.includes(V.asset))V.asset=ks.includes("EURUSD")?"EURUSD":ks[0];
  const coppie=ks.filter(k=>/^[A-Z]{6}$/.test(k)).sort(),altri=ks.filter(k=>!/^[A-Z]{6}$/.test(k)).sort();
  const opt=l=>l.map(k=>`<option value="${k}"${k==V.asset?" selected":""}>${k}${D.vol[k].regime?" · "+D.vol[k].regime.nome:""}</option>`).join("");
  return `<div class="card vfcomandi"><div class="vfriga"><span class="vfetich">Strumento</span><select id="vfasset" class="vfsel"><optgroup label="Cambi">${opt(coppie)}</optgroup><optgroup label="Indici, energia, crypto">${opt(altri)}</optgroup></select></div></div><div id="vfdati">${datiVol()}</div>`;}
 /* ---- ORIZZONTE DI USCITA scelto da chi guarda ----
    Uno speculatore chiude in settimana (5 sedute), un investitore tiene 4 settimane (20 sedute):
    V.d = giorni di mercato dopo l'ingresso (1..20) oppure "fine" (= fino al cambio di segnale).
    I dati arrivano compatti da Python (motore.giorni_stat): per ogni seduta [segnali, vinti, somme di
    risultato, guadagno massimo e drawdown massimo]. Qui si calcolano medie, % vinti e intervallo di Wilson. */
 function wilson(k,n){if(!n)return null;const z=1.96,p=k/n,den=1+z*z/n,c=(p+z*z/(2*n))/den,m=z*Math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den;
  return [Math.round(100*Math.max(0,c-m)),Math.round(100*Math.min(1,c+m))];}
 function st(R){if(!R)return null;
  if(V.d=="fine")return R.fine||null;
  const a=(R.g||[])[V.d-1];if(!a||!a[0])return null;
  const n=a[0],v=a[1],mfe=a[3]/n,mae=a[4]/n;
  return {n:n,vinti:v,hit:Math.round(100*v/n),ic:wilson(v,n),resa:a[2]/n,mfe:mfe,mae:mae,rapporto:mae<0?Math.round(100*mfe/Math.abs(mae))/100:null};}
 /* ---- DURATA DEL TRADE in parole: 13 -> "2 settimane e 3 giorni" (giorni di mercato: 5 a settimana) ---- */
 const durata=d=>{if(d=="fine")return "al cambio segnale";const w=Math.floor(d/5),g=d%5,
  S=w?w+(w==1?" settimana":" settimane"):"",G=g?g+(g==1?" giorno":" giorni"):"";return S&&G?S+" e "+G:S||G;};
 const nomeD=()=>V.d=="fine"?"fino al cambio di segnale":"dopo "+durata(V.d);

 /* ---- STUDIO DEL DRAWDOWN (calcolato in cot_radar/motore.py, funzione drawdown) ----
    Obiettivo: quanto il trade va contro prima di andare (o non andare) dove deve, rispetto alla volatilita'
    di quel mercato e al guadagno. Per ogni durata (1..20 giorni + "al cambio segnale") Python manda una riga
    compatta; i nomi dei campi sono nella lista dd_campi (spiegati in motore.DD_CAMPI). */
 function ddGruppo(F){const g=F&&F.dd;if(!g)return null;return V.strum=="tutti"?g.tutti:(g.strumento||{})[V.strum]||null;}
 function ddRiga(lista,campi,d){d=d??V.d;const r=lista&&lista[d=="fine"?20:d-1];if(!r||!campi)return null;
  const o={};campi.forEach((k,i)=>o[k]=r[i]);return o.n?o:null;}
 // punti: pip senza decimali, punti indice e dollari con i decimali che servono
 const fmtPt=(x,u)=>{const dec=u=="pip"?0:x<10?2:x<100?1:0;return x.toLocaleString("it-IT",{minimumFractionDigits:dec,maximumFractionDigits:dec})+(u=="$"?" $":" "+u);};
 const vx=x=>x==null?"n/d":x.toLocaleString("it-IT",{minimumFractionDigits:1,maximumFractionDigits:1})+"&times;";

 /* quattro riquadri: drawdown assoluto mediano e P90, in volatilita', guadagno contro drawdown (+ esito in piccolo) */
 function kpiDD(o,u){
  if(!o)return `<div class="card vfvuoto small">Nessun trade ${V.strum=="tutti"?"":"su "+esc(V.strum)+" "}con questa durata gi&agrave; concluso in questo storico.</div>`;
  const ptb=x=>u&&x!=null?"&asymp; "+fmtPt(x,u):"";
  return `<div class="grid k4 vfkpi">
   ${kcard("dki1","Drawdown assoluto mediano",pc(o.mae50),ptb(o.p50)||"mediana",`Quanto il trade va contro dall'ingresso fino alla durata scelta: la <b>met&agrave;</b> dei trade va contro meno di cos&igrave; (mediana del drawdown massimo)${u&&o.p50!=null?", cio&egrave; circa "+fmtPt(o.p50,u)+" sul prezzo d'ingresso":""}.`,"down")}
   ${kcard("dki2","Drawdown assoluto P90",pc(o.mae90),ptb(o.p90)||"1 trade su 10",`<b>1 trade su 10</b> va contro di pi&ugrave;${u&&o.p90!=null?" (circa "+fmtPt(o.p90,u)+")":""}. &Egrave; il numero da guardare per lo stop: uno stop pi&ugrave; stretto viene preso da almeno un trade su 10 anche quando l'idea era giusta.`,"down")}
   ${kcard("dki3","In volatilit&agrave;",vx(o.v50),"P90 "+vx(o.v90),`Il drawdown diviso il movimento di una settimana normale di quel mercato, misurato prima dell'ingresso. 1&times; = una settimana normale. Cos&igrave; EURUSD, petrolio e Bitcoin si confrontano sulla stessa scala. Mediano ${vx(o.v50)}, P90 (1 trade su 10) ${vx(o.v90)}.`)}
   ${kcard("dki4","Guadagno / drawdown",`<span class="up">${pc(o.mfe50)}</span> / <span class="down">${pc(o.mae50)}</span>`,o.prima!=null?"guadagno prima nel "+o.prima+"%":"mediane",`Guadagno massimo tipico e drawdown mediano (mediane). ${o.prima!=null?"Il guadagno massimo arriva prima del drawdown massimo nel <b>"+o.prima+"%</b> dei trade. ":""}${o.gmin?"Il punto peggiore arriva di solito al <b>"+Math.round(o.gmin)+"&deg; giorno</b> di mercato.":""}`,"vfgd")}</div>
   <p class="small vfesito">Esito, per completezza: <b>${o.hit}%</b> dei trade chiusi in guadagno &middot; resa media <b class="${col(o.resa)}">${pc(o.resa)}</b> al netto dei costi &middot; ${o.n.toLocaleString("it-IT")} trade misurati.</p>`;}

 /* GRAFICO giorno per giorno (1..20): guadagno massimo mediano (verde), drawdown mediano (rosso), drawdown P90
    (rosso tratteggiato) e risultato mediano (chiaro). In % oppure in volatilita' (settimane tipiche). */
 function graficoDD(lista,campi){const rows=[];for(let d=1;d<=20;d++){const o=ddRiga(lista,campi,d);if(o)rows.push(Object.assign({d:d},o));}
  if(rows.length<2)return "";
  const vol=V.unita=="vol",pts=rows.map(o=>vol?{d:o.d,mx:o.fv50??0,r:o.rv50??0,mn:-(o.v50??0),mb:-(o.v90??0)}:{d:o.d,mx:o.mfe50,r:o.res50,mn:o.mae50,mb:o.mae90});
  const mob=matchMedia("(max-width:600px)").matches,W=mob?400:760,H=mob?280:260,L=mob?42:50,Rr=mob?10:16,T=16,Bm=30;
  const lo=Math.min(0,...pts.map(p=>p.mb)),hi=Math.max(0.1,...pts.map(p=>p.mx));
  const X=d=>L+(d-1)/19*(W-L-Rr),Y=v=>T+(hi-v)/((hi-lo)||1)*(H-T-Bm);
  const linea=(k,c,w,tr)=>`<path d="${pts.map((p,i)=>(i?"L":"M")+X(p.d).toFixed(1)+" "+Y(p[k]).toFixed(1)).join(" ")}" fill="none" stroke="${c}" stroke-width="${w}" stroke-linejoin="round"${tr?' stroke-dasharray="6 5"':""}/>`;
  const area=`<path d="${pts.map((p,i)=>(i?"L":"M")+X(p.d).toFixed(1)+" "+Y(p.mx).toFixed(1)).join(" ")} ${pts.slice().reverse().map(p=>"L"+X(p.d).toFixed(1)+" "+Y(p.mn).toFixed(1)).join(" ")} Z" fill="var(--soft)" opacity=".6"/>`;
  const span=hi-lo,passo=vol?(span>6?2:span>3?1:0.5):(span>12?4:span>6?2:span>3?1:0.5),tick=[];
  for(let v=Math.ceil(lo/passo)*passo;v<=hi+1e-9;v+=passo)tick.push(v);
  const et=v=>vol?(v>0?"+":v<0?"−":"")+Math.abs(v).toLocaleString("it-IT",{maximumFractionDigits:1})+"×":(v>0?"+":"")+String(Math.round(v*10)/10).replace(".",",")+"%";
  const sel=V.d=="fine"?null:pts.find(p=>p.d==V.d);
  return `<div class="card vfgraf"><div class="vfgtesta"><b>Giorno per giorno</b><div class="filters vfunita"><button data-u="pct" class="${vol?"":"on"}">in %</button><button data-u="vol" class="${vol?"on":""}">in volatilit&agrave;</button></div></div>
   <svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Drawdown e guadagno giorno per giorno">
   ${tick.map(v=>`<line x1="${L}" x2="${W-Rr}" y1="${Y(v)}" y2="${Y(v)}" stroke="var(--line)" ${Math.abs(v)<1e-9?'stroke-width="1.5"':'stroke-dasharray="3 4"'}/><text x="${L-8}" y="${Y(v)+4}" text-anchor="end" class="vfax">${et(v)}</text>`).join("")}
   ${(mob?[5,10,15,20]:[1,5,10,15,20]).map(d=>`<text x="${X(d)}" y="${H-8}" text-anchor="${d==20?"end":d==1?"start":"middle"}" class="vfax">${d==1?"1 giorno":d/5+(d==5?" sett.":" sett.")}</text>`).join("")}
   ${area}${linea("mx","var(--b)",2)}${linea("mb","var(--s)",1.6,1)}${linea("mn","var(--s)",2.4)}${linea("r","var(--ink)",2)}
   ${sel?`<line x1="${X(sel.d)}" x2="${X(sel.d)}" y1="${T}" y2="${H-Bm}" stroke="var(--acc)" stroke-width="1.5"/>
    <circle cx="${X(sel.d)}" cy="${Y(sel.mx)}" r="4" fill="var(--b)"/><circle cx="${X(sel.d)}" cy="${Y(sel.mn)}" r="4.5" fill="var(--s)"/><circle cx="${X(sel.d)}" cy="${Y(sel.mb)}" r="3.5" fill="var(--s)"/>`:""}
   </svg><div class="vfleg small"><span><i style="background:var(--b)"></i>guadagno massimo mediano</span><span><i style="background:var(--s)"></i>drawdown mediano</span><span><i class="tratt"></i>drawdown P90 (1 su 10)</span><span><i style="background:var(--ink)"></i>risultato mediano</span></div>
   ${vol?`<p class="small vfnota">In volatilit&agrave;: 1&times; = quanto si muove di solito quel mercato in una settimana (misurato prima di ogni ingresso). Cos&igrave; EURUSD, petrolio e Bitcoin stanno sulla stessa scala.</p>`:""}</div>`;}

 /* FASCE: quanti trade sono andati contro meno di mezza settimana tipica, tra mezza e una, tra una e due, oltre */
 function fasce(o){if(!o||o.h1==null)return "";
  const f=[["sotto 0,5&times; (rumore di mercato)",o.h1,"var(--b)"],["da 0,5&times; a 1&times;",o.h2,"var(--warn)"],["da 1&times; a 2&times;",o.h3,"var(--s)"],["oltre 2&times; (movimento direzionale contro)",o.h4,"var(--ss)"]];
  return `<h3 class="vft">Distribuzione del drawdown in volatilit&agrave; <span class="small">(drawdown massimo ${nomeD()}, in multipli del movimento settimanale mediano di quel mercato, misurato prima dell'ingresso: 1&times; = una settimana normale. Sotto 0,5&times; &egrave; rumore di mercato, oltre 2&times; &egrave; un movimento direzionale contro il trade)</span></h3>
  <div class="card vffasce">${f.map(([t,v,c])=>`<div class="vffascia"><span>${t}</span><div class="vfbar"><i style="width:${v}%;background:${c}"></i></div><b>${v}%</b></div>`).join("")}</div>`;}

 /* ANNUNCI MACRO USA: il drawdown e' piu' grande quando c'e' un annuncio? Il giorno peggiore cade sugli annunci? */
 function annunci(o){const tit=`<h3 class="vft">Annunci macro USA <span class="small">(occupazione NFP e inflazione CPI dal 1985, decisioni della Fed dal 1994, date ufficiali. Un giorno "con annuncio" &egrave; una seduta la cui chiusura arriva dopo l'annuncio: per i cambi, chiusi alle 12 di New York, la Fed delle 14 conta il giorno dopo. Con i soli prezzi di chiusura il picco dentro la giornata non si vede. BCE non inclusa)</span></h3>`;
  if(V.d=="fine")return tit+`<p class="small">Disponibile per le durate da 1 giorno a 4 settimane: serve il percorso giorno per giorno.</p>`;
  if(!o||o.pg==null)return tit+`<p class="small">Dati non disponibili per questa scelta.</p>`;
  const conf=o.ev_n>=30&&o.no_n>=30,pochi=o.n<60,dd=o.pg-o.pa;
  const giud=pochi?["troppo pochi trade per un giudizio",""]:dd>=5?["pi&ugrave; del caso: gli annunci pesano sul drawdown","down"]:dd<=-5?["meno del caso",""]:["in linea con il caso: il drawdown non viene soprattutto dagli annunci",""];
  return tit+`<div class="grid k2 vfann">
   <div class="card kpi"><h3>Drawdown con e senza annunci</h3>${conf?`<div class="vfrighe"><div class="vfr"><span>con almeno un annuncio nel trade</span><b class="down">${pc(o.ev50)}</b></div><div class="vfr"><span>senza annunci</span><b class="down">${pc(o.no50)}</b></div></div><div class="note">drawdown mediano &middot; ${o.ev_n.toLocaleString("it-IT")} trade con annunci, ${o.no_n.toLocaleString("it-IT")} senza</div>`
    :`<div class="note">Con questa durata quasi ogni trade contiene un annuncio (solo ${o.no_n} senza): il confronto non &egrave; affidabile. Prova una durata pi&ugrave; breve.</div>`}</div>
   <div class="card kpi"><h3>Il giorno peggiore del trade</h3><div class="big">${o.pg}%</div><div class="note">cade su un giorno con annuncio; per puro caso sarebbe il <b>${o.pa}%</b> &rarr; <span class="${giud[1]}">${giud[0]}</span></div></div></div>`;}

 /* blocco completo del drawdown per la finestra scelta (live o backtest): F = statistiche, campi = nomi dei campi */
 function bloccoDD(F,campi,unitaPunti){const lista=ddGruppo(F),o=ddRiga(lista,campi),u=V.strum=="tutti"?null:(unitaPunti||{})[V.strum];
  return `<h3 class="vft">Drawdown assoluto del trade <span class="small">(quanto il trade va contro dall'ingresso. Assoluto = misurato dal prezzo d'ingresso, non dal massimo raggiunto. Mediano = la met&agrave; dei trade va contro meno di cos&igrave;; P90 (90&deg; percentile) = 1 trade su 10 va contro di pi&ugrave;. In volatilit&agrave; = drawdown diviso il movimento di una settimana normale di quel mercato, misurato prima dell'ingresso: cos&igrave; mercati diversi si confrontano. ${u?"Punti = drawdown in "+(u=="$"?"dollari":u)+" sul prezzo d'ingresso di ogni trade.":"Scegli uno strumento per vedere anche i punti (pip, punti indice, dollari)."})</span></h3>
  <p class="small vfcontesto">Durata <b>${durata(V.d)}</b> &middot; ${V.strum=="tutti"?"tutti gli strumenti":"<b>"+esc(V.strum)+"</b>"}${V.fin=="bt"?" &middot; storico: "+{tutti:"tutto",sviluppo:"sviluppo",holdout:"holdout (ultimi 2 anni)"}[V.per]:""}</p>`+
  kpiDD(o,u)+graficoDD(lista,campi)+fasce(o)+annunci(o);}

 /* tabella per gruppo (etichetta, volatilita', periodo, strumento): gr = {nome: riassunto} */
 function tabella(titolo,gr,ordine,min,prof){const ks=(ordine||Object.keys(gr||{})).filter(k=>gr&&gr[k]&&st(gr[k])&&st(gr[k]).n>=(min||1));
  if(!ks.length)return "";
  return `<h3 class="vft">${titolo}</h3><div class="tablewrap"><table class="compatta"><tr><th></th><th class="num">Segnali</th><th class="num">Vinti</th><th class="num">Probabile tra</th><th class="num">Resa media</th><th class="num" title="Media dei guadagni massimi (le schede in alto usano invece la mediana)">Guadagno max medio</th><th class="num" title="Media dei drawdown massimi (le schede in alto usano invece la mediana: i casi estremi pesano meno)">Drawdown max medio</th><th class="num">Rapporto</th>${prof?`<th class="num" title="Volatilita' annua dell'ultimo anno">Volatilit&agrave; annua</th><th class="num" title="Movimento tipico in una settimana (mediana), ultimo anno">Mossa tipica sett.</th><th class="num" title="Drawdown medio diviso la mossa settimanale tipica: sotto 1 = drawdown nella norma per quel mercato, sopra 1 = il segnale soffre piu' del normale rumore">Drawdown / mossa</th>`:""}</tr>
   ${ks.map(k=>{const x=st(gr[k]),p=prof&&prof[k];return `<tr><td><b>${esc(k)}</b></td><td class="num">${x.n.toLocaleString("it-IT")}</td><td class="num"><b>${x.hit}%</b></td><td class="num small">${x.ic[0]}&ndash;${x.ic[1]}%</td><td class="num ${col(x.resa)}">${pc(x.resa)}</td><td class="num up">${pc(x.mfe)}</td><td class="num down">${pc(x.mae)}</td><td class="num">${x.rapporto==null?"n/d":x.rapporto.toLocaleString("it-IT")}</td>${prof?(p?`<td class="num">${fx(p.ann,1)}%</td><td class="num">${fx(p.sett,2)}%</td><td class="num ${Math.abs(x.mae)/p.sett>1.5?"down":""}">${fx(Math.abs(x.mae)/p.sett,2)}&times;</td>`:'<td class="num small" colspan="3">n/d</td>'):""}</tr>`;}).join("")}</table></div>${prof?`<p class="small">Drawdown e volatilit&agrave; raccontano la <b>natura del mercato</b>: lo stesso drawdown del 2% &egrave; tanto su un cambio che si muove dell'1% a settimana e poco su un mercato che si muove dell'8%. "Drawdown / mossa" sopra 1,5 = il segnale soffre pi&ugrave; del normale rumore di quello strumento.</p>`:""}`;}

 /* confronto dei tre modi di entrare: calcolato a 1, 2 e 4 settimane (5, 10, 20 sedute) */
 function varianti(R){const h={5:"1s",10:"2s",20:"4s"}[V.d],x=h&&R&&R.var&&R.var[h];
  if(!x)return `<h3 class="vft">Tre modi di entrare</h3><p class="small">Il confronto tra ingresso subito, ritracciamento e met&agrave; e met&agrave; &egrave; calcolato a 1, 2 e 4 settimane: scegli 5, 10 o 20 sedute per vederlo.</p>`;
  return `<h3 class="vft">Tre modi di entrare <span class="small">(valore medio per segnale, ${nomeD()})</span></h3><div class="grid k3 vfvar">
   <div class="card"><b>A &middot; subito</b><div class="big ${col(x.resa)}">${pc(x.resa)}</div><div class="small">alla prima chiusura dopo il segnale</div></div>
   <div class="card"><b>B &middot; ritracciamento</b><div class="big ${col(x.B.valore)}">${pc(x.B.valore)}</div><div class="small">ordine limite a 0,5&times; il movimento settimanale tipico, valido 5 giorni: eseguito ${x.B.fill==null?"n/d":x.B.fill+"%"} delle volte${x.B.resa_eseguiti!=null?`, resa quando eseguito ${pc(x.B.resa_eseguiti)}`:""}</div></div>
   <div class="card"><b>C &middot; met&agrave; e met&agrave;</b><div class="big ${col(x.C.valore)}">${pc(x.C.valore)}</div><div class="small">met&agrave; subito, met&agrave; con l'ordine limite</div></div></div>
   <p class="small">Valore per segnale = percentuale di esecuzione &times; resa media: un ingresso "migliore" che scatta di rado pu&ograve; valere meno.</p>`;}

 /* comandi: storico usato (solo backtest), strumento, durata del trade. Le spiegazioni stanno dietro le (i). */
 const infoBtn=(id,tit)=>`<button type="button" class="info" data-apri="${id}" data-k="${id}" aria-expanded="${infoAperte.has(id)}" aria-label="${tit}" title="${tit}">i</button>`;
 const infoP=(id,testo)=>`<p id="${id}" class="sub infotesto${infoAperte.has(id)?" aperta":""}">${testo}</p>`;
 /* SCHEDA NUMERICA uniforme: titolo (con la "i" se c'e' una spiegazione), numero grande, UNA riga breve.
    La spiegazione lunga sta dentro la "i". Le schede di una riga sono allineate (CSS: .vfkpi con subgrid):
    i numeri restano sulla stessa linea anche se un titolo va a capo. */
 const kcard=(id,titolo,valore,breve,spiega,cls)=>`<div class="card kpi"><h3>${titolo}${spiega?infoBtn(id,"Cosa misura"):""}</h3>
  <div class="big ${cls||""}">${valore}</div><div class="note">${breve||"&nbsp;"}</div>${spiega?infoP(id,spiega):""}</div>`;
 function comandi(F){
  const per=V.fin=="bt"?`<div class="vfriga"><span class="vfetich">Storico usato ${infoBtn("vfinfostorico","Cosa sono tutto, sviluppo e holdout")}</span><div class="filters vfper">${[["tutti","Tutto"],["sviluppo","Sviluppo"],["holdout","Holdout (ultimi 2 anni)"]].map(([k,t])=>`<button data-p="${k}" class="${V.per==k?"on":""}">${t}</button>`).join("")}</div></div>
   ${infoP("vfinfostorico",`<b>Tutto</b>: tutti i segnali simulati dal 1987 a oggi. <b>Sviluppo</b>: dal 1987 a due anni fa, gli anni su cui il metodo &egrave; stato costruito e controllato. <b>Holdout</b>: gli ultimi 2 anni, tenuti da parte e mai usati per tarare nulla: &egrave; l'esame vero. Se sviluppo e holdout dicono cose molto diverse, il passato non &egrave; affidabile.`)}`:"";
  const ks=Object.keys((F&&F.dd&&F.dd.strumento)||{});if(V.strum!="tutti"&&!ks.includes(V.strum))V.strum="tutti";
  const cop=ks.filter(k=>/^[A-Z]{6}$/.test(k)).sort(),alt=ks.filter(k=>!/^[A-Z]{6}$/.test(k)).sort();
  const opt=l=>l.map(k=>`<option value="${k}"${k==V.strum?" selected":""}>${k}</option>`).join("");
  const str=`<div class="vfriga"><span class="vfetich">Strumento</span><select id="vfstrum" class="vfsel"><option value="tutti">Tutti gli strumenti</option>${cop.length?`<optgroup label="Cambi">${opt(cop)}</optgroup>`:""}${alt.length?`<optgroup label="Indici, energia, crypto">${opt(alt)}</optgroup>`:""}</select></div>`;
  return `<div class="card vfcomandi">${per}${str}<div class="vfriga"><span class="vfetich">Durata del trade ${infoBtn("vfinfodurata","Come si misura la durata")}</span><div class="filters vforz">${[[5,"1 settimana"],[10,"2 settimane"],[15,"3 settimane"],[20,"4 settimane"],["fine","al cambio segnale"]].map(([k,t])=>`<button data-h="${k}" class="${V.d==k?"on":""}">${t}</button>`).join("")}</div></div>
   <div class="vfriga vfslider"><span class="vfetich">oppure</span><input type="range" id="vfgiorni" min="1" max="20" step="1" value="${V.d=="fine"?20:V.d}" aria-label="Giorni di mercato dopo l'ingresso"><b id="vfgtesto">${durata(V.d)}</b></div>
   ${infoP("vfinfodurata",`I giorni sono <b>giorni di mercato</b> (5 per settimana: sabato e domenica non contano). L'ingresso &egrave; la prima chiusura dopo l'uscita del segnale; drawdown, guadagno e risultato sono misurati <b id="vfdurtesto">${nomeD()}</b> dall'ingresso. "Al cambio segnale" = il trade si chiude quando il segnale cambia (al massimo dopo 12 settimane).`)}</div>`;}

 /* SEZIONI NUMERATE (v6.49): la scheda e' lunga, quindi il contenuto e' diviso in tre blocchi con un numero,
    un titolo e una riga che dice a cosa serve. Cosi' si capisce dove si e' e cosa si sta guardando. */
 const blocco=(n,titolo,sotto,dentro)=>`<div class="vfsez"><div class="vfsez-t"><span class="vfsez-n">${n}</span>
  <div><h2>${titolo}</h2><p class="small">${sotto}</p></div></div>${dentro}</div>`;

 function datiLive(){const P=R.stat,ap=R.aperti||[],ch=R.chiusi||[];
  return blocco(1,"Quanto va contro","Prima dei guadagni: quanto il trade scende sotto l'ingresso, giorno per giorno.",
    bloccoDD(P,R.dd_campi,R.unita)+`<p class="small">I segnali gi&agrave; attivi all'avvio del registro sono esclusi.</p>`)
   +blocco(2,"Com'&egrave; andata","Gli stessi segnali divisi per etichetta, per volatilit&agrave; e per strumento.",
    tabella("Per etichetta",P.etichetta,["STRONG BUY","BUY","SELL","STRONG SELL"])+tabella("Per volatilit&agrave; al momento del segnale",P.vol,["calma","normale","agitata"])+varianti(P.riass)+tabella("Per strumento",P.strumento,null,1,R.profilo))
   +blocco(3,"I segnali uno per uno","Ogni segnale con data, ingresso e risultato alle varie durate.",
    `<h3 class="vft">Aperti <span class="small">(${ap.length})</span></h3><div class="grid vfgrid">${ap.map(s=>scheda(s)).join("")||'<div class="small">Nessun segnale aperto.</div>'}</div>
     <h3 class="vft">Chiusi <span class="small">(${R.n_chiusi})</span></h3><div class="grid vfgrid" id="vfchiusi">${ch.slice(0,12).map(s=>scheda(s)).join("")||'<div class="small">Ancora nessuno.</div>'}</div>
     ${ch.length>12?`<button class="vfaltro" id="vfaltro">Mostra tutti (${ch.length})</button>`:""}`);}

 function datiBt(){const P=B.periodi[V.per]||B.periodi.tutti,nomeP={tutti:"tutto il periodo",sviluppo:"sviluppo",holdout:"holdout"}[V.per];
  const per={"Tutto il periodo":B.periodi.tutti.riass,"Sviluppo":B.periodi.sviluppo.riass,"Holdout (ultimi 2 anni)":B.periodi.holdout.riass};
  const anni=Object.entries(B.anni||{}).map(([a,R])=>[a,st(R)]).filter(([a,x])=>x),mx=Math.max(0.5,...anni.map(([a,x])=>Math.abs(x.resa)));
  const barre=anni.length?`<h3 class="vft">Anno per anno <span class="small">(resa media ${nomeD()})</span></h3><div class="vfanni">${anni.map(([a,x])=>{const h=Math.round(Math.abs(x.resa)/mx*100),hold=a>=B.holdout_dal.slice(0,4);
   return `<div class="vfanno${hold?" vfhold":""}" title="${a}: ${x.n} segnali, vinti ${x.hit}%, resa media ${pc(x.resa)}"><div class="vfmeta">${x.resa>=0?`<i class="su" style="height:${h}%"></i>`:""}</div><div class="vfmeta giu">${x.resa<0?`<i class="giu" style="height:${h}%"></i>`:""}</div><span>${a.slice(2)}</span></div>`;}).join("")}</div>`:"";
  const ordS=Object.keys(P.strumento||{}).sort((a,b)=>((st(P.strumento[b])||{}).resa??-99)-((st(P.strumento[a])||{}).resa??-99));
  return blocco(1,"Quanto va contro","Prima dei guadagni: quanto il trade simulato scende sotto l'ingresso, giorno per giorno.",
    bloccoDD(P,B.dd_campi,B.unita))
   +blocco(2,"Il controllo onesto","Gli anni tenuti da parte (holdout) messi a confronto con quelli su cui il metodo &egrave; stato costruito.",
    tabella("Sviluppo e holdout a confronto",per,Object.keys(per))
    +`<p class="small">Il periodo di <b>holdout</b> (ultimi 2 anni) non va mai usato per tarare pesi o soglie: &egrave; il controllo onesto. Se sviluppo e holdout dicono cose molto diverse, il risultato del passato non &egrave; affidabile.</p>`)
   +blocco(3,"Com'&egrave; andata","Gli stessi segnali divisi per etichetta, per volatilit&agrave;, per anno e per strumento.",
    tabella(`Per etichetta <span class="small">(${nomeP})</span>`,P.etichetta,["STRONG BUY","BUY","SELL","STRONG SELL"])
    +tabella(`Per volatilit&agrave; al momento del segnale <span class="small">(${nomeP}: calma / normale / agitata rispetto ai 5 anni prima)</span>`,P.vol,["calma","normale","agitata"])
    +varianti(P.riass)+barre
    +tabella(`Per strumento <span class="small">(${nomeP}, almeno ${V.per=="holdout"?5:20} segnali)</span>`,P.strumento,ordS,V.per=="holdout"?5:20,B.profilo));}

 function live(){if(!R)return `<div class="card vfvuoto">Registro non disponibile in questo aggiornamento.</div>`;
  const cat=R.integra?`<span class="vfok">&#10003;</span> catena integra`:`<b class="vfko">&#10007; catena NON integra</b>`;
  const testa=`<div class="vfstato small">${R.dal?`Registro attivo dal <b>${esc(R.dal)}</b> &middot; `:""}${R.eventi} eventi &middot; ${cat}${R.ultimo_hash?` <button type="button" class="info" data-apri="vfcatena" data-k="vfcatena" aria-expanded="${infoAperte.has("vfcatena")}" aria-label="Cosa vuol dire catena integra" title="Cosa vuol dire?">i</button>`:""}${R.completi?"":" &middot; <b style='color:var(--warn)'>ultimo aggiornamento con dati incompleti: registro non aggiornato</b>"}</div>
  ${R.ultimo_hash?`<p id="vfcatena" class="sub infotesto${infoAperte.has("vfcatena")?" aperta":""}">Ogni evento del registro (apertura, conferma, chiusura di un segnale) &egrave; legato al precedente con un'impronta digitale (SHA-256). Se qualcuno modificasse o cancellasse un evento passato, le impronte non tornerebbero pi&ugrave; e qui comparirebbe <b>catena NON integra</b>: &egrave; la garanzia che i risultati non sono stati ritoccati dopo. Impronta dell'ultimo evento: <code class="vfhash">${esc(R.ultimo_hash)}</code></p>`:""}`;
  if(!R.eventi)return testa+`<div class="card vfvuoto"><b>Il registro parte con il prossimo aggiornamento completo.</b><p class="small">Da quel momento ogni segnale viene salvato con data e ora, prezzo d'ingresso e risultati. Gli eventi non si possono modificare: ognuno contiene l'impronta del precedente.</p></div>`;
  return testa+comandi(R.stat)+`<div id="vfdati">${datiLive()}</div>`;}

 function backtest(){if(!B)return `<div class="card vfvuoto">Backtest non disponibile in questo aggiornamento.</div>`;
  return `<div class="vfsimulato"><b>SIMULATO</b> &middot; risultati ricostruiti sul passato, non segnali reali. Servono a capire se il metodo ha un vantaggio, non promettono risultati futuri.</div>
   <div class="vfstato small">Dal <b>${fd(B.dal)}</b> al <b>${fd(B.al)}</b> &middot; ${B.n.toLocaleString("it-IT")} segnali (pi&ugrave; ${B.n_strong.toLocaleString("it-IT")} fasi STRONG) &middot; sviluppo ${(B.n_svil||0).toLocaleString("it-IT")} &middot; holdout dal ${fd(B.holdout_dal)}: ${(B.n_hold||0).toLocaleString("it-IT")}</div>
   ${comandi(B.periodi.tutti)}<div id="vfdati">${datiBt()}</div>
   <details class="vfdett"><summary>Come &egrave; costruito (e cosa manca rispetto al live)</summary><ul class="small">
    <li>Ogni settimana il punteggio COT &egrave; ricalcolato con i <b>soli report disponibili allora</b>; il segnale nasce alla pubblicazione (venerd&igrave; 15:30 di New York, 21:30 in Italia) ed entra alla prima chiusura successiva: da l&igrave; partono il percorso e i risultati.</li>
    <li>Stesse regole del sito per etichette, divergenza, dollaro composito, nascita/conferma/chiusura dei segnali.</li>
    <li>Non incluse: la parte <b>Mercato e macro</b> (30% del punteggio live), le notizie e la stagionalit&agrave;.</li>
    <li>Costi stimati andata e ritorno sottratti: cambi principali ${B.costi.major}%, incroci ${B.costi.cross}%, emergenti ${B.costi.em}%, indici ${B.costi.indici}%, petrolio ${B.costi.energia}%, gas ${B.costi.NATGAS}%, crypto ${B.costi.crypto}%. Swap e rollover esclusi.</li>
    <li>Prezzi solo di chiusura giornaliera (FRED): guadagno e drawdown massimi sono misurati sulle chiusure.</li></ul></details>
   ${blocco(4,"I segnali uno per uno","Gli ultimi segnali simulati conclusi, con ingresso e risultato alle varie durate.",`<div class="grid vfgrid">${(B.ultimi||[]).slice(0,12).map(s=>scheda(s,true)).join("")}</div>`)}`;}

 /* aggiorna SOLO i numeri (non i comandi): cosi' il cursore delle sedute si puo' trascinare senza scatti */
 function aggiorna(){const box=$("vfdati");if(!box)return;box.innerHTML=V.fin=="live"?datiLive():V.fin=="vol"?datiVol():datiBt();
  el.querySelectorAll(".vforz button").forEach(b=>b.classList.toggle("on",b.dataset.h==String(V.d)));
  const t=$("vfgtesto");if(t)t.textContent=durata(V.d);
  const dt=$("vfdurtesto");if(dt)dt.textContent=nomeD();
  box.querySelectorAll(".vfunita button").forEach(b=>b.onclick=()=>{V.unita=b.dataset.u;salva();aggiorna();});
  const alt=$("vfaltro");if(alt)alt.onclick=()=>{$("vfchiusi").innerHTML=R.chiusi.map(s=>scheda(s)).join("");alt.remove();};}

 function disegna(){el.innerHTML=`<h2>Backtest storico</h2><p class="sub">Ogni segnale misurato con prezzi veri dall'uscita dei dati: ingresso alla prima chiusura dopo il segnale, poi quanto va contro (drawdown), quanto guadagna al massimo e come finisce, per la durata del trade che scegli tu (da 1 giorno a 4 settimane, oppure fino al cambio di segnale). L'obiettivo &egrave; capire il rischio: quanto spazio lasciare allo stop rispetto alla volatilit&agrave; di ogni mercato.</p>
  <div class="vfswitch"><button data-f="live" class="${V.fin=="live"?"on":""}">Registro live</button><button data-f="bt" class="${V.fin=="bt"?"on":""}">Backtest <span class="vfsimtag">SIMULATO</span></button><button data-f="vol" class="${V.fin=="vol"?"on":""}">Volatilit&agrave; per asset</button></div>
  <div class="vfcorpo">${V.fin=="live"?live():V.fin=="vol"?volatilitaVista():backtest()}</div>`;
  el.querySelectorAll(".vfswitch button").forEach(b=>b.onclick=()=>{V.fin=b.dataset.f;salva();disegna();});
  el.querySelectorAll(".vforz button").forEach(b=>b.onclick=()=>{V.d=b.dataset.h=="fine"?"fine":+b.dataset.h;const r=$("vfgiorni");if(r&&V.d!="fine")r.value=V.d;salva();aggiorna();});
  el.querySelectorAll(".vfper button").forEach(b=>b.onclick=()=>{V.per=b.dataset.p;el.querySelectorAll(".vfper button").forEach(x=>x.classList.toggle("on",x==b));salva();aggiorna();});
  const r=$("vfgiorni");if(r){r.oninput=()=>{V.d=+r.value;aggiorna();};r.onchange=salva;}
  const sa=$("vfasset");if(sa)sa.onchange=()=>{V.asset=sa.value;salva();aggiorna();};
  const ss=$("vfstrum");if(ss)ss.onchange=()=>{V.strum=ss.value;salva();aggiorna();};
  aggiorna();}
 disegna();})();}catch(e){fail('Backtest storico','verifica',e);}}

/* CARICAMENTO A RICHIESTA (v6.35): sul sito registro live + backtest (~600 KB, piu' di meta' della pagina) stanno in
   un file a parte, terminale/verifica.json (D.verifica = indirizzo), e si scaricano solo la prima volta che si apre
   questa scheda. Cosi' la dashboard si apre molto piu' in fretta, soprattutto da telefono. Sul PC (pagina locale
   aperta da file) i dati restano dentro la pagina: il browser non permette di leggere file vicini. */
(function(){const el=$("verifica");if(!el)return;
 if(D.reg||D.bt||!D.verifica){ebVerifica();return;}
 let stato="";                                           // "" = da caricare, "in corso", "ok"
 const sk=(w,h)=>`<i class="sk" style="width:${w};height:${h}px;display:block;margin-bottom:14px;border-radius:12px"></i>`;
 function carica(){if(stato)return;stato="in corso";
  el.innerHTML=`<h2>Backtest storico</h2>${sk("40%",16)}${sk("100%",120)}${sk("100%",320)}`;
  fetch(D.verifica,{cache:"no-cache"}).then(r=>{if(!r.ok)throw new Error("HTTP "+r.status);return r.json();})
   .then(v=>{D.reg=v.reg;D.bt=v.bt;stato="ok";el.innerHTML="";ebVerifica();})
   .catch(e=>{stato="";console.warn("[BoardEdge] verifica.json:",e);
    el.innerHTML=`<h2>Backtest storico</h2><div class="card" style="padding:18px 20px"><p class="small">I dati della verifica non si sono caricati (connessione). </p><button class="tvbtn vfriprova">Riprova</button></div>`;
    const b=el.querySelector(".vfriprova");if(b)b.onclick=carica;});}
 if(el.classList.contains("on"))carica();
 new MutationObserver(()=>{if(el.classList.contains("on"))carica();}).observe(el,{attributes:true,attributeFilter:["class"]});
})();

