# Server 1.0.10

## Scope

- Seven-language standalone web UI, login and expandable device setup guide:
  English, Italian, Spanish, French, German, Portuguese and simplified Chinese.
- Public website/tutorial links beside optional Ko-fi support. Fixed external URLs,
  `noopener noreferrer` and the existing no-referrer policy avoid credential leakage.
- Existing shared/account API URLs, session duration, port and data paths preserved.
- Translation JSON ships in the explicit Docker context; source-only installations
  must keep it beside the server script. No new dependency.
- Catalog metadata refreshed for ZimaOS v2 Productivity; all existing store adapters
  pin the same server version. Official inclusion requires upstream acceptance.
- Windows 2.0.19, Android beta.12 and signed Apple exports are unchanged.

## Verification

- Local full Python suite: 554 passed, 15 environment-dependent skips.
- Focused server/metadata/site suite after documentation edits: 164 passed.
- Real disposable Docker tests: 13 passed, including all seven languages, transfers,
  account isolation, damaged storage handling and 1.0.9-to-1.0.10 data/session upgrade.
- Critical Ruff checks passed. Catalog source validator passed.
- No user's NAS container, desktop installation or private data was modified.
- Physical Android/iPhone/NAS installation and human native-language review remain
  manual checks; automated translation coverage is not a linguistic certification.

Publication commit, image digest, workflows and upstream submission are recorded
in the delivery pull requests. A proposed upstream app is not an accepted app.
