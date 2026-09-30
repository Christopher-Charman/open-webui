(() => {
  'use strict';
  const VERSION='20260930.5';
  if (window.__CONTINUITY_SHELL_LKG_MAPPER__) return;
  window.__CONTINUITY_SHELL_LKG_MAPPER__={version:VERSION,state:'booting'};

  const root=document.documentElement;

  function isAuthSurface(){
    const path=location.pathname || '/';
    if(path==='/auth' || path.startsWith('/auth/')) return true;
    const t=(document.body&&document.body.innerText)||'';
    return t.includes('Sign in to Open WebUI') && t.includes('Enter Your Password');
  }

  function themeId(){
    try { return window.ContinuityShell?.theme?.() || root.dataset.continuityTheme || ''; }
    catch(_) { return root.dataset.continuityTheme || ''; }
  }

  function syncTheme(){
    const auth=isAuthSurface();
    root.classList.toggle('continuity-shell-lkg',!auth);

    const wbw=!auth && themeId()==='wbw';
    if(wbw && !root.classList.contains('her')){
      root.classList.add('her');
      root.dataset.continuityShellManagedHer='1';
    } else if(!wbw && root.dataset.continuityShellManagedHer==='1'){
      root.classList.remove('her');
      delete root.dataset.continuityShellManagedHer;
    }
  }

  function commonAncestor(a,b){
    if(!a||!b) return null;
    const seen=new Set();
    for(let n=a;n;n=n.parentElement) seen.add(n);
    for(let n=b;n;n=n.parentElement) if(seen.has(n)) return n;
    return null;
  }

  function mapShellClasses(){
    if(isAuthSurface()) return;

    const composer=document.querySelector('#message-input-container');
    if(composer){
      composer.classList.add('custom-shell-prompt','custom-shell-controls');
    }

    const landing=document.querySelector('#owui-thinking-orb-v1[data-surface="landing"]');
    if(landing && composer){
      const lca=commonAncestor(landing,composer);
      if(lca) lca.classList.add('custom-shell-landing');
    }

    document.querySelectorAll('.continuity-neural-svg').forEach(el=>{
      el.classList.add('hero-network','chat-landing-network');
    });
    document.querySelectorAll('.continuity-neural-sphere-wrap').forEach(el=>{
      el.classList.add('hero-aura','chat-landing-aura');
    });

    const chatOrb=document.querySelector('#owui-thinking-orb-v1[data-surface="chat"]');
    if(chatOrb) chatOrb.classList.add('orb-slot');
  }

  function suppressLandingDetritus(){
    const landing=document.querySelector('#owui-thinking-orb-v1[data-surface="landing"]');
    const composer=document.querySelector('#message-input-container');
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
        if(pr.width<=160&&pr.height<=150&&pr.top>=lr.bottom-35&&pr.bottom<=cr.top+35){
          target=p;
        } else break;
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
      if(t==='Open WebUI · v0.11.3'){
        node.nodeValue='Continuity Shell · Open WebUI · v0.11.3';
        node.parentElement?.classList.add('custom-shell-footer');
      } else if(t==='Continuity Shell · Open WebUI · v0.11.3'){
        node.parentElement?.classList.add('custom-shell-footer');
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
      el.classList.add('custom-shell-top-control');
    });
  }

  function styleContinuityControl(){
    const host=document.getElementById('continuity-control-host');
    const sr=host?.shadowRoot;
    if(!sr||sr.getElementById('continuity-shell-lkg-shadow-style')) return;
    const st=document.createElement('style');
    st.id='continuity-shell-lkg-shadow-style';
    st.textContent=
      '.tab{border-color:rgba(128,220,255,.42)!important;background:rgba(4,11,23,.90)!important;color:rgba(214,240,255,.90)!important;box-shadow:0 8px 28px rgba(0,0,0,.38),0 0 18px rgba(115,216,255,.10)!important;backdrop-filter:blur(18px) saturate(1.3)!important}' +
      '.panel{border-color:rgba(128,220,255,.34)!important;background:linear-gradient(145deg,rgba(97,202,246,.055),transparent 31%),linear-gradient(320deg,rgba(223,106,60,.035),transparent 28%),rgba(4,11,23,.94)!important;color:rgba(242,248,255,.96)!important;box-shadow:0 20px 54px rgba(0,0,0,.42),0 0 24px rgba(115,216,255,.12),inset 0 1px 0 rgba(235,249,255,.06)!important;backdrop-filter:blur(20px) saturate(1.35)!important}' +
      '.panel h3,.status{color:rgba(171,197,224,.76)!important}' +
      'button.opt{border-color:rgba(143,218,248,.15)!important;background:rgba(106,192,228,.035)!important;color:rgba(242,248,255,.93)!important}' +
      'button.opt:hover{background:rgba(108,211,255,.11)!important;box-shadow:0 0 17px rgba(103,211,255,.11)!important}' +
      'button.opt[aria-pressed="true"]{background:linear-gradient(135deg,rgba(116,218,255,.19),rgba(223,106,60,.12))!important;border-color:rgba(133,222,255,.44)!important;box-shadow:inset 2px 0 0 rgba(119,219,255,.72),0 0 18px rgba(99,205,255,.10)!important}';
    sr.appendChild(st);
  }

  function apply(){
    syncTheme();
    if(isAuthSurface()){
      window.__CONTINUITY_SHELL_LKG_MAPPER__.state='auth-native';
      return;
    }
    mapShellClasses();
    suppressLandingDetritus();
    rewriteFooter();
    mapTopControls();
    styleContinuityControl();
    window.__CONTINUITY_SHELL_LKG_MAPPER__.state='ready';
  }

  let raf=0;
  const schedule=()=>{
    if(raf) return;
    raf=requestAnimationFrame(()=>{raf=0;apply();});
  };

  const mo=new MutationObserver(schedule);
  mo.observe(document.documentElement,{
    childList:true,subtree:true,characterData:true,attributes:true,
    attributeFilter:['data-surface','class','data-continuity-theme']
  });
  window.addEventListener('continuity-shell:theme',schedule);
  window.addEventListener('continuity-orb-beam:ready',schedule);
  window.addEventListener('popstate',schedule);
  window.addEventListener('resize',schedule,{passive:true});
  schedule();
})();