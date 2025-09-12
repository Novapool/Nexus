import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [sveltekit()],
	server: {
		proxy: {
			// Proxy WebSocket connections to FastAPI backend
			'/ws': {
				target: 'ws://localhost:8000',
				ws: true,
				changeOrigin: true
			},
			// Proxy API calls to FastAPI backend
			'/api': {
				target: 'http://localhost:8000',
				changeOrigin: true
			},
			// Proxy health check
			'/health': {
				target: 'http://localhost:8000',
				changeOrigin: true
			}
		}
	}
});