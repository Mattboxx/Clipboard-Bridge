# Installare il server Docker da zero

[English / DOCKER.md](DOCKER.md) | **Italiano**

Questa guida serve per installare Clipboard Bridge **senza store, Git, Python o
compilazioni**. Scaricherai due piccoli file di configurazione: Docker scarica e
avvia il server pronto all'uso. Non serve un database separato.

Il computer scelto come server deve rimanere acceso. Se vuoi solo collegare telefono
e PC Windows, puoi invece usare **Modalita Server** nell'app Windows, senza Docker.

Segui i punti nell'ordine. I comandi vanno eseguiti **sul computer che ospitera il
server**, non sul telefono. Copia le righe nei riquadri, non i delimitatori del
riquadro. Se un passaggio fallisce, fermati e consulta [Problemi comuni](#problemi-comuni).

1. [Installare e verificare Docker](#1-installare-e-verificare-docker)
2. [Preparare la cartella e scaricare i file](#2-preparare-la-cartella-e-scaricare-i-file)
3. [Configurare prima di avviare](#3-configurare-prima-di-avviare)
4. [Scaricare e avviare il server](#4-scaricare-e-avviare-il-server)
5. [Aprire la pagina e collegare i dispositivi](#5-aprire-la-pagina-e-collegare-i-dispositivi)
6. [Aggiornare e fare il backup](#6-aggiornare-e-fare-il-backup)

## 1. Installare e verificare Docker

**Hai gia Docker funzionante sul NAS/server?** Non reinstallarlo e non rimuovere
i suoi pacchetti. Apri il terminale dell'host e passa alle verifiche sotto.
Su un NAS usa l'installazione Docker/Container Manager supportata dal produttore.
L'immagine Clipboard Bridge supporta Linux a 64 bit **amd64 e arm64**, non ARM a 32 bit.

### Windows o Mac

1. Scarica Docker Desktop dalle istruzioni ufficiali per
   [Windows](https://docs.docker.com/desktop/setup/install/windows-install/) o
   [Mac](https://docs.docker.com/desktop/setup/install/mac-install/), scegliendo
   il processore corretto. Controlla i requisiti nella pagina.
2. Su Windows segui le indicazioni dell'installer per WSL 2 e riavvia se richiesto.
   Il server usa **container Linux**, non container Windows.
3. Apri Docker Desktop, leggi personalmente le condizioni e attendi che il motore
   sia in esecuzione. Compose e incluso: non va installato a parte.
4. Apri **PowerShell** su Windows o **Terminale** su Mac. Docker Desktop deve restare
   avviato anche durante l'uso del server e dopo un riavvio del computer.

### Ubuntu Server appena installato

Solo per una **nuova installazione Ubuntu supportata**, non Debian o NAS con altri
container. Se Docker esiste gia, passa alle verifiche. Per altri sistemi o pacchetti
in conflitto segui il [selettore ufficiale Docker](https://docs.docker.com/engine/install/).

Esegui un comando alla volta. `sudo` chiede la password Linux: mentre la digiti
non appaiono caratteri, e normale. Questi passaggi usano il
[repository ufficiale per Ubuntu](https://docs.docker.com/engine/install/ubuntu/).

```bash
sudo apt update
sudo apt install ca-certificates curl nano
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
```

Incolla il prossimo blocco **tutto insieme**, compresa l'ultima riga `EOF`:

```bash
sudo tee /etc/apt/sources.list.d/docker.sources > /dev/null <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
```

Poi installa e avvia Docker:

```bash
sudo apt update
sudo apt install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
```

### Verifica prima di proseguire

Su Docker Desktop:

```text
docker version
docker compose version
```

Su Linux, se il tuo utente non ha accesso a Docker:

```bash
sudo docker version
sudo docker compose version
```

Il primo comando deve mostrare **Client e Server**, senza errori di connessione.
Il secondo deve mostrare una versione di Compose. Se hai dovuto usare `sudo`,
anteponilo a **tutti i successivi comandi che iniziano con `docker`**.
Non cambiare i permessi del socket per aggirare un errore; per modificare
intenzionalmente gli accessi leggi la [guida Docker](https://docs.docker.com/engine/install/linux-postinstall/).

## 2. Preparare la cartella e scaricare i file

Usa una cartella **nuova e vuota**. Non riscaricare `.env` sopra quello di un server
gia configurato: sovrascriveresti le impostazioni. L'immagine e pubblica: non
servono account GitHub, token privati o `docker login`.

### Windows PowerShell

```powershell
New-Item -ItemType Directory -Path "$HOME\clipboard-bridge"
Set-Location "$HOME\clipboard-bridge"
Invoke-WebRequest -Uri https://raw.githubusercontent.com/Mattboxx/Clipboard-Bridge/main/compose.yaml -OutFile compose.yaml
Invoke-WebRequest -Uri https://raw.githubusercontent.com/Mattboxx/Clipboard-Bridge/main/.env.example -OutFile .env
Get-ChildItem -Force
```

### Terminale Linux o Mac

```bash
mkdir ~/clipboard-bridge
cd ~/clipboard-bridge
curl -fL https://raw.githubusercontent.com/Mattboxx/Clipboard-Bridge/main/compose.yaml -o compose.yaml
curl -fL https://raw.githubusercontent.com/Mattboxx/Clipboard-Bridge/main/.env.example -o .env
ls -la
```

Devi vedere **`compose.yaml` e `.env`** nella cartella. Il secondo file inizia con
un punto e potrebbe essere nascosto dal gestore file. Non chiamarlo `.env.txt`.
Non occorre scaricare script Python: il modello Compose contiene gia porte,
volume dati, controllo di salute e riavvio del container.

## 3. Configurare prima di avviare

Apri il file delle impostazioni. Su Windows:

```powershell
notepad .env
```

Su Linux usa `nano .env`: salva con **Ctrl+O**, Invio, poi esci con **Ctrl+X**.
Su Mac usa `open -t .env`, mantenendo il formato testo semplice.

Questo e un **esempio completo iniziale** da mettere dentro `.env`, sostituendo
i valori scaricati. **Non e un comando da incollare nel terminale**:

```dotenv
APP_PORT=5088
DATA_ROOT=./data
APP_IMAGE=ghcr.io/mattboxx/clipboard-bridge-server:1.0.10
MAX_HISTORY=200
MAX_UPLOAD_MB=64
API_TOKEN=
WEB_PASSWORD=
ACCOUNTS=
ACCOUNTS_FILE=
SESSION_DAYS=3650
```

**Salva prima dell'avvio.** Su Linux/Mac esegui `chmod 600 .env` per limitare
l'accesso al file. Questo esempio lascia aperta la clipboard generale:
usalo soltanto su una rete privata fidata. Chi raggiunge il servizio puo leggere,
inviare o eliminare contenuti se lasci vuote le protezioni.

| Impostazione | Significato e scelta iniziale |
|---|---|
| `APP_PORT` | Porta dell'host: lascia `5088`. Se occupata usa ad esempio `5089` e cambia tutti gli URL dei dispositivi. La porta interna resta `5088`. |
| `DATA_ROOT` | `./data` crea/conserva i dati nella cartella `data` accanto a `compose.yaml`, collegata a `/data` nel container. Su NAS/Portainer usa un percorso assoluto scrivibile. Non cambiare casualmente quello di un server esistente. |
| `APP_IMAGE` | Blocca la versione server a `1.0.10`; Docker sceglie automaticamente l'architettura supportata. |
| `MAX_HISTORY` | Numero di elementi conservati per spazio/account; oltre il limite vengono rimosse le voci piu vecchie. |
| `MAX_UPLOAD_MB` | Massimo in MB dell'intera richiesta di caricamento, anche quando contiene piu file. |
| `API_TOKEN` | Protezione facoltativa dell'API generale, usata dalle app e dai Comandi Rapidi. |
| `WEB_PASSWORD` | Password facoltativa della pagina web generale. Da sola **non** protegge l'API. |
| `ACCOUNTS` | Account facoltativi con cronologie separate. Vuoto significa nessun account aggiuntivo. |
| `ACCOUNTS_FILE` | File facoltativo per molti utenti; lascia vuoto alla prima installazione. |
| `SESSION_DAYS` | Giorni del login web ricordato, da 1 a 3650. Puoi scegliere `365` per ridurre la durata. |

### Facoltativo: proteggere la clipboard generale

Sostituisci le due righe vuote con **valori tuoi e diversi**, ad esempio:

```dotenv
API_TOKEN='SOSTITUISCI_CON_UN_TOKEN_CASUALE_TUO'
WEB_PASSWORD='SOSTITUISCI_CON_LA_TUA_PASSWORD_WEB'
```

Sono segnaposto, non password pronte da usare. Nel browser lascia il nome utente
vuoto e inserisci la password web. In Windows/Android imposta il token; nei due
Comandi Rapidi aggiungi `?token=TOKEN_CODIFICATO_PER_URL` agli URL.

### Facoltativo: aggiungere account separati

Per due clipboard private cambia solo la riga `ACCOUNTS`, con password tue:

```dotenv
ACCOUNTS='alice:SOSTITUISCI_PASSWORD_ALICE,bob:SOSTITUISCI_PASSWORD_BOB'
```

La clipboard generale **rimane disponibile**: proteggila separatamente se necessario.
Gli account usano nome e password nel browser e nelle impostazioni delle app;
non richiedono email o iscrizioni online. Scegli nomi univoci anche ignorando
maiuscole/minuscole.

Gli apici singoli in `.env` mantengono letterali `$` e `#`: in questi esempi non
usare un apice singolo nei valori. Nel formato a virgole non usare virgole o
ritorni a capo nelle password. Non pubblicare `.env` o URL con credenziali vere.
Per molti utenti vedi [file account e limiti](DOCKER.md#security-and-accounts).

## 4. Scaricare e avviare il server

Rimani nella cartella con i due file. Su Linux aggiungi `sudo` ai comandi Docker
se necessario, come spiegato al punto 1.

Controlla la configurazione senza stampare le password:

```text
docker compose config --quiet
```

Se non stampa errori, scarica l'immagine (serve accesso a internet):

```text
docker compose pull
```

Attendi il completamento, poi avvia in background:

```text
docker compose up -d
```

Controlla lo stato:

```text
docker compose ps
```

Devi vedere `Up` e, dopo l'avvio, **`healthy`**. `starting` nel primo minuto e
normale. Se non diventa sano, leggi gli ultimi messaggi:

```text
docker compose logs --tail=100 clipboard-bridge
```

Non condividere log integrali o l'output di `docker compose config`: possono
contenere dati personali o segreti. Non serve entrare nel container o copiarvi file.

## 5. Aprire la pagina e collegare i dispositivi

Sul computer server apri **`http://localhost:5088/`**. Sul telefono `localhost`
indica il telefono stesso, quindi devi usare **l'IP del computer server**.

| Host | Come trovare l'indirizzo |
|---|---|
| Windows | Esegui `ipconfig`: cerca IPv4 della scheda Wi-Fi/Ethernet connessa, non WSL/Docker/VPN. |
| Linux | Esegui `hostname -I` e scegli l'IP LAN, non quello del bridge Docker. Puoi controllare anche il router. |
| Mac | Impostazioni di Sistema > Rete > connessione attiva > Dettagli > TCP/IP. |
| NAS | L'IP della sua interfaccia di gestione, oppure l'elenco dispositivi del router. |

Esempio: se l'host fosse `192.168.1.50`, sul telefono apriresti
**`http://192.168.1.50:5088/`**. Non copiare questo IP senza cambiarlo con il tuo.
Se hai scelto `APP_PORT=5089`, sostituisci `5088` con `5089` in **tutti gli URL esterni**.
Per evitare cambi di indirizzo prenota l'IP dell'host nel router tramite DHCP.

1. Usa la stessa **rete locale fidata**, non una Wi-Fi ospiti che isola i dispositivi.
   Il firewall deve consentire la porta TCP scelta dai dispositivi fidati. Non
   disabilitarlo e non aprire porte sul router. Le porte pubblicate da Docker possono
   bypassare alcune regole firewall Linux: controlla le
   [note ufficiali](https://docs.docker.com/engine/install/ubuntu/#firewall-limitations),
   soprattutto su un VPS o host esposto pubblicamente. La password non cifra HTTP.
2. Dal telefono apri `http://IP_HOST:5088/health`: deve apparire JSON con stato sano
   e versione server. Questo verifica la raggiungibilita, non il login di tutti gli account.
3. Apri `http://IP_HOST:5088/`. Se configurato, usa nome vuoto e password web per
   lo spazio generale, oppure nome e password dell'account.
4. **Windows:** Impostazioni > Generali > **Modalita Client**. In Connessione inserisci
   `http://IP_HOST:5088`, imposta token/account se configurati e verifica la connessione.
   Non usare Modalita Server Windows per collegarti al container Docker.
5. **Android:** imposta lo stesso indirizzo base, scegli spazio condiviso o account,
   inserisci eventuali credenziali, verifica e salva.
6. **iPhone/iPad:** importa i due [Comandi Rapidi](README.it.md#download).
   Invio: metodo `POST`, URL `http://IP_HOST:5088/clipboard`.
   Ricezione: metodo `GET`, URL `http://IP_HOST:5088/clipboard/latest/raw`.
   **Sono campi da impostare nei Comandi Rapidi, non comandi da eseguire nel terminale.**
   Per corpo della richiesta, copia, foto e gruppi di file segui la
   [guida Apple completa](GUIDE.md#5-set-up-iphone-shortcuts).

Se usi l'account `alice`, entrambi gli URL includono le sue credenziali:

```text
http://IP_HOST:5088/clipboard?user=alice&password=PASSWORD_CODIFICATA_PER_URL
http://IP_HOST:5088/clipboard/latest/raw?user=alice&password=PASSWORD_CODIFICATA_PER_URL
```

Per il solo spazio generale protetto aggiungi invece `?token=TOKEN_CODIFICATO_PER_URL`.
Se non hai configurato protezioni, non aggiungere nulla. Codifica i **valori** per
l'URL (ad esempio `&` diventa `%26`), non l'intero indirizzo. `user` seleziona
l'account: non e una cartella nel percorso. Questi valori sono leggibili e HTTP
li trasmette senza cifratura. Non mostrarli in screenshot o segnalazioni pubbliche.

**Primo test:** salva nel browser una nota innocua, ad esempio `Test Clipboard Bridge`;
premi Ricevi sul telefono. Invia poi un altro testo dal telefono e aggiorna la
cronologia web. Tutti devono usare **lo stesso spazio/account**. Prova poi una
piccola foto o un file. Su iPhone le azioni rimangono manuali, non automatiche in background.

Fuori casa usa una VPN privata, ad esempio Tailscale, sull'host e sui dispositivi,
con l'indirizzo raggiungibile della VPN. Per conservare l'IP LAN anche fuori casa
serve configurare separatamente un subnet router: [guida rete](GUIDE.md#local-network-vpn-and-subnet-routing).
**Non esporre direttamente la porta del server su internet.**

## 6. Aggiornare e fare il backup

Torna nella cartella d'installazione: `cd ~/clipboard-bridge` su Linux/Mac oppure
`Set-Location "$HOME\clipboard-bridge"` su PowerShell, o il tuo percorso personalizzato.
Non ripetere i download iniziali: conserva `.env`, credenziali e dati esistenti.

### Backup prima di aggiornare

Ferma le scritture per copiare dati coerenti:

```text
docker compose stop
```

Su Linux/Mac, con `DATA_ROOT=./data`:

```bash
mkdir -m 700 ../clipboard-bridge-backup-before-update
sudo cp -a data compose.yaml .env ../clipboard-bridge-backup-before-update/
```

Su PowerShell:

```powershell
New-Item -ItemType Directory -Path ..\clipboard-bridge-backup-before-update
Copy-Item -Recurse -Path data,compose.yaml,.env -Destination ..\clipboard-bridge-backup-before-update
```

Ogni volta scegli un **nuovo nome di cartella backup**, senza unire copie diverse.
Se hai cambiato `DATA_ROOT`, copia quella cartella al posto di `data`. Il backup
contiene segreti e clipboard: conservalo privatamente, meglio su un altro disco.
Se la copia fallisce, non aggiornare: riavvia il vecchio container con
`docker compose start` mentre cerchi la causa.

### Passare a una nuova versione

1. Leggi le [release](https://github.com/Mattboxx/Clipboard-Bridge/releases): scegli
   una versione **server** pubblicata, non il numero dell'app Windows o Android.
2. Modifica solo `APP_IMAGE` in `.env` con il tag desiderato. Oggi l'esempio stabile
   e `APP_IMAGE=ghcr.io/mattboxx/clipboard-bridge-server:1.0.10`. Mantieni percorso
   dati, porta e credenziali. Salva.
3. Esegui nell'ordine, con `sudo` su Linux se necessario:

```text
docker compose config --quiet
docker compose pull
docker compose up -d
docker compose ps
```

Attendi `healthy`, controlla `/health`, cronologia e un trasferimento. Se il download
fallisce dopo il backup, `docker compose start` puo riavviare il container vecchio
ancora presente: risolvi l'errore prima di ricrearlo.

**Con un tag fisso `1.0.10`, `pull` non passa da solo alla versione successiva:**
prima devi cambiarlo. `latest` segue le versioni stabili quando scaricato, ma
non aggiorna da solo un container in esecuzione. `edge` non e consigliato per
un'installazione stabile da principianti.

### Cambiare impostazioni, fermare o ripristinare

- Modifica `.env`, salva e usa **`docker compose up -d`**: un semplice `restart`
  non applica le nuove variabili del container.
- Ferma temporaneamente con `docker compose stop`, riparti con `docker compose start`.
  Il riavvio automatico dell'engine vale salvo arresto volontario del container;
  su PC deve partire anche Docker Desktop.
- `docker compose down` rimuove il container, non questa cartella dati montata.
  Per ricrearlo usa `up -d` dalla stessa cartella con lo stesso `.env`.
  **Non aggiungere `--volumes`, non cancellare `data`, non eseguire pulizie/prune.**
- Per ripristinare: ferma il servizio, conserva una copia separata dei dati attuali,
  ripristina l'intera cartella dati del backup nel `DATA_ROOT` corretto insieme ai
  suoi `.env` e Compose. Usa la versione immagine di quel backup, avvia con `up -d`
  e controlla. Non mescolare copie di date diverse o presumere che una versione
  precedente legga dati di una versione nuova.

## Problemi comuni

Esegui i controlli nella cartella d'installazione, con `sudo` per Docker se necessario.
Non eliminare configurazione o cronologia per far sparire un errore.

| Problema | Controllo |
|---|---|
| Comando `docker` assente | Installa Docker sull'host e riapri il terminale. |
| Compare solo Client / daemon non raggiungibile | Avvia Docker Desktop; su Ubuntu controlla `sudo systemctl status docker` e premi `q` per uscire. |
| Accesso negato al socket Docker | Usa `sudo` su Linux, non `chmod 777`. |
| `compose` non riconosciuto | Installa il plugin Compose ufficiale o aggiorna Docker Desktop. Usa `docker compose`, non il vecchio `docker-compose`. |
| `no configuration file provided` | Cartella sbagliata: cerca `compose.yaml` con `ls -la` o `Get-ChildItem -Force`. |
| YAML/variabile non valida | Controlla nome file, apici e formato testo. Se il modello e danneggiato riscarica solo `compose.yaml`, preservando `.env`. Usa `config --quiet`. |
| Nome container gia usato | Controlla `docker ps -a` e trova l'installazione esistente: non eliminarla o avviare due server sugli stessi dati. |
| Porta occupata | Cambia `APP_PORT=5089`, usa `up -d` e modifica gli URL. Controlla anche Modalita Server dell'app Windows. |
| Immagine non trovata / accesso negato | Verifica nome, tag pubblicato, internet/DNS/proxy verso GHCR. Non serve un token GitHub privato. |
| `no matching manifest` | Serve un host Linux amd64/arm64 o Docker Desktop con container Linux, non ARM 32 bit o container Windows. |
| `unhealthy` / riavvii / errore storage | Leggi `docker compose logs --tail=100 clipboard-bridge`, controlla disco e permessi della cartella dati. Non cancellare l'indice; [guida recupero](DOCKER.md#history-storage-errors). |
| Si apre sul server ma non sul telefono | Usa l'IP LAN dell'host, non localhost/IP container. Controlla stessa LAN, Wi-Fi ospiti, firewall, porta e `/health`. |
| 401 / cronologie diverse | Usa lo stesso spazio/account e credenziali corrette su tutti i dispositivi. Il login web non autentica le app. Codifica le credenziali URL. |
| Modifiche `.env` ignorate | Salva e usa `docker compose up -d`, non solo `restart`. |
| Errore 413 | Controlla `MAX_UPLOAD_MB` per l'intero gruppo e gli eventuali limiti del reverse proxy. |

Per chiedere aiuto indica sistema, versione, passaggi ed errori **ripuliti**:
mai `.env`, URL con password, file personali o configurazioni complete.

## Store e documentazione avanzata

Questa procedura non richiede store. Se preferisci una piattaforma con interfaccia
grafica, trovi gli adattatori ZimaOS, Portainer, Umbrel, Runtipi e Dockge nel
[catalogo separato](https://github.com/Mattboxx/Clipboard-Bridge-AppStore/blob/main/README.it.md).
Non seguire entrambe le installazioni per gli stessi dati.

Il server web offre sette lingue, incluso l'italiano, dal selettore nell'intestazione.
Apri **Collega i tuoi dispositivi** per il riepilogo degli indirizzi e delle app.

[File account e sicurezza](DOCKER.md#security-and-accounts) |
[Recupero di una cronologia danneggiata](DOCKER.md#history-storage-errors) |
[Guida completa delle app e dei Comandi Rapidi](GUIDE.md)
