import { defineConfig, type Plugin } from 'vite';
import react from '@vitejs/plugin-react';

// Vite's dev server otherwise treats a public-directory index as an SPA route.
const docsIndex: Plugin = {
  name: 'sdk-docs-index',
  configureServer(server) {
    server.middlewares.use((req, res, next) => {
      const [path, query] = (req.url || '').split('?');
      if (path !== '/docs' && path !== '/docs/') return next();
      res.writeHead(302, { Location: '/docs/index.html' + (query ? '?' + query : '') });
      res.end();
    });
  },
};

export default defineConfig({
  plugins: [docsIndex, react()],
  server: { port: 5173, strictPort: true },
  build: { target: 'es2022', chunkSizeWarningLimit: 1500 },
});
