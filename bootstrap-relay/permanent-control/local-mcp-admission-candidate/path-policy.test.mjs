import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { createBoundedPathResolver } from './path-policy.mjs';

const root=fs.mkdtempSync(path.join(os.tmpdir(),'local-mcp-root-'));
const outside=fs.mkdtempSync(path.join(os.tmpdir(),'local-mcp-outside-'));
fs.writeFileSync(path.join(root,'ok.txt'),'ok');
fs.writeFileSync(path.join(outside,'secret.txt'),'secret');
fs.symlinkSync(path.join(outside,'secret.txt'),path.join(root,'escape-link.txt'));

const resolveSafe=await createBoundedPathResolver(root);
assert.equal(await resolveSafe('ok.txt'),await fs.promises.realpath(path.join(root,'ok.txt')));

for(const candidate of [
  '../'+path.basename(outside)+'/secret.txt',
  path.join(outside,'secret.txt'),
  'escape-link.txt'
]){
  await assert.rejects(()=>resolveSafe(candidate),/path outside bounded webapp root/);
}

console.log('PATH_POLICY=PASS');
