# Velocità e precisione — 16 ottobre 2026

Misure su questo PC: D1 Q8_0, Ollama 0.40.4 sulla porta 11435, GTX 1050 4 GB.
L'API `/api/ps` riportava circa 2.5 GB di modello in VRAM: non è una GPU che ospita
comodamente tutto il percorso multimodale. Non sono stati modificati modello, pesi o servizio Ollama.

## Problema riprodotto

Nel test Pi dell'utente, le chiamate `visual_assert` e `smart_type` richiedevano circa
25–28 secondi. I tentativi di individuare la ricerca si fermavano per bassa confidenza.
Il benchmark iniziale sulla pagina sintetica densa, con immagine 1280×800, ha riprodotto
il problema: `wait_until_ready` 24.247 s, `smart_type` 26.795 s, ricerca non compilata.
Il risultato iniziale è registrato in `before.json` (una misura, versione precedente).

## Confronto sulla stessa pagina sintetica

| Passaggio | Prima | Dopo, modalità hybrid |
|---|---:|---:|
| Readiness | 24.247 s, D1 | Circa 1–10 ms, DOM |
| Compilazione e invio ricerca | 26.795 s, fallito | Circa 0.17–0.26 s, verificato |
| Chiamate D1 nella sequenza | 2 | 0 |
| Campo corretto e invio verificati nel DOM | No | Sì, 3/3 prove |

Le misure finali esatte sono in `after.json`. Questo è il tempo dei tool, esclusi
ragionamento del modello principale, rete Amazon e caricamento dei risultati.
Il confronto non rappresenta un fattore di accelerazione fra due ricerche entrambe riuscite:
la versione iniziale falliva la selezione, quella ottimizzata completa la sequenza.

Forzando `D1_BROWSER_STRATEGY=vision`, la versione nuova usa ancora D1:
readiness circa 4.1 s, digitazione/invio circa 2.6 s, ricerca corretta.
Le misure sono in `after-vision.json`. L'immagine complessiva è ridotta a 768×480;
per la digitazione il modello riceve un ritaglio 646×115 con il campo e il contesto.
La riduzione è configurabile: `D1_IMAGE_MAX_SIDE=1024` per più dettaglio, `0` per disattivarla.

## Prova Amazon.it reale

Una prova ha caricato la homepage in 2.055 s e inviato la ricerca in 3.979 s tramite D1,
con `typed_verified=true` e navigazione a `/s?k=taglia+capelli+professionale`.
Il target generico non coincideva esattamente con l'etichetta reale `Cerca Amazon.it`,
quindi è intervenuto il fallback visivo (`amazon-after-vision.json`).

Altre richieste hanno ricevuto una challenge AWS WAF, HTTP 202, pagina visibile vuota.
La prova più recente registra `status=blocked`, `block_reason=waf_challenge`, apertura
1.326 s e arresto immediato della ricerca, senza inferenza (`amazon-after.json`).
Non è possibile garantire tempi costanti o completamento sul sito quando interviene questo controllo.
Il server segnala il blocco; non tenta di superarlo. La navigazione alla URL di ricerca
prova l'invio, non la disponibilità o correttezza dei prodotti restituiti.

## Precisione e verifiche

- Match DOM solo per etichette esplicite univoche o ruolo searchbox univoco in richieste generiche.
- Nomi duplicati non vengono risolti scegliendo arbitrariamente il primo elemento.
- Solo elementi editabili per `smart_type`; sostituzione del contenuto e verifica esatta prima di Invio.
- Riferimenti ai nodi DOM, revalidati per identità, etichetta, collegamento, stato e visibilità.
- Un nodo rimosso, rinominato o coperto non riceve il vecchio click.
- Probabilità visive deboli riportate come `answer=null`, `certain=false`.
- Screenshot interrotto dopo un'azione riuscita riportato come verifica pendente, evitando invii ripetuti.
- 33 test automatici passati, inclusi browser headless e protocollo MCP stdio.
- Configurazione Pi aggiornata; `pi mcp list --json`: connected, sei tool, nessun errore.

Riproduzione:

```bash
D1_BENCH_RUNS=3 .venv/bin/python benchmarks/browser_speed.py benchmarks/after.json
D1_BROWSER_STRATEGY=vision .venv/bin/python benchmarks/browser_speed.py benchmarks/after-vision.json
.venv/bin/python benchmarks/amazon_search.py
.venv/bin/python -m pytest -q
```

[Comportamento ufficiale degli header e status AWS WAF](https://docs.aws.amazon.com/waf/latest/developerguide/waf-captcha-and-challenge-actions.html)
