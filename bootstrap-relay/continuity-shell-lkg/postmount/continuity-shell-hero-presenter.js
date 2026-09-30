(() => {
  'use strict';

  const VERSION='20260930.4-landing';
  const HOST_ID='continuity-shell-landing-hero-presenter';
  const READY_SUPPRESS='continuity-shell-landing-ready-superseded';
  const LEGACY_SUPPRESS='data-continuity-hero-superseded';
  const NS='http://www.w3.org/2000/svg';

  if(window.__CONTINUITY_SHELL_HERO_PRESENTER__?.version===VERSION) return;
  window.__CONTINUITY_SHELL_HERO_PRESENTER__={version:VERSION,state:'booting'};

  const visible=(el)=>!!el&&!!(el.offsetWidth||el.offsetHeight||el.getClientRects().length);
  const norm=(s)=>String(s||'').replace(/\s+/g,' ').trim();

  function isAuthSurface(){
    if(/^\/auth(?:\/|$)/.test(location.pathname)) return true;
    const body=(document.body&&document.body.innerText)||'';
    return /Sign in to Open WebUI/i.test(body)&&!!document.querySelector('input[type="password"]');
  }

  function hasConversationMessages(){
    return [...document.querySelectorAll('.message-listitem,[role="listitem"].message-listitem')]
      .some(visible);
  }

  function isChatRoute(){
    return /^\/c\/[^/]+/.test(location.pathname)||hasConversationMessages();
  }

  function promptNode(){
    const direct=document.querySelector('#message-input-container');
    if(direct&&visible(direct)) return direct;
    const ta=[...document.querySelectorAll('textarea')].find(visible);
    if(!ta) return null;

    const candidates=[];
    for(let p=ta.parentElement,depth=0;p&&depth<9;p=p.parentElement,depth++){
      const r=p.getBoundingClientRect();
      const buttons=p.querySelectorAll?.('button').length||0;
      if(r.width>260&&r.height>=64&&r.height<320&&buttons>=2){
        candidates.push({el:p,r,buttons});
      }
    }
    if(!candidates.length) return ta.parentElement;
    candidates.sort((a,b)=>(b.r.width*b.r.height)-(a.r.width*a.r.height));
    return candidates[0].el;
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
    svg.classList.add('continuity-shell-hero-svg');

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
        .map(b=>({b,d:(a.x-b.x)**2+(a.y-b.y)**2+(a.z-b.z)**2}))
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
    aura.className='continuity-shell-hero-aura';
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

  function readyCandidates(){
    return [...document.querySelectorAll('div,span,p,h1,h2,h3,strong')]
      .filter(el=>{
        if(el.closest('#'+HOST_ID)||el.closest('#message-input-container')||el.closest('#continuity-control-host')) return false;
        if(el.children.length!==0||!visible(el)||norm(el.textContent)!=='READY') return false;
        const r=el.getBoundingClientRect();
        return r.width>0&&r.height>0;
      });
  }

  function suppressExternalReady(){
    for(const el of readyCandidates()) el.classList.add(READY_SUPPRESS);
  }

  function restoreExternalReady(){
    document.querySelectorAll('.'+READY_SUPPRESS).forEach(el=>el.classList.remove(READY_SUPPRESS));
  }

  function rewriteFooter(){
    const rx=/^Open WebUI\s*·\s*v0\.11\.3$/i;
    const nodes=[...document.querySelectorAll('div,span,p,a')];
    const hits=[];
    for(const el of nodes){
      if(!visible(el)||el.closest('#message-input-container')||el.closest('#continuity-control-host')) continue;
      const t=norm(el.textContent);
      if(!rx.test(t)) continue;
      const r=el.getBoundingClientRect();
      if(r.width>420||r.height>90) continue;
      hits.push({el,area:r.width*r.height});
    }
    hits.sort((a,b)=>a.area-b.area);
    for(const {el} of hits){
      if(norm(el.textContent)!=='Continuity Shell · Open WebUI · v0.11.3'){
        el.textContent='Continuity Shell · Open WebUI · v0.11.3';
      }
      el.classList.add('custom-shell-footer','continuity-shell-footer-bound');
      break;
    }
  }

  function nearbyIdentityTop(composer){
    const cr=composer.getBoundingClientRect();
    const cx=(cr.left+cr.right)/2;
    const minY=Math.max(0,cr.top-360);
    let top=null;

    for(const el of document.querySelectorAll('h1,h2,h3,div,p,span')){
      if(!visible(el)||el.closest('#'+HOST_ID)||el.closest('#message-input-container')||el.closest('#continuity-control-host')) continue;
      const text=norm(el.textContent);
      if(text.length<3||text.length>260) continue;
      if(/^(READY|WORLD BETWEEN WORLDS|CONTINUITY|INPUT|Open WebUI|Continuity Shell)/i.test(text)) continue;

      const r=el.getBoundingClientRect();
      if(!r.width||!r.height||r.bottom>cr.top+4||r.top<minY) continue;
      if(Math.abs((r.left+r.right)/2-cx)>Math.max(220,cr.width*.48)) continue;

      const fs=parseFloat(getComputedStyle(el).fontSize)||0;
      if(fs<17&&r.height<34) continue;
      if(top===null||r.top<top) top=r.top;
    }
    return top;
  }

  function positionHost(host,composer){
    const cr=composer.getBoundingClientRect();
    const vw=Math.max(320,window.innerWidth||320);
    const vh=Math.max(480,window.innerHeight||480);

    const size=Math.max(126,Math.min(174,vw*.34));
    const groupHeight=size+34;
    const identityTop=nearbyIdentityTop(composer);
    const anchorTop=identityTop===null?cr.top:Math.min(cr.top,identityTop);
    const gap=identityTop===null?28:20;

    let top=anchorTop-groupHeight-gap;
    const floor=Math.max(86,Math.min(176,vh*.12));
    if(top<floor) top=floor;

    host.style.setProperty('--continuity-hero-size',size.toFixed(1)+'px');
    host.style.setProperty('left',Math.round((cr.left+cr.right)/2)+'px','important');
    host.style.setProperty('top',Math.round(top)+'px','important');
    host.style.setProperty('bottom','auto','important');
    host.style.setProperty('transform','translateX(-50%)','important');
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
    suppressExternalReady();

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
  observer.observe(document.documentElement,{childList:true,subtree:true,characterData:true,attributes:true,attributeFilter:['class']});

  for(const type of ['popstate','resize','orientationchange']){
    addEventListener(type,schedule,{passive:true});
  }
  visualViewport?.addEventListener('resize',schedule,{passive:true});
  visualViewport?.addEventListener('scroll',schedule,{passive:true});
  addEventListener('continuity-shell:theme',schedule);

  schedule();

  window.ContinuityShellHeroPresenter=Object.freeze({
    version:VERSION,
    refresh:apply,
    status:()=>({
      state:window.__CONTINUITY_SHELL_HERO_PRESENTER__.state,
      path:location.pathname,
      messages:[...document.querySelectorAll('.message-listitem')].filter(visible).length,
      host:!!document.getElementById(HOST_ID),
      externalReadySuppressed:document.querySelectorAll('.'+READY_SUPPRESS).length,
      externalHeroSuppressed:document.querySelectorAll('['+LEGACY_SUPPRESS+'="1"]').length
    })
  });
})();