import { readdir, readFile } from 'node:fs/promises';

const root = new URL('../src/', import.meta.url);
const allowedExternalUrls = new Set(['https://mysignins.microsoft.com/security-info/password/change']);
const forbidden = [
  'backdrop-filter',
  'linear-gradient(',
  'radial-gradient(',
  'RoutingRegistry',
  'ApprovalService',
  'ExecutionEngine',
  'POLICY_DECISIONS',
  '/api/v1/access',
  'Authorization: Bearer',
  'http://127.0.0.1:',
  'http://localhost:',
  'https://cdn.',
];

async function files(dirUrl) {
  const entries = await readdir(dirUrl, { withFileTypes: true });
  const result = [];
  for (const entry of entries) {
    const target = new URL(entry.name, dirUrl);
    if (entry.isDirectory()) result.push(...(await files(new URL(`${entry.name}/`, dirUrl))));
    else result.push(target);
  }
  return result;
}

let failed = false;
for (const file of await files(root)) {
  if (file.pathname.endsWith('.png')) {
    const bytes = await readFile(file);
    if (!bytes.subarray(0, 8).equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]))) {
      console.error(`Invalid PNG asset in ${file.pathname}`); failed = true;
    }
    continue;
  }
  const text = await readFile(file, 'utf8');
  for (const token of forbidden) {
    if (text.includes(token)) {
      console.error(`Forbidden frontend token ${JSON.stringify(token)} in ${file.pathname}`);
      failed = true;
    }
  }
  const externalUrls = text.match(/https?:\/\/[^\s'"`<>]+/g) ?? [];
  for (const url of externalUrls) {
    if (!allowedExternalUrls.has(url)) {
      console.error(`External URL ${JSON.stringify(url)} is not allowed in ${file.pathname}`);
      failed = true;
    }
  }
}
if (failed) process.exit(1);
console.log('frontend lint ok');
