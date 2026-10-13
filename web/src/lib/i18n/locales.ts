export const locales = ['es', 'en', 'fr', 'zh-CN'] as const;

export type Locale = (typeof locales)[number];

export const STORAGE_KEY = 'mc-stats-locale';

export function isLocale(value: string | null | undefined): value is Locale {
	return locales.some((locale) => locale === value);
}
