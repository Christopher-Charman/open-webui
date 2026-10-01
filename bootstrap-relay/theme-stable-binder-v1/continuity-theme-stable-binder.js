(() => {
  'use strict';

  const VERSION = '20261001.1';
  if (window.__CONTINUITY_THEME_STABLE_BINDER__) return;
  const runtime = window.__CONTINUITY_THEME_STABLE_BINDER__ = {
    version: VERSION,
    state: 'booting',
    surface: 'none'
  };

  const LEGACY_PARITY_CLASSES = [
    'continuity-parity-hide',
    'continuity-parity-round-control',
    'continuity-parity-footer'
  ];

  function isAuthSurface() {
    return /^\/auth(?:\/|$)/.test(location.pathname);
  }

  function cleanupLegacyParityClasses() {
    document.querySelectorAll(
      '.continuity-parity-hide,.continuity-parity-round-control,.continuity-parity-footer'
    ).forEach((el) => el.classList.remove(...LEGACY_PARITY_CLASSES));
  }

  function syncAuthBoundary() {
    const auth = isAuthSurface();
    document.documentElement.classList.toggle('continuity-auth-native', auth);
    const controls = document.getElementById('continuity-control-host');
    if (controls) controls.style.display = auth ? 'none' : '';
    return auth;
  }

  function bindComposer() {
    const composer = document.getElementById('message-input-container');
    if (!composer) return;
    composer.classList.add('custom-shell-prompt', 'custom-shell-controls');
  }

  function restoreLandingOwnedDom(landing) {
    landing.classList.remove('continuity-chat-standalone', 'orb-slot');
    landing.querySelectorAll('.continuity-neural-hero,.continuity-neural-hero *').forEach((el) => {
      if (el.style.display === 'none') el.style.removeProperty('display');
    });
  }

  function bindLanding(landing, chatPane) {
    restoreLandingOwnedDom(landing);
    if (chatPane) chatPane.classList.add('custom-shell-landing');

    landing.querySelectorAll('.continuity-neural-svg').forEach((el) => {
      el.classList.add('hero-network', 'chat-landing-network');
    });
    landing.querySelectorAll('.continuity-neural-sphere-wrap').forEach((el) => {
      el.classList.add('hero-aura', 'chat-landing-aura');
    });
  }

  function collapseChatTelemetry(chatOrb) {
    chatOrb.classList.add('continuity-chat-standalone', 'orb-slot');

    chatOrb.querySelectorAll('.hero-network,.chat-landing-network').forEach((el) => {
      el.classList.remove('hero-network', 'chat-landing-network');
    });
    chatOrb.querySelectorAll('.hero-aura,.chat-landing-aura').forEach((el) => {
      el.classList.remove('hero-aura', 'chat-landing-aura');
    });

    const canvas = chatOrb.querySelector('canvas');
    if (!canvas) return;

    let keep = canvas;
    while (keep.parentElement && keep.parentElement !== chatOrb) keep = keep.parentElement;

    Array.from(chatOrb.children).forEach((child) => {
      if (child === keep || child.contains(canvas)) {
        child.style.display = '';
        child.querySelectorAll('*').forEach((el) => {
          if (el === canvas || el.contains(canvas)) {
            if (el !== canvas) el.style.display = '';
          } else {
            el.style.display = 'none';
          }
        });
      } else {
        child.style.display = 'none';
      }
    });
  }

  function apply() {
    cleanupLegacyParityClasses();

    const chatPane = document.getElementById('chat-pane');
    if (syncAuthBoundary()) {
      if (chatPane) chatPane.classList.remove('custom-shell-landing');
      runtime.state = 'auth-native';
      runtime.surface = 'auth';
      return;
    }

    bindComposer();

    const landing = document.querySelector('#owui-thinking-orb-v1[data-surface="landing"]');
    const chatOrb = document.querySelector('#owui-thinking-orb-v1[data-surface="chat"]');

    if (landing) {
      bindLanding(landing, chatPane);
      runtime.surface = 'landing';
    } else {
      if (chatPane) chatPane.classList.remove('custom-shell-landing');
      if (chatOrb) {
        collapseChatTelemetry(chatOrb);
        runtime.surface = 'chat';
      } else {
        runtime.surface = 'none';
      }
    }

    runtime.state = 'ready';
  }

  let raf = 0;
  function schedule() {
    if (raf) return;
    raf = requestAnimationFrame(() => {
      raf = 0;
      apply();
    });
  }

  const observer = new MutationObserver(schedule);
  observer.observe(document.documentElement, {
    childList: true,
    subtree: true,
    attributes: true,
    attributeFilter: ['data-surface']
  });

  window.addEventListener('popstate', schedule);
  window.addEventListener('continuity-postmount:ready', schedule);
  window.addEventListener('continuity-orb-beam:ready', schedule);
  schedule();
})();
