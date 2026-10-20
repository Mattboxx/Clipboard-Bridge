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
