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

