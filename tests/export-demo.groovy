import org.freeplane.features.mode.Controller
import org.freeplane.features.export.mindmapmode.ExportController
import org.freeplane.core.ui.CaseSensitiveFileNameExtensionFilter

return {
 def exports = ExportController.getController(Controller.currentModeController)
 def matches = exports.mapExportFileFilters.findAll { it.description == 'Interactive HTML (*.html)' }
 assert matches.size() == 1 : 'Startup init registration missing or duplicated'
 def filter = matches[0]
 assert filter instanceof CaseSensitiveFileNameExtensionFilter
 assert filter.extensionProposal == 'html'
 assert !filter.extensionListInDescription
 def destination = new File(node.map.file.parentFile, 'baseline.html')
 def originalClassLoader = Thread.currentThread().contextClassLoader
 exports.mapExportEngines[filter].export([node.map.root.delegate], destination)
 assert Thread.currentThread().contextClassLoader.is(originalClassLoader) : 'Export did not restore the callback context classloader'
 assert destination.isFile() : 'Demo export did not create baseline.html'
 println "PROBE_DEMO_EXPORT_OK filter=CaseSensitiveFileNameExtensionFilter destination=${destination} callbackOutsideScript=true"
} as Runnable
