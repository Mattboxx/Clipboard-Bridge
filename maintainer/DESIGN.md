# Desktop and Website Design

## Reference and Adaptation

The maintainer requested a lightweight design deeply inspired by
[Plexo](https://github.com/anmolkapil/plexo) and [its site](https://getplexo.app/).
The reference was inspected at commit `2ffd68177f5296916c6591660a1751c1e9eca90a`,
including its actual UI source, not only screenshots:

- `src/renderer/src/assets/main.css`: semantic light/graphite surface tokens.
- `components/ui/button.tsx`, `toggle.tsx`, `switch.tsx`: compact controls,
  icon gaps and distinct hover, selected, pressed, focus and disabled states.
- `components/DownloadFilterMenu.tsx`, `ScreenFooter.tsx` and
  `screens/DownloadsScreen.tsx`: quiet toolbars, stable actions and dense lists.
- `docs/landing.css` and `landing.js`: navigation, progressive reveals and
  small interaction feedback.

Clipboard Bridge translates these principles into its existing Tk/Pillow client
and static site. It does not import Plexo's React/Electron runtime, copy its logo,
fonts, marketing text or download-manager-specific charts. The blue clipboard
brand, host modes, API and transfer behavior remain Clipboard Bridge's own.
There is no real desktop blur or capture behind the opaque application surfaces.

## Contracts

- `clipboard_design.py` owns bounded cached raster surfaces and control states.
  Tk retains focus, keyboard navigation, selection and scroll bindings.
- Dark controls explicitly override Clam's light hover/readonly defaults.
  Test combined states, not just their normal backgrounds.
- History uses one host-derived list. Switching mode or account invalidates old
  requests, selection and preview caches. Old local cache files are not deleted.
- File icons have a fixed-width column without a disclosure indicator; names
  begin in the next column. Theme changes regenerate glyph colors.
- Progress indicators have fixed dimensions and stop on completion/close.
  Image/PDF work and network requests never run on the Tk thread.
- Public screenshots use the actual application with public example data only.
  Website motion respects reduced-motion preferences; content works without JS.
