import { defineConfig } from 'vite';
import { resolve } from 'node:path';
export default defineConfig({
  build: { rollupOptions: { input: {
    portal: resolve(__dirname, 'index.html'),
    moolog: resolve(__dirname, 'modules/moolog/index.html'),
    sigep: resolve(__dirname, 'modules/sigep/index.html')
  }}}
});
