# Community preview draft

Draft for review before posting to [Freeplane discussion #1112](https://github.com/freeplane/freeplane/discussions/1112). Publish the companion package and confirm its download link before posting. The current public releases still contain the earlier add-on approach.

## Proposed reply

An update on this idea: I've been working on an experimental interactive HTML exporter for Freeplane.

The viewer supports folding, expand/collapse all, search, pan, zoom, clickable URLs, both map sides, cubic cross-links, and single-level summary groups. It captures node artwork using Freeplane's own renderer and packages it with a browser viewer. The HTML is a viewer, not an editor, and its branch layout is not an exact reproduction of Freeplane's layout.

For this preview we're taking a companion-app approach: save a `.mm` map, run the exporter, and open the resulting HTML in a browser. Freeplane is required to produce the export; recipients do not need it to view the page. The initial package is for macOS. A fictional sample map is included so people can try it without sharing private maps.

Source and release information: https://github.com/shlomi-dr/freeplane-interactive-html

I'd appreciate feedback on:

1. Rendering problems, especially cross-links and summary nodes. A small fictional map that reproduces a problem would help.
2. Whether the companion workflow is convenient enough for sharing maps.
3. Whether maintainers would prefer eventual **File → Export map… → Interactive HTML** integration, and which extension approach would fit Freeplane best.

This is experimental. Formula nodes are exported as literal expressions, with formula evaluation disabled. Nested summaries, other connector shapes, large maps, external resources, and other platforms need further work or validation. I'd like to learn from real usage before proposing an upstream change.
