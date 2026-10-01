(() => {
  'use strict';

  const VERSION='20261001.1-telemetry';
  const HOST_ID='owui-thinking-orb-v1';
  const BEAM_ID='owui-border-beam-v1';
  const READY_SUPPRESS='continuity-shell-landing-ready-superseded';
  const LEGACY_SUPPRESS='data-continuity-hero-superseded';
  const NS='http://www.w3.org/2000/svg';

  if(window.__CONTINUITY_SHELL_TELEMETRY__?.version===VERSION) return;
  window.__CONTINUITY_SHELL_TELEMETRY__={version:VERSION,state:'booting',surface:null};

  const visible=(el)=>!!el&&!!(el.offsetWidth||el.offsetHeight||el.getClientRects().length);
  const norm=(s)=>String(s||'').replace(/\s+/g,' ').trim();

  function isAuthSurface(){
    if(/^\/auth(?:\/|$)/.test(location.pathname)) return true;
    const body=(document.body&&document.body.innerText)||'';
    return /Sign in to Open WebUI/i.test(body)&&!!document.querySelector('input[type="password"]');
  }

  function chatPane(){
    return document.querySelector('#chat-pane');
  }

  function promptNode(){
    const direct=document.querySelector('#message-input-container');
    if(direct&&visible(direct)) return direct;
    const ta=[...document.querySelectorAll('textarea')].find(visible);
    if(!ta) return null;
    for(let p=ta.parentElement,depth=0;p&&depth<9;p=p.parentElement,depth++){
      const r=p.getBoundingClientRect();
      const buttons=p.querySelectorAll?.('button').length||0;
      if(r.width>260&&r.height>=64&&r.height<320&&buttons>=2) return p;
    }
    return ta.parentElement;
  }

  function hasMessages(){
    return [...document.querySelectorAll('.message-listitem,[data-message-id],[role="listitem"]')]
      .some(el=>visible(el)&&!el.closest('#'+HOST_ID));
  }

  function surface(){
    if(isAuthSurface()) return 'auth';
    if(/^\/c\/[^/]+/.test(location.pathname)||hasMessages()) return 'chat';
    if((location.pathname==='/'||/^\/(?:new-chat)?$/.test(location.pathname))&&promptNode()) return 'landing';
    return 'inactive';
  }

  function svgEl(name,attrs={}){
    const el=document.createElementNS(NS,name);
    for(const [k,v] of Object.entries(attrs)) el.setAttribute(k,String(v));
    return el;
  }

  function colour(t,alpha=1){
    const h=202+t*92;
    return `hsla(${h},92%,67%,${alpha})`;
  }

  function fibonacciSphere(n=46){
    const out=[],ga=Math.PI*(3-Math.sqrt(5));
    for(let i=0;i<n;i++){
      const y=1-(i/(n-1))*2,r=Math.sqrt(Math.max(0,1-y*y)),th=ga*i;
      out.push({x:Math.cos(th)*r,y,z:Math.sin(th)*r});
    }
    return out;
  }

  function makeSphere(){
    const wrap=document.createElement('div');
    wrap.className='continuity-shell-telemetry-sphere-wrap';
    const svg=svgEl('svg',{viewBox:'0 0 240 240','aria-hidden':'true'});
    svg.classList.add('continuity-shell-telemetry-svg');

    const defs=svgEl('defs');
    const glow=svgEl('filter',{id:'continuity-shell-telemetry-glow',x:'-80%',y:'-80%',width:'260%',height:'260%'});
    glow.append(svgEl('feGaussianBlur',{stdDeviation:'2.1',result:'b'}));
    const merge=svgEl('feMerge');
    merge.append(svgEl('feMergeNode',{in:'b'}),svgEl('feMergeNode',{in:'SourceGraphic'}));
    glow.append(merge); defs.append(glow); svg.append(defs);

    const pts=fibonacciSphere().map((p,i)=>{
      const perspective=.78+(p.z+1)*.12;
      return {...p,i,sx:120+p.x*82*perspective,sy:120+p.y*82*perspective,depth:(p.z+1)/2};
    });
    const edgeKeys=new Set(),edges=svgEl('g',{class:'continuity-shell-telemetry-edges'});
    for(const a of pts){
      const nearest=pts.filter(b=>b!==a)
        .map(b=>({b,d:(a.x-b.x)**2+(a.y-b.y)**2+(a.z-b.z)**2}))
        .sort((u,v)=>u.d-v.d).slice(0,3);
      for(const {b} of nearest){
        const key=a.i<b.i?`${a.i}-${b.i}`:`${b.i}-${a.i}`;
        if(edgeKeys.has(key)) continue;
        edgeKeys.add(key);
        const dep=(a.depth+b.depth)/2;
        const line=svgEl('line',{x1:a.sx,y1:a.sy,x2:b.sx,y2:b.sy,stroke:colour((a.x+b.x+2)/4,.15+dep*.30),'stroke-width':.52+dep*.68});
        line.classList.add('continuity-shell-telemetry-edge');
        line.style.animationDelay=`${((a.i+b.i)%11)*-.31}s`;
        edges.append(line);
      }
    }
    svg.append(edges);
    const nodes=svgEl('g',{class:'continuity-shell-telemetry-nodes',filter:'url(#continuity-shell-telemetry-glow)'});
    for(const p of pts.slice().sort((a,b)=>a.z-b.z)){
      const c=svgEl('circle',{cx:p.sx,cy:p.sy,r:1.55+p.depth*2.8,fill:colour((p.x+1)/2,.72+p.depth*.26)});
      c.classList.add('continuity-shell-telemetry-node');
      c.style.animationDelay=`${p.i*-.13}s`; nodes.append(c);
    }
    svg.append(nodes); wrap.append(svg); return wrap;
  }

  function makeHost(){
    const host=document.createElement('section');
    host.id=HOST_ID;
    host.dataset.continuityTelemetry=VERSION;
    host.setAttribute('aria-live','polite');
    const aura=document.createElement('div'); aura.className='continuity-shell-telemetry-aura';
    const sphere=makeSphere();
    const copy=document.createElement('div'); copy.className='continuity-shell-telemetry-copy';
    const title=document.createElement('div'); title.className='continuity-shell-telemetry-title';
    const detail=document.createElement('div'); detail.className='continuity-shell-telemetry-detail';
    copy.append(title,detail); host.append(aura,sphere,copy); return host;
  }

  function state(){
    const body=(document.body&&document.body.innerText)||'';
    if(/Searching(?: the)? web|searching/i.test(body)) return ['searching','Searching…','RETRIEVING'];
    if(document.querySelector('button[aria-label*="Stop"],button[title*="Stop"]')) return ['working','Thinking…','EXECUTING'];
    if(document.querySelector('textarea:focus,input:focus')) return ['composing','Ready','SYSTEM READY'];
    return ['idle','Ready','SYSTEM READY'];
  }

  function suppressLandingDetritus(on){
    const selectors=['#continuity-shell-hero','.continuity-neural-hero','#continuity-shell-landing-hero-presenter'];
    for(const sel of selectors) document.querySelectorAll(sel).forEach(el=>{
      if(el.id===HOST_ID) return;
      if(on) el.setAttribute(LEGACY_SUPPRESS,'1'); else el.removeAttribute(LEGACY_SUPPRESS);
    });
    document.querySelectorAll('.'+READY_SUPPRESS).forEach(el=>el.classList.remove(READY_SUPPRESS));
    if(!on) return;
    [...document.querySelectorAll('div,span,p,h1,h2,h3,strong')].forEach(el=>{
      if(el.closest('#'+HOST_ID)||el.closest('#message-input-container')||el.children.length||!visible(el)) return;
      if(norm(el.textContent)==='READY') el.classList.add(READY_SUPPRESS);
    });
  }

  function ensureBeam(composer,s){
    let beam=document.getElementById(BEAM_ID);
    if(!composer||s==='inactive'||s==='auth'){
      beam?.remove(); return;
    }
    if(!beam){
      beam=document.createElement('span'); beam.id=BEAM_ID; beam.setAttribute('aria-hidden','true');
    }
    if(beam.parentElement!==composer) composer.appendChild(beam);
    beam.dataset.state=state()[0];
  }

  function mountHost(host,pane){
    if(host.parentElement!==pane) pane.prepend(host);
  }

  function apply(){
    const s=surface(),pane=chatPane(),composer=promptNode();
    if(s==='auth'||s==='inactive'||!pane||!composer){
      document.getElementById(HOST_ID)?.remove();
      document.getElementById(BEAM_ID)?.remove();
      suppressLandingDetritus(false);
      document.documentElement.removeAttribute('data-continuity-telemetry-surface');
      window.__CONTINUITY_SHELL_TELEMETRY__.state=s;
      window.__CONTINUITY_SHELL_TELEMETRY__.surface=s;
      return;
    }

    let host=document.getElementById(HOST_ID);
    if(!host) host=makeHost();
    mountHost(host,pane);
    host.dataset.surface=s;
    document.documentElement.dataset.continuityTelemetrySurface=s;

    const [st,title,detail]=state();
    host.dataset.state=st;
    host.querySelector('.continuity-shell-telemetry-title').textContent=title;
    host.querySelector('.continuity-shell-telemetry-detail').textContent=s==='landing'?detail:'';
    suppressLandingDetritus(s==='landing');
    ensureBeam(composer,s);

    window.__CONTINUITY_SHELL_TELEMETRY__.state=st;
    window.__CONTINUITY_SHELL_TELEMETRY__.surface=s;
    dispatchEvent(new CustomEvent('continuity-orb-beam:ready',{detail:{version:VERSION,surface:s,state:st}}));
  }

  let raf=0;
  function schedule(){
    if(raf) return;
    raf=requestAnimationFrame(()=>{raf=0;apply();});
  }
  new MutationObserver(schedule).observe(document.documentElement,{childList:true,subtree:true,characterData:true,attributes:true,attributeFilter:['class','data-surface']});
  for(const type of ['popstate','resize','orientationchange']) addEventListener(type,schedule,{passive:true});
  addEventListener('continuity-shell:theme',schedule);
  schedule();

  window.ContinuityShellTelemetry=Object.freeze({
    version:VERSION,refresh:apply,status:()=>({
      state:window.__CONTINUITY_SHELL_TELEMETRY__.state,
      surface:window.__CONTINUITY_SHELL_TELEMETRY__.surface,
      path:location.pathname,
      host:!!document.getElementById(HOST_ID),
      beam:!!document.getElementById(BEAM_ID)
    })
  });
})();