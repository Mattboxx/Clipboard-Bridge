# Upstream research, 27 October 2026

These are observed submission routes, not a promise of acceptance. Recheck the
owners' latest instructions before opening a PR. Submitted request links are
tracked in this package's README; none implies store acceptance.

## Big Bear

- Canonical source: [big-bear-universal-apps](https://github.com/bigbeartechworld/big-bear-universal-apps), `main`.
- Examined revision: `2faf2164ef3005699e866ca94dda0dec6f70e7b6`.
- [Schema and source format](https://github.com/bigbeartechworld/big-bear-universal-apps/blob/2faf2164ef3005699e866ca94dda0dec6f70e7b6/SCHEMA.md).
- [Validator](https://github.com/bigbeartechworld/big-bear-universal-apps/blob/2faf2164ef3005699e866ca94dda0dec6f70e7b6/scripts/validate-apps.sh),
  [converter](https://github.com/bigbeartechworld/big-bear-universal-apps/blob/2faf2164ef3005699e866ca94dda0dec6f70e7b6/scripts/convert-to-platforms.sh).
- App source is `apps/<id>/app.json` plus clean Compose. The pipeline generates
  `converted/casaos/<id>/docker-compose.yml`; the downstream
  [CasaOS repository](https://github.com/bigbeartechworld/big-bear-casaos) uses
  `Apps/<id>/docker-compose.yml`. Do not confuse source with generated output.
- The vendored schema and its MIT license are unchanged upstream files. Only
  CasaOS conversion is enabled in this proposed universal definition.

## LinuxServer AppStore

- [Current repository and contributing policy](https://github.com/WisdomSky/LinuxServer-AppStore#contributing), `main`.
- Examined revision: `22090955ae27a6f8492c17b6724f9088975d3017`.
- The owner asks contributors not to submit PRs because the catalog is generated.
  It catalogs LinuxServer.io images, not arbitrary compatible Docker images.
- Its `publish-v2.yml` generates the catalog from `Apps/` and `store-config.json`.
  This does not authorize hand-editing generated apps or inventing a new app list.
- [LinuxServer PUID/PGID explanation](https://docs.linuxserver.io/general/understanding-puid-and-pgid/).
  Clipboard Bridge has a Python base, not LinuxServer's ownership-init entrypoint.
  The numeric-user example is a manual Docker deployment, not store eligibility.

## mr-manuel HomeAutomation

- [Repository](https://github.com/mr-manuel/CasaOS-HomeAutomation-AppStore), `master`.
- Examined revision: `04c92f56a28844a6ed08b3ba72d7cf3dde7eeb80`.
- [Observed per-app layout](https://github.com/mr-manuel/CasaOS-HomeAutomation-AppStore/tree/04c92f56a28844a6ed08b3ba72d7cf3dde7eeb80/Apps/Mosquitto).
- [Registered category](https://github.com/mr-manuel/CasaOS-HomeAutomation-AppStore/blob/04c92f56a28844a6ed08b3ba72d7cf3dde7eeb80/category-list.json)
  is `HomeAutomation`. Some legacy manifests use the spaced label. The proposal
  uses the registered ID and modern `en_US` localization keys.
- No additional `CONTRIBUTING.md` or per-app `store.json` was found. The observed
  publication process archives the repository; follow the owner's process.
- Clipboard Bridge is a companion utility, not home-device automation. Ask whether
  that fits the store; the category is not a claim of MQTT/Home Assistant support.
