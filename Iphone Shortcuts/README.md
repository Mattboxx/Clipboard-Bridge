# iPhone Shortcuts

The two `.shortcut` files in this folder are Apple-signed exports. Apple does not allow a
signed Shortcut to be edited and re-signed on Windows.

To enable automatic multiple-file sharing, install the two Shortcuts, then apply the
actions described in [GUIDE.md](../GUIDE.md#51-send-clipboard-to-server) on the iPhone.
The updated **Load Clipboard** Shortcut automatically:

- uses Share Sheet input when available, otherwise the current clipboard;
- detects whether it received one item or several items;
- sends one item to `/clipboard`;
- appends the URL-encoded file name for a single non-text item, preserving uncommon
  extensions such as `.shortcut`;
- creates a temporary transport ZIP for several items and sends it to
  `/clipboard/bundle`.

The updated **Download Clipboard** Shortcut checks `/clipboard/latest/meta`, extracts a
group only when required, and copies every member together. Users never choose a content
type manually.

Account and token URL parameters remain optional and compatible with the existing
exports. No interactive login, pairing, token renewal or required HTTP header is
introduced. Header authentication is an optional alternative, not a new prerequisite.
Copied RTF text is converted by the updated servers; real `.rtf` documents remain files.

## Links must be sent as text, not downloaded pages

In Load Clipboard, turn a URL into a **Text** result. For a Safari Web Page, extract
its **URL** property first. Send that result to the host's `/clipboard` endpoint
with **POST > Request Body: JSON > text (Text)**. Keep the request URL pointed at
your Clipboard Bridge host; do not GET the shared address or pass the original URL
object as a File body. Actual files and multi-file ZIP uploads keep their existing
branches. See the [link troubleshooting steps](../GUIDE.md#sharing-a-link-sends-html-instead-of-its-address).

These are edits to make on the Apple device, not changes already included in the
signed exports in this folder.

## Nota in italiano

I file `.shortcut` sono esportazioni firmate da Apple e non possono essere modificati e
rifirmati da Windows. Dopo averli installati, applica sull'iPhone la procedura descritta
nella [guida completa](../GUIDE.md#51-send-clipboard-to-server). Il Comando rapido
riconosce automaticamente uno o più elementi: lo ZIP viene usato soltanto per il
trasporto e sul server i file appaiono come un unico gruppo, non come un archivio ZIP.

Se condividendo un link Reddit ricevi HTML, nel ramo dei link usa un'azione **Testo**
con l'indirizzo; per una pagina Safari estrai prima la proprieta **URL**. Invia il
risultato all'host con **POST > Corpo della richiesta: JSON > text (Testo)**, non come
File. L'URL della richiesta deve rimanere quello di Clipboard Bridge, non Reddit.
Foto, documenti e gruppi di file mantengono i loro rami. La modifica va applicata e
verificata sull'iPhone: le esportazioni firmate qui non sono state modificate.

## Built-in Apple actions only

The signed exports here require only Apple Shortcuts. Text and files are sent
directly over HTTP; Base64 encoding and additional apps are not required.

### Caricamento diretto con il tuo account

Usa i due comandi esistenti, senza azioni Base64 o app aggiuntive. I file firmati
non sono stati modificati: duplica i comandi importati prima di adattarli. Copia
dalla pagina di configurazione l'indirizzo completo del server, porta inclusa.

In ogni azione **Ottieni contenuti dell'URL** diretta al server Docker, aggiungi:

| Intestazione | Valore |
| --- | --- |
| `X-Clipboard-User` | Nome del tuo account Clipboard Bridge |
| `X-Clipboard-Password` | Password di quell'account |

Rimuovi eventuali parametri `token`, `user` e `password` dai vecchi URL.
Non codificare la password in Base64. Le intestazioni sono comunque leggibili
sulla rete con HTTP: usa una
LAN fidata o una VPN privata. Tieni le credenziali in un file locale o richiedile
al momento; non condividere un'esportazione che le contiene. L'host Windows
integrato non gestisce gli account del server Docker.

**Invia:** mantieni `POST /clipboard`. Per testo o link usa **Corpo della
richiesta: JSON** con un campo **Testo** `text`; per una foto o un file usa
**Corpo della richiesta: File** e passa l'originale. Per conservare il nome,
aggiungi `X-Clipboard-Filename` con il nome codificato per URL. I gruppi usano
la [procedura ZIP esistente](../GUIDE.md#51-send-clipboard-to-server).

**Ricevi:** mantieni `GET /clipboard/latest/raw` con le stesse intestazioni.
La risposta contiene direttamente il testo o i byte del file: passala a
**Copia negli appunti** oppure **Salva file**, senza decodificarla. Per
gestire anche gruppi ed evitare di sovrascrivere la clipboard quando non
ci sono elementi, segui la [variante con metadati](../GUIDE.md#52-receive-server-to-clipboard).
