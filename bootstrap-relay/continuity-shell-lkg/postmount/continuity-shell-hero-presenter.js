(() => {
  'use strict';

  const VERSION='20260930.3-landing';
  const HOST_ID='continuity-shell-landing-hero-presenter';
  const READY_SUPPRESS='continuity-shell-landing-ready-superseded';
  const LEGACY_SUPPRESS='data-continuity-hero-superseded';
  const NS='http://www.w3.org/2000/svg';

  if(window.__CONTINUITY_SHELL_HERO_PRESENTER__?.version===VERSION) return;
  window.__CONTINUITY_SHELL_HERO_PRESENTER__={version:VERSION,state:'booting'};

  const visible=(el)=>!!el&&!!(el.offsetWidth||el.offsetHeight||el.getClientRects().length);

  function isAuthSurface(){
    if(/^\/auth(?:\/|$)/.test(location.pathname)) return true;
    const body=(document.body&&document.body.innerText)||'';
    return /Sign in to Open WebUI/i.test(body)&&!!document.querySelector('input[type="password"]');
  }

  function isChatRoute(){
    return /^\/c\/[^/]+/.test(location.pathname);
  }

  function promptNode(){
    const direct=document.querySelector(
      '#message-input-container,[data-testid="message-input-container"],.message-input-container'
    );
    if(direct&&visible(direct)) return direct;
    const ta=[...document.querySelectorAll('textarea')].find(visible);
    if(!ta) return null;
    let p=ta;
    for(let i=0;i<7&&p;i++,p=p.parentElement){
      const r=p.getBoundingClientRect();
      const buttons=p.querySelectorAll?.('button').length||0;
      if(r.width>260&&r.height>=64&&r.height<300&&buttons>=2) return p;
    }
    return ta.parentElement;
  }

  function landingRoute(){
    if(isAuthSurface()||isChatRoute()) return false;
    const p=promptNode();
    if(!p) return false;
    return location.pathname==='/'||/^\/(?:new-chat)?$/.test(location.pathname);
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

  function fibonacciSphere(n=42){
    const out=[];
    const ga=Math.PI*(3-Math.sqrt(5));
    for(let i=0;i<n;i++){
      const y=1-(i/(n-1))*2;
      const r=Math.sqrt(Math.max(0,1-y*y));
      const th=ga*i;
      out.push({x:Math.cos(th)*r,y,z:Math.sin(th)*r});
    }
    return out;
  }

  function makeSphere(){
    const wrap=document.createElement('div');
    wrap.className='continuity-shell-hero-sphere-wrap';

    const svg=svgEl('svg',{viewBox:'0 0 240 240','aria-hidden':'true'});
    svg.classList.add('continuity-shell-hero-svg','hero-network','chat-landing-network');

    const defs=svgEl('defs');
    const glow=svgEl('filter',{
      id:'continuity-shell-hero-glow',
      x:'-80%',y:'-80%',width:'260%',height:'260%'
    });
    glow.append(
      svgEl('feGaussianBlur',{stdDeviation:'2.1',result:'b'}),
      (()=>{const m=svgEl('feMerge');m.append(svgEl('feMergeNode',{in:'b'}),svgEl('feMergeNode',{in:'SourceGraphic'}));return m;})()
    );
    defs.append(glow);
    svg.append(defs);

    const pts=fibonacciSphere(42).map((p,i)=>{
      const perspective=.78+(p.z+1)*.12;
      return {
        ...p,i,
        sx:120+p.x*82*perspective,
        sy:120+p.y*82*perspective,
        depth:(p.z+1)/2
      };
    });

    const edgeKeys=new Set();
    const edgeGroup=svgEl('g',{class:'continuity-shell-hero-edges'});
    for(const a of pts){
      const nearest=pts.filter(b=>b!==a)
        .map(b=>({
          b,
          d:(a.x-b.x)**2+(a.y-b.y)**2+(a.z-b.z)**2
        }))
        .sort((u,v)=>u.d-v.d)
        .slice(0,3);
      for(const {b} of nearest){
        const key=a.i<b.i?`${a.i}-${b.i}`:`${b.i}-${a.i}`;
        if(edgeKeys.has(key)) continue;
        edgeKeys.add(key);
        const dep=(a.depth+b.depth)/2;
        const line=svgEl('line',{
          x1:a.sx,y1:a.sy,x2:b.sx,y2:b.sy,
          stroke:colour((a.x+b.x+2)/4,.15+dep*.30),
          'stroke-width':.52+dep*.68
        });
        line.classList.add('continuity-shell-hero-edge');
        line.style.animationDelay=`${((a.i+b.i)%11)*-.31}s`;
        edgeGroup.append(line);
      }
    }
    svg.append(edgeGroup);

    const nodeGroup=svgEl('g',{
      class:'continuity-shell-hero-nodes',
      filter:'url(#continuity-shell-hero-glow)'
    });
    for(const p of pts.slice().sort((a,b)=>a.z-b.z)){
      const c=svgEl('circle',{
        cx:p.sx,cy:p.sy,
        r:1.55+p.depth*2.8,
        fill:colour((p.x+1)/2,.72+p.depth*.26)
      });
      c.classList.add('continuity-shell-hero-node');
      c.style.animationDelay=`${p.i*-.13}s`;
      nodeGroup.append(c);
    }
    svg.append(nodeGroup);
    wrap.append(svg);
    return wrap;
  }

  function makeHost(){
    const host=document.createElement('section');
    host.id=HOST_ID;
    host.className='continuity-shell-landing-hero-presenter';
    host.dataset.continuityHeroPresenter=VERSION;
    host.setAttribute('aria-label','Continuity system ready');

    const aura=document.createElement('div');
    aura.className='continuity-shell-hero-aura hero-aura chat-landing-aura';
    const sphere=makeSphere();
    const ready=document.createElement('div');
    ready.className='continuity-shell-hero-ready';
    ready.textContent='READY';
    host.append(aura,sphere,ready);
    return host;
  }

  function supersedeExternalHero(){
    const selectors=[
      '#owui-thinking-orb-v1[data-surface="landing"]',
      '#continuity-shell-hero',
      '.continuity-neural-hero'
    ];
    for(const sel of selectors){
      document.querySelectorAll(sel).forEach(el=>{
        if(el.closest('#'+HOST_ID)) return;
        el.setAttribute(LEGACY_SUPPRESS,'1');
      });
    }
  }

  function restoreExternalHero(){
    document.querySelectorAll('['+LEGACY_SUPPRESS+'="1"]').forEach(el=>el.removeAttribute(LEGACY_SUPPRESS));
  }

  function readyCandidates(composer){
    const cr=composer.getBoundingClientRect();
    const cx=(cr.left+cr.right)/2;
    return [...document.querySelectorAll('div,span,p,h1,h2,h3,strong')]
      .filter(el=>{
        if(el.closest('#'+HOST_ID)||el.closest('#message-input-container')||el.closest('#continuity-control-host')) return false;
        if(el.children.length!==0||!visible(el)||(el.textContent||'').trim()!=='READY') return false;
        const r=el.getBoundingClientRect();
        if(!r.width||!r.height) return false;
        if(r.bottom>cr.top+24) return false;
        if(cr.top-r.bottom>520) return false;
        if(Math.abs((r.left+r.right)/2-cx)>Math.max(180,cr.width*.42)) return false;
        return true;
      });
  }

  function suppressExternalReady(composer){
    for(const el of readyCandidates(composer)) el.classList.add(READY_SUPPRESS);
  }

  function restoreExternalReady(){
    document.querySelectorAll('.'+READY_SUPPRESS).forEach(el=>el.classList.remove(READY_SUPPRESS));
  }

  function rewriteFooter(){
    if(!document.body) return;
    const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
    const nodes=[];
    while(walker.nextNode()) nodes.push(walker.currentNode);
    for(const node of nodes){
      const t=(node.nodeValue||'').trim();
      if(/^Open WebUI\s*·\s*v0\.11\.3$/i.test(t)){
        node.nodeValue='Continuity Shell · Open WebUI · v0.11.3';
        node.parentElement?.classList.add('custom-shell-footer','continuity-shell-footer-bound');
      }else if(/^Continuity Shell\s*·\s*Open WebUI\s*·\s*v0\.11\.3$/i.test(t)){
        node.parentElement?.classList.add('custom-shell-footer','continuity-shell-footer-bound');
      }
    }
  }

  function positionHost(host,composer){
    const cr=composer.getBoundingClientRect();
    const vw=Math.max(320,window.innerWidth||320);
    const vh=Math.max(480,window.innerHeight||480);
    const size=Math.max(126,Math.min(176,vw*.36));
    const readyHeight=28;
    const groupHeight=size+readyHeight;
    let top=cr.top-groupHeight-28;
    const floor=Math.max(96,Math.min(188,vh*.155));
    if(top<floor) top=floor;
    const maxTop=Math.max(floor,cr.top-groupHeight-10);
    if(top>maxTop) top=maxTop;

    host.style.setProperty('--continuity-hero-size',size.toFixed(1)+'px');
    host.style.top=Math.round(top)+'px';
    host.style.left=Math.round((cr.left+cr.right)/2)+'px';
  }

  function cleanup(){
    document.getElementById(HOST_ID)?.remove();
    restoreExternalHero();
    restoreExternalReady();
    document.documentElement.classList.remove('continuity-shell-hero-presenter-active');
    window.__CONTINUITY_SHELL_HERO_PRESENTER__.state=isAuthSurface()?'auth-native':'inactive';
  }

  function apply(){
    if(!landingRoute()){
      cleanup();
      return;
    }
    const composer=promptNode();
    if(!composer) return;

    supersedeExternalHero();
    suppressExternalReady(composer);

    let host=document.getElementById(HOST_ID);
    if(!host){
      host=makeHost();
      document.body.appendChild(host);
    }

    positionHost(host,composer);
    rewriteFooter();
    document.documentElement.classList.add('continuity-shell-hero-presenter-active');
    window.__CONTINUITY_SHELL_HERO_PRESENTER__.state='landing-presented';
  }

  let raf=0;
  function schedule(){
    if(raf) return;
    raf=requestAnimationFrame(()=>{raf=0;apply();});
  }

  const observer=new MutationObserver(schedule);
  observer.observe(document.documentElement,{childList:true,subtree:true,characterData:true});

  for(const type of ['popstate','resize','orientationchange']){
    addEventListener(type,schedule,{passive:true});
  }
  visualViewport?.addEventListener('resize',schedule,{passive:true});

  schedule();

  window.ContinuityShellHeroPresenter=Object.freeze({
    version:VERSION,
    refresh:apply,
    status:()=>({
      state:window.__CONTINUITY_SHELL_HERO_PRESENTER__.state,
      path:location.pathname,
      host:!!document.getElementById(HOST_ID),
      externalReadySuppressed:document.querySelectorAll('.'+READY_SUPPRESS).length,
      externalHeroSuppressed:document.querySelectorAll('['+LEGACY_SUPPRESS+'="1"]').length
    })
  });
})();