(async function() {
  const cfg = window.__ABS_CHALLENGE__ || {};
  const nonce = cfg.nonce || '';
  const parsedDifficulty = Number(cfg.difficulty || 3);
  const baseDifficulty = Number.isFinite(parsedDifficulty) && parsedDifficulty > 0 ? Math.floor(parsedDifficulty) : 3;
  const parsedRounds = Number(cfg.pow_rounds || 1);
  const powRounds = Number.isFinite(parsedRounds) && parsedRounds > 0 ? Math.floor(parsedRounds) : 1;
  const nextUrl = cfg.next_url || '/';
  const endpoint = cfg.verify_endpoint || '/_abs/verify';
  const requestId = cfg.request_id || '';
  const preferredLocale = (cfg.preferred_locale || '').toLowerCase();

  const el = {
    badge: document.getElementById('badgeText'),
    pulse: document.getElementById('pulseText'),
    title: document.getElementById('titleText'),
    subtitle: document.getElementById('subtitleText'),
    status: document.getElementById('statusText'),
    footnote: document.getElementById('footnoteText'),
    retry: document.getElementById('retryBtn'),
    requestId: document.getElementById('requestIdText'),
    fpHash: document.getElementById('fpHashText'),
    stageHint: document.getElementById('stageHintText'),
    powInfo: document.getElementById('powInfoText'),
  };

  const FALLBACK = {
    badge: 'Secure Access',
    pulse: 'Checking',
    title: 'Please wait',
    subtitle: 'Verification in progress.',
    footnote: 'If the page does not continue, refresh and retry.',
    retry: 'Retry',
    stPreparing: 'Preparing...',
    stCollecting: 'Collecting...',
    stRunning: 'Verifying...',
    stSubmitting: 'Submitting...',
    stDone: 'Done. Redirecting...',
    stFailed: 'Verification failed. Retry.',
  };

  const STAGE_CLASSES = [
    'stage-preparing',
    'stage-collecting',
    'stage-running',
    'stage-submitting',
    'stage-done',
    'stage-failed',
  ];

  function localeCandidates() {
    const out = [];
    const push = (v) => {
      const n = String(v || '').toLowerCase().trim();
      if (!n) return;
      if (!out.includes(n)) out.push(n);
      const short = n.split('-')[0];
      if (short && !out.includes(short)) out.push(short);
    };

    if (preferredLocale) push(preferredLocale);
    if (Array.isArray(navigator.languages) && navigator.languages.length) {
      navigator.languages.forEach(push);
    } else {
      push(navigator.language || '');
    }
    push(document.documentElement.lang || '');
    push('en');
    return out;
  }

  async function loadLocale() {
    let base = { ...FALLBACK };
    try {
      const enRes = await fetch('/_abs/i18n/en.json', { cache: 'force-cache' });
      if (enRes.ok) base = { ...base, ...(await enRes.json()) };
    } catch (_) {
      // fallback remains
    }

    for (const code of localeCandidates()) {
      try {
        const res = await fetch(`/_abs/i18n/${encodeURIComponent(code)}.json`, { cache: 'force-cache' });
        if (res.ok) {
          return { ...base, ...(await res.json()), __locale: code };
        }
      } catch (_) {
        // next candidate
      }
    }

    return { ...base, __locale: 'en' };
  }

  function shortHash(v) {
    if (!v) return 'pending...';
    return `${v.slice(0, 12)}...${v.slice(-8)}`;
  }

  function swapText(node, text) {
    if (!node || !text) return;
    if (node.textContent === text) return;
    node.classList.add('text-flash');
    setTimeout(() => {
      node.textContent = text;
      node.classList.remove('text-flash');
    }, 120);
  }

  function setStage(stage) {
    document.body.classList.remove(...STAGE_CLASSES);
    document.body.classList.add(`stage-${stage}`);
  }

  function applyLocale(t) {
    if (el.badge) el.badge.textContent = t.badge;
    if (el.pulse) el.pulse.textContent = t.pulse;
    if (el.title) el.title.textContent = t.title;
    if (el.subtitle) el.subtitle.textContent = t.subtitle;
    if (el.footnote) el.footnote.textContent = t.footnote;
    if (el.retry) el.retry.textContent = t.retry;
    if (el.status) el.status.textContent = t.stPreparing;
    if (el.stageHint) el.stageHint.textContent = 'Initializing challenge pipeline...';
    if (el.powInfo) el.powInfo.textContent = `round 0/${powRounds} · 0 ms`;
  }

  function setStatus(text) {
    if (text && el.status) swapText(el.status, text);
  }

  function setPulse(text, stateClass) {
    if (!el.pulse || !text) return;
    el.pulse.textContent = text;
    el.pulse.classList.remove('ok', 'warn');
    if (stateClass) el.pulse.classList.add(stateClass);
  }

  function setHint(text) {
    if (text && el.stageHint) swapText(el.stageHint, text);
  }

  function setPowInfo(round, total, elapsedMs) {
    if (!el.powInfo) return;
    el.powInfo.textContent = `round ${round}/${total} · ${elapsedMs} ms`;
  }

  function initMotionField() {
    const root = document.documentElement;
    let tx = 0;
    let ty = 0;
    let cx = 0;
    let cy = 0;
    let rafId = 0;

    function step() {
      const now = performance.now();
      const driftX = Math.sin(now / 2400) * 1.6;
      const driftY = Math.cos(now / 2900) * 1.2;
      cx += (tx - cx) * 0.09;
      cy += (ty - cy) * 0.09;

      const x = cx + driftX;
      const y = cy + driftY;
      root.style.setProperty('--mx', `${x.toFixed(2)}px`);
      root.style.setProperty('--my', `${y.toFixed(2)}px`);
      root.style.setProperty('--orb-shift-x', `${(x * 1.55).toFixed(2)}px`);
      root.style.setProperty('--orb-shift-y', `${(y * 1.55).toFixed(2)}px`);
      rafId = requestAnimationFrame(step);
    }

    function onMove(ev) {
      const w = window.innerWidth || 1;
      const h = window.innerHeight || 1;
      const nx = (ev.clientX / w) * 2 - 1;
      const ny = (ev.clientY / h) * 2 - 1;
      tx = nx * 11;
      ty = ny * 9;
    }

    window.addEventListener('mousemove', onMove, { passive: true });
    window.addEventListener('mouseleave', () => {
      tx = 0;
      ty = 0;
    }, { passive: true });
    step();

    return () => {
      window.removeEventListener('mousemove', onMove);
      if (rafId) cancelAnimationFrame(rafId);
    };
  }

  async function sha256Hex(s) {
    const data = new TextEncoder().encode(s);
    const hash = await crypto.subtle.digest('SHA-256', data);
    return Array.from(new Uint8Array(hash)).map((b) => b.toString(16).padStart(2, '0')).join('');
  }

  function detectAutomationArtifacts() {
    const markers = ['_phantom', '__nightmare', 'callPhantom', 'webdriver'];
    let hits = 0;
    for (const m of markers) {
      if (m in window || m in navigator) hits += 1;
    }
    if (/HeadlessChrome|PhantomJS|Playwright|Selenium/i.test(navigator.userAgent || '')) hits += 2;
    return hits;
  }

  async function canvasHash() {
    try {
      const c = document.createElement('canvas');
      c.width = 320;
      c.height = 100;
      const x = c.getContext('2d');
      x.textBaseline = 'top';
      x.font = '17px Arial';
      x.fillStyle = '#f60';
      x.fillRect(12, 10, 160, 40);
      x.fillStyle = '#069';
      x.fillText('abs-canvas-fp-v2', 14, 14);
      x.strokeStyle = '#5ef';
      x.arc(210, 45, 22, 0, Math.PI * 2);
      x.stroke();
      return await sha256Hex(c.toDataURL());
    } catch (_) {
      return '';
    }
  }

  async function webglHash() {
    try {
      const c = document.createElement('canvas');
      const gl = c.getContext('webgl') || c.getContext('experimental-webgl');
      if (!gl) return '';
      const dbg = gl.getExtension('WEBGL_debug_renderer_info');
      const vendor = dbg ? gl.getParameter(dbg.UNMASKED_VENDOR_WEBGL) : 'unknown-vendor';
      const renderer = dbg ? gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL) : 'unknown-renderer';
      return await sha256Hex(`${vendor}|${renderer}|${gl.getParameter(gl.VERSION)}`);
    } catch (_) {
      return '';
    }
  }

  async function audioHash() {
    try {
      const Ctx = window.OfflineAudioContext || window.webkitOfflineAudioContext;
      if (!Ctx) return '';
      const ctx = new Ctx(1, 44100, 44100);
      const osc = ctx.createOscillator();
      const comp = ctx.createDynamicsCompressor();
      osc.type = 'triangle';
      osc.frequency.value = 10000;
      comp.threshold.value = -50;
      comp.knee.value = 40;
      comp.ratio.value = 12;
      comp.attack.value = 0;
      comp.release.value = 0.25;
      osc.connect(comp);
      comp.connect(ctx.destination);
      osc.start(0);
      const buffer = await ctx.startRendering();
      const data = buffer.getChannelData(0);
      let sum = 0;
      for (let i = 0; i < data.length; i += 97) sum += Math.abs(data[i]);
      return await sha256Hex(sum.toFixed(10));
    } catch (_) {
      return '';
    }
  }

  async function eventLoopJitter() {
    const samples = [];
    let last = performance.now();
    for (let i = 0; i < 6; i += 1) {
      await new Promise((r) => setTimeout(r, 30));
      const now = performance.now();
      samples.push(now - last);
      last = now;
    }
    const avg = samples.reduce((a, b) => a + b, 0) / samples.length;
    const variance = samples.reduce((a, b) => a + Math.pow(b - avg, 2), 0) / samples.length;
    return Number(Math.sqrt(variance).toFixed(3));
  }

  async function notificationsPermission() {
    try {
      if (!navigator.permissions || !navigator.permissions.query) return 'unknown';
      const p = await navigator.permissions.query({ name: 'notifications' });
      return p && p.state ? p.state : 'unknown';
    } catch (_) {
      return 'unknown';
    }
  }

  async function collectSignals() {
    const [canvas, webgl, audio, jitter, perm] = await Promise.all([
      canvasHash(),
      webglHash(),
      audioHash(),
      eventLoopJitter(),
      notificationsPermission(),
    ]);

    return {
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || '',
      language: navigator.language || '',
      languages: Array.isArray(navigator.languages) ? navigator.languages : [],
      hardware_concurrency: Number(navigator.hardwareConcurrency || 0),
      device_memory: Number(navigator.deviceMemory || 0),
      platform: navigator.platform || '',
      ua: navigator.userAgent || '',
      webdriver: navigator.webdriver === true,
      plugins_count: navigator.plugins ? navigator.plugins.length : 0,
      max_touch_points: Number(navigator.maxTouchPoints || 0),
      has_chrome_object: !!window.chrome,
      has_webcrypto: !!(window.crypto && window.crypto.subtle),
      screen: `${screen.width}x${screen.height}x${screen.colorDepth}`,
      canvas_hash: canvas,
      webgl_hash: webgl,
      audio_hash: audio,
      event_loop_jitter_ms: jitter,
      permission_notifications: perm,
      automation_artifacts: detectAutomationArtifacts(),
      locale_resolved: (navigator.language || '').toLowerCase(),
      timezone_offset_min: new Date().getTimezoneOffset(),
      color_scheme: window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light',
      reduced_motion: window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches,
    };
  }

  function estimateRisk(s) {
    let risk = 0;
    if (s.webdriver) risk += 65;
    if (!s.has_webcrypto) risk += 20;
    if (!s.timezone) risk += 12;
    if (!Array.isArray(s.languages) || s.languages.length === 0) risk += 10;
    if (!s.canvas_hash) risk += 15;
    if (!s.webgl_hash) risk += 12;
    if (!s.audio_hash) risk += 8;
    if ((s.automation_artifacts || 0) >= 2) risk += 40;
    if ((s.plugins_count || 0) === 0 && !/iphone|ipad|android/i.test((s.platform || '').toLowerCase())) risk += 10;
    if ((s.hardware_concurrency || 0) <= 0 || (s.hardware_concurrency || 0) > 128) risk += 12;
    if ((s.device_memory || 0) < 0 || (s.device_memory || 0) > 128) risk += 8;
    if ((s.event_loop_jitter_ms || 0) < 0.05) risk += 8;
    if (/headless|selenium|playwright|phantom/i.test((s.ua || '').toLowerCase())) risk += 55;
    return Math.max(0, Math.min(100, risk));
  }

  const t = await loadLocale();
  const localeShort = String(t.__locale || 'en').toLowerCase().split('-')[0];
  const stageHints = localeShort === 'ru'
    ? {
      prep: 'Инициализируем контур проверки...',
      collectA: 'Снимаем безопасные сигналы среды...',
      collectB: 'Проверяем консистентность браузера...',
      runA: 'Запускаем вычислительный раунд...',
      runB: 'Сопоставляем цифровой след...',
      runC: 'Усложняем задачу для автоматизации...',
      submit: 'Проверяем подпись и отправляем результат...',
      done: 'Доступ подтвержден, готовим переход...',
      failed: 'Сигнал проверки нестабилен, попробуйте снова.',
    }
    : {
      prep: 'Initializing challenge pipeline...',
      collectA: 'Sampling trusted browser signals...',
      collectB: 'Cross-checking runtime consistency...',
      runA: 'Running compute round...',
      runB: 'Matching secure device trace...',
      runC: 'Raising cost for automated traffic...',
      submit: 'Signing and submitting verification payload...',
      done: 'Access validated, preparing redirect...',
      failed: 'Verification signal unstable, please retry.',
    };

  if (['ar', 'he', 'fa'].includes((t.__locale || '').split('-')[0])) {
    document.documentElement.dir = 'rtl';
  }
  applyLocale(t);
  setStage('preparing');
  setHint(stageHints.prep);

  const reducedMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (!reducedMotion) initMotionField();

  if (el.requestId) el.requestId.textContent = requestId || 'pending...';
  if (el.fpHash) el.fpHash.textContent = 'pending...';

  if (el.retry) {
    el.retry.addEventListener('click', () => location.reload());
  }

  let hintTicker = null;

  try {
    setStage('collecting');
    setPulse(t.pulse, null);
    setStatus(t.stCollecting);
    setHint(stageHints.collectA);
    setTimeout(() => setHint(stageHints.collectB), 520);

    const signals = await collectSignals();
    const fpRaw = JSON.stringify(signals);
    const fpHash = await sha256Hex(fpRaw);
    if (el.fpHash) el.fpHash.textContent = shortHash(fpHash);

    const localRisk = estimateRisk(signals);
    const targetDifficulty = Math.max(1, baseDifficulty);

    setStage('running');
    setStatus(t.stRunning);
    setHint(stageHints.runA);
    const prefix = '0'.repeat(targetDifficulty);
    const counters = [];
    const powStartedAt = performance.now();
    const runtimeHints = [stageHints.runA, stageHints.runB, stageHints.runC];
    let hintIndex = 0;
    hintTicker = setInterval(() => {
      hintIndex = (hintIndex + 1) % runtimeHints.length;
      setHint(runtimeHints[hintIndex]);
    }, 980);

    for (let round = 0; round < powRounds; round += 1) {
      let counter = 0;
      while (true) {
        const digest = await sha256Hex(`${nonce}:${round}:${fpHash}:${counter}`);
        if (digest.startsWith(prefix)) break;
        counter += 1;
        if (counter % 320 === 0) {
          setStatus(`${t.stRunning} (${round + 1}/${powRounds})`);
          setPulse(`${round + 1}/${powRounds}`, null);
          setPowInfo(round + 1, powRounds, Math.round(performance.now() - powStartedAt));
        }
        if (counter > 1800000) throw new Error('pow_limit');
      }
      counters.push(counter);
      setStatus(`${t.stRunning} (${round + 1}/${powRounds})`);
      setPulse(`${round + 1}/${powRounds}`, null);
      setPowInfo(round + 1, powRounds, Math.round(performance.now() - powStartedAt));
    }

    const powElapsedMs = Math.round(performance.now() - powStartedAt);
    if (hintTicker) clearInterval(hintTicker);

    setStage('submitting');
    setStatus(t.stSubmitting);
    setHint(stageHints.submit);
    setPowInfo(powRounds, powRounds, powElapsedMs);
    const res = await fetch(endpoint, {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        'x-request-id': requestId,
      },
      body: JSON.stringify({
        nonce,
        counters,
        fp_hash: fpHash,
        fp_raw: fpRaw,
        signals,
        next: nextUrl,
        request_id: requestId,
        local_risk: localRisk,
        local_difficulty: targetDifficulty,
        pow_rounds: powRounds,
        pow_elapsed_ms: powElapsedMs,
      }),
    });

    if (!res.ok) throw new Error('verify_failed');

    setStage('done');
    setPulse(t.stDone, 'ok');
    setStatus(t.stDone);
    setHint(stageHints.done);
    setTimeout(() => location.assign(nextUrl), 240);
  } catch (_) {
    if (hintTicker) clearInterval(hintTicker);
    setStage('failed');
    setPulse(t.retry, 'warn');
    setStatus(t.stFailed);
    setHint(stageHints.failed);
    if (el.retry) el.retry.classList.remove('hidden');
  }
})();
