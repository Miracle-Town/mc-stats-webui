type LoadStatus = 'loading' | 'ready' | 'error';

const statuses = $state<Record<string, LoadStatus>>({});

export function atlasStatus(url: string): LoadStatus | undefined {
	return statuses[url];
}

// One load and one status per atlas, shared by every McItem on the page.
export function loadAtlas(url: string): void {
	if (typeof Image === 'undefined' || statuses[url]) return;
	statuses[url] = 'loading';
	const image = new Image();
	image.onload = () => { statuses[url] = 'ready'; };
	image.onerror = () => { statuses[url] = 'error'; };
	image.src = url;
}
