import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const account=process.env.PPC_ACCOUNT || os.homedir();
const root=process.env.PPC_WEBAPP_ROOT || path.join(account,'webapp');
const sdkRoot=path.join(root,'runtime-domains','local-mcp','node_modules','@modelcontextprotocol','sdk','dist','esm','client');
const { Client }=await import(pathToFileURL(path.join(sdkRoot,'index.js')).href);
const { StdioClientTransport, getDefaultEnvironment }=await import(pathToFileURL(path.join(sdkRoot,'stdio.js')).href);

const req=JSON.parse(fs.readFileSync(0,'utf8')||'{}');
const transport=new StdioClientTransport({
  command:path.join(root,'bin','local-mcp'),
  args:[],
  cwd:root,
  env:{...getDefaultEnvironment(),HOME:account}
});
const client=new Client({name:'powerpc-control-v1',version:'1.0.0'},{capabilities:{}});
try {
  await client.connect(transport);
  const result=await client.callTool({name:req.tool,arguments:req.arguments});
  process.stdout.write(JSON.stringify(result));
} finally {
  try { await client.close(); } catch {}
  try { await transport.close(); } catch {}
}
