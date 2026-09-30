import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';
const c=new Client({name:'smoke',version:'1'});
await c.connect(new StdioClientTransport({command:'/home/storage/781/4477781/user/webapp/bin/local-mcp'}));
console.log((await c.listTools()).tools.map(x=>x.name).join(','));
const r=await c.callTool({name:'terminal_exec',arguments:{command:'printf MCP_LOCAL_OK',timeout_ms:2000}});
console.log(r.content?.[0]?.text);
await c.close();
