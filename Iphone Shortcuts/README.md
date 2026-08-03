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

## Nota in italiano

I file `.shortcut` sono esportazioni firmate da Apple e non possono essere modificati e
rifirmati da Windows. Dopo averli installati, applica sull'iPhone la procedura descritta
nella [guida completa](../GUIDE.md#51-send-clipboard-to-server). Il Comando rapido
riconosce automaticamente uno o più elementi: lo ZIP viene usato soltanto per il
trasporto e sul server i file appaiono come un unico gruppo, non come un archivio ZIP.
