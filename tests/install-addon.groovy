import org.freeplane.core.resources.ResourceController
import org.freeplane.core.util.TextUtils
import org.freeplane.features.mode.Controller
import org.freeplane.features.export.mindmapmode.ExportController
import org.freeplane.main.addons.AddOnsController

def base = new File(System.getProperty('install.probe.base'))
def profile = ResourceController.resourceController.freeplaneUserDirectory
def phase = System.getProperty('install.probe.phase')
def version = System.getProperty('install.probe.version')
def addons = AddOnsController.controller
def installed = addons.getInstalledAddOn('interactive-html')
def probe = Class.forName('InstallProbe', true, ClassLoader.systemClassLoader)
def files = new File(base, 'payload-paths.txt').readLines()
assert new File(profile, 'unrelated-sentinel.txt').text == 'preserve me\n'
assert new File(profile, 'scripts/init/zz-install-probe.groovy').isFile()
if (phase == 'install') {
 def title = TextUtils.getText('addons.installer.title')
 def steps = [[title, installed ? TextUtils.format('addons.installer.update', installed.version) : TextUtils.getText('addons.installer.install')]]
 def license = node.map.root.children.find { it.plainText == 'license' }.children[0].text
 if (license && license != installed?.license) {
  def clean = license.replaceAll('</?(html|body|head)>', '').trim()
  def message = TextUtils.removeTranslateComment(TextUtils.format('addons.installer.confirm.licence', clean)).replace('\n', '<p>')
  steps << [title, TextUtils.getText('ok'), message]
 }
 def message = installed ? TextUtils.format('addons.installer.success.update', installed.version, version) : TextUtils.getText('addons.installer.success')
 steps << [title, TextUtils.getText('ok'), message]
 probe.getField('dialogSteps').set(null, steps.collect { it as String[] } as String[][])
} else if (phase == 'verify' || phase == 'manual') {
 assert phase == 'manual' ? installed == null : installed?.version == version
 def expected = phase == 'manual' ? 'legacy/' : version == '0.1.0-alpha.1' ? 'previous-expected/' : 'expected/'
 files.each { path ->
  assert new File(profile, path).bytes == new File(base, expected + path).bytes : "Installed payload differs: ${path}"
 }
 assert new File(profile, 'addons/interactive-html.script.xml').isFile() == (phase == 'verify')
 println "INSTALL_PROBE_METADATA_OK phase=${phase} version=${installed?.version}"
} else if (phase == 'uninstall') {
 assert installed?.version == version
 addons.deinstall(installed)
 assert addons.getInstalledAddOn('interactive-html') == null
 files.each { assert !new File(profile, it).exists() : "Uninstall left ${it}" }
 assert !new File(profile, 'addons/interactive-html.script.xml').exists()
 assert new File(profile, 'addons/interactive-html/unrelated.txt').text == 'preserve private sentinel\n'
 println 'INSTALL_PROBE_NATIVE_UNINSTALL_OK'
} else if (phase == 'absent') {
 assert installed == null
 def exports = ExportController.getController(Controller.currentModeController)
 assert !exports.mapExportFileFilters.any { it.description == 'Interactive HTML (*.html)' }
 files.each { assert !new File(profile, it).exists() }
 assert new File(profile, 'addons/interactive-html/unrelated.txt').text == 'preserve private sentinel\n'
 println 'INSTALL_PROBE_RESTART_REMOVAL_OK'
} else {
 throw new IllegalArgumentException("Unknown lifecycle phase: ${phase}")
}
