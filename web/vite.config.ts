import adapter from '@sveltejs/adapter-static';
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';
import { serverIcon } from './server-icon-plugin.js';
import { buildPaths } from './build-paths.js';

const { mcResources, webBuild, kitOutput, staticDir } = buildPaths();

export default defineConfig({
	build: {
		emptyOutDir: true
	},
	server: {
		port: 5173,
		proxy: {
			'/api': 'http://127.0.0.1:25580',
			'/mojang/session': {
				target: 'https://sessionserver.mojang.com',
				changeOrigin: true,
				secure: true,
				rewrite: (path) => path.replace(/^\/mojang/, '')
			},
			'/mojang/textures': {
				target: 'https://textures.minecraft.net',
				changeOrigin: true,
				secure: true,
				rewrite: (path) => path.replace(/^\/mojang\/textures/, '')
			}
		}
	},
	preview: {
		port: 4173
	},
	plugins: [
		serverIcon(),
		sveltekit({
			alias: {
				'$mc': mcResources
			},
			outDir: kitOutput,
			files: {
				assets: staticDir
			},
			compilerOptions: {
				runes: ({ filename }) =>
					filename.split(/[/\\]/).includes('node_modules') ? undefined : true
			},
			paths: {
				relative: false
			},
			adapter: adapter({
				pages: webBuild,
				assets: webBuild,
				fallback: '200.html',
				precompress: false,
				strict: true
			})
		})
	]
});
