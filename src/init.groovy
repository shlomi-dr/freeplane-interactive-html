import org.freeplane.core.resources.ResourceController
// Runs after Freeplane startup; no map or selected node is required.
def resources = new File(ResourceController.resourceController.freeplaneUserDirectory, 'addons/interactive-html/resources')
def exporter = evaluate(new File(resources, 'InteractiveHtmlAddon.groovy'))
exporter.register(new File(resources, 'viewer-template.html'))
