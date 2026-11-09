import java.io.*;
import javax.swing.SwingUtilities;
import org.freeplane.launcher.Launcher;
import org.freeplane.api.Controller;
public class Probe {
 public static final java.util.concurrent.CountDownLatch ready = new java.util.concurrent.CountDownLatch(1);
 static void prepareProfile(File base) throws Exception {
  for(String version : new String[]{"1.12.x", "1.13.x"}) {
   File profile = new File(base, "config/" + version);
   File resources = new File(profile, "addons/interactive-html/resources");
   File init = new File(profile, "scripts/init");
   resources.mkdirs(); init.mkdirs();
   for(String name : new String[]{"InteractiveHtmlAddon.groovy", "viewer-template.html"})
    java.nio.file.Files.copy(new File(base,name).toPath(), new File(resources,name).toPath(), java.nio.file.StandardCopyOption.REPLACE_EXISTING);
   java.nio.file.Files.writeString(new File(init,"interactive-html.groovy").toPath(),
    java.nio.file.Files.readString(new File(base,"init.groovy").toPath()) +
    "\nClass.forName(\"Probe\", true, ClassLoader.systemClassLoader).getField(\"ready\").get(null).countDown()\n");
   java.nio.file.Files.writeString(new File(profile,"auto.properties").toPath(), "single_instance=false\nsingle_instance_force=false\nexecute_scripts_without_asking=true\n");
  }
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
     System.err.println("PROBE_UNEXPECTED_MODAL " + dialog.getTitle());
     reportDialog(dialog);
     Runtime.getRuntime().halt(2);
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
  if(args.length < 2) throw new IllegalArgumentException("Expected artifact directory and Freeplane installation directory");
  File base=new File(args[0]);
  boolean demo=args.length > 2 && args[2].equals("demo");
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

   if(demo) {
    final Runnable[] export = new Runnable[1];
    SwingUtilities.invokeAndWait(()->{
     map[0]=controller[0].mapLoader(new File(base,"Clockwork Garden Festival.mm")).withView().getMap();
     controller[0].select(map[0].getRoot());
     export[0]=(Runnable)controller[0].script(new File(base,"export-demo.groovy")).readingFiles().writingFiles().executeOn(map[0].getRoot());
    });
    SwingUtilities.invokeAndWait(export[0]);
   } else {
    final Runnable[][] prepared = new Runnable[1][];
    SwingUtilities.invokeAndWait(()->{
     map[0]=controller[0].mapLoader(new File(base,"Clockwork Garden Festival.mm")).withView().getMap();
     controller[0].select(map[0].getRoot());
     prepared[0]=(Runnable[])controller[0].script(new File(base,"prepare.groovy")).readingFiles().writingFiles().executeOn(map[0].getRoot());
    });
    SwingUtilities.invokeAndWait(prepared[0][0]);
    SwingUtilities.invokeAndWait(prepared[0][1]);
    SwingUtilities.invokeAndWait(prepared[0][2]);
    final Runnable[][] verify = new Runnable[1][];
    SwingUtilities.invokeAndWait(()->{
     verify[0]=(Runnable[])controller[0].script(new File(base,"exercise.groovy")).readingFiles().writingFiles().executeOn(map[0].getRoot());
    });
    SwingUtilities.invokeAndWait(verify[0][0]);
    SwingUtilities.invokeAndWait(verify[0][1]);
   }
  } finally {
   SwingUtilities.invokeAndWait(()->{
    for(java.awt.Window window : java.awt.Window.getWindows()) window.dispose();
    launcher.shutdown();
   });
  }
  System.out.println("PROBE_COMPLETE");
  System.exit(0);
 }
}
