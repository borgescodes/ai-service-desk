import { copyFile, cp, mkdir, rm } from 'node:fs/promises';

const src = new URL('../src/', import.meta.url);
const dist = new URL('../dist/', import.meta.url);
await rm(dist, { recursive: true, force: true });
await mkdir(dist, { recursive: true });
await cp(src, dist, { recursive: true });

const vendorFiles = [
  ['../node_modules/gsap/index.js', '../dist/vendor/gsap/index.js'],
  ['../node_modules/gsap/gsap-core.js', '../dist/vendor/gsap/gsap-core.js'],
  ['../node_modules/gsap/CSSPlugin.js', '../dist/vendor/gsap/CSSPlugin.js'],
  ['../node_modules/gsap/Flip.js', '../dist/vendor/gsap/Flip.js'],
  ['../node_modules/gsap/utils/matrix.js', '../dist/vendor/gsap/utils/matrix.js'],
  ['../node_modules/boxicons/css/boxicons.min.css', '../dist/vendor/boxicons/css/boxicons.min.css'],
  ['../node_modules/boxicons/fonts/boxicons.woff2', '../dist/vendor/boxicons/fonts/boxicons.woff2'],
  [
    '../node_modules/@fontsource-variable/montserrat/files/montserrat-latin-wght-normal.woff2',
    '../dist/vendor/fonts/montserrat-latin-wght-normal.woff2',
  ],
];

for (const [sourcePath, destinationPath] of vendorFiles) {
  const destination = new URL(destinationPath, import.meta.url);
  await mkdir(new URL('./', destination), { recursive: true });
  await copyFile(new URL(sourcePath, import.meta.url), destination);
}

console.log('web build ok');
