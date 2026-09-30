import fs from 'node:fs/promises';
import path from 'node:path';

const inside=(candidate,root)=>candidate===root||candidate.startsWith(root+path.sep);

export const createBoundedPathResolver=async(root)=>{
  const lexicalRoot=path.resolve(root);
  const realRoot=await fs.realpath(lexicalRoot);
  return async(requestedPath)=>{
    const candidate=path.resolve(lexicalRoot,requestedPath);
    if(!inside(candidate,lexicalRoot))throw new Error('path outside bounded webapp root');
    const real=await fs.realpath(candidate);
    if(!inside(real,realRoot))throw new Error('path outside bounded webapp root');
    return real;
  };
};
