# Clipboard Bridge App Store

[English](README.md) | **Italiano**

Questa repository contiene il catalogo per installare
[Clipboard Bridge](https://github.com/mattbox03/Clipboard-Bridge) con un clic.

## ZimaOS: aggiungere lo store

Usa sempre questo indirizzo:

```text
https://github.com/mattbox03/Clipboard-Bridge-AppStore/archive/refs/heads/main.zip
```

L’indirizzo non contiene numeri di versione: scarica sempre il branch `main` e
rimane invariato quando il catalogo viene aggiornato.

### Procedura passo passo

1. Apri **App Store** in ZimaOS.
2. Apri la gestione delle sorgenti o degli store personalizzati.
3. Premi **Aggiungi sorgente**.
4. Incolla per intero l’indirizzo `main.zip` indicato sopra.
5. Conferma e attendi la fine dell’importazione.
6. Riavvia ZimaOS se la sorgente non viene aggiornata immediatamente.
7. Riapri l’App Store.
8. Cerca **Clipboard Bridge** oppure apri la categoria **Utilities**.
9. Seleziona l’applicazione e premi **Installa**.
10. Al termine apri `http://IP-ZIMA:5088`.

Sostituisci `IP-ZIMA` con l’indirizzo locale del dispositivo, per esempio:

```text
http://192.168.1.50:5088
```

Non usare come sorgente la normale pagina GitHub: è HTML e non un archivio ZIP.

## Prima configurazione

L’installazione predefinita funziona senza credenziali nella rete locale.
Per proteggerla, modifica in ZimaOS le variabili dell’app:

| Variabile | Funzione | Esempio |
|---|---|---|
| `CLIPBOARD_PASSWORD` | Password della pagina web | `cambia-questa-password` |
| `CLIPBOARD_TOKEN` | Token per client Windows e iPhone | `cambia-questo-token` |
| `CLIPBOARD_ACCOUNTS` | Utenti isolati aggiuntivi | `alice:pass1,bob:pass2` |
| `CLIPBOARD_MAX_HISTORY` | Elementi massimi nello storico | `200` |

La clipboard generale rimane sempre disponibile. Ogni account aggiuntivo ha
cronologia e file separati.

## Windows e iPhone

Nel client Windows imposta:

- indirizzo server: IP locale di ZimaOS;
- porta: `5088`;
- token: valore di `CLIPBOARD_TOKEN`;
- account e password: vuoti per la clipboard generale, oppure credenziali di un
  account aggiuntivo.

I due endpoint universali per Comandi Rapidi iPhone sono:

```text
POST http://IP-ZIMA:5088/clipboard
GET  http://IP-ZIMA:5088/clipboard/latest/raw
```

Per usare un account isolato aggiungi alla fine:

```text
?user=alice&password=pass1
```

Esempio completo:

```text
http://192.168.1.50:5088/clipboard/latest/raw?user=alice&password=pass1
```

## Aggiornamento

L’indirizzo dello store non cambia mai:

1. aggiorna la sorgente personalizzata in ZimaOS;
2. se manca il pulsante di aggiornamento, rimuovi e reinserisci lo stesso URL;
3. riavvia ZimaOS se continua a mostrare la copia in cache;
4. installa l’aggiornamento proposto per Clipboard Bridge.

## Backup

I dati persistenti sono salvati in:

```text
/DATA/AppData/clipboard-bridge/data
```

Esegui il backup dell’intera cartella. Contiene cronologia, file caricati,
account e chiave delle sessioni. Per ripristinarla, arresta l’app, rimetti la
cartella al suo posto e riavvia Clipboard Bridge.

## Risoluzione problemi

**La sorgente viene accettata ma l’app non appare**

1. Verifica che l’URL termini con `/archive/refs/heads/main.zip`.
2. Elimina le vecchie sorgenti versionate.
3. Reinserisci l’URL permanente.
4. Riavvia ZimaOS.
5. Cerca `Clipboard Bridge` nell’intero store.

**Errore `zip: not a valid zip file`**

Hai inserito la pagina GitHub invece dell’archivio. Usa l’indirizzo `main.zip`
riportato all’inizio.

**L’app è installata ma non si apre**

Controlla che la porta `5088` sia libera e visita:

```text
http://IP-ZIMA:5088/health
```

## Docker Compose, Docker Desktop e Dockge

Questa procedura funziona su qualsiasi macchina con Docker Compose:

```bash
git clone https://github.com/mattbox03/Clipboard-Bridge-AppStore.git
cd Clipboard-Bridge-AppStore
docker compose up -d
```

Apri `http://IP-SERVER:5088`. I dati persistenti vengono salvati nella cartella
`data` accanto a `compose.yaml`.

Per configurare il server crea un file `.env` nella stessa cartella:

```env
APP_PORT=5088
DATA_ROOT=./data
MAX_HISTORY=200
API_TOKEN=cambia-questo-token
WEB_PASSWORD=cambia-questa-password
ACCOUNTS=alice:pass1,bob:pass2
```

Applica le impostazioni:

```bash
docker compose up -d
```

In **Dockge**, crea un nuovo stack, incolla il contenuto di `compose.yaml`,
inserisci le stesse variabili d’ambiente e distribuisci lo stack.

Per aggiornare:

```bash
git pull
docker compose pull
docker compose up -d
```

## Portainer

Usa questo App Template:

```text
https://raw.githubusercontent.com/mattbox03/Clipboard-Bridge-AppStore/main/portainer/templates.json
```

1. Apri **Portainer**.
2. Vai in **Settings** e cerca **App Templates**.
3. Incolla l’indirizzo nel campo App Templates URL e salva.
4. Apri **App Templates** dal menu principale.
5. Cerca **Clipboard Bridge**.
6. Seleziona l’ambiente Docker.
7. Imposta porta pubblica e cartella dei dati persistenti.
8. Inserisci facoltativamente token, password web e account aggiuntivi.
9. Premi **Deploy the stack**.
10. Apri `http://IP-SERVER:5088`.

Se il template non appare subito, ricarica Portainer dopo aver salvato l’URL.
Per aggiornare, apri lo stack, scarica l’immagine indicata dal template e
ridistribuiscilo senza cancellare la cartella dati.

## Umbrel

Aggiungi come Community App Store:

```text
https://github.com/mattbox03/Clipboard-Bridge-AppStore
```

1. Apri l’App Store di Umbrel.
2. Apri **Community App Stores**.
3. Aggiungi l’indirizzo della repository.
4. Apri la sorgente **Clipboard Bridge App Store**.
5. Seleziona **Clipboard Bridge** e installala.
6. Apri l’applicazione dalla schermata principale.

Umbrel genera una password dell’applicazione. L’adattatore la utilizza sia per
la pagina web sia per l’API, quindi può essere inserita nel client Windows e nei
Comandi Rapidi iPhone. I dati restano nella directory applicativa di Umbrel.

## Runtipi

Il catalogo mantiene alla radice la compatibilità con ZimaOS; su Runtipi
Clipboard Bridge va quindi aggiunta con la funzione ufficiale
**Add custom app**. I file Runtipi già pronti si trovano in:

```text
adapters/runtipi/apps/clipboard-bridge/
```

1. Apri **App Store** in Runtipi.
2. Seleziona **Add custom app**.
3. Usa `clipboard-bridge` come ID e `Clipboard Bridge` come nome.
4. Inserisci l’immagine `ghcr.io/mattbox03/clipboard-bridge-server:1.0.0`.
5. Imposta la porta del container su `5088` e rendila esponibile.
6. Aggiungi un volume persistente dalla directory applicativa proposta da
   Runtipi a `/data` nel container.
7. Aggiungi `CLIPBOARD_PORT=5088` e `CLIPBOARD_DATA_DIR=/data`.
8. Aggiungi facoltativamente `CLIPBOARD_TOKEN`, `CLIPBOARD_PASSWORD` e
   `CLIPBOARD_ACCOUNTS`.
9. Salva e installa l’app personalizzata.

La configurazione completa di riferimento è in
`adapters/runtipi/apps/clipboard-bridge/docker-compose.yml`. Per aggiornare,
imposta il nuovo tag dell’immagine e ridistribuisci l’app senza eliminare i
dati applicativi.

## Riepilogo indirizzi

| Piattaforma | Sorgente |
|---|---|
| ZimaOS | `https://github.com/mattbox03/Clipboard-Bridge-AppStore/archive/refs/heads/main.zip` |
| Portainer | `https://raw.githubusercontent.com/mattbox03/Clipboard-Bridge-AppStore/main/portainer/templates.json` |
| Umbrel | `https://github.com/mattbox03/Clipboard-Bridge-AppStore` |
| Runtipi | **Add custom app**, usando `adapters/runtipi/apps/clipboard-bridge/` |
| Docker/Dockge | file `compose.yaml` della repository |
