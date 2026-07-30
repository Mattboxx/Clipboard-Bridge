# Clipboard Bridge

## Un'unica clipboard per Windows, Android e iPhone

[English](README.md) | **Italiano**

[Sito web](https://mattbox03.github.io/Clipboard-Bridge/) |
[Download](https://github.com/mattbox03/Clipboard-Bridge/releases/tag/2.0.4) |
[App Store del server](https://github.com/mattbox03/Clipboard-Bridge-AppStore) |
[Guida completa](GUIDE.md)

[![Windows](https://img.shields.io/badge/Windows-client%20%2B%20server-2563eb)](#windows)
[![Android](https://img.shields.io/badge/Android-app%20nativa-16805b)](#android)
[![iOS](https://img.shields.io/badge/iPhone-Comandi%20rapidi-111827)](#iphone-e-ipad)
[![Docker](https://img.shields.io/badge/server-Docker%20%2B%20Python-0ea5e9)](#server-indipendente)
[![Licenza](https://img.shields.io/badge/licenza-MIT-555)](LICENSE)
[![Verifica](https://github.com/mattbox03/Clipboard-Bridge/actions/workflows/validate.yml/badge.svg)](https://github.com/mattbox03/Clipboard-Bridge/actions/workflows/validate.yml)

Clipboard Bridge trasferisce **l'ultimo testo, immagine o file** tra Windows, Android e
iPhone tramite un server privato. Funziona in rete locale, non richiede account cloud e
permette a tutti i dispositivi di usare la stessa cronologia del server.

Per la configurazione più semplice, usa direttamente l'app Windows come server. In
alternativa, esegui il server Python/Docker su NAS, Raspberry Pi, home server o qualsiasi
host Docker.

## Download

| Piattaforma | Download | Contenuto |
|---|---|---|
| **Android 10+** | [APK Android 1.0.0-beta.6](https://github.com/mattbox03/Clipboard-Bridge/releases/download/2.0.4/Clipboard.Bridge.Android.universal.V1.0.0-beta.6.apk) | App nativa, menu Condividi, cronologia server e pulsanti rapidi |
| **Installer Windows** | [Installer Clipboard Bridge Windows 2.0.4](https://github.com/mattbox03/Clipboard-Bridge/releases/download/2.0.4/Clipboard.Bridge_windows_client_and_server_setup_x64_V2.0.4.exe) | Installazione per l'utente corrente, senza account amministratore |
| **Portable Windows** | [Clipboard Bridge 2.0.4 portable](https://github.com/mattbox03/Clipboard-Bridge/releases/download/2.0.4/Clipboard.Bridge.Portable.Windows.x64.V2.0.4.exe) | Un solo eseguibile, nessuna installazione |
| **Comando iPhone per inviare** | [Load Clipboard](https://github.com/mattbox03/Clipboard-Bridge/releases/download/2.0.4/Load.Clipboard.shortcut) | Invia la clipboard attuale di iOS |
| **Comando iPhone per ricevere** | [Download Clipboard](https://github.com/mattbox03/Clipboard-Bridge/releases/download/2.0.4/Download.Clipboard.shortcut) | Riceve l'ultimo elemento del server |
| **Server e sorgenti** | [Archivio server e sorgenti](https://github.com/mattbox03/Clipboard-Bridge/releases/download/2.0.4/Clipboard.Bridge.Source.and.Server.V2.0.4.zip) | Server Python, Docker, documentazione e test |

L'app Android è attualmente una beta pubblica. Nella release sono disponibili i checksum
dell'APK e dei programmi Windows.

> **Avviso download Windows:** gli eseguibili Windows non sono ancora firmati con un
> certificato Authenticode pubblico. Defender o Smart App Control potrebbero mostrare un
> avviso. Consulta [CODE_SIGNING.md](CODE_SIGNING.md).

## Come funziona

```text
App Windows  ─┐
App Android  ─┼── HTTP sulla rete privata ── Server Clipboard Bridge
Shortcut iOS ─┘                              ├─ ultimo elemento
Browser web ─────────────────────────────────└─ cronologia condivisa
```

Il server mantiene una cronologia ordinata per ogni spazio clipboard. **Testo, immagini
e file hanno la stessa priorità:** l'ultima richiesta ricevuta è sempre l'elemento più
recente.

Tutti i dispositivi devono usare gli stessi:

- indirizzo e porta del server;
- spazio condiviso oppure account;
- token, nome utente e password, quando l'autenticazione è abilitata.

La cronologia Android è una vista live di `GET /clipboard/history`. Non viene mantenuta
una seconda cronologia Android.

## Scegli la modalità server

Clipboard Bridge supporta due configurazioni distinte.

| | **Modalità Server Windows** | **Server indipendente** |
|---|---|---|
| Dove gira il server | Nell'app Windows | Su host Docker/Python |
| Computer aggiuntivo | Non necessario | NAS, Raspberry Pi, PC o home server |
| Interfaccia web | No | Sì |
| Supporto Android | Sì | Sì |
| Comandi rapidi iPhone | Sì | Sì |
| Client Windows | La stessa app | Uno o più client Windows |
| Ideale per | Configurazione veloce e collegamento telefono-PC | Più utenti e servizio sempre acceso |

![Modalità Server Windows e server indipendente](docs/modes.png)

### Configurazione più rapida: Windows come server

1. Installa o apri Clipboard Bridge su Windows.
2. Apri **Impostazioni > Generale** e seleziona **Modalità Server**.
3. Mantieni la porta `5088`, salvo che sia già occupata.
4. Copia l'indirizzo mostrato dall'app, ad esempio
   `http://192.168.1.20:5088`.
5. Consenti Clipboard Bridge nel Firewall di Windows.
6. Inserisci lo stesso indirizzo su Android e nei due Comandi rapidi iPhone.

Non servono Docker o un server web separato.

### Configurazione sempre attiva: Docker o Python

1. Avvia il server indipendente su NAS, Raspberry Pi, PC o host Docker.
2. Apri `http://IP_SERVER:5088/` per verificare l'interfaccia web.
3. Imposta l'app Windows in **Modalità Client**.
4. Configura Android e iPhone con lo stesso indirizzo.

## Android

Il client Android nativo supporta Android 10 e versioni successive.

### Funzionalità

- Invio e ricezione di testo Unicode.
- Invio di fotografie, PDF, archivi e file generici.
- Salvataggio dei file ricevuti in `Download/Clipboard Bridge`.
- Inserimento nella clipboard Android di testo e URI dei file ricevuti.
- Cronologia live del server aggiornata ogni cinque secondi mentre l'app è visibile.
- Ripristino di qualsiasi elemento della cronologia server.
- Integrazione nel menu **Condividi** di Android.
- Pulsanti **Invia clipboard** e **Ricevi clipboard** nelle Impostazioni rapide.
- Controllo opzionale in primo piano dei nuovi elementi del server.
- Notifiche separate per testo ricevuto, file ricevuti ed elementi inviati.
- Supporto per token generale e account isolati.
- Interfaccia italiana e inglese.

### Installare l'APK

1. Scarica l'[APK Android](https://github.com/mattbox03/Clipboard-Bridge/releases/download/2.0.4/Clipboard.Bridge.Android.universal.V1.0.0-beta.6.apk).
2. Apri il file scaricato sul dispositivo Android.
3. Se richiesto, consenti al browser o al file manager di installare app da quella fonte.
4. Scegli **Installa** oppure **Aggiorna**.
5. Apri Clipboard Bridge e consenti le notifiche se vuoi il controllo automatico.

Gli aggiornamenti firmati dal progetto mantengono la configurazione Android esistente.

### Configurare Android

1. Apri il pulsante con l'ingranaggio.
2. Inserisci soltanto l'indirizzo base del server, ad esempio:

   ```text
   http://192.168.1.20:5088
   ```

3. Scegli **Spazio condiviso** per usare la clipboard generale.
4. Inserisci il token API soltanto se il server usa `CLIPBOARD_TOKEN`.
5. Scegli **Account** soltanto se quel nome utente esiste in
   `CLIPBOARD_ACCOUNTS`.
6. Inserisci nome utente e password dell'account.
7. Esegui **Verifica connessione**, quindi salva.

In modalità account la fascia di stato deve mostrare **Connesso - @NOMEUTENTE**.
Android aggiunge `user` e `password` a ogni URL, quindi carica la clipboard isolata
dell'account e non lo spazio generale. La sezione **Cronologia server** visualizza gli
stessi elementi restituiti da:

```text
http://IP_SERVER:5088/clipboard/history?limit=200&user=NOMEUTENTE&password=PASSWORD
```

Se Android e la pagina web mostrano cronologie diverse, verifica che entrambi stiano
usando lo stesso spazio condiviso oppure lo stesso account.

### Usare l'app Android

- **Invia clipboard:** carica la clipboard Android attuale.
- **Ricevi ultimo:** scarica l'elemento più recente e lo inserisce nella clipboard.
- **Invia file:** apre il selettore file di Android.
- **Elemento della cronologia:** scarica esattamente quell'elemento del server.
- **Condividi con Clipboard Bridge:** invia contenuti da Foto, File, browser e altre app.

### Aggiungere i pulsanti alle Impostazioni rapide

1. Apri completamente la tendina delle Impostazioni rapide.
2. Tocca **Modifica** o il pulsante con la matita.
3. Cerca **Invia clipboard** e **Ricevi clipboard**.
4. Trascina entrambi tra i controlli attivi.

I controlli usano un passaggio trasparente perché Android richiede un'app con il focus
per accedere in modo affidabile alla clipboard. Clipboard Bridge ritorna subito alla
schermata precedente senza aprire l'interfaccia principale.

### Sincronizzazione automatica Android

Da Android 10 le normali applicazioni in background non possono leggere continuamente
la clipboard. Clipboard Bridge usa quindi flussi compatibili con il sistema:

- il controllo in ricezione usa un servizio in primo piano e una notifica;
- **Ricevi clipboard** è sempre disponibile dalle Impostazioni rapide;
- l'invio automatico funziona mentre Clipboard Bridge è visibile;
- menu Condividi e pulsante **Invia clipboard** funzionano dalle altre applicazioni.

Alcuni produttori applicano ulteriori restrizioni alla batteria. Se il controllo si
interrompe, escludi Clipboard Bridge dall'ottimizzazione batteria e mantieni attiva la
notifica del servizio.

Consulta [android/README.md](android/README.md) per compilazione e dettagli tecnici.

## Windows

Il client Windows funziona dall'area di notifica.

### Funzionalità principali

- Modalità Client per un server esterno.
- Modalità Server con server HTTP integrato.
- Invio e ricezione manuali.
- Scorciatoie da tastiera globali configurabili.
- Sincronizzazione automatica della clipboard.
- Cronologia locale della clipboard.
- Download automatico dei file in arrivo.
- Notifiche file cliccabili.
- Notifiche configurabili per testo, immagini e file.
- Token condiviso e autenticazione tramite account.
- Protezione contro istanze multiple.
- Interfaccia italiana e inglese.

### Cronologia locale Windows e cronologia server

L'app Windows può registrare una cronologia privata locale. È diversa dalla cronologia
del server:

- la **cronologia locale** contiene gli eventi osservati su quel PC Windows;
- la **cronologia server** contiene gli elementi realmente inviati al server selezionato;
- Android, iPhone e interfaccia web possono vedere soltanto la cronologia server.

Abilita **Sincronizzazione automatica** oppure usa **Invia clipboard** per pubblicare sul
server gli elementi copiati in Windows.

> Le modifiche alla clipboard effettuate da programmi avviati come amministratore
> possono essere nascoste a un processo Windows normale. Se l'auto-sync non le rileva,
> avvia come amministratore anche Clipboard Bridge.

## iPhone e iPad

iOS usa due Comandi rapidi universali. Gli stessi comandi gestiscono testo, foto e file.

### Inviare la clipboard attuale

Installa [Load Clipboard](https://github.com/mattbox03/Clipboard-Bridge/releases/download/2.0.4/Load.Clipboard.shortcut)
e imposta l'URL della richiesta:

```text
http://IP_SERVER:5088/clipboard
```

### Ricevere l'ultimo elemento

Installa [Download Clipboard](https://github.com/mattbox03/Clipboard-Bridge/releases/download/2.0.4/Download.Clipboard.shortcut)
e imposta:

```text
http://IP_SERVER:5088/clipboard/latest/raw
```

Aggiungi entrambi i Comandi rapidi al Centro di Controllo:

1. Apri la personalizzazione del Centro di Controllo.
2. Aggiungi un controllo **Comando rapido**.
3. Seleziona **Load Clipboard**.
4. Aggiungi un secondo controllo e seleziona **Download Clipboard**.

Per un account isolato aggiungi nome utente e password codificati alla fine:

```text
http://IP_SERVER:5088/clipboard?user=alice&password=segreto
http://IP_SERVER:5088/clipboard/latest/raw?user=alice&password=segreto
```

Per il token API dello spazio condiviso:

```text
http://IP_SERVER:5088/clipboard?token=IL_TUO_TOKEN
http://IP_SERVER:5088/clipboard/latest/raw?token=IL_TUO_TOKEN
```

La [guida completa](GUIDE.md) descrive nel dettaglio azioni, foto e file.

## Server indipendente

### Docker Compose

```bash
git clone https://github.com/mattbox03/Clipboard-Bridge.git
cd Clipboard-Bridge
docker compose up -d --build
```

Apri `http://localhost:5088/`. I dati persistenti restano in `./data`.

### Python

```bash
pip install -r requirements-server.txt
python clipboard_bridge-Server.py
```

### App Store

Il repository separato [Clipboard Bridge App Store](https://github.com/mattbox03/Clipboard-Bridge-AppStore)
contiene le istruzioni per ZimaOS, Portainer, Umbrel, Runtipi, Dockge e Docker Compose.

La sorgente permanente per ZimaOS è:

```text
https://github.com/mattbox03/Clipboard-Bridge-AppStore/archive/refs/heads/main.zip
```

## Configurazione del server

| Variabile | Valore predefinito | Descrizione |
|---|---:|---|
| `CLIPBOARD_PORT` | `5088` | Porta di ascolto |
| `CLIPBOARD_TOKEN` | vuoto | Token API opzionale dello spazio condiviso |
| `CLIPBOARD_PASSWORD` | vuoto | Password opzionale della pagina web |
| `CLIPBOARD_ACCOUNTS` | vuoto | Account `utente:password` separati da virgole |
| `CLIPBOARD_ACCOUNTS_FILE` | vuoto | File con un account `utente:password` per riga |
| `CLIPBOARD_MAX_HISTORY` | `200` | Limite della cronologia server |
| `CLIPBOARD_MAX_UPLOAD_MB` | `64` | Dimensione massima di un caricamento |
| `CLIPBOARD_DATA_DIR` | `./clipboard_data` | Cartella dei dati persistenti |

Lo spazio condiviso rimane disponibile quando vengono aggiunti account. Gli account
hanno cronologie separate e non esiste un limite fisso al loro numero. Per installazioni
grandi usa `CLIPBOARD_ACCOUNTS_FILE`.

## Rete e sicurezza

Clipboard Bridge è progettato per reti private.

- Non esporre direttamente la porta `5088` su Internet.
- Usa token o account se altre persone possono accedere alla rete.
- Per l'accesso fuori casa usa una VPN. Tailscale è un esempio, non un requisito.
- La VPN funziona sia con il server indipendente sia con la Modalità Server Windows.
- Puoi aggiungere HTTPS tramite un reverse proxy attendibile.

Con Tailscale sostituisci l'indirizzo LAN con l'indirizzo privato del server:

```text
http://100.x.y.z:5088
```

Consulta [SECURITY.md](SECURITY.md) prima di usare il server fuori da una LAN attendibile.

## Struttura del repository

| Percorso | Contenuto |
|---|---|
| `android/` | Applicazione Android nativa |
| `clipboard_bridge_windows.py` | Client Windows e server integrato |
| `clipboard_bridge-Server.py` | Server Flask indipendente e interfaccia web |
| `Iphone Shortcuts/` | Comandi rapidi iOS pronti |
| `Dockerfile`, `compose.yaml` | Distribuzione tramite container |
| `tests/` | Test di regressione server e Windows |
| `docs/` | Sito GitHub Pages |

## Compilazione e contributi

- Compilazione Android: [android/README.md](android/README.md)
- Pacchetti Windows: [guida build e firma](CODE_SIGNING.md)
- Installazione Docker: [DOCKER.md](DOCKER.md)
- Regole per contribuire: [CONTRIBUTING.md](CONTRIBUTING.md)

Clipboard Bridge è distribuito con [licenza MIT](LICENSE).
