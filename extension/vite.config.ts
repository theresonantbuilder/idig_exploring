import { defineConfig } from 'vite';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = fileURLToPath(new URL('.', import.meta.url));

// Extension pages + the background service worker. The launcher content
// script is a separate build (vite.content.config.ts) because Chrome loads
// manifest-declared content scripts as classic scripts, so it must be one
// self-contained IIFE with no imports.
export default defineConfig({
  root: resolve(__dirname, 'src'),
  publicDir: resolve(__dirname, 'public'),
  envDir: __dirname,
  base: './',
  build: {
    outDir: resolve(__dirname, 'dist'),
    emptyOutDir: true,
    target: 'chrome120',
    rollupOptions: {
      input: {
        background: resolve(__dirname, 'src/background/background.ts'),
        review: resolve(__dirname, 'src/review/review.html'),
      },
      output: {
        entryFileNames: '[name].js',
        chunkFileNames: 'chunks/[name].js',
        assetFileNames: 'assets/[name][extname]',
      },
    },
  },
});
