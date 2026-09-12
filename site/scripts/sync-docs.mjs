// Ship the SDK's committed static documentation with the landing page.
// Regenerate upstream with `npm run docs:generate` after editing SDK docs.
import { cp, mkdir, readdir, readFile, writeFile, rm } from 'node:fs/promises';
const source = new URL('../../sdk/web/dist/', import.meta.url);
const destination = new URL('../public/docs/', import.meta.url);
await readFile(new URL('index.html', source)); // Fail before modifying output if the build is missing.
await rm(destination, { recursive: true, force: true });
await mkdir(destination, { recursive: true });
await cp(source, destination, { recursive: true });
for (const file of await readdir(destination)) {
  if (!file.endsWith('.html')) continue;
  const path = new URL(file, destination);
  const html = await readFile(path, 'utf8');
  await writeFile(path, html.replace(/\bTICK\b/g, 'ETH Arcade')
    .replace('<html lang="en">', '<html lang="en" data-theme="light">')
    .replaceAll('tick-theme', 'eth-arcade-docs-theme')
    .replace('<link rel="stylesheet" href="style.css">', '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@62..125,400..900&family=Chivo+Mono:wght@400;500;700&display=swap"><link rel="stylesheet" href="style.css"><link rel="stylesheet" href="landing-theme.css">').replace('<div class="side" id="side">', '<div class="side" id="side"><a class="site-home" href="/">← ETH Arcade home</a>'));
}
await cp(new URL('../docs-theme.css', import.meta.url), new URL('landing-theme.css', destination));
const app = new URL('app.js', destination);
await writeFile(app, (await readFile(app, 'utf8')).replaceAll('tick-theme', 'eth-arcade-docs-theme'));
console.log('SDK documentation ready at /docs/');
