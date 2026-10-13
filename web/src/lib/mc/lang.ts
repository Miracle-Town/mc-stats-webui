import en from '$mc/lang/en.json';
import es from '$mc/lang/es.json';
import fr from '$mc/lang/fr.json';
import zhCN from '$mc/lang/zh-CN.json';
import type { Locale } from '$lib/i18n/i18n.svelte';

export const minecraftTranslations: Record<Locale, Record<string, string>> = {
	en, es, fr, 'zh-CN': zhCN
};
