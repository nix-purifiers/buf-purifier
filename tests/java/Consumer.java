import com.google.protobuf.GeneratedMessage;
import com.google.protobuf.RuntimeVersion;
import com.google.protobuf.Timestamp;
import java.io.InputStream;
import java.net.JarURLConnection;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.HexFormat;
import org.nixpurifiers.proof.v1.Answer;
import org.nixpurifiers.proof.v1.Common;

public class Consumer {
  static String digest(byte[] value) throws Exception {
    return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(value));
  }
  static void origin(Class<?> type, Path expected) throws Exception {
    Path actual = Path.of(type.getProtectionDomain().getCodeSource().getLocation().toURI()).toRealPath();
    if (!actual.equals(expected)) throw new AssertionError(type.getName() + " origin " + actual);
    String entry = type.getName().replace('.', '/') + ".class";
    try (InputStream stream = type.getClassLoader().getResourceAsStream(entry)) {
      if (stream == null) throw new AssertionError(entry);
      System.out.println("CLASS\t" + entry + "\t" + actual + "\t" + digest(stream.readAllBytes()));
    }
  }
  public static void main(String[] args) throws Exception {
    Path project = Path.of(args[0]).toRealPath(), runtime = Path.of(args[1]).toRealPath();
    int field = Integer.parseInt(args[2]);
    int number = Common.getDescriptor().findFieldByName("value").getNumber();
    if (number != field) throw new AssertionError("schema field " + number);
    for (int value : new int[] {42, 43}) {
      Answer message = Answer.newBuilder().setCommon(Common.newBuilder().setValue(value))
        .setTimestamp(Timestamp.newBuilder().setSeconds(1)).build();
      byte[] bytes = message.toByteArray();
      Answer parsed = Answer.parseFrom(bytes);
      if (parsed.getCommon().getValue() != value || parsed.getTimestamp().getSeconds() != 1) throw new AssertionError("roundtrip");
      String expected = field == 1 ? "0a0208" : "0a0210";
      expected += Integer.toHexString(value) + "12020801";
      String wire = HexFormat.of().formatHex(bytes);
      if (!wire.equals(expected)) throw new AssertionError("wire " + wire);
      System.out.println("VALUE\t" + value + "\t" + wire);
    }
    for (String name : Files.readAllLines(Path.of(args[3]))) {
      origin(Class.forName(name), project);
    }
    for (Class<?> type : new Class<?>[] {RuntimeVersion.class, Timestamp.class, GeneratedMessage.class}) origin(type, runtime);
    var resource = RuntimeVersion.class.getClassLoader().getResource("google/protobuf/timestamp.proto");
    if (resource == null) throw new AssertionError("schema resource");
    JarURLConnection connection = (JarURLConnection) resource.openConnection();
    if (!Path.of(connection.getJarFileURL().toURI()).toRealPath().equals(runtime)) throw new AssertionError("schema resource origin");
    try (InputStream stream = resource.openStream()) {
      System.out.println("RESOURCE\tgoogle/protobuf/timestamp.proto\t" + runtime + "\t" + digest(stream.readAllBytes()));
    }
    String version = RuntimeVersion.class.getField("MAJOR").getInt(null) + "."
      + RuntimeVersion.class.getField("MINOR").getInt(null) + "." + RuntimeVersion.class.getField("PATCH").getInt(null);
    if (!version.equals("4.36.2")) throw new AssertionError("runtime " + version);
    System.out.println("RUNTIME\t" + version);
  }
}
