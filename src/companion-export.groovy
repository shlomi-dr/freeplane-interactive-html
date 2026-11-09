import org.freeplane.features.mode.Controller
import org.freeplane.features.export.mindmapmode.ExportController
import java.nio.file.Files
import java.nio.file.StandardOpenOption

// Invoked explicitly with Freeplane's -R launcher option. Paths arrive through
// the process environment so user supplied filenames never become Groovy source.
def addonFile = new File(System.getenv('COMPANION_ADDON'))
def templateFile = new File(System.getenv('COMPANION_TEMPLATE'))
def destination = new File(System.getenv('COMPANION_OUTPUT'))
def marker = new File(System.getenv('COMPANION_MARKER'))
def expectedInput = new File(System.getenv('COMPANION_INPUT')).toPath()
if (!addonFile.isFile() || !templateFile.isFile())
    throw new IllegalStateException('Companion exporter resources are unavailable')

def exporter = evaluate(addonFile)
exporter.registerTemplate(templateFile.getText('UTF-8'))
def controller = Controller.currentController
def mapView = controller.mapViewManager.mapViewComponent
def sourceMap = mapView.map
if (sourceMap.file == null || !Files.isSameFile(expectedInput, sourceMap.file.toPath()))
    throw new IllegalStateException('Freeplane did not load the requested input map')
sourceMap.setReadOnly(true)
def root = mapView.map.rootNode
if (root == null) throw new IllegalStateException('Freeplane did not load a mind map')
def exportController = ExportController.getController(Controller.currentModeController)
def filter = exportController.mapExportFileFilters.find {
    it.description == 'Interactive HTML (*.html)'
}
if (filter == null) throw new IllegalStateException('Interactive HTML exporter registration failed')
exportController.mapExportEngines[filter].export([root], destination)
if (!destination.isFile() || destination.length() == 0)
    throw new IllegalStateException('Interactive HTML exporter produced no output')
Files.writeString(marker.toPath(), 'ok', java.nio.charset.StandardCharsets.UTF_8,
    StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE)
println "COMPANION_EXPORT_OK bytes=${destination.length()}"
