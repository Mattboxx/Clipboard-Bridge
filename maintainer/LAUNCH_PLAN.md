# Launch preparation, not publication

Status: **draft; maintainer approval required**. No announcements, directory submissions,
new stable release or app-store update is authorized by this document. SignPath is deferred.

## Positioning

Clipboard Bridge shares text, photos and files between Windows, Android and Apple
Shortcuts through a host you control. Start with Windows Server mode; use an always-on
Docker/NAS server for shared history, browser access and isolated optional accounts.
LAN or private VPN, no mandatory cloud service or online account. Do not promise
continuous automatic iPhone synchronization or unrestricted Android background access.

## 25-second demo storyboard

| Time | Actual action to record | Honest caption |
|---|---|---|
| 0-4s | Show Windows Server mode address and a phone already configured with that address | One host, your own network |
| 4-10s | Copy `Hello from Windows` with an emoji, Send on Windows, Receive on Android, paste in a blank note | Windows to Android; show the manual Receive |
| 10-16s | On iPhone share a sample photo to Load Clipboard; on Windows receive and show the thumbnail | iPhone uses an Apple Shortcut |
| 16-22s | Select three public sample files, send once through Docker host, show one history row and restore all | One group, three original files |
| 22-25s | Open History with the configured hotkey, then close it with the same combination | Configurable History toggle |

Use a demo-only account, generic filenames and a non-personal wallpaper. Hide password
fields and URL query credentials. Do not use an edited animation as evidence of a real
transfer. Record on real devices with consent; none were available for a full demo here.

## Verified comparison, 14 October 2026

These are documented features, not a hands-on competitive benchmark. `Not verified`
means unknown, not unsupported. Do not claim competing tools are text-only.

| Tool | Platforms documented | Text / images / file groups | Host/history model | Offline LAN / online account | Automation |
|---|---|---|---|---|---|
| Clipboard Bridge | Windows, Android; iPhone/iPad/Mac via Shortcuts; Linux Docker/Python host | Text, photos, arbitrary files; one ordered group | Windows host or Docker host; server history; optional accounts | LAN supported; no online account | Windows optional sync; Android foreground limits; Apple actions run manually |
| [LocalSend](https://localsend.org/) | Windows, macOS, Linux, Android, iOS | Text and arbitrary files documented; exact clipboard-group restoration not verified | Direct device selection; shared server history not verified | Offline LAN; no account | Select content and recipient to send |
| [KDE Connect](https://github.com/KDE/kdeconnect-kde) | Linux, Windows, Android, iPhone/iPad; see platform-specific packages | Shared clipboard and file/URL sharing documented; batch behavior not verified here | Paired devices; shared retained server history not verified | Local paired workflow; online-account requirement not asserted here | Clipboard plugin behavior varies by OS |
| [UniClipboard](https://github.com/UniClipboard/UniClipboard) | Desktop Windows/macOS/Linux; mobile compatibility/beta products | Text, images and files documented; exact multi-file grouping not verified | P2P spaces and local searchable history; different architecture from a persistent Docker clipboard hub | No cloud account; LAN and cross-network features documented | Desktop real-time sync; mobile capabilities version-dependent |

The practical distinction is a simple persistent clipboard hub and uniform latest-item
API, not that other projects cannot share files or have weaker security.

## Channels and gates

| Channel | Verified route / current limitation | Next step after approval |
|---|---|---|
| r/selfhosted | [Rules](https://www.reddit.com/r/selfhosted/about/rules/) did not expose full text to the tool. Recent moderator messages require a self-hostable released app, docs and restrained promotion. | Read live rules/flairs, disclose AI assistance if required, ask mods if uncertain; publish one useful post, not repeated ads |
| r/opensource | [Rules](https://www.reddit.com/r/opensource/about/rules/) require manual verification | Discuss MIT source and contributions, not repeated download advertising |
| r/windows | [Rules](https://www.reddit.com/r/windows/about/rules/) require manual verification | Lead with Windows tray/hotkeys, standard-user install and unsigned-build caveat |
| r/Android | [Rules](https://www.reddit.com/r/Android/about/rules/) require manual verification | Use the permitted developer/promotion venue; disclose beta and background limits |
| r/homelab | [Rules](https://www.reddit.com/r/homelab/about/rules/) require manual verification | Focus on persistence, NAS setup and rollback |
| r/raspberry_pi | [Rules](https://www.reddit.com/r/raspberry_pi/about/rules/) require manual verification | Show a real ARM64 server deployment first |
| selfh.st | [Submit content](https://selfh.st/submit/) and [directory criteria](https://selfh.st/apps-about/) support proposing project details | Submit the listing brief from COMMUNITY_DRAFTS.md; acceptance is not guaranteed |
| Dev.to | Technical article draft prepared, not posted | Review examples, publish as the maintainer, answer practical questions |
| Hacker News | [Show HN guidelines](https://news.ycombinator.com/showhn.html): make a working project easy to try; not just a landing page or update announcement | Only after demo and beginner pilot; no vote requests or coordinated comments |
| AlternativeTo | Search did not find a confirmed listing for this specific Mattboxx project; [FAQ](https://alternativeto.net/faq/) must be checked in the logged-in UI | Check duplicates, propose accurate categories, not fake competitor limitations |
| Awesome Selfhosted | [Contribution rules](https://github.com/awesome-selfhosted/awesome-selfhosted-data/blob/master/CONTRIBUTING.md) require a first release older than four months and disallow LLM-generated contributions | First release 25 June 2026: not yet eligible on 14 October; after 25 October, maintainer must write the proposal personally and verify architectural eligibility |

Do not submit these AI-assisted drafts where a community prohibits them. Rewrite and
review personally when permitted; never claim that a generated submission is human-only.
Rule checks are point-in-time and must be repeated on the intended posting day.

The limited Reddit findings above come from a [recent moderator removal message](https://www.reddit.com/r/selfhosted/comments/1wx078h/removed/),
not a complete retrieval of the current rule list. Do not infer posting permission from it.

## NAS distribution

Existing integration is a **custom catalog**, not acceptance into official stores.
ZimaOS uses the permanent `store.json` URL, not a release ZIP. Its generator supplies
index/meta/compose JSON. Existing Umbrel, Runtipi, Portainer and Compose/Dockge files
are custom adapters. Keep `/data`, account values, stable IDs and installed volume
paths unchanged when updating. Publish an image before changing store tags to it.

TrueNAS can be evaluated as a custom Compose app; Unraid can be evaluated as a custom
Docker template. Neither has an official project listing verified here. Do not add
unproven one-click claims; test on those systems before producing new adapters.

## SEO and measurement

- Repository already has relevant clipboard-sync, self-hosted, Docker, Android,
  Windows and ios-shortcuts topics. Proposal: replace generic `mobile` with
  `file-transfer` only after approval; no topic change was pushed during the audit.
- Existing website has a specific title, description, canonical URL, Open Graph and
  structured app metadata. Prefer useful setup articles over repetitive keywords.
- Suggested description: `Share text, photos and files between Windows, Android and
  iPhone. Use your Windows PC or a Docker host, on a trusted LAN or private VPN.`
- Weekly snapshot: release asset `download_count`, stars, issue themes and GitHub
  traffic when accessible. Counts are aggregate; do not add application analytics.
- Baseline: 5 stars, 0 forks; GitHub returned 117 views/45 unique visitors and
  131 clones/51 unique cloners for its available traffic window. This is not active
  usage and does not prove installation or a first successful transfer.
- Voluntary beginner pilot measures time-to-first-transfer and confusion directly.
  No telemetry, email list requirement or clipboard-content collection.

## Release gate

- [ ] Review the technical audit and final source diff.
- [ ] Python, Android, frozen Windows and Docker compatibility checks pass.
- [x] Native ARM64 candidate packages are verified on the ARM64 runner.
- [ ] Complete the device/manual checklist and 3-5-person beginner pilot.
- [ ] Record a real demo; keep every manual action visible.
- [ ] Document unsigned Windows binaries clearly; SignPath is not a launch promise.
- [ ] Verify APK certificate continuity and original Shortcut hashes.
- [ ] Finish all seven release assets and compute checksums on final bytes.
- [ ] Remove preparation banners and validate download URLs before publishing Pages.
- [ ] Obtain separate maintainer approval for releases, store deployment and promotional posts.
- [ ] Publish server image, then catalogs, then matching website/docs; smoke-test public links.
