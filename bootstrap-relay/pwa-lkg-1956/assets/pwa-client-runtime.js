(() => {
  'use strict';

  const VERSION = '0.6.2';
  const SHELL_BUILD = '20260928.6';
  const SHELL_BUILD_KEY = 'owui-shell-build';
  const MANIFEST_URL = '/static/client-artifacts/manifest.json';
  const DB_NAME = 'owui-client-runtime';
  const DB_VERSION = 1;
  const OPFS_ROOT = 'owui-client';
  const OPFS_ARTIFACTS = 'artifacts';

  if (window.__OWUI_CLIENT_RUNTIME__) return;

  // iOS standalone can retain the root document indefinitely. Perform one bounded
  // reload only when a *new* build-addressed runtime reaches an older document.
  // Never clear caches/storage: the query-addressed shell is sufficient after reload.
  try {
    const previousBuild = localStorage.getItem(SHELL_BUILD_KEY);
    localStorage.setItem(SHELL_BUILD_KEY, SHELL_BUILD);
    const standalone = window.matchMedia?.('(display-mode: standalone)')?.matches || navigator.standalone === true;
    const guard = `owui-shell-reload:${SHELL_BUILD}`;
    if (standalone && previousBuild && previousBuild !== SHELL_BUILD && !sessionStorage.getItem(guard)) {
      sessionStorage.setItem(guard, '1');
      const u = new URL(location.href);
      u.searchParams.set('_shell', SHELL_BUILD);
      location.replace(u.href);
      return;
    }
  } catch {}

  let manifestCache = null;
  let dbPromise = null;

  const openDb = () => {
    if (dbPromise) return dbPromise;
    dbPromise = new Promise((resolve, reject) => {
      const req = indexedDB.open(DB_NAME, DB_VERSION);
      req.onupgradeneeded = () => {
        const db = req.result;
        if (!db.objectStoreNames.contains('artifacts')) {
          db.createObjectStore('artifacts', { keyPath: 'id' });
        }
        if (!db.objectStoreNames.contains('benchmarks')) {
          db.createObjectStore('benchmarks', { keyPath: 'key' });
        }
      };
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
    return dbPromise;
  };

  const dbGet = async (store, key) => {
    const db = await openDb();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(store, 'readonly');
      const req = tx.objectStore(store).get(key);
      req.onsuccess = () => resolve(req.result ?? null);
      req.onerror = () => reject(req.error);
    });
  };

  const dbPut = async (store, value) => {
    const db = await openDb();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(store, 'readwrite');
      tx.oncomplete = () => resolve(value);
      tx.onerror = () => reject(tx.error);
      tx.objectStore(store).put(value);
    });
  };

  const dbDelete = async (store, key) => {
    const db = await openDb();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(store, 'readwrite');
      tx.oncomplete = () => resolve(true);
      tx.onerror = () => reject(tx.error);
      tx.objectStore(store).delete(key);
    });
  };

  const manifest = async ({ force = false } = {}) => {
    if (manifestCache && !force) return manifestCache;
    const response = await fetch(MANIFEST_URL, {
      credentials: 'same-origin',
      cache: force ? 'no-store' : 'default'
    });
    if (!response.ok) throw new Error(`client manifest HTTP ${response.status}`);
    const data = await response.json();
    if (![1, 2].includes(data?.schema) || !Array.isArray(data?.artifacts)) {
      throw new Error('invalid client artifact manifest');
    }
    manifestCache = data;
    return data;
  };

  const opfsArtifacts = async () => {
    if (!navigator.storage?.getDirectory) {
      throw new Error('OPFS unavailable');
    }
    const root = await navigator.storage.getDirectory();
    const app = await root.getDirectoryHandle(OPFS_ROOT, { create: true });
    return app.getDirectoryHandle(OPFS_ARTIFACTS, { create: true });
  };

  const storageStatus = async () => {
    let estimate = {};
    let persisted = false;
    try { estimate = await navigator.storage?.estimate?.() ?? {}; } catch {}
    try { persisted = Boolean(await navigator.storage?.persisted?.()); } catch {}
    return {
      opfs: Boolean(navigator.storage?.getDirectory),
      persisted,
      usage: Number.isFinite(estimate.usage) ? estimate.usage : null,
      quota: Number.isFinite(estimate.quota) ? estimate.quota : null
    };
  };

  const persistStorage = async () => {
    try {
      if (await navigator.storage?.persisted?.()) return true;
      return Boolean(await navigator.storage?.persist?.());
    } catch {
      return false;
    }
  };

  const filenameFor = (artifact) => {
    const url = new URL(artifact.url, location.origin);
    return decodeURIComponent(url.pathname.split('/').pop());
  };

  const artifactById = async (id) => {
    const m = await manifest();
    const artifact = m.artifacts.find((item) => item.id === id);
    if (!artifact) throw new Error(`unknown client artifact: ${id}`);
    return artifact;
  };

  const fileExists = async (filename) => {
    try {
      const dir = await opfsArtifacts();
      const handle = await dir.getFileHandle(filename);
      return await handle.getFile();
    } catch {
      return null;
    }
  };

  // Incremental SHA-256 avoids an additional full-size ArrayBuffer for 100s MB models.
  const K = new Uint32Array([
    0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
    0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
    0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
    0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
    0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
    0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
    0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
    0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2
  ]);
  const rotr = (x, n) => (x >>> n) | (x << (32 - n));

  class Sha256 {
    constructor() {
      this.h = new Uint32Array([0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19]);
      this.buf = new Uint8Array(64);
      this.bufLen = 0;
      this.bytes = 0;
      this.w = new Uint32Array(64);
      this.done = false;
    }
    block(data, off = 0) {
      const w = this.w;
      for (let i = 0; i < 16; i++) {
        const j = off + i * 4;
        w[i] = ((data[j] << 24) | (data[j+1] << 16) | (data[j+2] << 8) | data[j+3]) >>> 0;
      }
      for (let i = 16; i < 64; i++) {
        const x=w[i-15], y=w[i-2];
        const s0=(rotr(x,7)^rotr(x,18)^(x>>>3))>>>0;
        const s1=(rotr(y,17)^rotr(y,19)^(y>>>10))>>>0;
        w[i]=(w[i-16]+s0+w[i-7]+s1)>>>0;
      }
      let [a,b,c,d,e,f,g,h] = this.h;
      for (let i=0;i<64;i++) {
        const s1=(rotr(e,6)^rotr(e,11)^rotr(e,25))>>>0;
        const ch=((e&f)^(~e&g))>>>0;
        const t1=(h+s1+ch+K[i]+w[i])>>>0;
        const s0=(rotr(a,2)^rotr(a,13)^rotr(a,22))>>>0;
        const maj=((a&b)^(a&c)^(b&c))>>>0;
        const t2=(s0+maj)>>>0;
        h=g; g=f; f=e; e=(d+t1)>>>0; d=c; c=b; b=a; a=(t1+t2)>>>0;
      }
      this.h[0]=(this.h[0]+a)>>>0; this.h[1]=(this.h[1]+b)>>>0;
      this.h[2]=(this.h[2]+c)>>>0; this.h[3]=(this.h[3]+d)>>>0;
      this.h[4]=(this.h[4]+e)>>>0; this.h[5]=(this.h[5]+f)>>>0;
      this.h[6]=(this.h[6]+g)>>>0; this.h[7]=(this.h[7]+h)>>>0;
    }
    update(input) {
      const data = input instanceof Uint8Array ? input : new Uint8Array(input);
      this.bytes += data.byteLength;
      let off = 0;
      if (this.bufLen) {
        const n = Math.min(64 - this.bufLen, data.length);
        this.buf.set(data.subarray(0,n), this.bufLen);
        this.bufLen += n; off += n;
        if (this.bufLen === 64) { this.block(this.buf); this.bufLen = 0; }
      }
      while (off + 64 <= data.length) { this.block(data, off); off += 64; }
      if (off < data.length) {
        this.buf.set(data.subarray(off), 0);
        this.bufLen = data.length - off;
      }
      return this;
    }
    hex() {
      if (this.done) throw new Error('hash already finalized');
      this.done = true;
      const hi = Math.floor(this.bytes / 0x20000000) >>> 0;
      const lo = (this.bytes * 8) >>> 0;
      this.buf[this.bufLen++] = 0x80;
      if (this.bufLen > 56) {
        this.buf.fill(0, this.bufLen, 64); this.block(this.buf); this.bufLen = 0;
      }
      this.buf.fill(0, this.bufLen, 56);
      this.buf[56]=hi>>>24; this.buf[57]=hi>>>16; this.buf[58]=hi>>>8; this.buf[59]=hi;
      this.buf[60]=lo>>>24; this.buf[61]=lo>>>16; this.buf[62]=lo>>>8; this.buf[63]=lo;
      this.block(this.buf);
      return [...this.h].map(v => v.toString(16).padStart(8,'0')).join('');
    }
  }

  const hashFile = async (file) => {
    const hash = new Sha256();
    const reader = file.stream().getReader();
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      hash.update(value);
    }
    return hash.hex();
  };

  const cachedMeta = async (id) => dbGet('artifacts', id);

  const ensureArtifact = async (id, {
    verify = true,
    onProgress = null,
    signal = undefined
  } = {}) => {
    const artifact = await artifactById(id);
    const filename = filenameFor(artifact);
    const existingMeta = await cachedMeta(id);
    const existingFile = await fileExists(filename);

    if (
      existingMeta &&
      existingFile &&
      existingFile.size === artifact.size &&
      existingMeta.sha256 === artifact.sha256 &&
      existingMeta.version === artifact.version
    ) {
      return { meta: existingMeta, file: existingFile, cached: true };
    }

    const response = await fetch(artifact.url, {
      credentials: 'same-origin',
      cache: 'force-cache',
      signal
    });
    if (!response.ok || !response.body) {
      throw new Error(`artifact ${id} HTTP ${response.status}`);
    }

    const dir = await opfsArtifacts();
    const handle = await dir.getFileHandle(filename, { create: true });
    const writable = await handle.createWritable();
    const reader = response.body.getReader();
    let written = 0;

    try {
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        await writable.write(value);
        written += value.byteLength;
        onProgress?.({ id, written, total: artifact.size });
      }
      await writable.close();
    } catch (error) {
      try { await writable.abort(); } catch {}
      try { await dir.removeEntry(filename); } catch {}
      throw error;
    }

    const file = await handle.getFile();
    if (file.size !== artifact.size) {
      try { await dir.removeEntry(filename); } catch {}
      throw new Error(`artifact ${id} size mismatch ${file.size} != ${artifact.size}`);
    }

    if (verify && artifact.sha256) {
      const digest = await hashFile(file);
      if (digest !== artifact.sha256) {
        try { await dir.removeEntry(filename); } catch {}
        throw new Error(`artifact ${id} SHA-256 mismatch`);
      }
    }

    const meta = {
      id,
      filename,
      family: artifact.family ?? null,
      role: artifact.role ?? null,
      precision: artifact.precision ?? null,
      version: artifact.version,
      size: artifact.size,
      sha256: artifact.sha256,
      verified: Boolean(verify && artifact.sha256),
      cachedAt: Date.now()
    };
    await dbPut('artifacts', meta);
    return { meta, file, cached: false };
  };

  const ensureGroup = async (name, options = {}) => {
    const m = await manifest();
    const group = m.groups?.[name];
    if (!group) throw new Error(`unknown artifact group: ${name}`);
    if (group.status !== 'ready' && !options.allowPartial) {
      throw new Error(`artifact group ${name} is ${group.status}`);
    }
    const results = [];
    for (const id of group.artifacts) {
      results.push(await ensureArtifact(id, options));
    }
    return results;
  };

  const removeArtifact = async (id) => {
    const meta = await cachedMeta(id);
    if (meta?.filename) {
      try {
        const dir = await opfsArtifacts();
        await dir.removeEntry(meta.filename);
      } catch {}
    }
    await dbDelete('artifacts', id);
    return true;
  };

  const webgpu = async () => {
    if (!navigator.gpu) return { available: false, shaderF16: false, features: [] };
    try {
      const adapter = await navigator.gpu.requestAdapter();
      if (!adapter) return { available: false, shaderF16: false, features: [] };
      const features = [...adapter.features].map(String);
      return {
        available: true,
        shaderF16: features.includes('shader-f16'),
        features,
        limits: {
          maxBufferSize: Number(adapter.limits?.maxBufferSize ?? 0),
          maxStorageBufferBindingSize: Number(adapter.limits?.maxStorageBufferBindingSize ?? 0)
        }
      };
    } catch {
      return { available: false, shaderF16: false, features: [] };
    }
  };

  const capabilities = async () => ({
    secureContext: isSecureContext,
    opfs: Boolean(navigator.storage?.getDirectory),
    webgpu: await webgpu(),
    storage: await storageStatus()
  });

  const saveBenchmark = async (entry) => dbPut('benchmarks', {
    ...entry,
    at: Date.now()
  });

  const getBenchmark = async (key) => dbGet('benchmarks', key);

  const RETIRED_RVC_ARTIFACT_IDS = [
    'cortana-rvc-encoder-flow-fp32',
    'cortana-rvc-decoder-fp32',
    'cortana-rvc-metadata',
    'cortana-hubert-fp16',
    'cortana-hubert-fp32',
    'cortana-fcpe-fp16',
    'cortana-fcpe-fp32'
  ];
  const RETIRED_RVC_FILENAMES = [
    'CortanaHALO3_fp32.enc.onnx',
    'CortanaHALO3_fp32.dec.onnx',
    'CortanaHALO3_fp32.json',
    'hubert_rvc_v2_fp16.onnx',
    'hubert_rvc_v2_fp32.onnx',
    'fcpe_fp16.onnx',
    'fcpe_fp32.onnx'
  ];

  const retireRvcClientArtifacts = async () => {
    for (const id of RETIRED_RVC_ARTIFACT_IDS) {
      try { await removeArtifact(id); } catch {}
    }
    try {
      const dir = await opfsArtifacts();
      for (const filename of RETIRED_RVC_FILENAMES) {
        try { await dir.removeEntry(filename); } catch {}
      }
    } catch {}
  };

  const api = {
    version: VERSION,
    manifest,
    capabilities,
    storage: {
      status: storageStatus,
      persist: persistStorage
    },
    artifacts: {
      getMeta: cachedMeta,
      ensure: ensureArtifact,
      ensureGroup,
      remove: removeArtifact
    },
    benchmarks: {
      get: getBenchmark,
      save: saveBenchmark
    },
    ahsoka: {
      prepare: (options = {}) => ensureGroup('ahsoka-model', options)
    }
  };

  window.__OWUI_CLIENT_RUNTIME__ = api;
  retireRvcClientArtifacts().catch(() => {});
  window.dispatchEvent(new CustomEvent('owui:client-runtime', {
    detail: { version: VERSION }
  }));
})();
