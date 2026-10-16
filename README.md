# Flash computer use

Server **MCP (Model Context Protocol)** in Python ad alte prestazioni per il controllo completo di **browser web** e **desktop fisico** (Linux, Windows, macOS).

Progettato per essere **veloce**, **preciso** e **naturale**:
- **Strategia Ibrida (`hybrid`)**: combina l'accesso istantaneo al DOM (browser) e agli alberi di accessibilità nativi del sistema operativo (desktop) con il fallback visivo decisionale **LiquidAI D1** (**Ollama**, **Transformers locale** o **API System One**).
- **Movimento umano del mouse reale (Web + Desktop)**: sposta sempre il puntatore fisico del sistema operativo lungo una curva fluida **minimum-jerk** ($10t^3 - 15t^4 + 6t^5$) con lieve arco naturale del polso e atterraggio esatto al pixel, sincronizzando automaticamente le coordinate del browser con quelle dello schermo reale.
- **Disegno e trascinamento su Paint e `<canvas>`**: rileva automaticamente il foglio da disegno bianco/chiaro nei programmi di grafica desktop (es. MS Paint, KolourPaint, Pinta) o gli elementi `<canvas>` nel browser, permettendo di trascinare il mouse (`mouse_drag`), disegnare a mano libera o a tratti multipli (`draw_path`) e tracciare 12 forme geometriche pronte (`draw_shape`).

---

## Indice

1. [Requisiti di sistema](#1-requisiti-di-sistema)
2. [Installazione passo-passo](#2-installazione-passo-passo)
3. [Avvio e configurazione di Ollama (Modello D1)](#3-avvio-e-configurazione-di-ollama-modello-d1)
4. [Come configurare l'MCP nei client (Cursor, Claude, Codex, Antigravity, Pi)](#4-come-configurare-lmcp-nei-client-cursor-claude-codex-antigravity-pi)
5. [Variabili d'ambiente e parametri di configurazione](#5-variabili-dambiente-e-parametri-di-configurazione)
6. [Elenco completo dei 15 Tool MCP](#6-elenco-completo-dei-15-tool-mcp)
7. [Uso con programmi di disegno (Paint, KolourPaint, Canvas Web)](#7-uso-con-programmi-di-disegno-paint-kolourpaint-canvas-web)
8. [Supporto Multi-Piattaforma (Linux, Windows, macOS)](#8-supporto-multi-piattaforma-linux-windows-macos)
9. [Test e Benchmark](#9-test-e-benchmark)

---

## 1. Requisiti di sistema

- **Python**: `>= 3.11`
- **Gestore pacchetti**: [`uv`](https://docs.astral.sh/uv/) (consigliato) oppure `pip`
- **Provider decisionale (uno a scelta)**:
  - **Ollama** (consigliato, locale): versione con supporto `/v1/systemone` (es. `>= 0.40`) e modello `d1:3b`
  - **Transformers locale**: GPU CUDA / Apple MPS / CPU con modello `LiquidAI/d1-3B`
  - **Cloud API**: endpoint compatibile con `/v1/systemone`
- **Prerequisiti Desktop per sistema operativo**:
  - **Linux**: sessione grafica **X11** (`DISPLAY` attivo) e `xclip` o `xsel` per l'inserimento rapido di testo Unicode negli appunti.
  - **Windows**: desktop interattivo sbloccato (la consapevolezza DPI Per-Monitor viene attivata automaticamente dal server).
  - **macOS**: permessi di **Accessibilità** e **Registrazione schermo** concessi al terminale o al client MCP.

---

## 2. Installazione passo-passo

### Linux / macOS

```bash
git clone https://github.com/<TUO_USERNAME>/flash-computer-use.git
cd flash-computer-use

# 1. Crea l'ambiente virtuale e installa le dipendenze
uv venv
uv pip install -e '.[dev]'

# 2. Installa il browser Chromium per Playwright
PLAYWRIGHT_BROWSERS_PATH=.runtime/playwright .venv/bin/python -m playwright install chromium
```

### Windows (PowerShell)

```powershell
git clone https://github.com/<TUO_USERNAME>/flash-computer-use.git
cd flash-computer-use

uv venv
uv pip install -e ".[dev,accessibility]"
$env:PLAYWRIGHT_BROWSERS_PATH=".runtime\playwright"
.\.venv\Scripts\python.exe -m playwright install chromium
```

---

## 3. Avvio e configurazione di Ollama (Modello D1)

Il server usa il modello decisionale multimodale **`d1:3b`** tramite l'endpoint nativo `/v1/systemone` di Ollama (zero token generati, decisioni calibrate `noul`, `choice`, `score`).

```bash
# Scarica il modello D1
ollama pull d1:3b

# Verifica lo stato del sistema e delle dipendenze
.venv/bin/flash-doctor

# Verifica che l'inferenza D1 risponda correttamente
D1_PROVIDER=ollama D1_MODEL_NAME=d1:3b .venv/bin/flash-check --inference
```

> **Nota**: se Ollama è in esecuzione su una porta diversa da quella predefinita (es. `11435`), passa `D1_OLLAMA_BASE_URL=http://127.0.0.1:11435`.

---

## 4. Come configurare l'MCP nei client (Cursor, Claude, Codex, Antigravity, Pi)

### Generazione automatica della configurazione JSON

Puoi generare in qualsiasi momento il blocco JSON pronto con il percorso esatto del tuo interprete Python eseguendo:

```bash
.venv/bin/flash-config --ollama-url http://localhost:11434
```

Per salvarlo direttamente su file:

```bash
.venv/bin/flash-config --ollama-url http://localhost:11434 --output mcp.json
```

---

### A. Cursor / Claude Desktop / Google Antigravity (`mcp.json` / `claude_desktop_config.json`)

Aggiungi questo blocco nel file di configurazione MCP del client (vedi anche [`examples/mcp.ollama.json`](examples/mcp.ollama.json)):

```json
{
  "mcpServers": {
    "Flash computer use": {
      "command": "/percorso/assoluto/flash-computer-use/run-mcp.sh",
      "env": {
        "D1_PROVIDER": "ollama",
        "D1_MODEL_NAME": "d1:3b",
        "D1_OLLAMA_BASE_URL": "http://localhost:11434",
        "D1_TIMEOUT_SECONDS": "120",
        "D1_BROWSER_STRATEGY": "hybrid",
        "D1_DESKTOP_STRATEGY": "hybrid",
        "D1_IMAGE_MAX_SIDE": "768",
        "D1_REAL_MOUSE": "true",
        "D1_MOUSE_DURATION": "0.04"
      }
    }
  }
}
```

*(Su **Windows**, usa `"C:\\percorso\\assoluto\\flash-computer-use\\run-mcp.cmd"` come `command`).*

---

### B. OpenAI Codex CLI (`~/.codex/config.toml`)

Puoi registrarlo da terminale con un solo comando:

```bash
codex mcp add "Flash computer use" \
  --env D1_PROVIDER=ollama \
  --env D1_MODEL_NAME=d1:3b \
  --env D1_OLLAMA_BASE_URL=http://localhost:11434 \
  --env D1_TIMEOUT_SECONDS=120 \
  --env D1_BROWSER_STRATEGY=hybrid \
  --env D1_DESKTOP_STRATEGY=hybrid \
  -- '/percorso/assoluto/flash-computer-use/run-mcp.sh'
```

Oppure copia il contenuto di [`examples/codex.ollama.toml`](examples/codex.ollama.toml) nel tuo `~/.codex/config.toml`:

```toml
[mcp_servers."Flash computer use"]
command = "/percorso/assoluto/flash-computer-use/run-mcp.sh"
startup_timeout_sec = 30
tool_timeout_sec = 120

[mcp_servers."Flash computer use".env]
D1_PROVIDER = "ollama"
D1_MODEL_NAME = "d1:3b"
D1_OLLAMA_BASE_URL = "http://localhost:11434"
D1_TIMEOUT_SECONDS = "120"
D1_BROWSER_STRATEGY = "hybrid"
D1_DESKTOP_STRATEGY = "hybrid"
D1_IMAGE_MAX_SIDE = "768"
```

---

### C. Claude Code CLI

```bash
claude mcp add --transport stdio \
  --env D1_PROVIDER=ollama \
  --env D1_MODEL_NAME=d1:3b \
  --env D1_OLLAMA_BASE_URL=http://localhost:11434 \
  "Flash computer use" -- '/percorso/assoluto/flash-computer-use/run-mcp.sh'
```

---

## 5. Variabili d'ambiente e parametri di configurazione

Un template completo è disponibile in [`.env.example`](.env.example).

| Variabile | Default | Descrizione |
|---|---|---|
| `D1_PROVIDER` | `local` | Provider di inferenza: `ollama`, `local` (Transformers) o `api` |
| `D1_MODEL_NAME` | `d1:3b` / `LiquidAI/d1-3B` | Nome modello su Ollama (`d1:3b`) o HuggingFace / Cloud API |
| `D1_OLLAMA_BASE_URL` | `http://localhost:11434` | Indirizzo del server Ollama |
| `D1_OLLAMA_KEEP_ALIVE` | `10m` | Durata di permanenza del modello in VRAM/RAM |
| `D1_API_BASE_URL` | — | URL endpoint `/v1/systemone` quando `D1_PROVIDER=api` |
| `D1_API_KEY` | — | Chiave di autenticazione per `D1_PROVIDER=api` |
| `D1_TIMEOUT_SECONDS` | `60` | Timeout massimo per chiamata al provider |
| `D1_BROWSER_STRATEGY` | `hybrid` | `hybrid`: DOM istantaneo + fallback visivo D1; `vision`: usa sempre D1 |
| `D1_DESKTOP_STRATEGY` | `hybrid` | `hybrid`: Accessibilità nativa SO + fallback D1; `vision`: usa sempre D1 |
| `D1_IMAGE_MAX_SIDE` | `768` | Lato massimo in pixel delle immagini inviate a D1 (`0` disabilita il resize) |
| `D1_CONFIDENCE_THRESHOLD` | `0.65` | Confidenza minima richiesta prima di eseguire un click |
| `D1_BROWSER_HEADLESS` | `false` | `false` mostra la finestra del browser; `true` esegue in background |
| `D1_BROWSER_CDP_URL` | — | Endpoint CDP opzionale (es. `http://localhost:9222`) per collegarsi a un browser già aperto |
| `D1_BROWSER_PAGE_URL` | — | URL esatto della scheda da usare se CDP espone più schede |
| `D1_MONITOR` | `1` | Indice del monitor MSS da catturare in modalità `desktop` |
| `D1_REAL_MOUSE` | `true` | Sposta sempre il puntatore fisico reale del SO anche durante le azioni sul browser visibile (`false` per disattivare, `always` anche in headless) |
| `D1_MOUSE_DURATION` | `0.04` | Durata in secondi del movimento umano minimum-jerk del puntatore |

---

## 6. Elenco completo dei 15 Tool MCP

Tutti i tool sono serializzati tramite lock asincrono e restituiscono JSON compatti con il tempo di esecuzione `elapsed_ms`.

### Browser & Navigazione
1. **`browser_open(url)`**: apre un URL e restituisce titolo, stato `ready`, elenco delle etichette dei campi di input, anteprima testuale ed eventuali popup visibili.
2. **`handle_popup(action="inspect" | "reject" | "accept" | "dismiss", max_scrolls=8)`**: ispeziona o gestisce banner cookie, dialog modali e pagine di consenso (scorrendo automaticamente i termini se il pulsante si abilita a fondo testo).
3. **`browser_scroll(direction="down" | "up", pixels=600, container="auto" | "popup" | "page")`**: scorre il contenitore del popup attivo o la pagina principale.

### Azioni Intelligenti (`mode="browser"` oppure `mode="desktop"`)
4. **`smart_click(target_description, mode="browser", double_click=False)`**: individua l'elemento (tramite DOM/accessibilità o Set-of-Mark / griglia gerarchica D1), muove il puntatore fisico lungo una curva umana e clicca sul punto non ostruito.
5. **`smart_move(target_description, mode="desktop")`**: individua l'elemento e vi posiziona il puntatore del mouse senza cliccare (hover).
6. **`smart_type(target_description, text_to_type, press_enter=True, mode="browser")`**: seleziona un campo di testo editabile, sostituisce il contenuto precedente, verifica che il testo sia stato scritto correttamente (`typed_verified=true`) e preme Invio.
7. **`scroll_until_visible(target_description, direction="down", max_scrolls=8, mode="browser")`**: scorre gradualmente finché il bersaglio non è visibile con probabilità $\ge 0.80$.
8. **`visual_assert(questions, mode="browser")`**: valuta da 1 a 64 domande binarie sullo stato visivo corrente in una sola chiamata.
9. **`wait_until_ready(timeout_seconds=10, mode="browser")`**: attende la stabilità del DOM o la conferma visiva che l'interfaccia sia pronta.
10. **`desktop_inspect()`**: restituisce informazioni di portabilità sul sistema operativo, l'elenco degli elementi accessibili del desktop e le coordinate del foglio di disegno (`canvas_bounds`).

### Controllo Diretto del Mouse e Disegno (`Paint` / `Canvas`)
11. **`mouse_move(x, y, duration=0.04, mode="desktop")`**: muove il puntatore alle coordinate `(x, y)` con traiettoria umana minimum-jerk.
12. **`mouse_click(x=None, y=None, button="left", double_click=False, mode="desktop")`**: esegue un click (`left`, `right`, `middle`) sul posto o dopo essersi spostato in `(x, y)`.
13. **`mouse_drag(start_x, start_y, end_x, end_y, button="left", duration=0.12, mode="desktop")`**: porta il mouse su `(start_x, start_y)`, tiene premuto il pulsante, trascina fluidamente fino a `(end_x, end_y)` e rilascia il tasto.
14. **`draw_path(points, canvas_bounds=None, duration=0.4, mode="desktop")`**: disegna sul foglio trascinando il mouse. Accetta sia un singolo tratto `[[x, y], ...]` sia **tratti multipli** `[[[x, y], ...], ...]` (sollevando il tasto del mouse tra un tratto e l'altro). Se `canvas_bounds` è omesso, rileva automaticamente il foglio di disegno.
15. **`draw_shape(shape, x=None, y=None, width=None, height=None, canvas_bounds=None, duration=0.4, mode="desktop")`**: disegna una forma geometrica pronta sul foglio attivo (centrandola automaticamente se `x, y, width, height` o `canvas_bounds` vengono omessi).

---

## 7. Uso con programmi di disegno (Paint, KolourPaint, Canvas Web)

**Flash computer use** è progettato per interagire con applicazioni di grafica come farebbe una persona:

- **Rilevamento automatico del foglio (`canvas_bounds`)**: quando apri Paint, KolourPaint, Pinta o una pagina web con `<canvas>`, non serve calcolare manualmente i bordi del foglio. Il server individua automaticamente l'area di disegno più ampia (tramite ruolo di accessibilità o analisi istogramma rettangolare dello screenshot).
- **Interpolazione continua dei tratti**: durante il trascinamento, i segmenti lunghi vengono suddivisi in passi ravvicinati (~6–8 px) così che il pennello di Paint tracci linee continue senza interruzioni o punti saltati.
- **Forme supportate da `draw_shape`**:
  - `line`, `rectangle`, `ellipse`, `circle`, `triangle`, `diamond`, `star`, `arrow`, `heart`, `house`, `spiral`, `wave`.
- **Rilascio sicuro del pulsante**: ogni operazione di trascinamento e disegno garantisce il rilascio del pulsante del mouse (`mouseUp`) in un blocco `finally`, anche in caso di errore.

---

## 8. Supporto Multi-Piattaforma (Linux, Windows, macOS)

| Sistema Operativo | Accessibilità Nativa | Gestione Coordinate e DPI | Digitazione Testo |
|---|---|---|---|
| **Linux (X11)** | AT-SPI (`gi.repository.Atspi`) | Coordinate X11 dirette | Appunti `xclip` / `xsel` + `Ctrl+V` o fallback `pyautogui.write` |
| **Windows** | UI Automation (`pywinauto` / PowerShell UIA) | Attivazione automatica Per-Monitor DPI Awareness (`shcore` / `user32`) | Appunti `Set-Clipboard` + `Ctrl+V` o fallback `pyautogui.write` |
| **macOS** | Accessibility API (`ApplicationServices` / `osascript`) | Riscalatura automatica tra pixel fisici Retina (`mss`) e punti logici (`pyautogui`) | Appunti `pbcopy` + `Cmd+V` o fallback `pyautogui.write` |

---

## 9. Test e Benchmark

Per eseguire l'intera suite di test automatici (68 test che coprono protocollo MCP stdio, motore D1, browser headless, disegno su `<canvas>`, traiettorie umane del mouse e portabilità multi-OS):

```bash
.venv/bin/python -m pytest -q
```

I dettagli sui benchmark di velocità e precisione sono documentati in [`benchmarks/REPORT.md`](benchmarks/REPORT.md).

---

## Licenza

Distribuito sotto licenza [MIT](LICENSE).
