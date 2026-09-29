import fs from 'node:fs';
import { Client } from 'file:///home/storage/781/4477781/user/webapp/.local/desktop-commander-remote/node_modules/@modelcontextprotocol/sdk/dist/esm/client/index.js';
import { StdioClientTransport, getDefaultEnvironment } from 'file:///home/storage/781/4477781/user/webapp/.local/desktop-commander-remote/node_modules/@modelcontextprotocol/sdk/dist/esm/client/stdio.js';
const root='/home/storage/781/4477781/user/webapp';
const req=JSON.parse(fs.readFileSync(0,'utf8')||'{}');
const transport=new StdioClientTransport({command:root+'/bin/local-mcp',args:[],cwd:root,env:{...getDefaultEnvironment(),HOME:'/home/storage/781/4477781/user'}});
const client=new Client({name:'powerpc-control-v1',version:'1.0.0'},{capabilities:{}});
try {
  await client.connect(transport);
  const result=await client.callTool({name:req.tool,arguments:req.arguments});
  process.stdout.write(JSON.stringify(result));
} finally {
  try { await client.close(); } catch {}
  try { await transport.close(); } catch {}
}
