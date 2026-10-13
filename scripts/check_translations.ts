import assert from 'node:assert/strict';
import { es } from '../web/src/lib/i18n/messages/es.ts';
import { en } from '../web/src/lib/i18n/messages/en.ts';
import { fr } from '../web/src/lib/i18n/messages/fr.ts';
import { zhCN } from '../web/src/lib/i18n/messages/zh-CN.ts';
import advancements from '../web/src/lib/mc/advancementLang.json' with { type: 'json' };
import vanilla from '../web/src/lib/mc/zh-CN.json' with { type: 'json' };

// TypeScript checks completeness; also catch dropped or renamed interpolation variables.
const keys = Object.keys(es).sort();
const placeholders = (text: string) => [...text.matchAll(/\{([\w]+)\}/g)]
	.map((match) => match[1]).sort();

for (const [locale, dictionary] of Object.entries({ en, fr, 'zh-CN': zhCN })) {
	assert.deepEqual(Object.keys(dictionary).sort(), keys, `${locale}: translation keys differ`);
	for (const key of keys) {
		const text = dictionary[key as keyof typeof dictionary];
		assert.ok(text.trim(), `${locale}: empty translation for ${key}`);
		assert.deepEqual(placeholders(text), placeholders(es[key as keyof typeof es]),
			`${locale}: interpolation variables differ for ${key}`);
	}
}
console.log(`Checked ${keys.length} messages in all four languages.`);

// These vanilla IDs differ from their language keys; guard against English fallbacks.
for (const locale of ['en', 'es', 'fr', 'zh-CN']) {
	const dictionary = advancements[locale as keyof typeof advancements] as Record<string, string>;
	for (const id of ['adventure.read_power_of_chiseled_bookshelf',
		'husbandry.obtain_netherite_hoe', 'husbandry.bred_all_animals']) {
		for (const kind of ['title', 'description']) {
			assert.ok(dictionary[`advancements.${id}.${kind}`], `${locale}: missing ${id} ${kind}`);
		}
	}
}
assert.equal(vanilla['item.minecraft.diamond'], '钻石');
assert.equal(vanilla['entity.minecraft.zombie'], '僵尸');
console.log('Checked generated advancement aliases and Chinese vanilla names.');
