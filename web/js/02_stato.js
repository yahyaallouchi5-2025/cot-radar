/* ---------- stato fonti e avvisi ----------
   Un riquadro per fonte (pallino verde/giallo/rosso) e, sotto, gli avvisi in chiaro.
   Se l'ora attuale supera la prossima uscita prevista (next_ms), la pagina avvisa che ci sono dati nuovi. */
try{
$("updated").innerHTML=`<span class="dataagg" title="Ultimo aggiornamento dei dati">${M.now}</span>`;
var DOT={ok:"var(--b)",cache:"var(--warn)",late:"var(--s)",err:"var(--s)"};
var STX={ok:"aggiornato",cache:"dati salvati (offline)",late:"IN RITARDO",err:"errore"};
/* stato delle fonti nella sidebar: pallino + nome, sotto data e prossimo aggiornamento (a barra ridotta resta il pallino) */
$("status").innerHTML=D.sources.filter(s=>s.st!="err").map(s=>`<div class="srow" title="${esc(s.name)}: ${esc(s.last)} (${STX[s.st]}) - prossimo: ${esc(s.next)}"><i style="background:${DOT[s.st]};color:${DOT[s.st]}"></i>
 <div class="stx"><b>${s.name}</b><small>${s.last} &middot; ${STX[s.st]}</small><small>Prossimo: ${s.next}</small></div></div>`).join("");
/* ERRORI DI DOWNLOAD (righe "Download ..."): MAI una barra rossa per gli utenti. Il dettaglio tecnico resta nel registro
   admin; solo se un'intera fonte e' ferma (s.grave) compare il popup di manutenzione con il codice (es. "Errore server 504").
   Lo stesso per FRED "in manutenzione": la pagina usa gli ultimi dati validi senza allarmare. */
var gravi=D.sources.filter(s=>/^Download /.test(s.name)&&(s.grave||/manutenzione/.test(s.msg||"")));
if(gravi.length)setTimeout(()=>{try{window.ebManutenzione&&ebManutenzione({scheda:"sig",codice:gravi[0].codice||"503",
 quando:(D.stato&&D.stato.creato)||"",dal:""});}catch(e){}},0);       // dopo: ebManutenzione e' definita in 20_manutenzione.js
var al=[];D.sources.forEach(s=>{if(s.msg&&!/^Download /.test(s.name))al.push(`<div class="alert ${s.st=='late'||s.st=='err'?'red':''}"><b>${s.name}:</b> ${esc(s.msg)}</div>`);
 if(s.next_ms&&Date.now()>s.next_ms&&!/^https?:/.test(location.protocol))al.push(`<div class="alert red"><b>${s.name}:</b> sono usciti dati nuovi (${s.next}) dopo questo aggiornamento. ${/^https?:/.test(location.protocol)?"Il sito si aggiorna in automatico a breve.":"Riapri cot_radar.py per scaricarli."}</div>`);});
if(M.demo)al.unshift(`<div class="alert red"><b>DATI DIMOSTRATIVI:</b> pagina creata con --demo, i numeri sono finti.</div>`);
$("alerts").innerHTML=al.join("");
}catch(e){fail('Stato fonti e avvisi','alerts',e);}

