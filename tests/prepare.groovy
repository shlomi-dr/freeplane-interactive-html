import org.freeplane.view.swing.map.MapView
import org.freeplane.features.mode.Controller
import org.freeplane.features.text.DetailModel
import org.freeplane.features.link.NodeLinks
import org.freeplane.core.util.Hyperlink
import java.net.URI
// Deliberately unsaved edits; all source data must come from live models.
node.text = 'Unsaved <interactive> \u2028 proof'
DetailModel.createDetailText(node.delegate).setText('<html><body>Unsaved details sentinel</body></html>')
NodeLinks.createLinkExtension(node.delegate).setHyperLink(new Hyperlink(new URI('https://example.invalid/unsaved')))
def view = Controller.currentController.mapViewManager.mapViewComponent
def candidates = node.map.root.children.findAll { it.children }
assert candidates
candidates[0].folded = true
view.putClientProperty(MapView.FOLDING_FOLLOWS_SELECTION, Boolean.TRUE)
c.select(node.map.root)
c.select(candidates[0])
c.zoom = 0.75f
def viewport = javax.swing.SwingUtilities.getAncestorOfClass(javax.swing.JViewport, view)
def baselinePosition
return [{
 assert !view.getNodeView(candidates[0].delegate).folded : 'Selection should automatically unfold the folded branch'
} as Runnable, {
 // Let selection and zoom's native deferred scroll complete before the baseline.
 viewport.viewPosition = new java.awt.Point(13, 17)
 baselinePosition = new java.awt.Point(viewport.viewPosition)
} as Runnable, {
 assert viewport.viewPosition == baselinePosition : "No-export viewport drift: before=${baselinePosition}, after=${viewport.viewPosition}"
 println 'PROBE_NO_EXPORT_BASELINE_OK deferred=true'
 println 'PREPARED_UNSAVED_STATE'
} as Runnable] as Runnable[]
