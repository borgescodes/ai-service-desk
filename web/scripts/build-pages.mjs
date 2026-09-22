import { cp, mkdir, readFile, readdir, rm, writeFile } from 'node:fs/promises';

await import('./build.mjs');

const dist = new URL('../dist/', import.meta.url);
const pages = new URL('../pages-dist/', import.meta.url);
const base = String(process.env.JUP_PAGES_BASE_PATH ?? '')
  .trim()
  .replace(/\/+$/, '')
  .replace(/^([^/])/, '/$1');

await rm(pages, { recursive: true, force: true });
await mkdir(pages, { recursive: true });
await cp(dist, pages, { recursive: true });

const staticPrefixes = [
  '/assets/',
  '/vendor/',
  '/tokens.css',
  '/styles.css',
  '/desktop-responsive.css',
  '/app.mjs',
  '/ui-polish.mjs',
];

async function textFiles(root) {
  const entries = await readdir(root, { withFileTypes: true });
  const nested = await Promise.all(entries.map(async entry => {
    const target = new URL(entry.name + (entry.isDirectory() ? '/' : ''), root);
    if (entry.isDirectory()) return textFiles(target);
    return /\.(?:html|css|mjs)$/i.test(entry.name) ? [target] : [];
  }));
  return nested.flat();
}

if (base) {
  for (const target of await textFiles(pages)) {
    let text = await readFile(target, 'utf8');
    for (const prefix of staticPrefixes) {
      text = text
        .replaceAll(`"${prefix}`, `"${base}${prefix}`)
        .replaceAll(`'${prefix}`, `'${base}${prefix}`);
    }
    text = text
      .replaceAll('url("/assets/', `url("${base}/assets/`)
      .replaceAll("url('/assets/", `url('${base}/assets/`)
      .replaceAll('url("/vendor/', `url("${base}/vendor/`)
      .replaceAll("url('/vendor/", `url('${base}/vendor/`);
    await writeFile(target, text, 'utf8');
  }
}

const index = await readFile(new URL('index.html', pages), 'utf8');
await writeFile(new URL('404.html', pages), index, 'utf8');
await writeFile(new URL('.nojekyll', pages), '', 'utf8');

console.log(`pages build ok${base ? ` at ${base}/` : ''}`);
