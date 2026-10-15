# r/selfhosted: reviewed links, message and posting instructions

Status: **not posted**. The maintainer asked for a message to send personally. The demo
and tutorial are published on the project website, not submitted to Reddit or Dev.to.
Read the final text yourself before sending it and do not claim tests you have not run.

## Title

Clipboard Bridge: a self-hosted clipboard for Windows, Android and Apple Shortcuts

## Body

Hi! I'm the maintainer of Clipboard Bridge. I wanted a shared place for copied text,
photos and files so I wouldn't have to send everything to myself through a chat app.

You can run the host on a Docker/NAS server, or let the Windows app be the host without
extra hardware. The standalone server adds browser access, persistent history and
optional separate accounts. There is no mandatory cloud service or online account.

The clients are a Windows tray app, a native Android app and two Apple Shortcuts.
Text, images and files follow the same latest-item flow. Files sent together stay in
one history entry; copied rich text is received as plain Unicode, while documents keep
their original bytes.

This is for a trusted LAN or private VPN, not direct public exposure. Windows has
optional synchronization; Android background clipboard access is restricted by the OS;
iPhone actions run when you trigger the Shortcuts. Android is a beta and the Windows
downloads are currently unsigned. Account/token URLs are optional and readable; plain
HTTP does not encrypt them.

- Source and downloads: https://github.com/Mattboxx/Clipboard-Bridge
- Tutorial and live web demo: https://mattboxx.github.io/Clipboard-Bridge/tutorial.html
- Docker/custom-store setup: https://github.com/Mattboxx/Clipboard-Bridge-AppStore

The walkthrough illustrates Windows-to-iPhone sending and receiving with a real
Windows screenshot. A separate technical recording shows the optional web interface
with independent HTTP checks. Neither is a physical phone-to-PC recording.
The source is MIT-licensed. AI tools have been used
substantially for implementation, tests and documentation, including this draft.

I'd appreciate feedback on the setup instructions and everyday clipboard workflow,
especially from people using Windows with Apple and Android devices. Please report
versions and steps, not private clipboard contents or credential URLs.

## If the moderation bot asks about AI

Answer its actual question, rather than reposting a temporarily removed post.
This is a truthful starting point to review personally:

> AI coding assistants were used substantially for implementation, bug fixes, tests,
> documentation and drafting this post. I direct the requirements and maintain the
> project and releases. The main walkthrough is an illustrated Windows/iPhone workflow,
> not a physical-phone test. A separate recording shows the actual web UI with sample data.

Do not claim AI was used only for grammar. Do not claim every line was reviewed manually.

## Come pubblicarlo

1. Accedi al tuo account Reddit e apri [r/selfhosted](https://www.reddit.com/r/selfhosted/).
2. Leggi le regole aggiornate e i post fissati. Se il tuo account e' usato solo per
   promozione, o non sei sicuro della maturita' richiesta al progetto, chiedi prima
   ai moderatori. Non creare attivita' finta per aggirare i requisiti.
3. Se le regole consentono un post autonomo, apri
   [Create post](https://www.reddit.com/r/selfhosted/submit/?type=self) e scegli
   il formato testo. Inserisci il Title e il Body sopra; scegli il flair pertinente
   tra quelli effettivamente disponibili. Non inventare un flair e non scegliere "No AI".
4. Se viene richiesto il New Project Megathread, usa il thread corrente: non un post
   vecchio trovato da una ricerca. Il repository e' pubblico dal 25 giugno 2026;
   questo soddisfa soltanto il criterio d'eta' di tre mesi, non tutti gli altri requisiti.
5. Controlla l'anteprima, i link, la dichiarazione AI e l'assenza di dati privati.
   Il link al tutorial contiene anche la demo: non serve caricare un video separato.
6. Pubblica una volta sola e rimani disponibile per rispondere. Se il bot chiede una
   dichiarazione, rispondi sotto il suo commento seguendo le istruzioni correnti.
   Non ripubblicare per aggirare una rimozione; se rimane bloccato, usa il modmail.

## Regole verificate e limiti della verifica

La pagina [regole](https://www.reddit.com/r/selfhosted/about/rules/) non ha reso
disponibile l'elenco completo alla consultazione automatica. L'
[annuncio ufficiale dei moderatori](https://www.reddit.com/r/selfhosted/comments/1sey9ch/quarter_2_update_revisiting_rules_again/)
descrive il megathread e il bot che richiede una spiegazione dell'uso di AI. I
[messaggi recenti di moderazione](https://www.reddit.com/r/selfhosted/comments/1x3f8wo/removed/)
ribadiscono documentazione, disponibilita' del software e promozione non ripetitiva.
Sono fonti consultate il 14 ottobre 2026, non un'autorizzazione a pubblicare.
I test fisici delle ultime build mobili sono ancora da fare: non presentare il
progetto come collaudato su ogni dispositivo o automaticamente approvato dai moderatori.

## Tutorial su Dev.to

Il tutorial e' gia' pubblicato sul sito. Per proporlo anche su Dev.to:

1. Apri [DEV](https://dev.to/) e accedi o crea personalmente il tuo account.
2. Scegli **Create Post**, passa all'editor Markdown se necessario e usa il testo di
   [TUTORIAL_DEVTO.md](TUTORIAL_DEVTO.md). L'header `published: false` mantiene la bozza.
3. Lascia il canonical URL del tutorial ufficiale, sostituisci eventuali campi che
   l'editor gestisce separatamente e controlla l'anteprima.
4. Verifica personalmente istruzioni e dichiarazione AI. Non caricare screenshot
   delle tue credenziali e non scrivere che i test sui telefoni sono gia' completati.
5. Pubblica dal tuo account quando il contenuto ti rappresenta; non l'ho inviato io.

La [content policy DEV](https://dev.to/terms) richiede contenuto sostanziale e utile,
non soltanto un link promozionale. L'articolo contiene la procedura completa.
