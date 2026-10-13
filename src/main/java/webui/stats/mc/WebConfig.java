package webui.stats.mc;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import net.fabricmc.loader.api.FabricLoader;

import java.io.IOException;
import java.io.Reader;
import java.io.Writer;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.LinkedHashMap;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

public final class WebConfig {
	public static final int DEFAULT_PORT = 25580;
	public static final String DEFAULT_BIND = "0.0.0.0";
	public static final String DEFAULT_WORLD = "";
	public static final String DEFAULT_TITLE = "Ranking";
	public static final String DEFAULT_SLOGAN = "Server stats.";
	public static final String DEFAULT_TAGLINE = "by borrageiros";
	public static final String DEFAULT_ICON = "";
	private static final Set<String> ICON_EXTENSIONS = Set.of("png", "ico", "svg", "webp", "jpg", "jpeg", "gif");
	public static final String DEFAULT_WINDOW_TITLE = "{page} - Server Ranking";

	private static final Gson GSON = new GsonBuilder().setPrettyPrinting().disableHtmlEscaping().create();

	private final String bind;
	private final int port;
	private final String world;
	private final String title;
	private final String slogan;
	private final String tagline;
	private final String windowTitle;
	private final String icon;

	public WebConfig(
		String bind,
		int port,
		String world,
		String title,
		String slogan,
		String tagline,
		String windowTitle
	) {
		this(bind, port, world, title, slogan, tagline, windowTitle, DEFAULT_ICON);
	}

	public WebConfig(
		String bind,
		int port,
		String world,
		String title,
		String slogan,
		String tagline,
		String windowTitle,
		String icon
	) {
		this.bind = bind;
		this.port = port;
		this.world = world;
		this.title = title;
		this.slogan = slogan;
		this.tagline = tagline;
		this.windowTitle = windowTitle;
		this.icon = icon;
	}

	public String bind() {
		return bind;
	}

	public int port() {
		return port;
	}

	public String world() {
		return world;
	}

	public String title() {
		return title;
	}

	public String slogan() {
		return slogan;
	}

	public String tagline() {
		return tagline;
	}

	public String windowTitle() {
		return windowTitle;
	}

	public String icon() {
		return icon;
	}

	public static Path directory() {
		return FabricLoader.getInstance().getConfigDir().resolve("mc-stats-webui");
	}

	public Path iconPath() {
		return icon.isEmpty()
			? FabricLoader.getInstance().getGameDir().resolve("server-icon.png")
			: directory().resolve(icon);
	}

	public Map<String, Object> brandingPayload() {
		Map<String, Object> body = new LinkedHashMap<>();
		body.put("title", title);
		body.put("slogan", slogan);
		body.put("tagline", tagline);
		body.put("windowTitle", windowTitle);
		return body;
	}

	public static WebConfig defaults() {
		return new WebConfig(
			DEFAULT_BIND,
			DEFAULT_PORT,
			DEFAULT_WORLD,
			DEFAULT_TITLE,
			DEFAULT_SLOGAN,
			DEFAULT_TAGLINE,
			DEFAULT_WINDOW_TITLE
		);
	}

	public static WebConfig load() {
		return load(FabricLoader.getInstance().getConfigDir());
	}

	static WebConfig load(Path configRoot) {
		Path path = configRoot.resolve("mc-stats-webui/config.json");
		Path legacy = configRoot.resolve("mc-stats-webui.json");
		WebConfig loaded = defaults();
		try {
			Files.createDirectories(path.getParent());
			if (!Files.exists(path) && Files.isRegularFile(legacy)) {
				Files.move(legacy, path);
				McStatsWebui.LOGGER.info("Migrated config {} to {}", legacy, path);
			}
			if (!Files.isRegularFile(path)) {
				write(path, loaded);
				McStatsWebui.LOGGER.info("Wrote default config {}", path);
				return loaded;
			}
			try (Reader reader = Files.newBufferedReader(path, StandardCharsets.UTF_8)) {
				loaded = parse(JsonParser.parseReader(reader).getAsJsonObject());
			}
			write(path, loaded);
		} catch (Exception e) {
			McStatsWebui.LOGGER.warn("Could not read {}, using defaults", path, e);
			return defaults();
		}
		return loaded;
	}

	private static WebConfig parse(JsonObject json) {
		int port = json.has("port") ? json.get("port").getAsInt() : DEFAULT_PORT;
		if (port < 1 || port > 65535) {
			McStatsWebui.LOGGER.warn("Invalid port {}, using {}", port, DEFAULT_PORT);
			port = DEFAULT_PORT;
		}
		String bind = text(json, "bind", DEFAULT_BIND);
		if (bind.isEmpty()) {
			bind = DEFAULT_BIND;
		}
		String world = text(json, "world", DEFAULT_WORLD);
		if (world.contains("..") || world.startsWith("/") || world.startsWith("\\")) {
			McStatsWebui.LOGGER.warn("Ignoring unsafe world folder {}", world);
			world = DEFAULT_WORLD;
		}
		String title = text(json, "title", DEFAULT_TITLE);
		if (title.isEmpty()) {
			title = DEFAULT_TITLE;
		}
		String slogan = text(json, "slogan", DEFAULT_SLOGAN);
		if (slogan.isEmpty()) {
			slogan = DEFAULT_SLOGAN;
		}
		String tagline = text(json, "tagline", DEFAULT_TAGLINE);
		if (tagline.isEmpty()) {
			tagline = DEFAULT_TAGLINE;
		}
		String windowTitle = text(json, "windowTitle", DEFAULT_WINDOW_TITLE);
		if (windowTitle.isEmpty() || (!windowTitle.contains("{page}") && !windowTitle.contains("<page>"))) {
			McStatsWebui.LOGGER.warn("windowTitle must include {page} or <page>, using default");
			windowTitle = DEFAULT_WINDOW_TITLE;
		}
		String icon = text(json, "icon", DEFAULT_ICON);
		if (!icon.isEmpty() && !isIconFilename(icon)) {
			McStatsWebui.LOGGER.warn("icon must be an image filename beside config.json, ignoring {}", icon);
			icon = DEFAULT_ICON;
		}
		return new WebConfig(bind, port, world, title, slogan, tagline, windowTitle, icon);
	}

	private static boolean isIconFilename(String name) {
		if (name.contains("/") || name.contains("\\") || name.contains(":") || name.indexOf('\0') >= 0) {
			return false;
		}
		int dot = name.lastIndexOf('.');
		return dot > 0 && ICON_EXTENSIONS.contains(name.substring(dot + 1).toLowerCase(Locale.ROOT));
	}

	private static String text(JsonObject json, String key, String fallback) {
		if (!json.has(key) || json.get(key).isJsonNull()) {
			return fallback;
		}
		return json.get(key).getAsString().trim();
	}

	private static void write(Path path, WebConfig config) throws IOException {
		Map<String, Object> body = new LinkedHashMap<>();
		body.put("port", config.port());
		body.put("bind", config.bind());
		body.put("world", config.world());
		body.put("title", config.title());
		body.put("slogan", config.slogan());
		body.put("tagline", config.tagline());
		body.put("windowTitle", config.windowTitle());
		body.put("icon", config.icon());
		try (Writer writer = Files.newBufferedWriter(path, StandardCharsets.UTF_8)) {
			GSON.toJson(body, writer);
			writer.write('\n');
		}
	}
}
