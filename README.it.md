# Clipboard Bridge

[English](README.md) · **Italiano**

![platform](https://img.shields.io/badge/platform-Windows%20%2B%20iPhone-2563eb)
![modes](https://img.shields.io/badge/modalit%C3%A0-Server%20%C2%B7%20Client-6f42c1)
![network](https://img.shields.io/badge/rete-solo%20locale-2ea44f)
![license](https://img.shields.io/badge/licenza-MIT-555)

Condividi gli appunti — testo, immagini e **file di qualsiasi tipo** — tra **Windows e
iPhone** in rete locale, tramite l'app Comandi rapidi (Shortcuts). Niente cloud, niente
account. Interfaccia in **inglese (predefinita)** e in italiano.

## ⚡ Funziona in due modalità distinte

![Modalità Server vs Modalità Client](docs/modes.png)

Si cambia quando vuoi dall'icona nella tray (**clic destro → Modalità**):

| | 🖥️ Modalità Server | 🔌 Modalità Client |
|---|---|---|
| **Chi fa da server** | la **stessa app Windows** | un **server a parte** (PC, NAS, Raspberry Pi, Docker) |
| **L'iPhone si connette a** | il tuo PC, direttamente | il server |
| **Configurazione extra** | nessuna — basta l'interruttore | far girare il server da qualche parte |
| **Pagina web** | no (minimale) | sì |
| **Ideale per** | PC ↔ iPhone al volo, zero setup | sempre disponibile, anche a PC spento o anche tra molteplici PC |

> 📖 **Prima volta?** Segui la [guida passo-passo](GUIDE.md) (in inglese).

## Funzionalità
- Scambio di **testo, immagini e file** di qualsiasi tipo.
- **Cronologia** sul server e sul client.
- **Client Windows** nella tray: invio/ricezione e scorciatoie da tastiera globali.
- **Interfaccia web** del server (utilizzabile anche dal browser dell'iPhone) per
  incollare testo e caricare/scaricare file.
- Integrazione con le **Shortcuts iPhone** tramite semplici richieste HTTP.
- **Nessun server a parte (opzionale):** l'app Windows può fare da server (tray → **Modalità → Server**),
  così l'iPhone si connette direttamente al tuo PC.
- **Token** opzionale per l'API e **password** opzionale per la pagina web.
- Server eseguibile direttamente oppure in **Docker**.

<img width="888" height="650" alt="features" src="https://github.com/user-attachments/assets/6894847e-004d-4f2e-8f5d-9c3c4b226ae7" />

<img width="790" height="1060" alt="settings" src="https://github.com/user-attachments/assets/dfdaafd8-1611-4dfa-8640-33cb9228ab68" />




## Struttura del repository

| File | Descrizione |
|------|-------------|
| `clipboard_bridge-Server.py` | server (Flask): API, interfaccia web, storico |
| `clipboard_bridge_windows.py` | client Windows (icona nella tray) |
| `Dockerfile`, `docker-compose.yml` | esecuzione del server in container |
| `requirements-server.txt`, `requirements-client.txt` | dipendenze |
| `build_client.bat` | compila il client in un singolo `.exe` |
| `icon.ico` | icona dell'applicazione |

> L'eseguibile del client non è incluso nel repository: compilalo con `build_client.bat`
> (vedi sotto) oppure scaricalo dalle Release, se disponibili.

---

## 1. Server

### Esecuzione diretta
```bash
pip install -r requirements-server.txt
python clipboard_bridge-Server.py
```
Il server ascolta su tutte le interfacce, porta **5088**. Apri `http://localhost:5088/`
nel browser per l'interfaccia web.

### Docker
```bash
docker compose up -d --build
```
La cronologia resta nella cartella `./data` e sopravvive ai riavvii. Funziona in
qualsiasi ambiente Docker.

### Opzioni (variabili d'ambiente)

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `CLIPBOARD_PORT` | `5088` | porta di ascolto |
| `CLIPBOARD_TOKEN` | *(vuoto)* | se impostato, l'API (`/clipboard/*`) richiede l'header `X-Auth-Token` |
| `CLIPBOARD_PASSWORD` | *(vuoto)* | se impostato, la pagina web richiede il login (sessione lunga per dispositivo) |
| `CLIPBOARD_MAX_HISTORY` | `200` | numero di elementi tenuti nello storico |
| `CLIPBOARD_DATA_DIR` | `./clipboard_data` | cartella dei dati |

> Per l'uso fuori dalla rete locale imposta un token e usa una VPN o un reverse proxy con
> HTTPS. Sulla rete locale, consenti la porta 5088 nel firewall.

---

## 2. Client Windows

Sostituisci `SERVER_IP` con l'indirizzo del computer su cui gira il server.

### Eseguibile
Compila il client con `build_client.bat` (richiede Python). Otterrai
`dist\Clipboard Bridge.exe`, che puoi avviare senza installare nulla.

### Da sorgente
```bash
pip install -r requirements-client.txt
python clipboard_bridge_windows.py
```

Compare un'icona nella tray (clic destro per il menu):
- **Invia appunti -> server** / **Ricevi ultimo <- server** (testo, immagini, file).
- **Invia un file...** e **Apri cartella ricevuti** (i file ricevuti finiscono in `ricevuti`).
- **Cronologia...**, **Scorciatoie da tastiera** (default `Ctrl+Alt+C` invia, `Ctrl+Alt+V` riceve).
- **Lingua** (English / Italiano) e **Impostazioni...** (IP, porta, token del server).

### Avvio automatico
`Win+R` -> `shell:startup` e metti lì un collegamento all'eseguibile.

---

## 3. Interfaccia web

Aprendo l'indirizzo del server in un browser (anche da iPhone) trovi una pagina da cui
puoi incollare testo, caricare e scaricare file e leggere le istruzioni per le Shortcut.
Con il token: `http://SERVER_IP:5088/?token=IL_TUO_TOKEN`. Aggiungi `?lang=it` per l'italiano.

---

## 4. iPhone (Comandi rapidi)

Crea dei comandi con l'azione **Ottieni contenuto dell'URL**. Se usi un token, aggiungi
l'intestazione `X-Auth-Token`.
- **Invio Generale** - POST to `http://SERVER_IP:5088/clipboard` (Request body : File, File -> Clipboard).
- **Ricezione Generale** - GET contents of `http://SERVER_IP:5088/clipboard/latest/raw`(Method : GET ; Copy "Contents of URL" to clipboard).
- **Invia testo** — POST a `http://SERVER_IP:5088/clipboard/text` (corpo JSON, campo `text`).
- **Ricevi testo** — GET a `http://SERVER_IP:5088/clipboard/text/raw`, poi *Copia negli appunti*.
- **Invia foto/file** — POST a `http://SERVER_IP:5088/clipboard/image` (corpo: File).
- **Ricevi immagine** — GET a `http://SERVER_IP:5088/clipboard/image/latest/raw`, poi *Salva nell'album*.

---

## 5. API del server

| Metodo | Endpoint | Descrizione |
|--------|----------|-------------|
| GET | `/health` | stato del server (pubblico) |
| POST | `/clipboard` | salva qualsiasi cosa (testo o binario), tipo rilevato in automatico |
| POST | `/clipboard/text` | salva testo (JSON, form o corpo grezzo) |
| GET | `/clipboard/text/raw` | ultimo testo come text/plain |
| POST | `/clipboard/image` | salva un file/immagine (base64, multipart o binario) |
| GET | `/clipboard/image/latest/raw` | ultima immagine come binario |
| POST | `/clipboard/file` | salva un file (JSON `{filename, data}`) |
| GET | `/clipboard/latest` | ultimo elemento di qualsiasi tipo, contenuto incluso |
| GET | `/clipboard/latest/raw` | ultimo elemento (qualsiasi tipo) come contenuto grezzo |
| GET | `/clipboard/history?limit=N` | elenco dello storico (metadati) |
| GET/DELETE | `/clipboard/item/<id>` | legge o elimina un elemento |
| DELETE | `/clipboard/history` | svuota lo storico |

---

## Compilare l'eseguibile del client

```bash
build_client.bat
```
Usa PyInstaller per produrre `dist\Clipboard Bridge.exe`. Per cambiare icona, sostituisci
`icon.ico` con la tua e rilancia lo script.

## Licenza

Distribuito con licenza [MIT](LICENSE).
