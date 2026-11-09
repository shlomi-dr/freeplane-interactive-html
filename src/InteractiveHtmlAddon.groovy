import org.freeplane.features.mode.Controller
import org.freeplane.features.map.*
import org.freeplane.features.text.DetailModel
import org.freeplane.features.text.TextController
import org.freeplane.features.link.NodeLinks
import org.freeplane.features.export.mindmapmode.ExportController
import org.freeplane.features.export.mindmapmode.IExportEngine
import org.freeplane.core.util.HtmlUtils
import groovy.json.JsonOutput
import java.awt.Dimension
import java.awt.RenderingHints
import java.awt.image.BufferedImage
import java.nio.file.Files
import java.nio.file.StandardCopyOption
import javax.swing.SwingUtilities
import javax.swing.JViewport
import javax.swing.filechooser.FileFilter
import org.freeplane.core.ui.CaseSensitiveFileNameExtensionFilter

// Experimental Freeplane 1.13.3–1.13.4 compatibility seam: native Batik and renderer reflection.
class InteractiveHtmlExporter implements IExportEngine {
 static final String FILTER_DESCRIPTION = 'Interactive HTML (*.html)'
 final String template
 final ClassLoader scriptingClassLoader
 boolean forceFailureForTest = false
 InteractiveHtmlExporter(String templateText) {
  template = templateText
  scriptingClassLoader = Thread.currentThread().contextClassLoader
 }
 InteractiveHtmlExporter(File templateFile) { this(templateFile.getText('UTF-8')) }
 static FileFilter registerTemplate(String templateText) {
  if (!SwingUtilities.isEventDispatchThread()) throw new IllegalStateException('Register on EDT')
  def controller = ExportController.getController(Controller.currentModeController)
  if (!controller) throw new IllegalStateException('Mind-map export controller is not ready')
  def existing = controller.mapExportFileFilters.find { it.description == FILTER_DESCRIPTION }
  if (existing) return existing
  def filter = new CaseSensitiveFileNameExtensionFilter('html', FILTER_DESCRIPTION)
  filter.setExtensionListInDescription(false)
  controller.addMapExportEngine(filter, new InteractiveHtmlExporter(templateText))
  filter
 }
 static FileFilter register(File templateFile) {
  registerTemplate(templateFile.getText('UTF-8'))
 }
 static def field(Object object, String name) {
  Class type = object.class
  while (type != null) {
   try { def f = type.getDeclaredField(name); f.accessible = true; return f }
   catch (NoSuchFieldException ignored) { type = type.superclass }
  }
  throw new NoSuchFieldException(name)
 }
 static String plain(NodeModel node) { TextController.controller.getPlainTransformedTextWithoutNodeNumber(node) ?: '' }
 static void layout(def view) {
  view.topLevelAncestor?.validate()
  def method = view.class.getDeclaredMethod('validateTree'); method.accessible = true
  synchronized (view.treeLock) { method.invoke(view) }
 }
 static String html(String value) { value.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('"','&quot;').replace("'",'&#39;') }
 void export(List<NodeModel> selectedNodes, File destination) {
  def thread = Thread.currentThread()
  def originalClassLoader = thread.contextClassLoader
  try {
   thread.contextClassLoader = scriptingClassLoader
   exportWithScriptingClassLoader(selectedNodes, destination)
  } finally { thread.contextClassLoader = originalClassLoader }
 }
 private void exportWithScriptingClassLoader(List<NodeModel> selectedNodes, File destination) {
  if (!SwingUtilities.isEventDispatchThread()) throw new IllegalStateException('Export on EDT')
  def mapView = Controller.currentController.mapViewManager.mapViewComponent
  if (!selectedNodes || selectedNodes.size() != 1 || !selectedNodes[0].is(mapView.map.rootNode))
   throw new IllegalArgumentException('Interactive HTML supports the whole current map only')
  def map = mapView.map
  def nodes = []
  def visit
  visit = { n -> nodes << n; n.children.each { visit(it) } }
  visit(map.rootNode)
  def folds = nodes.collectEntries { n -> [(n): [model:n.folded, view:mapView.getNodeView(n)?.folded]] }
  def nodeViewFolder = field(mapView, 'nodeViewFolder').get(mapView)
  def automaticFolds = field(nodeViewFolder, 'unfoldedNodeViews').get(nodeViewFolder)
  def unfoldedNodeViews = new HashSet(automaticFolds)
  def selection = mapView.orderedSelectedNodes.toList()
  float zoom = mapView.zoom
  def viewport = SwingUtilities.getAncestorOfClass(JViewport, mapView)
  def position = viewport ? new java.awt.Point(viewport.viewPosition) : null
  def scrollsField = field(mapView, 'scrollsViewAfterLayout')
  def scrollsAfterLayout = scrollsField.get(mapView)
  def changesField = field(map, 'changesPerformedSinceLastSave')
  def changes = changesField.get(map)
  // Restore pending native scroll directives as well as the actual viewport location.
  def scrollerField = field(mapView, 'mapScroller')
  def scroller = scrollerField.get(mapView)
  def scrollState = scroller.class.declaredFields.findAll { !java.lang.reflect.Modifier.isStatic(it.modifiers) && !java.lang.reflect.Modifier.isFinal(it.modifiers) }.collectEntries { f ->
   f.accessible = true; [(f): f.get(scroller)]
  }
  String result
  try {
   nodes.each { n ->
    def view = mapView.getNodeView(n)
    if (view?.folded) view.setFolded(false)
   }
   mapView.setZoom(1f)
   layout(mapView)
   result = capture(mapView, nodes, map)
  } finally {
   nodes.reverseEach { n ->
    def view = mapView.getNodeView(n)
    boolean folded = folds[n].view == null ? folds[n].model : folds[n].view
    if (view && view.folded != folded) view.setFolded(folded)
   }
   mapView.setZoom(zoom)
   // Reapplying an unchanged selection requests focus and queues a native viewport scroll.
   if (mapView.orderedSelectedNodes.toList() != selection)
    mapView.replaceSelection(selection.collect { mapView.getNodeView(it) } as org.freeplane.view.swing.map.NodeView[])
   layout(mapView)
   automaticFolds.clear()
   automaticFolds.addAll(unfoldedNodeViews)
   scrollState.each { f, value -> f.set(scroller, value) }
   scrollsField.set(mapView, scrollsAfterLayout)
   if (viewport) viewport.viewPosition = position
   changesField.set(map, changes)
  }
  // No destination is touched until capture and restoration both succeed.
  def target = destination.toPath().toAbsolutePath()
  def temporary = Files.createTempFile(target.parent, '.freeplane-interactive-', '.tmp')
  try {
   Files.writeString(temporary, result, java.nio.charset.StandardCharsets.UTF_8)
   Files.move(temporary, target, StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING)
  } finally { Files.deleteIfExists(temporary) }
 }
 String capture(def mapView, List<NodeModel> nodes, MapModel map) {
def bundle = org.osgi.framework.FrameworkUtil.getBundle(Controller).bundleContext.bundles.find { it.symbolicName == 'org.freeplane.plugin.svg' }
assert bundle != null
def domImplClass = bundle.loadClass('org.apache.batik.dom.GenericDOMImplementation')
def contextClass = bundle.loadClass('org.apache.batik.svggen.SVGGeneratorContext')
def graphicsClass = bundle.loadClass('org.apache.batik.svggen.SVGGraphics2D')
def gradientHandlerClass = bundle.loadClass('org.freeplane.plugin.svg.GradientExtensionHandler')
def makeSVG = { int width, int height ->
 def dom = domImplClass.getDOMImplementation().createDocument('http://www.w3.org/2000/svg', 'svg', null)
 def context = contextClass.createDefault(dom)
 // Match Freeplane's vector exporter for native icon gradient paints.
 context.setExtensionHandler(gradientHandlerClass.getConstructor().newInstance())
 def g = graphicsClass.getConstructor(contextClass, Boolean.TYPE).newInstance(context, true)
 g.setSVGCanvasSize(new Dimension(width, height))
 g.setClip(0, 0, width, height)
 g.setRenderingHint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON)
 g
}
def records = []
def connectorRecords = []
mapView.preparePrinting()
try {
 def paintingModeField = mapView.class.getDeclaredField('paintingMode')
 paintingModeField.setAccessible(true)
 def originalPaintingMode = paintingModeField.get(mapView)
 def modes = paintingModeField.type.enumConstants
 try {
  nodes.each { n ->
   def view = mapView.getNodeView(n)
   assert view != null : "No native view for ${n.ID}, folded=${n.folded}"
   def content = view.getContent()
   def main = view.mainView
   assert content.width >= 0 && content.height >= 0 : "Unlaid node ${n.ID}"
   if (plain(n)) assert content.width > 0 && content.height > 0 : "Unlaid nonempty node ${n.ID}"
   int width = content.width + 6, height = content.height + 6
   paintingModeField.set(mapView, modes.find { it.name() == (view.isSelected() ? 'SELECTED_NODES' : 'NODES') })
   def paintContent = { g ->
    g.translate(3, 3)
    g.setFont(main.font)
    g.setColor(main.foreground)
    content.paint(g)
   }
   def g = makeSVG(width, height)
   paintContent(g)
   def writer = new StringWriter()
   g.stream(writer, true)
   g.dispose()
   if (forceFailureForTest) throw new IllegalStateException('Forced capture failure for restoration test')
   records << [id:n.ID, parentId:n.parentNode?.ID, label:plain(n), width:width, height:height, artwork:writer.toString(), topOrLeft:view.isTopOrLeft()]
  }
 } finally { paintingModeField.set(mapView, originalPaintingMode) }
 // Resolve styles through the live controller and geometry through its native renderer.
 def linkController = org.freeplane.features.link.LinkController.getController()
 def fieldValue = { obj, name ->
  def field = obj.class.getDeclaredField(name); field.accessible = true; field.get(obj)
 }
 def pointData = { p -> p == null ? null : [x:p.x, y:p.y] }
 nodes.each { n ->
  org.freeplane.features.link.NodeLinks.getLinks(n).findAll { it instanceof org.freeplane.features.link.ConnectorModel }.each { connector ->
   def source = mapView.getNodeView(connector.source)
   def target = mapView.getNodeView(connector.target)
   assert source && target
   // Sample the native complete line irrespective of selection-only UI visibility.
   // This is a temporary view field; restore it before any further capture.
   def visibilityField = mapView.class.getDeclaredField('showConnectors'); visibilityField.accessible = true
   def visibilityConstant = mapView.class.getDeclaredField('SHOW_CONNECTOR_LINES'); visibilityConstant.accessible = true
   def originalVisibility = visibilityField.get(mapView)
   def nativeView
   try {
    visibilityField.set(mapView, visibilityConstant.get(null))
    nativeView = new org.freeplane.view.swing.map.link.ConnectorView(connector, source, target, mapView.background)
   } finally { visibilityField.set(mapView, originalVisibility) }
   def image = new BufferedImage(1, 1, BufferedImage.TYPE_INT_ARGB)
   def graphics = image.createGraphics()
   nativeView.paint(graphics)
   graphics.dispose()
   def curve = fieldValue(nativeView, 'arrowLinkCurve')
   assert curve instanceof java.awt.geom.CubicCurve2D : "Unsupported captured connector shape: ${curve?.class}"
   def origin = { view -> SwingUtilities.convertPoint(view.content, 0, 0, mapView) }
   def sourceOrigin = origin(source), targetOrigin = origin(target)
   // Node artwork includes three pixels of capture padding around content.
   def sourceAnchor = [x:curve.x1-sourceOrigin.x+3, y:curve.y1-sourceOrigin.y+3]
   def targetAnchor = [x:curve.x2-targetOrigin.x+3, y:curve.y2-targetOrigin.y+3]
   def arrows = linkController.getArrows(connector)
   def arrowEnds = []
   if (arrows.start.name() != 'NONE') arrowEnds << 'source'
   if (arrows.end.name() != 'NONE') arrowEnds << 'target'
   def polygons = fieldValue(nativeView, 'arrows')
   assert polygons.size() == arrowEnds.size()
   def arrowGeometry = polygons.withIndex().collect { polygon, index ->
    def end = arrowEnds[index]
    double ax = end == 'source' ? curve.x1 : curve.x2
    double ay = end == 'source' ? curve.y1 : curve.y2
    [end:end, points:(0..<polygon.npoints).collect { i -> [x:polygon.xpoints[i]-ax, y:polygon.ypoints[i]-ay] }]
   }
   def color = linkController.getColor(connector)
   def stroke = fieldValue(nativeView, 'stroke')
   connectorRecords << [sourceId:connector.source.ID, targetId:connector.targetID,
    resolved:[color:String.format('#%02x%02x%02x', color.red, color.green, color.blue),
     width:linkController.getWidth(connector), alpha:linkController.getOpacity(connector),
     dash:(linkController.getDashArray(connector) ?: []).toList(), shape:linkController.getShape(connector).name(),
     startArrow:arrows.start.name(), endArrow:arrows.end.name(),
     labelFontFamily:linkController.getLabelFontFamily(connector), labelFontSize:linkController.getLabelFontSize(connector),
     labelFontStyle:linkController.getLabelFontStyle(connector),
     sourceLabel:linkController.getSourceLabel(connector), middleLabel:linkController.getMiddleLabel(connector), targetLabel:linkController.getTargetLabel(connector)],
    geometry:[zoom:mapView.zoom, sourceAnchor:sourceAnchor, targetAnchor:targetAnchor,
     sourceControl:[x:curve.ctrlX1-curve.x1,y:curve.ctrlY1-curve.y1],
     targetControl:[x:curve.ctrlX2-curve.x2,y:curve.ctrlY2-curve.y2], arrowPolygons:arrowGeometry,
     nativeSource:pointData(curve.p1), nativeTarget:pointData(curve.p2),
     modelStartInclination:pointData(connector.startInclination), modelEndInclination:pointData(connector.endInclination),
     strokeDash:(stroke.dashArray ?: []).toList(), strokeWidth:stroke.lineWidth, strokeCap:stroke.endCap, strokeJoin:stroke.lineJoin]]
  }
 }

} finally { mapView.endPrinting() }
def summaries = []
records.each { record ->
 def n = nodes.find { it.ID == record.id }
 record.firstGroup = SummaryNode.isFirstGroupNode(n)
 record.summary = SummaryNode.isSummaryNode(n)
 record.alwaysUnfolded = AlwaysUnfoldedNode.isAlwaysUnfolded(n)
 record.linkHref = NodeLinks.getLinkAsString(n)
 def details = HtmlUtils.htmlToPlain(DetailModel.getDetailText(n) ?: '')
 record.searchText = [record.label, details].findAll { it }.join(' ')
 def starts = []
 n.children.eachWithIndex { child, index ->
  if (SummaryNode.isFirstGroupNode(child)) starts << index
  if (SummaryNode.isSummaryNode(child)) {
   if (!starts) throw new IllegalStateException('Summary has no first-group marker')
   int start = starts.remove(starts.size() - 1)
   summaries << [markerId:child.ID, startMarkerId:n.children[start].ID, parentId:n.ID,
    memberIds:n.children.subList(start + 1, index).findAll { !SummaryNode.isFirstGroupNode(it) && !SummaryNode.isSummaryNode(it) }.collect { it.ID },
    summaryChildIds:child.children.collect { it.ID }]
  }
 }
}
def ids = records.collect { it.id } as Set
if (ids.size() != records.size()) throw new IllegalStateException('Duplicate node IDs')
if (records.any { it.parentId != null && !ids.contains(it.parentId) }) throw new IllegalStateException('Missing node parent')
def payload = JsonOutput.toJson([nodes:records, rootId:map.rootNode.ID, links:connectorRecords, summaries:summaries])
 .replace('<', '\\u003c').replace(String.valueOf((char)0x2028), '\\u2028').replace(String.valueOf((char)0x2029), '\\u2029')
def title = map.file?.name?.replaceFirst(/\.mm$/, '') ?: plain(map.rootNode)
return template.replace('__MAP_TITLE__', html(title ?: 'Mind map')).replace('/*__MANIFEST__*/', payload)
 }
}
// The returned Class exposes register(File templateFile) to an in-process init script.
return InteractiveHtmlExporter
