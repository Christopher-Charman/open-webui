(() => {
  'use strict';

  const VERSION = '1.3.1';
  const VOICE_KEY_PREFIX = 'owui.client.voice';
  const PANEL_ID = 'owui-client-voice-panel';
  const EVENT_NAME = 'owui:client-voice';

  if (window.__OWUI_VOICE_ROUTER__) return;

  const synth = window.speechSynthesis ?? null;
  const providers = new Map();
  let generation = 0;
  let active = null;

  const validVoices = new Set(['ahsoka-pocket-hybrid-ep', 'ahsoka', 'cortana', 'majel-computer']);
  const SERVER_PREF_FIELD = 'client_voice';
  let userScope = 'anonymous';
  let preferenceTouched = false;
  let serverPreferenceLoaded = false;
  const voiceKey = () => `${VOICE_KEY_PREFIX}:${userScope}`;

  const state = {
    version: VERSION,
    voice: 'ahsoka-pocket-hybrid-ep',
    resolvedProvider: null,
    playbackUnlocked: false
  };

  const authHeaders = (extra = {}) => {
    const token = localStorage.getItem('token');
    return {
      ...extra,
      ...(token ? { Authorization: `Bearer ${token}` } : {})
    };
  };

  const tokenUserScope = () => {
    const token = localStorage.getItem('token');
    if (!token) return null;
    try {
      const part = token.split('.')[1];
      if (!part) return null;
      const normalized = part.replace(/-/g, '+').replace(/_/g, '/');
      const padded = normalized + '='.repeat((4 - normalized.length % 4) % 4);
      const payload = JSON.parse(atob(padded));
      return payload?.id ? String(payload.id) : null;
    } catch {
      return null;
    }
  };

  const resolveUserScope = async () => {
    const tokenScope = tokenUserScope();
    if (tokenScope) {
      userScope = tokenScope;
      return userScope;
    }

    try {
      const response = await fetch('/api/v1/auths/', {
        credentials: 'same-origin',
        cache: 'no-store',
        headers: authHeaders()
      });
      if (response.ok) {
        const user = await response.json();
        if (user?.id) userScope = String(user.id);
      }
    } catch {}

    return userScope;
  };

  const readServerPreference = async () => {
    try {
      const response = await fetch('/api/v1/users/user/settings?raw=true', {
        credentials: 'same-origin',
        cache: 'no-store',
        headers: authHeaders()
      });
      if (!response.ok) return null;
      const settings = await response.json();
      const preferred = settings?.[SERVER_PREF_FIELD]?.selected;
      if (validVoices.has(preferred)) {
        serverPreferenceLoaded = true;
        return preferred;
      }
    } catch {}
    return null;
  };

  const saveServerPreference = async (voice) => {
    try {
      const response = await fetch('/api/v1/users/user/settings/update', {
        method: 'POST',
        credentials: 'same-origin',
        cache: 'no-store',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({
          [SERVER_PREF_FIELD]: { selected: voice }
        })
      });
      if (!response.ok) return false;
      serverPreferenceLoaded = true;
      return true;
    } catch {
      return false;
    }
  };

  const loadScopedPreference = async ({ force = false } = {}) => {
    await resolveUserScope();

    const serverPreferred = await readServerPreference();
    const scoped = localStorage.getItem(voiceKey());
    const legacy = localStorage.getItem(VOICE_KEY_PREFIX);
    const preferred =
      serverPreferred ??
      (validVoices.has(scoped) ? scoped : null) ??
      (userScope === 'anonymous' && validVoices.has(legacy) ? legacy : null) ??
      'ahsoka-pocket-hybrid-ep';

    if (!preferenceTouched || force) {
      state.voice = preferred;
      state.resolvedProvider = null;
    }

    localStorage.setItem(voiceKey(), state.voice);
    if (legacy && userScope !== 'anonymous') {
      localStorage.removeItem(VOICE_KEY_PREFIX);
    }
    refreshPanel();
    warmSelectedVoice(state.voice).catch(() => {});
    return state.voice;
  };

  const emit = (type, detail = {}) => {
    window.dispatchEvent(new CustomEvent(EVENT_NAME, {
      detail: { type, ...detail, state: { ...state } }
    }));
  };

  const priorityForKind = (kind) => ({
    coreml: 500,
    webgpu: 400,
    wasm: 300,
    server: 100
  }[kind] ?? 0);

  const supported = async (record) => {
    const inCooldown = record.failUntil && Date.now() < record.failUntil;
    if (inCooldown && !record.meta.reprobeDuringCooldown) return false;
    try {
      if (typeof record.provider.supports !== 'function') return true;
      const ok = Boolean(await record.provider.supports());
      if (ok) record.failUntil = 0;
      return ok;
    } catch (error) {
      emit('provider-probe-error', { provider: record.name, error: String(error) });
      return false;
    }
  };

  const compatible = async (voice) => {
    const records = [...providers.values()]
      .filter((record) => record.meta.voice === voice)
      .sort((a, b) => b.meta.priority - a.meta.priority);

    const result = [];
    for (const record of records) {
      if (await supported(record)) result.push(record);
    }
    return result;
  };

  const api = {
    version: VERSION,
    state: () => ({ ...state }),
    providers: () => [...providers.values()].map((r) => ({
      name: r.name,
      ...r.meta
    })),
    registerProvider(name, provider, meta = {}) {
      if (!name || typeof provider?.speak !== 'function') {
        throw new TypeError('provider requires a name and speak()');
      }
      const voice = meta.voice;
      if (!validVoices.has(voice) || voice === 'apple') {
        throw new TypeError('provider voice must be a registered custom voice');
      }
      providers.set(name, {
        name,
        provider,
        failUntil: 0,
        meta: {
          voice,
          kind: meta.kind || name,
          priority: Number.isFinite(meta.priority)
            ? meta.priority
            : priorityForKind(meta.kind || name),
          local: meta.local !== false,
          reprobeDuringCooldown: meta.reprobeDuringCooldown === true
        }
      });
      emit('provider-registered', { name, voice });
      refreshPanel();
      return true;
    },
    unregisterProvider(name) {
      providers.delete(name);
      if (state.resolvedProvider === name) state.resolvedProvider = null;
      emit('provider-unregistered', { name });
      refreshPanel();
    },
    setVoice(voice) {
      if (!validVoices.has(voice)) return false;

      const scope = tokenUserScope();
      if (scope) userScope = scope;

      state.voice = voice;
      state.resolvedProvider = null;
      preferenceTouched = true;
      localStorage.setItem(voiceKey(), voice);

      for (const record of providers.values()) {
        if (record.meta.voice === voice) record.failUntil = 0;
      }

      saveServerPreference(voice).then((saved) => {
        emit('voice-preference-saved', {
          voice,
          server: Boolean(saved),
          scope: userScope
        });
      });

      emit('voice', { voice });
      warmSelectedVoice(voice).catch(() => {});
      refreshPanel();
      return true;
    },
    cancel() {
      synth?.cancel?.();
    },
    async diagnose() {
      const voices = {};
      for (const voice of ['ahsoka-pocket-hybrid-ep', 'ahsoka', 'cortana']) {
        voices[voice] = (await compatible(voice)).map((r) => ({
          name: r.name,
          ...r.meta
        }));
      }
      return {
        version: VERSION,
        voice: state.voice,
        speechSynthesis: Boolean(synth),
        standalone:
          window.matchMedia?.('(display-mode: standalone)').matches === true ||
          window.navigator.standalone === true,
        voices
      };
    }
  };

  api.status = () => ({ ...state });
  window.__OWUI_VOICE_ROUTER__ = api;
  window.OWUIClientVoice = api;

  let unlockAudio = null;
  const unlockPlayback = () => {
    if (state.playbackUnlocked) return;
    try {
      unlockAudio ||= new Audio('data:audio/wav;base64,UklGRigAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQQAAACAgICA');
      unlockAudio.volume = 1;
      const p = unlockAudio.play();
      if (p?.then) p.then(() => { state.playbackUnlocked = true; unlockAudio.pause(); }).catch(() => {});
    } catch {}
  };
  for (const event of ['pointerdown','touchend','click']) {
    document.addEventListener(event, unlockPlayback, { capture: true, passive: true });
  }

  const warmSelectedVoice = async (voice) => {
    if (!validVoices.has(voice)) return false;
    try {
      const response = await fetch('/api/v1/audio/local-voice/speech', {
        method: 'POST', credentials: 'same-origin', cache: 'no-store',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ input: 'Ready.', voice, speed: 1 })
      });
      if (!response.ok) return false;
      await response.blob();
      emit('voice-warmed', { voice });
      return true;
    } catch { return false; }
  };

  const splitForStreaming = (text, maxChars = 170) => {
    const parts = String(text || '')
      .match(/[^.!?]+[.!?]+|[^.!?]+$/g) || [String(text || '')];
    const chunks = [];

    for (const raw of parts) {
      let part = raw.trim();
      if (!part) continue;

      while (part.length > maxChars) {
        let cut = part.lastIndexOf(' ', maxChars);
        if (cut < Math.floor(maxChars * 0.6)) cut = maxChars;
        chunks.push(part.slice(0, cut).trim());
        part = part.slice(cut).trim();
      }

      if (!part) continue;
      const previous = chunks[chunks.length - 1];
      if (previous && previous.length + 1 + part.length <= maxChars) {
        chunks[chunks.length - 1] = `${previous} ${part}`;
      } else {
        chunks.push(part);
      }
    }

    return chunks.length ? chunks : [String(text || '')];
  };

  const makeServerProvider = (voice) => {
    let audio = null;
    let objectUrl = null;
    let statusCheckedAt = 0;
    let statusAvailable = false;

    const ensureAudio = () => {
      if (!audio) {
        audio = new Audio();
        audio.preload = 'auto';
      }
      return audio;
    };

    const cleanup = () => {
      if (audio) {
        try { audio.pause(); } catch {}
        try {
          audio.removeAttribute('src');
          audio.load();
        } catch {}
      }
      if (objectUrl) {
        try { URL.revokeObjectURL(objectUrl); } catch {}
        objectUrl = null;
      }
    };

    const requestChunk = async (text, rate, signal) => {
      const response = await fetch('/api/v1/audio/local-voice/speech', {
        method: 'POST',
        credentials: 'same-origin',
        signal,
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({
          input: text,
          voice,
          speed: Math.max(0.25, Math.min(4, Number(rate) || 1))
        })
      });

      if (!response.ok) {
        let message = `${voice} voice HTTP ${response.status}`;
        try {
          const body = await response.json();
          if (body?.detail) message = String(body.detail);
        } catch {}
        throw new Error(message);
      }

      return response.blob();
    };

    const playBlob = async (blob, volume, signal) => {
      cleanup();
      objectUrl = URL.createObjectURL(blob);
      const player = ensureAudio();
      player.src = objectUrl;
      player.volume = Math.max(0, Math.min(1, Number(volume) || 1));

      await new Promise((resolve, reject) => {
        let settled = false;
        const finish = (fn, value) => {
          if (settled) return;
          settled = true;
          signal?.removeEventListener('abort', abort);
          player.onended = null;
          player.onerror = null;
          cleanup();
          fn(value);
        };
        const abort = () =>
          finish(reject, new DOMException('Voice request cancelled', 'AbortError'));

        if (signal?.aborted) return abort();
        signal?.addEventListener('abort', abort, { once: true });

        player.onended = () => finish(resolve);
        player.onerror = () => finish(reject, new Error('audio playback failed'));

        const play = player.play();
        if (play?.catch) {
          play.catch((error) => finish(reject, error));
        }
      });
    };

    const probeStatus = async () => {
      const now = Date.now();
      if (statusAvailable && now - statusCheckedAt < 5000) return true;

      statusCheckedAt = now;
      try {
        const response = await fetch('/api/v1/audio/local-voice/status', {
          credentials: 'same-origin',
          cache: 'no-store',
          headers: authHeaders()
        });
        if (!response.ok) {
          statusAvailable = false;
          return false;
        }
        const data = await response.json();
        statusAvailable =
          data?.status === true &&
          data?.voices?.[voice] === true;
        return statusAvailable;
      } catch {
        statusAvailable = false;
        return false;
      }
    };

    return {
      supports: probeStatus,
      cancel: cleanup,
      async speak({ text, rate = 1, volume = 1, signal }) {
        cleanup();

        const chunks =
          voice === 'majel-computer'
            ? splitForStreaming(text, 48)
            : (voice === 'cortana' || voice.startsWith('ahsoka-pocket-'))
              ? splitForStreaming(text, 150)
              : splitForStreaming(text, 900);

        let pending = requestChunk(chunks[0], rate, signal);
        for (let i = 0; i < chunks.length; i++) {
          const blob = await pending;
          pending =
            i + 1 < chunks.length
              ? requestChunk(chunks[i + 1], rate, signal)
              : null;
          await playBlob(blob, volume, signal);
        }
      }
    };
  };

  const makeAhsokaLocalProvider = () => {
    let worker = null;
    let rpc = null;
    let initialized = null;
    let audio = null;
    let objectUrl = null;

    const cleanupAudio = () => {
      if (audio) {
        try { audio.pause(); } catch {}
        try {
          audio.removeAttribute('src');
          audio.load();
        } catch {}
      }
      if (objectUrl) {
        try { URL.revokeObjectURL(objectUrl); } catch {}
        objectUrl = null;
      }
    };

    const resetWorker = () => {
      if (worker) {
        try { worker.terminate(); } catch {}
      }
      worker = null;
      rpc = null;
      initialized = null;
    };

    const makeRpc = (instance) => {
      let nextId = 1;
      const pending = new Map();

      instance.onmessage = (event) => {
        const message = event.data || {};
        const slot = pending.get(message.id);
        if (!slot) return;
        pending.delete(message.id);
        clearTimeout(slot.timer);
        message.ok
          ? slot.resolve(message.result)
          : slot.reject(new Error(message.error || 'Piper worker error'));
      };

      instance.onerror = (event) => {
        const error = new Error(event.message || 'Piper worker failed');
        for (const slot of pending.values()) {
          clearTimeout(slot.timer);
          slot.reject(error);
        }
        pending.clear();
      };

      return (type, payload = {}, timeoutMs = 120000) =>
        new Promise((resolve, reject) => {
          const id = nextId++;
          const timer = setTimeout(() => {
            pending.delete(id);
            reject(new Error(`Piper worker timeout during ${type}`));
          }, timeoutMs);
          pending.set(id, { resolve, reject, timer });
          instance.postMessage({ id, type, payload });
        });
    };

    const runtimeReady = async () => {
      const runtime = window.__OWUI_CLIENT_RUNTIME__;
      if (!runtime?.artifacts?.getMeta || !runtime?.capabilities) return null;

      const [meta, caps] = await Promise.all([
        runtime.artifacts.getMeta('ahsoka-piper-model'),
        runtime.capabilities()
      ]);

      if (!meta?.verified || !caps?.opfs) return null;
      return { runtime, meta, caps };
    };

    const ensureWorker = async () => {
      const ready = await runtimeReady();
      if (!ready) throw new Error('Ahsoka local model is not cached');

      if (worker && initialized) return initialized;

      worker = new Worker(
        '/static/client-runtime/piper-core.worker.mjs?v=0.1.0',
        { type: 'module', name: 'owui-piper-ahsoka' }
      );
      rpc = makeRpc(worker);

      try {
        initialized = await rpc('init', {
          backend: ready.caps.webgpu?.available ? 'webgpu' : 'wasm',
          modelFilename: ready.meta.filename
        });
        emit('local-provider-ready', {
          voice: 'ahsoka',
          provider: 'client-ahsoka',
          backend: initialized.backend,
          loadMs: initialized.loadMs
        });
        return initialized;
      } catch (error) {
        resetWorker();
        throw error;
      }
    };

    const fetchPlan = async (text, rate, signal) => {
      const response = await fetch('/api/v1/audio/local-voice/phonemize', {
        method: 'POST',
        credentials: 'same-origin',
        cache: 'no-store',
        signal,
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({
          input: text,
          voice: 'ahsoka',
          speed: Math.max(0.25, Math.min(4, Number(rate) || 1))
        })
      });

      if (!response.ok) {
        let message = `Ahsoka phonemizer HTTP ${response.status}`;
        try {
          const body = await response.json();
          if (body?.detail) message = String(body.detail);
        } catch {}
        throw new Error(message);
      }
      return response.json();
    };

    const wavBlob = (samples, sampleRate) => {
      const audioData =
        samples instanceof Float32Array
          ? samples
          : new Float32Array(samples);
      const buffer = new ArrayBuffer(44 + audioData.length * 2);
      const view = new DataView(buffer);

      const writeText = (offset, value) => {
        for (let i = 0; i < value.length; i++) {
          view.setUint8(offset + i, value.charCodeAt(i));
        }
      };

      writeText(0, 'RIFF');
      view.setUint32(4, 36 + audioData.length * 2, true);
      writeText(8, 'WAVE');
      writeText(12, 'fmt ');
      view.setUint32(16, 16, true);
      view.setUint16(20, 1, true);
      view.setUint16(22, 1, true);
      view.setUint32(24, sampleRate, true);
      view.setUint32(28, sampleRate * 2, true);
      view.setUint16(32, 2, true);
      view.setUint16(34, 16, true);
      writeText(36, 'data');
      view.setUint32(40, audioData.length * 2, true);

      let offset = 44;
      for (let i = 0; i < audioData.length; i++, offset += 2) {
        const sample = Math.max(-1, Math.min(1, audioData[i]));
        view.setInt16(
          offset,
          sample < 0 ? Math.round(sample * 32768) : Math.round(sample * 32767),
          true
        );
      }

      return new Blob([buffer], { type: 'audio/wav' });
    };

    const playBlob = async (blob, volume, signal) => {
      cleanupAudio();
      if (!audio) {
        audio = new Audio();
        audio.preload = 'auto';
      }
      objectUrl = URL.createObjectURL(blob);
      audio.src = objectUrl;
      audio.volume = Math.max(0, Math.min(1, Number(volume) || 1));

      await new Promise((resolve, reject) => {
        let settled = false;
        const finish = (fn, value) => {
          if (settled) return;
          settled = true;
          signal?.removeEventListener('abort', abort);
          audio.onended = null;
          audio.onerror = null;
          cleanupAudio();
          fn(value);
        };
        const abort = () =>
          finish(reject, new DOMException('Voice request cancelled', 'AbortError'));

        if (signal?.aborted) return abort();
        signal?.addEventListener('abort', abort, { once: true });
        audio.onended = () => finish(resolve);
        audio.onerror = () => finish(reject, new Error('local Ahsoka playback failed'));

        const playing = audio.play();
        if (playing?.catch) playing.catch((error) => finish(reject, error));
      });
    };

    const synthPlan = async (plan) => {
      const init = await ensureWorker();
      const result = await rpc('synth', {
        groups: plan.groups,
        sampleRate: plan.sample_rate,
        scales: plan.scales,
        volume: plan.volume,
        edgeFade: plan.edge_fade
      });

      if (!result?.audio?.length) {
        throw new Error('local Ahsoka returned no audio');
      }

      let finite = true;
      let peak = 0;
      for (let i = 0; i < result.audio.length; i++) {
        const value = Number(result.audio[i]);
        if (!Number.isFinite(value)) {
          finite = false;
          break;
        }
        const abs = Math.abs(value);
        if (abs > peak) peak = abs;
      }

      return { init, result, finite, peak };
    };

    return {
      async supports() {
        return Boolean(await runtimeReady());
      },
      cancel() {
        cleanupAudio();
      },
      async canary() {
        const plan = await fetchPlan(
          'Systems online. Ahsoka local inference test.',
          1
        );
        const { init, result, finite, peak } = await synthPlan(plan);
        if (!finite) throw new Error('local Ahsoka canary returned non-finite audio');

        const runtime = window.__OWUI_CLIENT_RUNTIME__;
        await runtime?.benchmarks?.save?.({
          key: 'ahsoka-piper:' + (result.backend || init.backend),
          backend: result.backend || init.backend,
          model: 'ahsoka-final.onnx',
          coldMs: init.loadMs || 0,
          warmMs: result.synthMs || 0,
          ok: true,
          details: {
            samples: result.audio.length,
            sampleRate: result.sampleRate || plan.sample_rate,
            peak
          }
        });

        return {
          backend: result.backend || init.backend,
          loadMs: init.loadMs || 0,
          synthMs: result.synthMs || 0,
          samples: result.audio.length,
          sampleRate: result.sampleRate || plan.sample_rate,
          peak
        };
      },
      async speak({ text, rate = 1, volume = 1, signal }) {
        const plan = await fetchPlan(text, rate, signal);
        if (signal?.aborted) throw new DOMException('Voice request cancelled', 'AbortError');

        const { init, result, finite } = await synthPlan(plan);
        if (!finite) throw new Error('local Ahsoka returned non-finite audio');

        emit('local-synthesis', {
          voice: 'ahsoka',
          backend: result.backend || init.backend,
          synthMs: result.synthMs,
          samples: result.audio.length
        });

        await playBlob(
          wavBlob(result.audio, result.sampleRate || plan.sample_rate),
          volume,
          signal
        );
      }
    };
  };

  const ahsokaLocalProvider = makeAhsokaLocalProvider();

  // Production recovery 2026-09-26 (GPT-5.6 Sol):
  // client Ahsoka inference is intentionally not registered. Server Piper is
  // the known user-validated path; local inference returns to lab status.

  api.registerProvider(
    'server-ahsoka',
    makeServerProvider('ahsoka'),
    {
      voice: 'ahsoka',
      kind: 'server',
      priority: 100,
      local: false,
      reprobeDuringCooldown: true
    }
  );
  api.registerProvider(
    'server-ahsoka-pocket-hybrid-ep',
    makeServerProvider('ahsoka-pocket-hybrid-ep'),
    {
      voice: 'ahsoka-pocket-hybrid-ep',
      kind: 'server',
      priority: 100,
      local: false,
      reprobeDuringCooldown: true
    }
  );
  api.registerProvider(
    'server-cortana',
    makeServerProvider('cortana'),
    {
      voice: 'cortana',
      kind: 'server',
      priority: 100,
      local: false,
      reprobeDuringCooldown: true
    }
  );
  api.registerProvider(
    'server-majel-computer',
    makeServerProvider('majel-computer'),
    {
      voice: 'majel-computer',
      kind: 'server',
      priority: 100,
      local: false,
      reprobeDuringCooldown: true
    }
  );

  if (synth) {
    const nativeSpeak = synth.speak.bind(synth);
    const nativeCancel = synth.cancel.bind(synth);

    const finish = (utterance, token) => {
      if (token !== generation) return;
      active = null;
      emit('ended');
      try { utterance.dispatchEvent(new Event('end')); } catch {}
    };

    synth.speak = function routedSpeak(utterance) {
      const token = ++generation;
      const controller = new AbortController();

      Promise.resolve(compatible(state.voice)).then(async (records) => {
        if (token !== generation) return;

        for (const record of records) {
          if (controller.signal.aborted || token !== generation) return;

          state.resolvedProvider = record.name;
          active = { record, controller, token };
          emit('started', { provider: record.name, voice: state.voice });
          try { utterance.dispatchEvent(new Event('start')); } catch {}

          try {
            await record.provider.speak({
              text: utterance?.text ?? '',
              lang: utterance?.lang ?? '',
              rate: utterance?.rate ?? 1,
              pitch: utterance?.pitch ?? 1,
              volume: utterance?.volume ?? 1,
              signal: controller.signal
            });
            finish(utterance, token);
            return;
          } catch (error) {
            if (controller.signal.aborted || token !== generation) return;
            record.failUntil = Date.now() + 30000;
            emit('provider-error', {
              provider: record.name,
              voice: state.voice,
              error: String(error),
              retryAfterMs: 30000
            });
          }
        }

        if (token !== generation) return;
        state.resolvedProvider = null;
        active = null;
        emit('fallback', { voice: state.voice, to: 'apple' });
        nativeSpeak(utterance);
      });
    };

    synth.cancel = function routedCancel() {
      generation += 1;
      if (active) {
        try { active.controller.abort(); } catch {}
        try { active.record.provider.cancel?.(); } catch {}
        active = null;
      }
      nativeCancel();
      emit('cancelled');
    };
  }

  // Presentation panel migrated to Continuity Shell; this bridge owns voice execution/persistence only.

  const refreshIdentityPreference = () => {
    loadScopedPreference().catch(() => {});
  };

  const start = () => {
    observer.observe(document.documentElement, { childList: true, subtree: true });
    mountPanel();
    refreshIdentityPreference();

    setTimeout(refreshIdentityPreference, 750);
    setTimeout(refreshIdentityPreference, 2500);

    window.addEventListener('focus', refreshIdentityPreference);
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'visible') refreshIdentityPreference();
    });

    emit('ready');
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start, { once: true });
  } else {
    start();
  }
})();
