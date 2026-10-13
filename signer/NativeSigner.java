import com.alibaba.fastjson.JSON;
import com.alibaba.fastjson.JSONObject;
import com.github.unidbg.AndroidEmulator;
import com.github.unidbg.arm.backend.Unicorn2Factory;
import com.github.unidbg.linux.android.AndroidEmulatorBuilder;
import com.github.unidbg.linux.android.AndroidResolver;
import com.github.unidbg.linux.android.dvm.*;
import com.github.unidbg.linux.android.dvm.array.ByteArray;
import com.github.unidbg.virtualmodule.android.AndroidModule;
import com.github.unidbg.file.FileResult;
import com.github.unidbg.linux.file.ByteArrayFileIO;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.*;

/** Run the user's App libraries without a phone or a complete Android system. */
public final class NativeSigner extends AbstractJni {
    private final AndroidEmulator emulator;
    private final VM vm;
    private final DvmClass shader, ndk;
    private final DvmObject<?> context;
    private final String debugInfo;

    @Override public boolean acceptMethod(DvmClass clazz, String signature, boolean isStatic) {
        // Android declares isCharging()Z; the byte-returning method does not exist.
        return !signature.equals("android/os/BatteryManager->isCharging()B")
                && super.acceptMethod(clazz, signature, isStatic);
    }
    @Override public int getStaticIntField(BaseVM vm, DvmClass clazz, String signature) {
        if (signature.equals("android/content/Context->MODE_PRIVATE:I") ||
                signature.equals("android/content/ContextWrapper->MODE_PRIVATE:I")) return 0;
        return super.getStaticIntField(vm, clazz, signature);
    }
    @Override public DvmObject<?> callObjectMethodV(BaseVM vm, DvmObject<?> object, String signature, VaList args) {
        if (signature.equals("android/content/ContextWrapper->getSharedPreferences(Ljava/lang/String;I)Landroid/content/SharedPreferences;"))
            return vm.resolveClass("android/content/SharedPreferences").newObject(null);
        if (signature.equals("android/content/SharedPreferences->getString(Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;")
                && "DebugInfo".equals(args.getObjectArg(0).getValue())) return new StringObject(vm, debugInfo);
        return super.callObjectMethodV(vm, object, signature, args);
    }

    NativeSigner(File root, String debugInfo) throws Exception {
        this.debugInfo = debugInfo;
        emulator = AndroidEmulatorBuilder.for64Bit().setProcessName("com.max.xiaoheihe")
                .setRootDir(new File(System.getProperty("java.io.tmpdir"), "heybox-native-rootfs"))
                .addBackendFactory(new Unicorn2Factory(true)).build();
        emulator.getMemory().setLibraryResolver(new AndroidResolver(23));
        emulator.getSyscallHandler().setEnableThreadDispatcher(true);
        // App startup has already opened more than twenty file descriptors.
        for (int i = 0; i < 24; i++) emulator.getSyscallHandler().addFileIO(new ByteArrayFileIO(0, "/dev/null", new byte[0]));
        emulator.getSyscallHandler().addIOResolver((emu, path, flags) -> {
            if (path.equals("/proc/self/status")) return FileResult.success(new ByteArrayFileIO(flags, path,
                    "Name:\tcom.max.xiaoheihe\nState:\tS (sleeping)\nTracerPid:\t0\n".getBytes(StandardCharsets.UTF_8)));
            return null;
        });
        vm = emulator.createDalvikVM(new File(root, "app-metadata.apk"));
        vm.setJni(this);
        vm.setVerbose(false);
        new AndroidModule(emulator, vm).register(emulator.getMemory());
        context = vm.resolveClass("android/content/ContextWrapper", vm.resolveClass("android/content/Context")).newObject(null);
        ndk = vm.resolveClass("com/max/xiaoheihe/utils/NDKTools");
        vm.loadLibrary(new File(root, "libnative-lib.so"), true).callJNI_OnLoad(emulator);
        shader = vm.resolveClass("com/graphice/shaderar/ShaderManager");
        vm.loadLibrary(new File(root, "libglesv3_1.so"), true).callJNI_OnLoad(emulator);
        shader.callStaticJniMethod(emulator, "setParseDepth(Ljava/lang/String;Z)V", "/data/user/0/com.max.xiaoheihe/cache", true);
        shader.callStaticJniMethod(emulator, "setSecLevel()V");
        shader.callStaticJniMethod(emulator, "setHdrField([B)V", new ByteArray(vm, Files.readAllBytes(new File(root, "shader-code.bin").toPath())));
    }

    Map<String, String> sign(JSONObject input) {
        String path = input.getString("path"), account = input.getString("account");
        String timestamp = Long.toString(System.currentTimeMillis() / 1000);
        DvmObject<?> seed = shader.callStaticJniMethodObject(emulator,
                "getChunkFlag(Landroid/content/Context;Ljava/lang/String;)Ljava/lang/String;",
                context, "PAENEHAMGACOBHIEMIHIJLKJPMMHJMMQABCNGBPPENCENP");
        if (seed == null) throw new IllegalStateException("Nonce initialization failed");
        DvmObject<?> nonceObject = shader.callStaticJniMethodObject(emulator,
                "getIdxOffset(Landroid/content/Context;Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;",
                context, seed.getValue(), timestamp, account);
        if (nonceObject == null) throw new IllegalStateException("Nonce calculation failed");
        String nonce = nonceObject.getValue().toString();
        String[][] values = {{"setViewport", timestamp}, {"setGramLen", path}, {"setBuf", timestamp},
                {"setDepRel", input.getString("model")}, {"setDLen", input.getString("os_version")},
                {"setPtrOffset", input.getString("version")}};
        for (String[] value : values) shader.callStaticJniMethod(emulator,
                value[0] + "(Ljava/lang/String;Ljava/lang/String;)V", value[1], nonce);
        ndk.callStaticJniMethodObject(emulator,
                "encode(Ljava/lang/Object;Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;",
                context, path, timestamp, nonce);
        DvmObject<?> key = shader.callStaticJniMethodObject(emulator,
                "getObjType(Landroid/content/Context;Ljava/lang/String;Z)Ljava/lang/String;", context, nonce, false);
        if (key == null) throw new IllegalStateException("Native signature failed");
        DvmObject<?> rnd = shader.callStaticJniMethodObject(emulator,
                "getObjType(Landroid/content/Context;Ljava/lang/String;Z)Ljava/lang/String;", context, nonce, true);
        // Native hexadecimal values omit leading zeroes; preserve them verbatim.
        if (rnd == null || !key.getValue().toString().matches("[0-9A-F]{1,8}") || !rnd.getValue().toString().matches("[0-9A-F]{1,8}")
                || !nonce.matches("[A-Za-z0-9]{32}")) throw new IllegalStateException("Unexpected native signature: hkey length="
                + key.getValue().toString().length() + ", rnd length=" + (rnd == null ? -1 : rnd.getValue().toString().length())
                + ", nonce length=" + nonce.length());
        Map<String, String> output = new LinkedHashMap<>();
        output.put("_time", timestamp); output.put("nonce", nonce); output.put("hkey", key.getValue().toString());
        output.put("_rnd", "14:" + rnd.getValue());
        return output;
    }
    public static void main(String[] args) throws Exception {
        JSONObject input = JSON.parseObject(new BufferedReader(new InputStreamReader(System.in, StandardCharsets.UTF_8)).readLine());
        NativeSigner signer = new NativeSigner(new File(args[0]), input.getString("debug_info"));
        try { System.out.println(JSON.toJSONString(signer.sign(input))); }
        finally { signer.emulator.close(); }
    }
}
