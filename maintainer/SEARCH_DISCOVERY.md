# Search discovery: English first

The public project website is English by default. Keep the Italian tutorial and
README, but prioritize useful answers for international users with mixed Apple,
Windows and Android devices. Do not rename the project to chase a broad keyword.

## Pages and search intent

| Page | Reader's question | Primary English phrases |
| --- | --- | --- |
| [Homepage](https://mattboxx.github.io/Clipboard-Bridge/) | What does this do, and what do I download? | cross-platform clipboard sharing; Windows iPhone Android clipboard |
| [Windows and iPhone](https://mattboxx.github.io/Clipboard-Bridge/windows-iphone-clipboard.html) | How do I copy and paste between my PC and iPhone? | share clipboard between Windows and iPhone; Windows to iPhone clipboard; copy paste without iCloud |
| [Apple and Android](https://mattboxx.github.io/Clipboard-Bridge/apple-android-clipboard.html) | How do I connect devices from different ecosystems? | iPhone to Android clipboard; Mac Android clipboard; Apple and non-Apple clipboard sharing |
| [Full tutorial](https://mattboxx.github.io/Clipboard-Bridge/tutorial.html) | How do I set it up and fix a failed transfer? | self-hosted clipboard setup; iPhone Shortcuts clipboard; Windows clipboard server |

The use-case guides must remain genuinely different and useful, not cloned
keyword pages. Link to them from the homepage, tutorial and README. Explain
Control Center and Share Sheet access early: after configuration, iPhone users
can run Send/Receive without returning to the Shortcut editor.

## Honest platform descriptions

- Native apps: Windows and Android; Android is a beta.
- Apple: user-triggered Shortcuts on iPhone/iPad and a manual Mac workflow. Do not
  promise a native Mac app or automatic background iOS synchronization.
- All clients need one reachable host: Windows Server mode or the standalone
  Docker/Python server. No direct mobile-to-mobile hosting.
- Accounts and tokens are optional. URL credentials are readable; HTTP does not
  encrypt them. Public documentation does not make private clipboard endpoints
  suitable for public exposure.
- No fabricated reviews, stars, screenshots, physical-device test claims,
  competitor comparisons, hidden keyword blocks or instructions to AI crawlers.

Structured data identifies the software and articles, without invented ratings.
It does not establish eligibility for a Google software rich result: Google's
[software application requirements](https://developers.google.com/search/docs/appearance/structured-data/software-app)
include genuine review/rating data for that feature.

## Google Search Console: owner action

1. Sign in to [Google Search Console](https://search.google.com/search-console/).
2. Choose or add the **URL-prefix** property
   `https://mattboxx.github.io/Clipboard-Bridge/` (not a domain property for all of
   `github.io`, which is not ours).
3. If asked to verify by HTML file, the existing published file is
   `google5c0f8ebcc14bd106.html`. Keep it at the same URL; its presence alone does
   not mean the current signed-in account is verified. Use the file requested
   by Google if the account/property requires another one.
4. Under **Sitemaps**, submit
   `https://mattboxx.github.io/Clipboard-Bridge/sitemap.xml`.
5. Inspect the homepage and the two English use-case URLs. Check the live page
   and request indexing once per new or substantially updated page.
6. In **Performance**, compare English query impressions and clicks over several
   weeks. Inspect the actual landing pages and improve answers, not repetitions.

Google describes [recrawl requests](https://developers.google.com/search/docs/crawling-indexing/ask-google-to-recrawl)
as discovery requests, not guaranteed indexing. Repeated requests do not make
them faster. No Search Console submission is implied by committing these files.
Do not use the Google Indexing API for ordinary software pages.

## Bing and IndexNow

The site publishes an IndexNow ownership file in the project directory. The
explicit `keyLocation` scopes notifications to this GitHub Pages project, not
other repositories on the same host. This is a public ownership proof, not a
clipboard password or API token.

After a successful Pages deployment:

```sh
python scripts/notify_search_engines.py
python scripts/notify_search_engines.py --submit
```

The first command is a local preview, with no network request. The second first
checks the live key file, then submits only the public HTML URLs in the sitemap.
It rejects external URLs, local host addresses, query strings and missing pages.
It never submits private clipboard history or account URLs.

HTTP **200** means the notification was received, **not** that pages were indexed.
HTTP **202** means ownership validation is pending. Do not repeatedly submit an
unchanged sitemap. See the [IndexNow protocol](https://www.indexnow.org/documentation).
This notification does not submit the Google Search Console property.

For indexing reports, add the URL-prefix site in
[Bing Webmaster Tools](https://www.bing.com/webmasters/), verify ownership or import
a verified Search Console property, then submit the sitemap there. That requires
the owner's account and is separate from an IndexNow receipt.

## GitHub Pages and search/AI crawlers

The pages are static HTML: the core explanation, links and download paths do not
require JavaScript. JSON-LD and canonical URLs describe the same visible content.
English/Italian alternate links exist only for genuinely equivalent tutorials.

Bots read `https://mattboxx.github.io/robots.txt` at the **origin root**, not the
project's `/Clipboard-Bridge/robots.txt`. The root currently returns 404: it does
not prohibit crawling. The project's robots file is not an authoritative
origin-wide rule and is not a substitute for submitting the sitemap. If a profile
Pages site is added later, review its root rules so this project is not blocked.

[OpenAI's crawler documentation](https://developers.openai.com/api/docs/bots)
distinguishes OAI-SearchBot (search) from GPTBot (training). Allowing search
crawling does not require opting into training and does not guarantee a citation.
Do not claim an OpenAI registration or submission has occurred.

Google's [AI search guidance](https://developers.google.com/search/docs/fundamentals/ai-optimization-guide)
uses ordinary search fundamentals: useful, crawlable content. It says `llms.txt`
does not improve Google visibility. This project does not depend on a special
AI prompt file, hidden instructions or a promise of first position.

## Checks before publishing

```sh
python -m pytest -q tests/test_site_seo.py tests/test_release_metadata.py
python scripts/release_metadata.py --check
python scripts/notify_search_engines.py
```

Preview at desktop and phone widths. Verify that metadata, internal links,
Control Center/Share Sheet instructions and network limitations agree. After
deploying, check HTTP 200 for each canonical URL and unchanged verification
files. Keep `lastmod` dates tied to real page changes, not every build.

Monitor Search Console/Bing reports and real support questions. Community posts
and tutorials should disclose project authorship and link to the relevant guide;
do not buy links, post fake recommendations or promise a ranking deadline.
