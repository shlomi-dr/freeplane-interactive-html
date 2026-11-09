# Freeplane Interactive HTML Companion

Freeplane Interactive HTML is an experimental companion that exports one saved Freeplane map (`.mm`) to a standalone HTML viewer. It does not install an add-on, change Freeplane, or change your existing Freeplane profile. The first delivery is a local macOS app, version `0.2.0-alpha.1`; it has not been published. A command-line ZIP is also built locally.

The viewer supports folding, expand/collapse all, search, pan, zoom, fit, links on both sides, single-level summary groups, and cubic crosslinks. Straight crosslinks are not supported. The browser layout and summary routing are custom and do not reproduce Freeplane's exact layout. Nested summaries are unsupported.

## Use the macOS app

You need macOS and an installed Freeplane application; Freeplane 1.13.4 is the tested version. Save your map in Freeplane before exporting: the companion reads the saved file, including its saved fold state, rather than unsaved changes in an open window. Java comes from Freeplane. Python is needed only if you build the companion yourself.

1. Obtain `dist/freeplane-interactive-html-macos.zip` from a local build. No public download is available yet. Unzip it and move `Freeplane Interactive HTML.app` to `~/Applications` if desired.
2. Open the app, choose one saved `.mm` file (or drop one onto the app), then choose where to save the `.html` file. On success, the app opens the HTML output in the default browser.
3. The app uses Java from an installed Freeplane application. It searches common Applications folders and prompts you to choose Freeplane if needed. The CLI's optional `FREEPLANE_HOME` setting points to the installed app's `Contents/app` directory. A graphical Freeplane runtime is required. During capture, Freeplane may briefly appear. Headless `-N` mode is not used.
4. To uninstall, quit the companion and remove its `.app`. It creates no profile artifacts. If you previously installed the experimental startup add-on, uninstall that separately through Freeplane's Add-ons manager and restart. For a manual legacy installation, quit Freeplane and remove only these files from its user directory, preserving unrelated files:

   ```text
   scripts/init/interactive-html.groovy
   addons/interactive-html/resources/InteractiveHtmlAddon.groovy
   addons/interactive-html/resources/viewer-template.html
   addons/interactive-html/README.md
   addons/interactive-html/LICENSE
   addons/interactive-html/NOTICE
   ```

   The companion does not remove an older add-on.

The published alpha.2 startup add-on and manual ZIP are historical experimental packages. They are not recommended for new installations: the add-on depended on startup-script permissions and failed its default-restrictions check. The companion supersedes that approach.

## Build and try the preview

While [PR #2](https://github.com/shlomi-dr/freeplane-interactive-html/pull/2) is open, build its branch on a Mac with Git and Python 3 installed:

```sh
git clone --branch shlomi/1-interactive-html-export https://github.com/shlomi-dr/freeplane-interactive-html.git
cd freeplane-interactive-html
python3 scripts/package.py
open dist
```

1. Unzip `freeplane-interactive-html-macos.zip`. Keep the extracted `examples` folder for the first test.
2. Open `Freeplane Interactive HTML.app`, choose `examples/Clockwork Garden Festival.mm`, and save the result as `Clockwork Garden Festival.html` in a writable folder. You can also drop that one `.mm` file onto the app.
3. Wait for the export. A separate Freeplane window may appear during capture. A successful export opens in your default browser. The default time limit is three minutes.
4. Try the controls below, then repeat with one of your own saved maps. Choosing an existing HTML destination replaces it only after the export completes successfully.
5. Share the resulting `.html` file with recipients. They can open the viewer in a browser without installing Freeplane. External links and linked resources may still require access to their original locations.

## Use the HTML viewer

1. Click a node's small **+ / −** button to expand or collapse that branch. The toolbar's **Collapse all / Expand all** button switches between the two actions; hover over its icon to see the current action.
2. Drag the map to pan. Use the mouse wheel, trackpad scroll, or toolbar **+ / −** buttons to zoom. Choose **Fit** to bring the visible map into view.
3. Type into **Search nodes…** to search node text and captured details, including folded branches. The viewer reveals the path to a match. Press **Enter** or the toolbar arrow to move to the next match; clear the search field to remove highlights.
4. Click a node's link to open its destination. Collapse/expand and search affect the browser view; they do not edit the original `.mm` file or save a changed mind map.

## Command-line export

The local CLI package is `dist/freeplane-interactive-html-companion.zip`. Its entry point accepts an input map and output HTML path:

```sh
bin/export-map.sh INPUT.mm OUTPUT.html
```

For example, from the extracted CLI package or repository:

```sh
./bin/export-map.sh "examples/Clockwork Garden Festival.mm" "$PWD/festival.html"
open festival.html
```

The CLI prints the output path on success; it does not open the browser itself. The output directory must already exist. Quote paths containing spaces. To choose a nonstandard Freeplane installation:

```sh
FREEPLANE_HOME="$HOME/Applications/Freeplane.app/Contents/app" \
  ./bin/export-map.sh "/path/to/map.mm" "/path/to/map.html"
```

`FREEPLANE_HOME` is optional when an installed Freeplane app can be discovered; otherwise set it to the installed distribution's `Contents/app` directory. The exporter runs in an isolated CLI process with a unique Freeplane profile, the trusted bundled export script, and `-S`. It needs the graphical runtime and does not use headless `-N`. It does not modify the installed app or the user's normal profile.

Python and Node are not required for end users. Building the macOS app requires Python 3 and the macOS `osacompile`, `ditto`, and `codesign` tools. The local preview packages have passed build and integrity checks; they are not yet a published release.

## Troubleshooting

1. **Freeplane not found:** choose the installed `Freeplane.app` when prompted by the companion. For the CLI, set `FREEPLANE_HOME` as above. The companion itself is not the Freeplane application.
2. **Export failed:** the error includes the location of a retained Freeplane log. An unsupported feature, such as a straight cross-link, can cause capture to fail. Try the fictional example to distinguish an installation problem from a map-specific problem. An existing destination is preserved on failure.
3. **Export timed out:** the companion stops its export process after three minutes and retains a diagnostic log. For a larger map, use the CLI with `FREEPLANE_EXPORT_TIMEOUT=600` before the command to allow ten minutes.
4. **HTML did not open automatically:** open the selected `.html` file manually in a browser. If no file was produced, check the export error and log.
5. **Unexpected appearance or literal formulas:** review the compatibility notes below. The companion uses a fresh profile and does not evaluate formulas.

## Compatibility and limitations

1. The companion runner and the runner bundled inside the macOS app passed runtime checks with Freeplane 1.13.4 and its bundled Java 21.0.11 on macOS 26.2. Finder choose/drop dialogs and automatic browser opening still need a manual check. Freeplane 1.13.3 compatibility for the companion, Linux, and Windows are unverified.
2. The viewer offers interactive map navigation, but its layout and branch/summary routing are custom. Exact Freeplane layout, nested summaries, and all map feature combinations are not supported or established.
3. Export operates on a saved `.mm` file and one map per invocation. A graphical Freeplane runtime is required, and Freeplane can briefly show during capture.
4. Formula evaluation is disabled in the temporary export profile. Formula nodes are exported as literal expressions rather than calculated values. The companion is not a general sandbox for untrusted map files.
5. The preview app is ad-hoc signed for bundle integrity, not Developer ID signed or notarized. macOS may require an explicit Open confirmation for a downloaded copy.
6. The temporary profile does not inherit your per-user preferences or add-ons. Maps that depend on those settings or external resources may render differently.

See [validation status](docs/VALIDATION.md) for the tested behavior and remaining checks. The fictional [example map](examples/Clockwork%20Garden%20Festival.mm) and [preview](examples/preview.jpg) are included for reference; the checked-in HTML was generated by the earlier in-process prototype.

## Development

1. Build the CLI ZIP and macOS app ZIP with `python3 scripts/package.py` on macOS. The generated files belong under `dist/`.
2. Run `python3 tests/companion-integration.py` for the mock-launcher checks, or add `--runtime` to also launch the installed Freeplane and test real exports in temporary profiles. Set `FREEPLANE_HOME` to select another installation. The older `scripts/smoke-test.sh` and `scripts/install-test.sh` belong to the superseded startup add-on; use the companion integration suite for this version.
3. Authored project content is licensed under **GPL-2.0-only**. See [LICENSE](LICENSE) and [NOTICE](NOTICE). Freeplane and its runtime dependencies are supplied by the user's installed application and are not bundled here.
