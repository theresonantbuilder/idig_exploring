import { defineConfig } from 'vite';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = fileURLToPath(new URL('.', import.meta.url));

// The persistent launcher + selection surface, declared in the manifest's
// content_scripts. Built second, into the same dist/, without emptying it.
export default defineConfig({
  envDir: __dirname,
  publicDir: false,
  build: {
    outDir: resolve(__dirname, 'dist'),
    emptyOutDir: false,
    target: 'chrome120',
    lib: {
      entry: resolve(__dirname, 'src/content/launcher.ts'),
      formats: ['iife'],
      name: 'idigLauncher',
      fileName: () => 'launcher.js',
    },
  },
});
