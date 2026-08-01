# Clipboard Bridge: condivisione multipiattaforma di clipboard e file

## Un'unica clipboard privata per Windows, Android, iPhone e iPad

[English](README.md) | **Italiano**

[Sito web](https://mattboxx.github.io/Clipboard-Bridge/) |
[Download](https://github.com/Mattboxx/Clipboard-Bridge/releases/tag/2.0.4) |
[App Store del server](https://github.com/Mattboxx/Clipboard-Bridge-AppStore) |
[Guida completa](GUIDE.md)

![Clipboard Bridge collega Windows, Android e iPhone](docs/assets/hero-showcase.png)

[![Windows](https://img.shields.io/badge/Windows-client%20%2B%20server-2563eb)](#windows)
[![Android](https://img.shields.io/badge/Android-app%20nativa-16805b)](#android)
[![iOS](https://img.shields.io/badge/iPhone-Comandi%20rapidi-111827)](#iphone-e-ipad)
[![Docker](https://img.shields.io/badge/server-Docker%20%2B%20Python-0ea5e9)](#server-indipendente)
[![Licenza](https://img.shields.io/badge/licenza-MIT-555)](LICENSE)
[![Verifica](https://github.com/Mattboxx/Clipboard-Bridge/actions/workflows/validate.yml/badge.svg)](https://github.com/Mattboxx/Clipboard-Bridge/actions/workflows/validate.yml)

Copia un testo su Windows e ricevilo su Android. Condividi un PDF da Android e scaricalo
su iPhone. Invia una foto da iOS e ricevila automaticamente sul PC.

Clipboard Bridge collega **Windows, Android e iOS/iPadOS** tramite un'unica clipboard
privata e self-hosted. Testo, fotografie e file di qualsiasi tipo usano lo stesso flusso
Invia/Ricevi: l'ultimo elemento caricato è sempre la clipboard corrente.

Non serve un account cloud. Puoi usare direttamente l'app Windows come server oppure
eseguire il server Python/Docker su NAS, Raspberry Pi, home server o host Docker.

## Piattaforme supportate

| Piattaforma | Integrazione | Invio | Ricezione | Cronologia server |
|---|---|---|---|---|
| **Windows 10/11** | Applicazione nella tray | Clipboard, hotkey configurabili e auto-sync | Manuale o automatica, con notifiche file cliccabili | Cronologia locale e operazioni server |
| **Android 10+** | Applicazione nativa | Clipboard, selettore file, menu Condividi universale e Impostazioni rapide | Ultimo elemento, voce specifica o controllo automatico | Lista live con download ed eliminazione singola |
| **iPhone/iPad** | Due Comandi rapidi iOS | Testo, foto e file dalla clipboard o dal menu Condividi | Ultimo testo, foto o file | Disponibile dall'interfaccia web |
| **Browser web** | Pagina del server indipendente | Incolla testo o carica file | Copia o scarica qualsiasi elemento | Visualizza, aggiorna ed elimina |

### Cosa può essere trasferito

- Testo Unicode, link e contenuti su più righe.
- Fotografie e immagini presenti nella clipboard.
- PDF, archivi, documenti Office, audio, video e file con estensioni personalizzate.
- Uno o più file selezionati dal menu Condividi di Android.

Clipboard Bridge non assegna priorità maggiore a file o immagini: conta soltanto
l'ordine di arrivo.

## Avvio rapido

1. Scegli il server: attiva la **Modalità Server** nell'app Windows oppure avvia il server
   indipendente Docker/Python.
2. Usa lo stesso indirizzo server su Windows, Android e nei due Comandi rapidi iPhone.
3. Lascia vuota l'autenticazione per la clipboard generale, oppure configura lo stesso
   token/account opzionale su tutti i dispositivi.
4. Invia da un dispositivo e ricevi l'ultimo elemento da un altro.

## Download

| Piattaforma | Download | Contenuto |
|---|---|---|
| **Android 10+** | [APK Android 1.0.0-beta.8](https://github.com/Mattboxx/Clipboard-Bridge/releases/download/2.0.4/Clipboard.Bridge.Android.universal.V1.0.0-beta.8.apk) | App nativa, destinazione Condividi universale, cronologia server modificabile e pulsanti rapidi |
| **Installer Windows** | [Installer Clipboard Bridge Windows 2.0.4](https://github.com/Mattboxx/Clipboard-Bridge/releases/download/2.0.4/Clipboard.Bridge_windows_client_and_server_setup_x64_V2.0.4.exe) | Installazione per l'utente corrente, senza account amministratore |
| **Portable Windows** | [Clipboard Bridge 2.0.4 portable](https://github.com/Mattboxx/Clipboard-Bridge/releases/download/2.0.4/Clipboard.Bridge.Portable.Windows.x64.V2.0.4.exe) | Un solo eseguibile, nessuna installazione |
| **Comando iPhone per inviare** | [iPhone Load Clipboard](https://github.com/Mattboxx/Clipboard-Bridge/releases/download/2.0.4/iPhone.Load.Clipboard.shortcut) | Invia la clipboard attuale di iOS |
| **Comando iPhone per ricevere** | [iPhone Download Clipboard](https://github.com/Mattboxx/Clipboard-Bridge/releases/download/2.0.4/iPhone.Download.Clipboard.shortcut) | Riceve l'ultimo elemento del server |
| **Server Python** | [clipboard_bridge-Server.py](https://github.com/Mattboxx/Clipboard-Bridge/releases/download/2.0.4/clipboard_bridge-Server.py) | Script server indipendente; dipendenze e file Docker restano nel repository |
| **Client Windows Python** | [clipboard_bridge_windows.py](https://github.com/Mattboxx/Clipboard-Bridge/releases/download/2.0.4/clipboard_bridge_windows.py) | Sorgente non compilato del client Windows |

L'app Android è attualmente una beta pubblica. La release contiene soltanto i download
pronti all'uso e i due script Python principali. Gli sviluppatori possono clonare il
repository per documentazione, test, file Docker e sorgenti completi.

> **Avviso download Windows:** gli eseguibili Windows non sono ancora firmati con un
> certificato Authenticode pubblico. Defender o Smart App Control potrebbero mostrare un
> avviso. Consulta [CODE_SIGNING.md](CODE_SIGNING.md).

## Come funziona

```mermaid
flowchart TB
    subgraph M1["Modalità 1 - nessun server separato"]
        direction LR
        P1["App Android + Comandi rapidi iPhone"] <--> W1["App Windows - modalità Server"]
    end
    subgraph M2["Modalità 2 - server sempre attivo opzionale"]
        direction LR
        P2["Client Windows + app Android + Comandi rapidi iPhone"] <--> S2["Server Docker o Python"]
    end
```

Scegli una modalità. In entrambi i casi ogni collegamento è bidirezionale e il server
attivo mantiene una cronologia ordinata per ogni spazio clipboard. **Testo, immagini e
file hanno la stessa priorità:** l'ultima richiesta ricevuta è sempre l'elemento più
recente.

Tutti i dispositivi devono usare gli stessi:

- indirizzo e porta del server;
- spazio condiviso oppure account;
- token, nome utente e password, quando l'autenticazione è abilitata.

> **L'autenticazione è opzionale.** Se non configuri token o account, tutti i dispositivi
> usano la clipboard generale condivisa. Nei link con token o account, `token`, `user` e
> `password` sono visibili in chiaro nell'URL. HTTP locale non li cifra: usa soltanto una
> LAN attendibile, una VPN privata oppure un reverse proxy HTTPS.

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

![Modalità Server Windows e server indipendente](docs/assets/two-modes.png)

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

Il client Android nativo supporta Android 10 e versioni successive e legge la cronologia
direttamente dal server Clipboard Bridge selezionato.

### Funzionalità

- Invio e ricezione di testo Unicode.
- Invio di fotografie, PDF, archivi e file generici.
- Salvataggio dei file ricevuti in `Download/Clipboard Bridge`.
- Inserimento nella clipboard Android di testo e URI dei file ricevuti.
- Cronologia live del server aggiornata ogni cinque secondi mentre l'app è visibile.
- Ripristino di qualsiasi elemento della cronologia server.
- Eliminazione delle singole voci server con richiesta di conferma.
- Integrazione nel menu **Condividi** di Android.
- Pulsanti **Invia clipboard** e **Ricevi clipboard** nelle Impostazioni rapide.
- Controllo opzionale in primo piano dei nuovi elementi del server.
- Notifiche separate per testo ricevuto, file ricevuti ed elementi inviati.
- Supporto per token generale e account isolati.
- Interfaccia italiana e inglese.

### Installare l'APK

1. Scarica l'[APK Android](https://github.com/Mattboxx/Clipboard-Bridge/releases/download/2.0.4/Clipboard.Bridge.Android.universal.V1.0.0-beta.8.apk).
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
- **Pulsante cestino:** elimina soltanto quella voce dalla cronologia dell'account o
  dello spazio condiviso selezionato, dopo una richiesta di conferma.
- **Condividi con Clipboard Bridge:** appare nel menu Condividi di Android per testo,
  immagini, documenti e file di qualsiasi tipo. Può caricare anche più file selezionati
  senza lasciare aperta la schermata principale di Clipboard Bridge.

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

<table>
  <tr>
    <td width="50%"><img src="docs/assets/windows-connection.png" alt="Impostazioni di connessione Windows con stato connesso"></td>
    <td width="50%"><img src="docs/assets/windows-automation.png" alt="Impostazioni Windows per automazione e notifiche"></td>
  </tr>
  <tr>
    <td align="center"><strong>Connessione e autenticazione opzionale</strong></td>
    <td align="center"><strong>Sincronizzazione e notifiche configurabili</strong></td>
  </tr>
</table>

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

Installa [iPhone Load Clipboard](https://github.com/Mattboxx/Clipboard-Bridge/releases/download/2.0.4/iPhone.Load.Clipboard.shortcut)
e imposta l'URL della richiesta:

```text
http://IP_SERVER:5088/clipboard
```

### Ricevere l'ultimo elemento

Installa [iPhone Download Clipboard](https://github.com/Mattboxx/Clipboard-Bridge/releases/download/2.0.4/iPhone.Download.Clipboard.shortcut)
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
git clone https://github.com/Mattboxx/Clipboard-Bridge.git
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

Il repository separato [Clipboard Bridge App Store](https://github.com/Mattboxx/Clipboard-Bridge-AppStore)
contiene le istruzioni per ZimaOS, Portainer, Umbrel, Runtipi, Dockge e Docker Compose.

La sorgente permanente per ZimaOS è:

```text
https://github.com/Mattboxx/Clipboard-Bridge-AppStore/archive/refs/heads/main.zip
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

- Token API e account isolati sono opzionali; la clipboard generale funziona senza
  entrambi.
- I link account di iPhone e Android contengono `user` e `password` in chiaro nell'URL.
  I link con token mostrano allo stesso modo il valore di `token`.
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
