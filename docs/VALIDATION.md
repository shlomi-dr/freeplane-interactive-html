# Validation status

1. The project is experimental. The portable smoke test compiled and ran successfully with Freeplane 1.13.3, JDK 21.0.11, and macOS 26.2, exiting with status 0. Java compilation emitted four deprecated-API warnings. Other Freeplane versions, Java configurations, and platforms are unverified.
2. The runtime probe recorded these acceptance markers:

   ```text
   PROBE_NO_EXPORT_BASELINE_OK deferred=true
   PROBE_NATIVE_EXPORT_DIALOG_OK filter=CaseSensitiveFileNameExtensionFilter extension=html
   PROBE_EXPORT_OK nodes=43 links=2 summaries=1
   PROBE_REGISTRATION_OK count=1 branchCount=0
   PROBE_RESTORATION_OK success=true forcedFailure=true deferred=true undoEvents=0
   PROBE_AUTOMATIC_FOLDING_OK enabled=true subsequentSelectionCollapsed=true
   PROBE_COMPLETE
   ```

   Checks cover startup registration once, whole-map export, both sides, native artwork, a single-level summary group, cubic crosslinks, unsaved changes, and restoration of folds, selection, zoom, scroll, modified state, and undo behavior after success and injected capture failure, including deferred UI work. A failed export preserved an existing destination. Automatic folding remained enabled and still collapsed nodes on subsequent selection. The no-export baseline checked deferred viewport stability independently of capture.
3. Native `ExportDialog` dispatch selected the registered HTML filter and appended `.html` using an approving chooser shim. This verifies the native action path but does not constitute a pixel-level click through the save dialog. Startup used default resource permissions in a disposable profile configured with `execute_scripts_without_asking=true` to approve known test scripts. An ordinary installation may prompt for startup-script approval. The launcher's `disableSecurityManager()` setting is test bootstrap only; Freeplane installs its own manager. Global file/network restrictions need not be relaxed for installation.
4. A separate `scripts/smoke-test.sh --demo` run exited with status 0 and exported the unmodified `examples/Clockwork Garden Festival.mm` fixture through the current engine. Its generated HTML is checked in as `examples/Clockwork Garden Festival.html`. Browser checks passed for this fresh output served over local HTTP: 41 visible nodes and two crosslinks; collapse all reduced that to eight nodes and no crosslinks, and expand all restored 41 nodes and two crosslinks. Details search found Fable, and searching for the hidden Picture Guide revealed its path. Zoom changed scale from 0.31709 to 0.39636; pan moved by 50 and 20 pixels. Clicking an SVG link opened the expected reserved example.com destination. Browser warning and error logs were empty. Visual review confirmed four left branches, three right branches, and the summary bracket; the preview is checked in as `examples/preview.jpg`. Fit restored the full-map view after zooming and panning. Direct `file://` loading remains unverified.
5. The final demo callback also passed on a subsequent EDT turn outside the scripting invocation (`callbackOutsideScript=true`), with the caller's classloader restored afterward. Its HTML was byte-identical to the browser-tested example. The full smoke test passed again after this callback integration change.
6. Packaging checks establish deterministic bytes, the exact manual installation paths, and archive integrity. They do not establish browser behavior. Reproduce the runtime and demo checks with the `FREEPLANE_HOME`, `JAVA_HOME`, and command examples in [README.md](../README.md). The scripts retain logs and output in their reported temporary artifact directory.
7. Geometry support is limited to cubic crosslinks and single-level summary groups. Custom branch and summary routing does not reproduce Freeplane's exact native `AUTO_FLOW` layout. Nested summaries, other connector shapes, broader map features, external resources, direct `file://` behavior, large-map performance, and other platforms remain unverified.
8. Native `.mm` add-on installation remains unimplemented until binary-node XML encoding is verified against Freeplane's installed API and installer. The manual ZIP is not managed by Freeplane's add-on uninstall UI; use the exact removal instructions in README.md.
