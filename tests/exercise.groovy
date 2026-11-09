import org.freeplane.view.swing.map.MapView
import org.freeplane.features.mode.Controller
import org.freeplane.features.export.mindmapmode.ExportController
import org.freeplane.features.text.DetailModel
import org.freeplane.features.link.NodeLinks
import org.freeplane.features.map.SummaryNode
import groovy.json.JsonSlurper
import javax.swing.SwingUtilities
import javax.swing.JViewport
import org.freeplane.core.ui.CaseSensitiveFileNameExtensionFilter
import org.freeplane.features.export.mindmapmode.ExportDialog

def base = node.map.file.parentFile
def ec = ExportController.getController(Controller.currentModeController)
def matches = ec.mapExportFileFilters.findAll { it.description == 'Interactive HTML (*.html)' }
assert matches.size() == 1 : 'Startup init registration missing or duplicated'
def filter = matches[0]
assert filter instanceof CaseSensitiveFileNameExtensionFilter
assert filter.extensionProposal == 'html'
assert !filter.extensionListInDescription
def engine = ec.mapExportEngines[filter]
assert engine.class.register(new File(base, 'viewer-template.html')).is(filter)
assert ec.mapExportFileFilters.count { it.description == 'Interactive HTML (*.html)' } == 1
assert !ec.branchExportFileFilters.any { it.description == 'Interactive HTML (*.html)' }
def view = Controller.currentController.mapViewManager.mapViewComponent
def nodes = []
def visit
visit = { n -> nodes << n; n.children.each { visit(it) } }
visit(view.map.rootNode)
assert view.getClientProperty(MapView.FOLDING_FOLLOWS_SELECTION) == Boolean.TRUE
def folder = engine.class.field(view, 'nodeViewFolder').get(view)
def automaticFolds = engine.class.field(folder, 'unfoldedNodeViews').get(folder)
assert automaticFolds : 'Automatic selection unfolding was not exercised'
def automaticallyUnfolded = new HashSet(automaticFolds)
def viewport = SwingUtilities.getAncestorOfClass(JViewport, view)
assert viewport
viewport.viewPosition = new java.awt.Point(Math.min(13, Math.max(0, view.width - viewport.width)), Math.min(17, Math.max(0, view.height - viewport.height)))
def undo = view.map.getExtension(org.freeplane.core.undo.IUndoHandler)
assert undo : 'Undo handler unavailable for proof'
def undoEvents = [0]
def listener = { event -> undoEvents[0]++ } as javax.swing.event.ChangeListener
undo?.addChangeListener(listener)
def snapshot = {
 [folds:nodes.collect { [it.ID, it.folded, view.getNodeView(it)?.folded] }, zoom:view.zoom,
  selection:view.orderedSelectedNodes.collect { it.ID }, position:new java.awt.Point(viewport.viewPosition),
  automaticFolds:new HashSet(automaticFolds), changes:view.map.numberOfChangesSinceLastSave, saved:view.map.saved,
  undo:undo ? [undo.canUndo(), undo.canRedo(), undo.lastDescription] : null]
}
def before = snapshot()
def verify = { def after = snapshot(); assert after == before : 'Export state differences: ' + before.keySet().findAll { after[it] != before[it] }.collectEntries { [(it): [before:before[it], after:after[it]]] }; assert undoEvents[0] == 0 : 'Export changed undo history' }
def destination = new File(base, 'viewer.html')
// Exercise the native dialog's approval, filter validation and destination dispatch.
def constructor = ExportDialog.getDeclaredConstructor(List, Map, String)
constructor.accessible = true
def dialog = constructor.newInstance(ec.mapExportFileFilters, ec.mapExportEngines, ExportDialog.EXPORT_MAP_TITLE)
def chooser = new org.freeplane.api.swing.JFileChooser() {
 int showSaveDialog(java.awt.Component parent) {
  setSelectedFile(new File(base, 'viewer'))
  APPROVE_OPTION
 }
}
chooser.setCurrentDirectory(base)
chooser.setAcceptAllFileFilterUsed(false)
chooser.addChoosableFileFilter(filter)
chooser.setFileFilter(filter)
engine.class.field(dialog, 'fileChooser').set(dialog, chooser)
assert !destination.exists() || destination.delete()
def nativeExport = ExportDialog.getDeclaredMethod('export', java.awt.Component, List)
nativeExport.accessible = true
nativeExport.invoke(dialog, view, [view.map.rootNode])
assert destination.isFile() : 'Native ExportDialog did not dispatch the exporter or append .html'
println 'PROBE_NATIVE_EXPORT_DIALOG_OK filter=CaseSensitiveFileNameExtensionFilter extension=html'
verify()
def source = destination.getText('UTF-8')
def json = source.substring(source.indexOf('<script id="manifest" type="application/json">') + '<script id="manifest" type="application/json">'.length(), source.indexOf('</script>', source.indexOf('<script id="manifest"')))
assert !json.contains('<') && !json.contains(String.valueOf((char)0x2028)) && !json.contains(String.valueOf((char)0x2029))
def manifest = new JsonSlurper().parseText(json)
assert manifest.nodes.size() == nodes.size()
def root = manifest.nodes.find { it.id == view.map.rootNode.ID }
assert root.label.contains('Unsaved <interactive>')
assert root.searchText.contains('Unsaved details sentinel')
assert root.linkHref == 'https://example.invalid/unsaved'
assert manifest.links.size() == 2
assert manifest.summaries.size() > 0
assert manifest.nodes.any { it.topOrLeft } && manifest.nodes.any { !it.topOrLeft }
assert manifest.nodes.every { it.artwork.contains('<svg') }
def sentinel = new File(base, 'failure-sentinel.html')
sentinel.setText('KEEP EXISTING DESTINATION', 'UTF-8')
engine.forceFailureForTest = true
try {
 boolean failed = false
 try { ec.mapExportEngines[filter].export([view.map.rootNode], sentinel) }
 catch (IllegalStateException expected) { assert expected.message == 'Forced capture failure for restoration test'; failed = true }
 assert failed
 assert sentinel.getText('UTF-8') == 'KEEP EXISTING DESTINATION'
 verify()
} finally { engine.forceFailureForTest = false }
assert !base.listFiles().any { it.name.startsWith('.freeplane-interactive-') }
println "PROBE_EXPORT_OK nodes=${manifest.nodes.size()} links=${manifest.links.size()} summaries=${manifest.summaries.size()}"
println 'PROBE_REGISTRATION_OK count=1 branchCount=0'
return [{
  verify()
  println 'PROBE_RESTORATION_OK success=true forcedFailure=true deferred=true undoEvents=0'
  view.selectAsTheOnlyOneSelected(view.getNodeView(view.map.rootNode))
 } as Runnable, {
 try {
  assert automaticallyUnfolded.every { it.folded } : 'Selection change did not automatically collapse the original unfolded branches'
  assert undoEvents[0] == 0 : 'Selection folding changed undo history'
  println 'PROBE_AUTOMATIC_FOLDING_OK enabled=true subsequentSelectionCollapsed=true'
 }
 finally { undo?.removeChangeListener(listener) }
} as Runnable] as Runnable[]
