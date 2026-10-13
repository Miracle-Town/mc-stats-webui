import { cpSync, existsSync, mkdirSync, readFileSync, rmSync, symlinkSync, writeFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import path from 'node:path';
import { buildPaths } from '../build-paths.js';

const paths = buildPaths();
const webRoot = path.join(paths.repoRoot, 'web');
const [command = 'sync', ...args] = process.argv.slice(2);
const commands = new Set(['sync', 'check', 'dev', 'build', 'preview']);
if (!commands.has(command)) throw new Error(`Unknown web command: ${command}`);

if (command !== 'sync' && command !== 'preview') {
	const manifestFile = path.join(paths.mcResources, 'manifest.json');
	if (!existsSync(manifestFile)) {
		throw new Error(`Generate Minecraft ${paths.version} resources first: ./gradlew generateMcResources -Pminecraft_version=${paths.version}`);
	}
	const manifest = JSON.parse(readFileSync(manifestFile, 'utf8'));
	if (manifest.minecraftVersion !== paths.version) {
		throw new Error(`Resource version ${manifest.minecraftVersion} does not match MC_VERSION=${paths.version}`);
	}
}

// Copy only authored public assets. Old texture-extraction outputs must never enter a new JAR.
rmSync(paths.staticDir, { recursive: true, force: true });
cpSync(path.join(webRoot, 'static'), paths.staticDir, {
	recursive: true,
	filter: (source) => source !== path.join(webRoot, 'static', 'mc')
});
mkdirSync(paths.versionBuild, { recursive: true });
// SvelteKit loads the generated SSR modules from this directory during prerendering.
// Let Node resolve their packages without duplicating the dependency installation.
const modules = path.join(paths.versionBuild, 'node_modules');
if (!existsSync(modules)) {
	symlinkSync(path.join(webRoot, 'node_modules'), modules, process.platform === 'win32' ? 'junction' : 'dir');
}
writeFileSync(paths.tsconfig, JSON.stringify({
	extends: [path.join(paths.kitOutput, 'tsconfig.json'), path.join(webRoot, 'tsconfig.base.json')]
}, null, 2) + '\n');

function run(binary, parameters) {
	const script = path.join(webRoot, 'node_modules', ...binary.split('/'));
	const result = spawnSync(process.execPath, [script, ...parameters], { cwd: webRoot, stdio: 'inherit' });
	if (result.error) throw result.error;
	if (result.status !== 0) process.exit(result.status ?? 1);
}

if (command !== 'preview') run('@sveltejs/kit/svelte-kit.js', ['sync']);
if (command === 'check') {
	run('svelte-check/bin/svelte-check', ['--tsconfig', paths.tsconfig, ...args]);
} else if (command !== 'sync') {
	run('vite/bin/vite.js', [command === 'dev' ? 'dev' : command, ...args]);
}
