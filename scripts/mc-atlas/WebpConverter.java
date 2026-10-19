import java.awt.image.BufferedImage;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Arrays;
import java.util.Comparator;
import java.util.regex.Pattern;
import javax.imageio.ImageIO;

/** Lossless libwebp encoding, verified against every source RGBA pixel using the JDK's PNG reader. */
public class WebpConverter {
    private static final Pattern ATLAS = Pattern.compile("minecraft_texture_atlas(?:-([1-9][0-9]*))?\\.png");

    public static void main(String[] args) throws Exception {
        if (args.length != 4)
            throw new IllegalArgumentException("Usage: WebpConverter <input-directory> <output-directory> <quality> <method>");
        int quality = Integer.parseInt(args[2]);
        int method = Integer.parseInt(args[3]);
        if (quality < 0 || quality > 100 || method < 0 || method > 6)
            throw new IllegalArgumentException("WebP quality must be 0–100 and method must be 0–6");
        Path output = Path.of(args[1]);
        Files.createDirectories(output);
        try (var files = Files.list(Path.of(args[0]))) {
            var atlases = files.filter(path -> ATLAS.matcher(path.getFileName().toString()).matches())
                .sorted(Comparator.comparing(Path::toString)).toList();
            if (atlases.isEmpty()) throw new IOException("No atlas PNGs to convert");
            for (Path source : atlases) {
                var match = ATLAS.matcher(source.getFileName().toString());
                if (!match.matches()) throw new IOException("Invalid atlas filename: " + source);
                int page = match.group(1) == null ? 0 : Integer.parseInt(match.group(1));
                Path target = output.resolve("items-" + page + ".webp");
                Path decoded = Files.createTempFile(output, "webp-check-", ".png");
                boolean verified = false;
                try {
                    run("cwebp", "-quiet", "-lossless", "-exact", "-q", args[2], "-m", args[3],
                        source.toString(), "-o", target.toString());
                    run("dwebp", "-quiet", target.toString(), "-o", decoded.toString());
                    verifyPixels(source, decoded);
                    verified = true;
                    System.out.println("Verified lossless WebP: " + target.getFileName()
                        + " (" + Files.size(source) + " -> " + Files.size(target) + " bytes)");
                } finally {
                    Files.deleteIfExists(decoded);
                    if (!verified) Files.deleteIfExists(target);
                }
            }
        }
    }

    private static void run(String... command) throws IOException, InterruptedException {
        if (new ProcessBuilder(command).inheritIO().start().waitFor() != 0)
            throw new IOException("WebP command failed: " + command[0]);
    }

    static void verifyPixels(Path source, Path decoded) throws IOException {
        BufferedImage original = ImageIO.read(source.toFile());
        BufferedImage converted = ImageIO.read(decoded.toFile());
        if (original == null || converted == null)
            throw new IOException("Cannot decode PNG for WebP verification: " + source);
        int width = original.getWidth();
        if (width != converted.getWidth() || original.getHeight() != converted.getHeight())
            throw new IOException("WebP dimensions changed: " + source);
        for (int y = 0; y < original.getHeight(); y++) {
            if (!Arrays.equals(original.getRGB(0, y, width, 1, null, 0, width),
                               converted.getRGB(0, y, width, 1, null, 0, width)))
                throw new IOException("WebP RGBA pixels changed: " + source + ", row " + y);
        }
    }
}
