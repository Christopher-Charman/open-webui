(() => {
  'use strict';

  const VERSION='20260930.2';
  if(window.__CONTINUITY_SHELL_SEMANTIC_BINDER__) return;
  window.__CONTINUITY_SHELL_SEMANTIC_BINDER__={version:VERSION,state:'booting'};

  const root=document.documentElement;

  function isAuthSurface(){
    if(/^\/auth(?:\/|$)/.test(location.pathname)) return true;
    const body=(document.body&&document.body.innerText)||'';
    return /Sign in to Open WebUI/i.test(body) && !!document.querySelector('input[type="password"]');
  }

  function promptNode(){
    const direct=document.querySelector(
      '#message-input-container,[data-testid="message-input-container"],.message-input-container'
    );
    if(direct) return direct;
    const ta=[...document.querySelectorAll('textarea')].find(el=>el.offsetWidth||el.offsetHeight||el.getClientRects().length);
    if(!ta) return null;
    let p=ta;
    for(let i=0;i<7&&p;i++,p=p.parentElement){
      const r=p.getBoundingClientRect();
      const buttons=p.querySelectorAll?.('button').length||0;
      if(r.width>260&&r.height>=64&&r.height<300&&buttons>=2) return p;
    }
    return ta.parentElement;
  }

  function commonAncestor(a,b){
    if(!a||!b) return null;
    const seen=new Set();
    for(let n=a;n;n=n.parentElement) seen.add(n);
    for(let n=b;n;n=n.parentElement) if(seen.has(n)) return n;
    return null;
  }

  function mapPrompt(){
    const p=promptNode();
    if(!p) return null;
    p.classList.add('custom-shell-prompt','custom-shell-controls','continuity-semantic-bound');
    p.dataset.continuitySemanticBinder=VERSION;
    return p;
  }

  function mapLanding(){
    const composer=mapPrompt();
    const landing=document.querySelector('#owui-thinking-orb-v1[data-surface="landing"]');
    if(!landing||!composer) return false;

    const lca=commonAncestor(landing,composer);
    if(lca) lca.classList.add('custom-shell-landing','continuity-semantic-bound');

    document.querySelectorAll('.continuity-neural-svg').forEach(el=>{
      el.classList.add('hero-network','chat-landing-network');
    });
    document.querySelectorAll('.continuity-neural-sphere-wrap').forEach(el=>{
      el.classList.add('hero-aura','chat-landing-aura');
    });

    return true;
  }

  function mapChat(){
    mapPrompt();
    const chatOrb=document.querySelector('#owui-thinking-orb-v1[data-surface="chat"]');
    if(chatOrb) chatOrb.classList.add('orb-slot','continuity-semantic-bound');
  }

  function mapSidebar(){
    const trigger=document.querySelector('#sidebar-new-chat-button,[data-testid="sidebar-new-chat-button"]');
    if(!trigger) return;
    const side=trigger.closest('aside,nav,[data-testid*="sidebar"],.sidebar')||trigger.parentElement?.parentElement;
    side?.classList.add('custom-shell-sidebar','continuity-semantic-bound');
  }

  function suppressLandingDetritus(){
    const landing=document.querySelector('#owui-thinking-orb-v1[data-surface="landing"]');
    const composer=promptNode();
    if(!landing||!composer) return;

    const lr=landing.getBoundingClientRect();
    const cr=composer.getBoundingClientRect();
    const cx=(cr.left+cr.right)/2;

    document.querySelectorAll('img,svg,canvas,[role="img"]').forEach(el=>{
      if(landing.contains(el)||composer.contains(el)) return;
      if(el.closest('#continuity-control-host')) return;
      const r=el.getBoundingClientRect();
      if(!r.width||!r.height) return;
      if(r.width<22||r.height<22||r.width>110||r.height>110) return;
      if(r.top<lr.bottom-24||r.bottom>cr.top+24) return;
      if(Math.abs((r.left+r.right)/2-cx)>150) return;

      let target=el;
      for(let i=0,p=el.parentElement;i<3&&p;i++,p=p.parentElement){
        const pr=p.getBoundingClientRect();
        if(pr.width<=160&&pr.height<=150&&pr.top>=lr.bottom-35&&pr.bottom<=cr.top+35) target=p;
        else break;
      }
      target.classList.add('continuity-shell-hide-landing-detritus');
    });
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
        node.parentElement?.classList.add('custom-shell-footer','continuity-semantic-bound');
      } else if(/^Continuity Shell\s*·\s*Open WebUI\s*·\s*v0\.11\.3$/i.test(t)){
        node.parentElement?.classList.add('custom-shell-footer','continuity-semantic-bound');
      }
    }
  }

  function mapTopControls(){
    if(!document.querySelector('#owui-thinking-orb-v1[data-surface="landing"]')) return;
    const w=innerWidth,h=innerHeight;
    document.querySelectorAll('button,a,[role="button"]').forEach(el=>{
      if(el.closest('#message-input-container')||el.closest('#continuity-control-host')) return;
      const r=el.getBoundingClientRect();
      if(r.width<28||r.height<28||r.width>96||r.height>96) return;
      if(r.top<18||r.top>Math.min(285,h*.30)) return;
      if(!(r.left<160||r.right>w-160)) return;
      if((el.textContent||'').trim().length>8 && !el.querySelector('svg,img')) return;
      el.classList.add('custom-shell-top-control','continuity-semantic-bound');
    });
  }

  function apply(){
    if(isAuthSurface()){
      root.classList.remove('continuity-shell-semantic-active');
      window.__CONTINUITY_SHELL_SEMANTIC_BINDER__.state='auth-native';
      return;
    }

    root.classList.add('continuity-shell-semantic-active');
    const landing=mapLanding();
    if(!landing) mapChat();
    mapSidebar();
    if(landing){
      suppressLandingDetritus();
      rewriteFooter();
      mapTopControls();
    }

    window.__CONTINUITY_SHELL_SEMANTIC_BINDER__.state=landing?'landing-mapped':'chat-mapped';
  }

  let raf=0;
  function schedule(){
    if(raf) return;
    raf=requestAnimationFrame(()=>{raf=0;apply();});
  }

  const observer=new MutationObserver(schedule);
  observer.observe(document.documentElement,{
    childList:true,
    subtree:true,
    characterData:true,
    attributes:true,
    attributeFilter:['data-surface','class','data-continuity-theme']
  });

  addEventListener('popstate',schedule);
  addEventListener('resize',schedule,{passive:true});
  addEventListener('continuity-orb-beam:ready',schedule);
  addEventListener('continuity-shell:theme',schedule);

  schedule();

  window.ContinuityShellSemanticBinder=Object.freeze({
    version:VERSION,
    refresh:apply,
    status:()=>({
      state:window.__CONTINUITY_SHELL_SEMANTIC_BINDER__.state,
      path:location.pathname,
      landing:!!document.querySelector('#owui-thinking-orb-v1[data-surface="landing"]'),
      chat:!!document.querySelector('#owui-thinking-orb-v1[data-surface="chat"]')
    })
  });
})();