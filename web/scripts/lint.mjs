import { readdir, readFile } from 'node:fs/promises';

const root = new URL('../src/', import.meta.url);
const forbidden = [
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
  const text = await readFile(file, 'utf8');
  for (const token of forbidden) {
    if (text.includes(token)) {
      console.error(`Forbidden frontend token ${JSON.stringify(token)} in ${file.pathname}`);
      failed = true;
    }
  }
  if (/https?:\/\//.test(text)) {
    console.error(`External URL is not allowed in ${file.pathname}`);
    failed = true;
  }
}
if (failed) process.exit(1);
console.log('frontend lint ok');
