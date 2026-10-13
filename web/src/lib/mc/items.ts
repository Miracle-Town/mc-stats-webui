import iconIndex from '$mc/icons.json';
import atlasUrls from '$mc/atlas';

export interface ItemSprite {
	atlas: number;
	x: number;
	y: number;
	size: number;
}

interface Atlas {
	file: string;
	width: number;
	height: number;
}

const index = iconIndex as {
	atlases: Atlas[];
	sprites: Record<string, ItemSprite>;
};

export function shortItemId(id: string): string {
	return id.replace(/^minecraft:/, '');
}

export function itemLetter(id: string): string {
	return shortItemId(id).charAt(0).toUpperCase();
}

export function itemSprite(id: string) {
	const identifier = id.includes(':') ? id : `minecraft:${id}`;
	const sprite = index.sprites[identifier];
	if (!sprite) return undefined;
	const atlas = index.atlases[sprite.atlas];
	const url = atlasUrls[sprite.atlas];
	if (!atlas || !url) return undefined;
	return { ...sprite, url, width: atlas.width, height: atlas.height };
}
