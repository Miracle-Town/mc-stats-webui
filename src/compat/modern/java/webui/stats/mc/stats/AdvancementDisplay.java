package webui.stats.mc.stats;

import net.minecraft.advancements.AdvancementType;
import net.minecraft.advancements.DisplayInfo;
import net.minecraft.network.chat.Component;
import net.minecraft.world.item.ItemStackTemplate;

/** Normalizes the advancement display API used by Minecraft 26.3. */
record AdvancementDisplay(Component title, Component description, ItemStackTemplate icon,
		AdvancementType type, boolean hidden) {
	static AdvancementDisplay from(DisplayInfo info) {
		return new AdvancementDisplay(info.title(), info.description(), info.icon(),
			info.type(), info.hidden());
	}
}
