import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { z } from 'zod';
import { spawn } from 'node:child_process';
import fs from 'node:fs/promises';
import { createBoundedPathResolver } from './path-policy.mjs';

const ROOT='/home/storage/781/4477781/user/webapp';
const safeExistingPath=await createBoundedPathResolver(ROOT);
const server=new McpServer({name:'chris-fasthosts-local',version:'1.0.0'});
const appendBounded=(current,chunk,max)=>current.length>=max?current:(current+chunk).slice(0,max);

server.tool('runtime_health','Run the canonical architecture health check',{},async()=>new Promise((resolve)=>{
  const p=spawn(ROOT+'/runtime-domains/tools/architecture-health.sh',[],{cwd:ROOT,env:{...process.env,HOME:ROOT},detached:true});
  let o='',e='',done=false,t;
  const finish=(c,why='')=>{
    if(done)return;
    done=true;
    if(t)clearTimeout(t);
    resolve({content:[{type:'text',text:(o+e+(why?'\n'+why:'')).slice(-30000)}],isError:c!==0});
  };
  p.stdout.on('data',d=>{o=appendBounded(o,d.toString(),30000)});
  p.stderr.on('data',d=>{e=appendBounded(e,d.toString(),15000)});
  p.on('error',err=>finish(1,'SPAWN_ERROR: '+err.message));
  p.on('close',c=>finish(c??1));
  t=setTimeout(()=>{try{process.kill(-p.pid,'SIGTERM')}catch{};finish(124,'TIMEOUT')},30000);
}));

server.tool('read_text','Read a UTF-8 text file inside the bounded webapp root',{path:z.string(),max_bytes:z.number().int().positive().max(262144).optional()},async({path:requestedPath,max_bytes=65536})=>{
  const q=await safeExistingPath(requestedPath);
  const h=await fs.open(q,'r');
  try{
    const b=Buffer.alloc(max_bytes);
    const {bytesRead}=await h.read(b,0,max_bytes,0);
    return {content:[{type:'text',text:b.subarray(0,bytesRead).toString('utf8')}]};
  }finally{
    await h.close();
  }
});

server.tool('list_dir','List one directory inside the bounded webapp root',{path:z.string().optional()},async({path:requestedPath='.'})=>{
  const q=await safeExistingPath(requestedPath);
  const entries=[];
  const dir=await fs.opendir(q);
  for await(const x of dir){
    entries.push((x.isDirectory()?'d ':'f ')+x.name);
    if(entries.length>=500)break;
  }
  return {content:[{type:'text',text:entries.join('\n')}]};
});

server.tool('terminal_exec','Execute one bounded shell command as the existing Fasthosts account. No privilege escalation. Output is capped.',{command:z.string().min(1).max(8192),timeout_ms:z.number().int().min(100).max(30000).optional()},async({command,timeout_ms=10000})=>new Promise((resolve)=>{
  const p=spawn('/bin/bash',['-lc',command],{cwd:ROOT,env:{...process.env,HOME:ROOT,PATH:ROOT+'/.local/node22-glibc217/bin:'+ROOT+'/miniconda/bin:/usr/local/bin:/usr/bin:/bin'},detached:true});
  let o='',e='',done=false,t;
  const finish=(c,why='')=>{
    if(done)return;
    done=true;
    if(t)clearTimeout(t);
    resolve({content:[{type:'text',text:(o+e+(why?'\n'+why:'')).slice(-60000)}],isError:c!==0});
  };
  p.stdout.on('data',d=>{o=appendBounded(o,d.toString(),60000)});
  p.stderr.on('data',d=>{e=appendBounded(e,d.toString(),30000)});
  p.on('error',err=>finish(1,'SPAWN_ERROR: '+err.message));
  p.on('close',c=>finish(c??1));
  t=setTimeout(()=>{try{process.kill(-p.pid,'SIGTERM')}catch{};finish(124,'TIMEOUT')},timeout_ms);
}));

await server.connect(new StdioServerTransport());
