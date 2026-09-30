(() => {
  'use strict';

  const VERSION = '20260930.1';
  const ROOT_ID = 'continuity-shell-semantic-binder';
  const HERO_ID = 'continuity-shell-hero';
  const TELEMETRY_ID = 'continuity-shell-chat-telemetry';
  const FOOTER_ID = 'continuity-shell-footer-owned';
  const SUPERSEDED = 'data-continuity-superseded';

  if (window.__CONTINUITY_SHELL_SEMANTIC_BINDER__) return;
  window.__CONTINUITY_SHELL_SEMANTIC_BINDER__ = VERSION;

  const state = {
    phase: 'ready',
    detail: '',
    observer: null,
    scheduled: false
  };

  document.documentElement.dataset.continuitySemanticBinder = VERSION;

  const visible = (el) => !!el && !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);

  function isAuthSurface() {
    if (/\/auth(?:\/|$)/.test(location.pathname)) return true;
    const body = document.body?.innerText || '';
    return body.includes('Sign in to Open WebUI') && !!document.querySelector('input[type="password"]');
  }

  function promptNode() {
    const direct = document.querySelector(
      '[data-testid="message-input-container"], #message-input-container, .message-input-container'
    );
    if (direct) return direct;
    const ta = [...document.querySelectorAll('textarea')].find(visible);
    if (!ta) return null;
    let p = ta;
    for (let i = 0; i < 7 && p; i++, p = p.parentElement) {
      const rect = p.getBoundingClientRect();
      const buttons = p.querySelectorAll?.('button').length || 0;
      if (rect.width > 260 && rect.height >= 64 && rect.height < 280 && buttons >= 2) return p;
    }
    return ta.parentElement;
  }

  function sidebarNode() {
    const trigger = document.querySelector('#sidebar-new-chat-button, [data-testid="sidebar-new-chat-button"]');
    if (!trigger) return null;
    return trigger.closest('aside,nav,[data-testid*="sidebar"],.sidebar') || trigger.parentElement?.parentElement;
  }

  function appNode() {
    return document.querySelector('#app') || document.body;
  }

  function chatRoute() {
    return /^\/c\/[^/]+/.test(location.pathname);
  }

  function landingRoute() {
    if (isAuthSurface() || chatRoute()) return false;
    return !!promptNode() && (location.pathname === '/' || /^\/(?:new-chat)?$/.test(location.pathname));
  }

  function removeNode(id) {
    document.getElementById(id)?.remove();
  }

  function resolveShellVisualState(phase, detail) {
    const p = String(phase || 'ready').toLowerCase();
    const table = {
      ready:      { label: 'Ready',      orbState: 'idle',       active: false },
      idle:       { label: 'Ready',      orbState: 'idle',       active: false },
      listening:  { label: 'Listening',  orbState: 'listening',  active: true  },
      processing: { label: 'Thinking…',  orbState: 'processing', active: true  },
      thinking:   { label: 'Thinking…',  orbState: 'processing', active: true  },
      generating: { label: 'Responding', orbState: 'generating', active: true  },
      speaking:   { label: 'Speaking',   orbState: 'speaking',   active: true  },
      tool:       { label: 'Working',    orbState: 'tool',       active: true  },
      warning:    { label: 'Attention',  orbState: 'warning',    active: true  },
      error:      { label: 'Error',      orbState: 'error',      active: true  }
    };
    const v = table[p] || table.ready;
    return { ...v, detail: detail || '' };
  }

  function makeNeuralSvg(kind) {
    const ns='http://www.w3.org/2000/svg';
    const svg=document.createElementNS(ns,'svg');
    svg.setAttribute('viewBox','0 0 240 240');
    svg.setAttribute('aria-hidden','true');
    svg.classList.add(kind === 'hero' ? 'continuity-neural-svg' : 'continuity-telemetry-orb-svg');

    const defs=document.createElementNS(ns,'defs');
    defs.innerHTML =
      '<radialGradient id="csglow" cx="40%" cy="38%" r="72%">'+
      '<stop offset="0%" stop-color="#58c8ff" stop-opacity=".92"/>'+
      '<stop offset="52%" stop-color="#696cff" stop-opacity=".82"/>'+
      '<stop offset="100%" stop-color="#ef53da" stop-opacity=".86"/>'+
      '</radialGradient>';
    svg.appendChild(defs);

    if (kind !== 'hero') {
      const g=document.createElementNS(ns,'g');
      g.setAttribute('class','continuity-orb-ring');
      for(let i=0;i<30;i++){
        const a=(Math.PI*2*i)/30;
        const c=document.createElementNS(ns,'circle');
        const r=82;
        c.setAttribute('cx',String(120+Math.cos(a)*r));
        c.setAttribute('cy',String(120+Math.sin(a)*r));
        c.setAttribute('r',String(2.5+(i%5===0?1.2:0)));
        c.setAttribute('fill','url(#csglow)');
        c.setAttribute('opacity',String(.38+.58*(i/29)));
        g.appendChild(c);
      }
      svg.appendChild(g);
      return svg;
    }

    const pts=[];
    const n=44;
    for(let i=0;i<n;i++){
      const y=1-(i/(n-1))*2;
      const rr=Math.sqrt(Math.max(0,1-y*y));
      const theta=2.399963229728653*i;
      const x=Math.cos(theta)*rr;
      const z=Math.sin(theta)*rr;
      pts.push({x:120+x*82,y:120+y*82,z});
    }

    const lines=document.createElementNS(ns,'g');
    lines.setAttribute('class','continuity-neural-lines');
    for(let i=0;i<n;i++){
      const near=[];
      for(let j=i+1;j<n;j++){
        const dx=pts[i].x-pts[j].x, dy=pts[i].y-pts[j].y;
        const d=Math.hypot(dx,dy);
        if(d<58) near.push({j,d});
      }
      near.sort((a,b)=>a.d-b.d);
      for(const e of near.slice(0,3)){
        const l=document.createElementNS(ns,'line');
        l.setAttribute('x1',pts[i].x.toFixed(2));
        l.setAttribute('y1',pts[i].y.toFixed(2));
        l.setAttribute('x2',pts[e.j].x.toFixed(2));
        l.setAttribute('y2',pts[e.j].y.toFixed(2));
        l.setAttribute('stroke','url(#csglow)');
        l.setAttribute('stroke-width','1.2');
        l.setAttribute('opacity',String(.12+.20*((pts[i].z+1)/2)));
        lines.appendChild(l);
      }
    }
    svg.appendChild(lines);

    const nodes=document.createElementNS(ns,'g');
    nodes.setAttribute('class','continuity-neural-nodes');
    pts.forEach((p,i)=>{
      const c=document.createElementNS(ns,'circle');
      c.setAttribute('cx',p.x.toFixed(2));
      c.setAttribute('cy',p.y.toFixed(2));
      c.setAttribute('r',String(2.7 + ((i*7)%9)/3));
      c.setAttribute('fill','url(#csglow)');
      c.setAttribute('opacity',String(.64+.30*((p.z+1)/2)));
      nodes.appendChild(c);
    });
    svg.appendChild(nodes);
    return svg;
  }

  function bindPrompt() {
    const p = promptNode();
    if (!p) return null;
    p.classList.add('custom-shell-prompt','continuity-bound');
    p.dataset.continuityBinder = VERSION;
    return p;
  }

  function bindSidebar() {
    const s=sidebarNode();
    if (s) s.classList.add('custom-shell-sidebar','continuity-bound');
  }

  function supersedeLegacyOrb() {
    const selectors = [
      '#owui-thinking-orb-v1',
      '#owui-border-beam-v1',
      '#continuity-neural-sphere-wrap',
      '.continuity-neural-sphere-wrap'
    ];
    for (const sel of selectors) {
      document.querySelectorAll(sel).forEach(el => {
        if (el.id === HERO_ID || el.closest?.('#'+HERO_ID)) return;
        el.setAttribute(SUPERSEDED,'1');
      });
    }
  }

  function mountHero() {
    if (!landingRoute()) {
      removeNode(HERO_ID);
      removeNode(FOOTER_ID);
      appNode()?.classList.remove('custom-shell-landing');
      return;
    }

    const app=appNode();
    const prompt=bindPrompt();
    if (!app || !prompt) return;
    app.classList.add('custom-shell-landing');

    let hero=document.getElementById(HERO_ID);
    if(!hero){
      hero=document.createElement('section');
      hero.id=HERO_ID;
      hero.className='continuity-hero-owned';
      hero.setAttribute('aria-label','Continuity system ready');
      const aura=document.createElement('div');
      aura.className='hero-aura chat-landing-aura';
      const network=document.createElement('div');
      network.className='hero-network chat-landing-network';
      network.appendChild(makeNeuralSvg('hero'));
      const ready=document.createElement('div');
      ready.className='continuity-hero-ready';
      ready.textContent='READY';
      hero.append(aura,network,ready);
      document.body.appendChild(hero);
    }

    let footer=document.getElementById(FOOTER_ID);
    if(!footer){
      footer=document.createElement('div');
      footer.id=FOOTER_ID;
      footer.className='custom-shell-footer continuity-footer-owned';
      footer.textContent='Continuity Shell · Open WebUI · v0.11.3';
      document.body.appendChild(footer);
    }
    supersedeLegacyOrb();
  }

  function mountTelemetry() {
    if (!chatRoute() || isAuthSurface()) {
      removeNode(TELEMETRY_ID);
      return;
    }

    let el=document.getElementById(TELEMETRY_ID);
    if(!el){
      el=document.createElement('div');
      el.id=TELEMETRY_ID;
      el.className='chat-telemetry custom-shell-motion continuity-chat-telemetry-owned';
      el.setAttribute('role','status');
      el.setAttribute('aria-live','polite');
      el.dataset.lcarsLabel='COMPUTER CORE';

      const orb=document.createElement('span');
      orb.className='orb-slot';
      orb.appendChild(makeNeuralSvg('telemetry'));

      const copy=document.createElement('span');
      copy.className='copy';
      const strong=document.createElement('strong');
      strong.className='continuity-telemetry-label';
      const detail=document.createElement('span');
      detail.className='continuity-telemetry-detail';
      copy.append(strong,detail);

      const hidden=document.createElement('span');
      hidden.setAttribute('aria-hidden','true');
      el.append(orb,copy,hidden);
      document.body.appendChild(el);
    }

    renderState();
    supersedeLegacyOrb();
  }

  function renderState() {
    const v=resolveShellVisualState(state.phase,state.detail);
    const el=document.getElementById(TELEMETRY_ID);
    if(el){
      el.dataset.phase=state.phase;
      el.dataset.orbState=v.orbState;
      el.classList.toggle('is-active',v.active);
      const label=el.querySelector('.continuity-telemetry-label');
      const detail=el.querySelector('.continuity-telemetry-detail');
      if(label) label.textContent=v.label;
      if(detail) {
        detail.textContent=v.detail ? ' · '+v.detail : '';
        detail.hidden=!v.detail;
      }
    }
    const p=promptNode();
    p?.classList.toggle('shell-generating',['processing','thinking','generating','tool'].includes(String(state.phase).toLowerCase()));
  }

  function setState(phase,detail='') {
    state.phase=phase || 'ready';
    state.detail=detail || '';
    renderState();
  }

  function inferStateFromDom() {
    if (!chatRoute()) return;
    const stop=[...document.querySelectorAll('button')].find(b => {
      if(!visible(b)) return false;
      const a=(b.getAttribute('aria-label')||'').toLowerCase();
      const t=(b.textContent||'').trim().toLowerCase();
      return a.includes('stop') || t==='stop';
    });
    if(stop && !['speaking','listening'].includes(state.phase)) setState('generating');
    else if(!stop && ['generating','processing','thinking','tool'].includes(state.phase)) setState('ready');
  }

  function bindAll() {
    state.scheduled=false;
    if (isAuthSurface()) {
      removeNode(HERO_ID);
      removeNode(TELEMETRY_ID);
      removeNode(FOOTER_ID);
      return;
    }
    bindPrompt();
    bindSidebar();
    mountHero();
    mountTelemetry();
    inferStateFromDom();
  }

  function schedule() {
    if(state.scheduled) return;
    state.scheduled=true;
    requestAnimationFrame(bindAll);
  }

  function patchHistory() {
    for (const k of ['pushState','replaceState']) {
      const orig=history[k];
      if(typeof orig!=='function' || orig.__continuityWrapped) continue;
      const wrapped=function(...args){
        const ret=orig.apply(this,args);
        queueMicrotask(schedule);
        return ret;
      };
      wrapped.__continuityWrapped=true;
      history[k]=wrapped;
    }
    addEventListener('popstate',schedule);
  }

  addEventListener('continuity-shell:runtime-state',e=>{
    const d=e.detail||{};
    setState(d.state||d.phase||'ready',d.detail||'');
  });

  addEventListener('lcars:state',e=>{
    const d=e.detail||{};
    setState(d.state||'ready',d.detail||'');
  });

  addEventListener('owui:client-voice',e=>{
    const d=e.detail||{};
    if(d.speaking===true || d.state==='speaking') setState('speaking');
    else if(d.state==='listening') setState('listening');
    else if((d.speaking===false || d.state==='idle' || d.state==='ready') && ['speaking','listening'].includes(state.phase)) setState('ready');
  });

  function start() {
    if(document.getElementById(ROOT_ID)) return;

    const marker=document.createElement('meta');
    marker.id=ROOT_ID;
    marker.name='continuity-shell-semantic-binder';
    marker.content=VERSION;
    document.head.appendChild(marker);

    patchHistory();
    state.observer=new MutationObserver(schedule);
    const target=document.querySelector('#app') || document.body;
    if(target) state.observer.observe(target,{subtree:true,childList:true,attributes:true,attributeFilter:['class','aria-label','disabled']});
    bindAll();

    window.ContinuityShellSemanticBinder=Object.freeze({
      version:VERSION,
      status:()=>({phase:state.phase,detail:state.detail,path:location.pathname,hero:!!document.getElementById(HERO_ID),telemetry:!!document.getElementById(TELEMETRY_ID)}),
      setState,
      refresh:bindAll
    });

    dispatchEvent(new CustomEvent('continuity-shell:semantic-binder-ready',{detail:{version:VERSION}}));
  }

  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',start,{once:true});
  else start();
})();