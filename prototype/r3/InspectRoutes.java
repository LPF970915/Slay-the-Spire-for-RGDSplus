import javassist.*;
import javassist.expr.*;

/** Print local API/call metadata only, without extracting game assets. */
public final class InspectRoutes {
    public static void main(String[] args) throws Exception {
        ClassPool pool = new ClassPool(true);
        pool.insertClassPath(args[0]);
        for (int i = 1; i < args.length; i++) {
            CtClass type = pool.get("com.megacrit.cardcrawl." + args[i]);
            System.out.println("\nCLASS " + type.getName());
            for (CtMethod method : type.getDeclaredMethods()) {
                if (!method.getName().startsWith("render")) continue;
                System.out.println(" METHOD " + method.getName() + method.getSignature());
                method.instrument(new ExprEditor() {
                    public void edit(MethodCall call) {
                        System.out.println("  " + call.getClassName() + "." + call.getMethodName()
                                + call.getSignature());
                    }
                });
            }
        }
    }
}
