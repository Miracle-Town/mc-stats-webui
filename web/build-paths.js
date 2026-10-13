import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

export function buildPaths() {
	const repoRoot = fileURLToPath(new URL('../', import.meta.url));
	const defaultVersion = readFileSync(path.join(repoRoot, 'gradle.properties'), 'utf8')
		.match(/^minecraft_version=(.+)$/m)?.[1]?.trim();
	const version = process.env.MC_VERSION ?? defaultVersion;
	if (!version || !/^\d[\w.-]*$/.test(version)) {
		throw new Error('Set MC_VERSION to a supported Minecraft version.');
	}
	const versionBuild = path.join(repoRoot, 'build', version);
	return {
		version,
		repoRoot,
		versionBuild,
		mcResources: path.resolve(process.env.MC_RESOURCES_DIR ?? path.join(versionBuild, 'mc/generated')),
		webBuild: path.resolve(process.env.WEB_BUILD_DIR ?? path.join(versionBuild, 'web')),
		kitOutput: path.join(versionBuild, 'svelte-kit'),
		staticDir: path.join(versionBuild, 'web-static'),
		tsconfig: path.join(versionBuild, 'tsconfig.web.json')
	};
}
