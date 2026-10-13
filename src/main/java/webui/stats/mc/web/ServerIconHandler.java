package webui.stats.mc.web;

import com.sun.net.httpserver.HttpExchange;
import net.fabricmc.loader.api.FabricLoader;

import java.io.IOException;
import java.io.OutputStream;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.util.Locale;

public final class ServerIconHandler {
	private final Path icon;

	public ServerIconHandler() {
		this(FabricLoader.getInstance().getGameDir().resolve("server-icon.png"));
	}

	public ServerIconHandler(Path icon) {
		this.icon = icon;
	}

	public void handle(HttpExchange exchange) throws IOException {
		String method = exchange.getRequestMethod();
		if (!"GET".equalsIgnoreCase(method) && !"HEAD".equalsIgnoreCase(method)) {
			exchange.sendResponseHeaders(405, -1);
			exchange.close();
			return;
		}

		if (!Files.isRegularFile(icon, LinkOption.NOFOLLOW_LINKS)) {
			exchange.sendResponseHeaders(404, -1);
			exchange.close();
			return;
		}

		byte[] bytes = Files.readAllBytes(icon);
		exchange.getResponseHeaders().set("Content-Type", contentType(icon));
		exchange.getResponseHeaders().set("Cache-Control", "no-cache");
		boolean head = "HEAD".equalsIgnoreCase(method);
		exchange.sendResponseHeaders(200, head ? -1 : bytes.length);
		if (!head) {
			try (OutputStream out = exchange.getResponseBody()) {
				out.write(bytes);
			}
		} else {
			exchange.close();
		}
	}

	private static String contentType(Path icon) {
		String name = icon.getFileName().toString().toLowerCase(Locale.ROOT);
		return switch (name.substring(name.lastIndexOf('.') + 1)) {
			case "ico" -> "image/x-icon";
			case "svg" -> "image/svg+xml";
			case "webp" -> "image/webp";
			case "jpg", "jpeg" -> "image/jpeg";
			case "gif" -> "image/gif";
			default -> "image/png";
		};
	}
}
