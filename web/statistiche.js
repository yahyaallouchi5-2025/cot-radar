/* =====================================================================================================
   statistiche.js - STATISTICHE DI VISITA ANONIME, SENZA COOKIE (landing page + terminale)
   Inserito da Python al posto del segnaposto STATISTICHE tra doppie graffe (vedi pagina.statistiche()).

   COSA MISURA (per capire come si usa il sito e migliorarlo):
     - visite e pagine viste (automatico): quanti visitatori, da dove arrivano, telefono o PC;
     - EVENTI = i click che contano: pass gratuito, Telegram, schede del terminale, grafici aperti, filtri...
     - SEZIONI VISTE della landing (fin dove si scorre la pagina, una volta per visita);
     - ERRORI delle sezioni del terminale (per scoprire bug che i visitatori vedono e noi no).
   PRIVACY: fornitore Umami (cloud.umami.is), senza cookie e senza dati personali: niente banner da accettare.
     Nessun testo scritto dall'utente viene inviato, solo nomi fissi di eventi e valori dei pulsanti.
   SPENTO quando config.STATISTICHE_ID e' vuoto, oppure fuori dal sito pubblicato (file aperto in locale, prove):
     in quel caso ebStat.ev() non fa nulla e la pagina funziona identica.
   AGGIUNGERE UN EVENTO: in HTML basta  data-ev="nome"  (piu' eventualmente data-pos="dove") sull'elemento;
     da JavaScript: ebStat.ev("nome", {chiave: "valore"}).
   DEBUG (console del browser): ebStat.attivo, ebStat.coda  |  ?statdebug nell'indirizzo = stampa ogni evento.
   ===================================================================================================== */
(function(){
 var ID="__STAT_ID__";                                   // sostituito da Python (stringa vuota = statistiche spente)
 var DOMINIO="yahyaallouchi5-2025.github.io";            // si conta solo il sito vero, mai le prove in locale
 var debug=/[?&]statdebug/.test(location.search);
 var attivo=!!ID&&location.hostname==DOMINIO;
 var coda=[];                                            // eventi arrivati prima che lo script di Umami sia pronto

 function invia(nome,dati){
  if(debug)console.log("[statistiche]",nome,dati||{});
  if(!attivo)return;
  if(window.umami&&umami.track){try{umami.track(nome,dati);}catch(e){}}
  else if(coda.length<50)coda.push([nome,dati]);
 }
 window.ebStat={ev:invia,attivo:attivo,coda:coda};
 if(!attivo)return;

 // script di Umami: visite e pagine viste automatiche; data-domains = conta solo sul dominio del sito
 var s=document.createElement("script");
 s.defer=true;s.src="https://cloud.umami.is/script.js";
 s.setAttribute("data-website-id",ID);s.setAttribute("data-domains",DOMINIO);
 s.onload=function(){var c=coda.splice(0);c.forEach(function(x){invia(x[0],x[1]);});};
 document.head.appendChild(s);
})();

/* ---------- CLICK: regole in ordine, vince la prima che corrisponde ----------
   Ascolto in fase di "cattura": l'evento si registra anche se poi il pulsante cambia pagina o ridisegna la scheda. */
(function(){
 function testo(el){return (el.textContent||"").replace(/\s+/g," ").trim().slice(0,40);}
 function pos(el){var p=el.closest("[data-pos]");return p?p.dataset.pos:(el.id||el.className||"").toString().split(" ")[0]||"pagina";}
 var REGOLE=[
  // --- comuni / landing ---
  ["[data-ev]",          function(el){return [el.dataset.ev,{pos:pos(el)}];}],
  ["[data-entra]",       function(el){return ["pass",{pos:pos(el)}];}],
  ["a[href*='t.me/']",   function(el){return ["telegram",{pos:pos(el)}];}],
  ["header nav a[href^='#']",function(el){return ["menu",{voce:el.getAttribute("href").slice(1)}];}],
  // --- terminale ---
  ["#nav button[data-t]",function(el){return ["scheda",{nome:el.dataset.t}];}],
  ["[data-vai]",         function(el){return ["scheda",{nome:el.dataset.vai,da:"link"}];}],
  ["#filters button",    function(el){return ["filtro",{gruppo:"coppie",valore:testo(el)}];}],
  ["#sfilters button",   function(el){return ["filtro",{gruppo:"mercati",valore:testo(el)}];}],
  ["#cfilters button",   function(el){return ["filtro",{gruppo:"correlazioni",valore:testo(el)}];}],
  ["#tviv button",       function(el){return ["grafico_intervallo",{iv:el.dataset.iv}];}],
  ["#tvfull",            function(){return ["grafico_schermo_intero"];}],
  ["#tvlink",            function(){return ["tradingview"];}],
  [".vfswitch button",   function(el){return ["backtest_vista",{vista:el.dataset.f}];}],
  [".vforz button",      function(el){return ["backtest_durata",{giorni:el.dataset.h}];}],
  [".stagbtn",           function(el){return ["stagionalita",{mercato:el.dataset.k}];}],
  ["#gapri",             function(){return ["guida"];}],
  ["#evtutti",           function(){return ["eventi_tutti"];}],
  ["button.info",        function(el){return ["info",{voce:(el.getAttribute("aria-label")||el.title||"").slice(0,40)}];}],
  // card cliccabile = grafico a candele (come app.js: non se il click e' su un pulsante o link dentro la card)
  ["[data-tv]",          function(el,t){return t.closest("button,a,input")?null:["grafico",{strumento:el.dataset.tv.slice(2),tipo:el.dataset.tv[0]=="p"?"coppia":"mercato"}];}]
 ];
 document.addEventListener("click",function(ev){var t=ev.target;if(!t||!t.closest)return;
  for(var i=0;i<REGOLE.length;i++){var el=t.closest(REGOLE[i][0]);if(!el)continue;
   var r=REGOLE[i][1](el,t);if(r){ebStat.ev(r[0],r[1]);return;}}},true);

 /* ---------- SEZIONI VISTE (landing): data-ev-vista="nome" -> evento "sezione" una sola volta per pagina ---------- */
 var viste=document.querySelectorAll("[data-ev-vista]");
 if(viste.length&&"IntersectionObserver" in window){
  var io=new IntersectionObserver(function(v){v.forEach(function(x){if(!x.isIntersecting)return;
   ebStat.ev("sezione",{nome:x.target.dataset.evVista});io.unobserve(x.target);});},{threshold:.35});
  viste.forEach(function(x){io.observe(x);});}
})();
