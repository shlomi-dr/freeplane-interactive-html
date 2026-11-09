import java.io.*;
import javax.swing.SwingUtilities;
import org.freeplane.launcher.Launcher;
import org.freeplane.api.Controller;
public class InstallProbe {
 public static final java.util.concurrent.CountDownLatch ready = new java.util.concurrent.CountDownLatch(1);
 public static volatile String[][] dialogSteps = new String[0][];
 public static volatile int dialogIndex;
 static void prepareProfile(File base) throws Exception {
  for(String version : new String[]{"1.12.x", "1.13.x"}) {
   File profile = new File(base, "config/" + version);
   File init = new File(profile, "scripts/init");
   init.mkdirs();
   File properties = new File(profile,"auto.properties");
   if(!properties.exists()) {
    java.nio.file.Files.writeString(new File(init,"zz-install-probe.groovy").toPath(),
     "Class.forName(\"InstallProbe\", true, ClassLoader.systemClassLoader).getField(\"ready\").get(null).countDown()\n");
    java.nio.file.Files.writeString(new File(profile,"unrelated-sentinel.txt").toPath(), "preserve me\n");
    java.nio.file.Files.writeString(properties.toPath(),
     "single_instance=false\nsingle_instance_force=false\nexecute_scripts_without_asking=true\nlanguage=en\n");
   }
  }
 }
 static javax.swing.JButton button(java.awt.Component component, String label) {
  if(component instanceof javax.swing.JButton && label.equals(((javax.swing.JButton)component).getText()))
   return (javax.swing.JButton)component;
  if(component instanceof java.awt.Container)
   for(java.awt.Component child : ((java.awt.Container)component).getComponents()) {
    javax.swing.JButton found=button(child,label);
    if(found != null) return found;
   }
  return null;
 }
 static javax.swing.JOptionPane pane(java.awt.Component component) {
  if(component instanceof javax.swing.JOptionPane) return (javax.swing.JOptionPane)component;
  if(component instanceof java.awt.Container)
   for(java.awt.Component child : ((java.awt.Container)component).getComponents()) {
    javax.swing.JOptionPane found=pane(child);
    if(found != null) return found;
   }
  return null;
 }
 static void reportDialog(java.awt.Component component) {
  if(component instanceof javax.swing.text.JTextComponent) System.err.println("PROBE_MODAL_TEXT " + ((javax.swing.text.JTextComponent)component).getText());
  if(component instanceof javax.swing.JOptionPane)
   System.err.println("PROBE_MODAL_MESSAGE " + java.util.Arrays.deepToString(new Object[]{((javax.swing.JOptionPane)component).getMessage()}));
  if(component instanceof java.awt.Container)
   for(java.awt.Component child : ((java.awt.Container)component).getComponents()) reportDialog(child);
 }
 static void boundFailures() {
  java.awt.Toolkit.getDefaultToolkit().addAWTEventListener(event->{
   if(event.getID() == java.awt.event.WindowEvent.WINDOW_OPENED && event.getSource() instanceof java.awt.Dialog) {
    java.awt.Dialog dialog=(java.awt.Dialog)event.getSource();
    if(dialog.isModal()) {
     String[][] steps=dialogSteps;
     String[] step=dialogIndex < steps.length ? steps[dialogIndex] : null;
     javax.swing.JOptionPane message=pane(dialog);
     javax.swing.JButton accept=step == null ? null : button(dialog,step[1]);
     boolean expected=step != null && dialog.getTitle().equals(step[0]) && accept != null;
     if(expected && step.length > 2)
      expected=message != null && step[2].equals(String.valueOf(message.getMessage()))
       && message.getMessageType() != javax.swing.JOptionPane.ERROR_MESSAGE;
     else if(expected) expected=message == null;
     if(!expected) {
      System.err.println("PROBE_UNEXPECTED_MODAL " + dialog.getTitle());
      reportDialog(dialog);
      Runtime.getRuntime().halt(2);
     }
     dialogIndex++;
     System.out.println("INSTALL_PROBE_ACCEPT_DIALOG " + dialogIndex + " " + step[1]);
     SwingUtilities.invokeLater(accept::doClick);
    }
   }
  }, java.awt.AWTEvent.WINDOW_EVENT_MASK);
  Thread watchdog=new Thread(()->{
   try { Thread.sleep(90000); }
   catch(InterruptedException interrupted) { return; }
   System.err.println("PROBE_TIMEOUT after 90 seconds");
   for(java.util.Map.Entry<Thread, StackTraceElement[]> entry : Thread.getAllStackTraces().entrySet()) {
    System.err.println(entry.getKey().getName());
    for(StackTraceElement frame : entry.getValue()) System.err.println(" at " + frame);
   }
   Runtime.getRuntime().halt(3);
  }, "probe-watchdog");
  watchdog.setDaemon(true);
  watchdog.start();
 }
 public static void main(String[] args) throws Exception {
  if(args.length != 5) throw new IllegalArgumentException("Expected artifact directory, Freeplane installation, phase, version and package");
  File base=new File(args[0]);
  String phase=args[2];
  System.setProperty("install.probe.phase",phase);
  System.setProperty("install.probe.base",base.getAbsolutePath());
  System.setProperty("install.probe.version",args[3]);
  prepareProfile(base);
  boundFailures();
  Launcher launcher=Launcher.createForInstallation(new File(args[1])).userDirectory(new File(base,"config")).disableSecurityManager();
  final Controller[] controller=new Controller[1];
  final org.freeplane.api.Map[] map=new org.freeplane.api.Map[1];
  try {
   controller[0]=launcher.launchWithUI(new String[]{new File(base,"Clockwork Garden Festival.mm").getAbsolutePath()});
   if(!ready.await(30, java.util.concurrent.TimeUnit.SECONDS))
    throw new IllegalStateException("Startup init registration did not complete within 30 seconds");
   if(controller[0] == null) {
    java.lang.reflect.Field field=Launcher.class.getDeclaredField("framework");
    field.setAccessible(true);
    org.osgi.framework.launch.Framework framework=(org.osgi.framework.launch.Framework)field.get(launcher);
    org.osgi.framework.BundleContext context=framework.getBundleContext();
    org.osgi.framework.ServiceReference<Controller> reference=context.getServiceReference(Controller.class);
    if(reference == null) throw new IllegalStateException("Controller service unavailable after UI startup");
    controller[0]=context.getService(reference);
   }

   SwingUtilities.invokeAndWait(()->{
    File input=new File(base, phase.equals("install") ? args[4] : "Clockwork Garden Festival.mm");
    map[0]=controller[0].mapLoader(input).withView().getMap();
    controller[0].select(map[0].getRoot());
    controller[0].script(new File(base,"install-addon.groovy")).withAllPermissions().executeOn(map[0].getRoot());
    if(phase.equals("install")) {
     Object installed=controller[0].script(new File(args[1],"scripts/installScriptAddOn.groovy"))
      .withAllPermissions().executeOn(map[0].getRoot());
     if(installed == null || dialogIndex != dialogSteps.length)
      throw new IllegalStateException("Native installation failed or dialog sequence incomplete");
    }
   });
   if(phase.equals("verify") || phase.equals("manual")) {
    java.nio.file.Files.deleteIfExists(new File(base,"baseline.html").toPath());
    final Runnable[] export=new Runnable[1];
    SwingUtilities.invokeAndWait(()->export[0]=(Runnable)controller[0].script(new File(base,"export-demo.groovy"))
     .readingFiles().writingFiles().executeOn(map[0].getRoot()));
    SwingUtilities.invokeAndWait(export[0]);
   }

  } finally {
   SwingUtilities.invokeAndWait(()->{
    for(java.awt.Window window : java.awt.Window.getWindows()) window.dispose();
    launcher.shutdown();
   });
  }
  System.out.println("INSTALL_PROBE_COMPLETE " + phase);
  System.exit(0);
 }
}
