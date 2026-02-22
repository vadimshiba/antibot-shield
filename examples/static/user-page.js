(async function () {
  const el = {
    chip: document.getElementById('chipText'),
    title: document.getElementById('titleText'),
    subtitle: document.getElementById('subtitleText'),
    status: document.getElementById('statusText'),
    stateLabel: document.getElementById('stateLabel'),
    stateText: document.getElementById('stateText'),
    requestLabel: document.getElementById('requestLabel'),
    requestId: document.getElementById('requestId'),
    fpLabel: document.getElementById('fpLabel'),
    fpHash: document.getElementById('fpHash'),
    resultPill: document.getElementById('resultPill'),
  };

  const I18N = {
    en: {
      chip: 'Session Security',
      title: 'Secure access is being validated',
      subtitle: 'We are running lightweight browser verification before granting access.',
      stPrepare: 'Preparing secure checks...',
      stRun: 'Running browser checks...',
      stFinalize: 'Finalizing verification...',
      stDone: 'Verification completed',
      stLimited: 'Verification completed with limits',
      stRetry: 'Unable to reach service, please retry',
      stateLabel: 'Session state',
      stateChecking: 'Checking environment...',
      stateVerified: 'Environment verified',
      requestLabel: 'session id',
      fpLabel: 'device fp',
      fpPending: 'pending...',
      fpUnavailable: 'unavailable',
      ridUnavailable: 'unavailable',
      statusInProgress: 'status: in progress',
      statusVerified: 'status: verified',
      statusLimited: 'status: limited',
      statusRetry: 'status: retry',
    },
    ru: {
      chip: 'Безопасность сессии',
      title: 'Проверяем безопасный доступ',
      subtitle: 'Выполняем быструю проверку браузера перед выдачей доступа.',
      stPrepare: 'Подготавливаем проверки...',
      stRun: 'Запускаем проверку браузера...',
      stFinalize: 'Завершаем валидацию...',
      stDone: 'Проверка завершена',
      stLimited: 'Проверка завершена с ограничениями',
      stRetry: 'Нет связи с сервисом, попробуйте ещё раз',
      stateLabel: 'Состояние сессии',
      stateChecking: 'Проверяем окружение...',
      stateVerified: 'Окружение подтверждено',
      requestLabel: 'id сессии',
      fpLabel: 'отпечаток устройства',
      fpPending: 'ожидание...',
      fpUnavailable: 'недоступно',
      ridUnavailable: 'недоступно',
      statusInProgress: 'статус: проверка',
      statusVerified: 'статус: подтверждено',
      statusLimited: 'статус: ограничено',
      statusRetry: 'статус: повтор',
    },
  };

  function pickLocale() {
    const candidates = [];
    if (Array.isArray(navigator.languages)) candidates.push(...navigator.languages);
    if (navigator.language) candidates.push(navigator.language);
    if (document.documentElement.lang) candidates.push(document.documentElement.lang);

    for (const code of candidates) {
      const norm = String(code || '').toLowerCase().trim();
      if (!norm) continue;
      if (norm.startsWith('ru')) return 'ru';
      if (norm.startsWith('en')) return 'en';
    }
    return 'en';
  }

  const locale = pickLocale();
  const t = I18N[locale] || I18N.en;
  document.documentElement.lang = locale;

  function applyStaticText() {
    el.chip.textContent = t.chip;
    el.title.textContent = t.title;
    el.subtitle.textContent = t.subtitle;
    el.status.textContent = t.stPrepare;
    el.stateLabel.textContent = t.stateLabel;
    el.stateText.textContent = t.stateChecking;
    el.requestLabel.textContent = t.requestLabel;
    el.requestId.textContent = t.fpPending;
    el.fpLabel.textContent = t.fpLabel;
    el.fpHash.textContent = t.fpPending;
    el.resultPill.textContent = t.statusInProgress;
    el.resultPill.className = 'mini-state';
  }

  function shortHash(v) {
    if (!v) return t.fpUnavailable;
    return `${v.slice(0, 12)}...${v.slice(-8)}`;
  }

  async function sha256Hex(text) {
    const data = new TextEncoder().encode(text);
    const hash = await crypto.subtle.digest('SHA-256', data);
    return Array.from(new Uint8Array(hash)).map((b) => b.toString(16).padStart(2, '0')).join('');
  }

  async function canvasHash() {
    try {
      const canvas = document.createElement('canvas');
      canvas.width = 220;
      canvas.height = 70;
      const ctx = canvas.getContext('2d');
      ctx.fillStyle = '#123';
      ctx.fillRect(0, 0, 220, 70);
      ctx.fillStyle = '#5ef';
      ctx.font = '16px Arial';
      ctx.fillText('antibot-user-page', 8, 22);
      return await sha256Hex(canvas.toDataURL());
    } catch (_) {
      return '';
    }
  }

  applyStaticText();

  const signals = {
    userAgent: navigator.userAgent || '',
    language: navigator.language || '',
    languages: Array.isArray(navigator.languages) ? navigator.languages : [],
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || '',
    hardwareConcurrency: Number(navigator.hardwareConcurrency || 0),
    deviceMemory: Number(navigator.deviceMemory || 0),
    cookieEnabled: navigator.cookieEnabled === true,
    webdriver: navigator.webdriver === true,
    pluginsCount: navigator.plugins ? navigator.plugins.length : 0,
    maxTouchPoints: Number(navigator.maxTouchPoints || 0),
    screen: `${screen.width}x${screen.height}x${screen.colorDepth}`,
    platform: navigator.platform || '',
    hasWebCrypto: !!(window.crypto && window.crypto.subtle),
    hasChromeObj: !!window.chrome,
  };

  el.status.textContent = t.stRun;
  signals.canvasHash = await canvasHash();

  let integrity = 100;
  if (!signals.cookieEnabled) integrity -= 15;
  if (signals.webdriver) integrity -= 40;
  if (!signals.hasWebCrypto) integrity -= 20;
  if (!signals.timezone) integrity -= 8;
  if ((signals.pluginsCount || 0) === 0) integrity -= 8;
  if (!signals.hardwareConcurrency) integrity -= 8;
  if (!signals.canvasHash) integrity -= 10;
  if (/headless|selenium|playwright/i.test(signals.userAgent)) integrity -= 25;
  integrity = Math.max(0, integrity);

  el.status.textContent = t.stFinalize;
  const fpRaw = JSON.stringify(signals);
  const fpHash = await sha256Hex(fpRaw);
  el.fpHash.textContent = shortHash(fpHash);
  el.stateText.textContent = t.stateVerified;

  try {
    const health = await fetch('/health', { headers: { 'x-device-fp': fpHash } });
    const rid = health.headers.get('x-request-id') || t.ridUnavailable;
    el.requestId.textContent = rid;

    if (integrity >= 80) {
      el.resultPill.textContent = t.statusVerified;
      el.resultPill.className = 'mini-state ok';
      el.status.textContent = t.stDone;
    } else {
      el.resultPill.textContent = t.statusLimited;
      el.resultPill.className = 'mini-state warn';
      el.status.textContent = t.stLimited;
    }
  } catch (_) {
    el.requestId.textContent = t.ridUnavailable;
    el.resultPill.textContent = t.statusRetry;
    el.resultPill.className = 'mini-state warn';
    el.status.textContent = t.stRetry;
  }
})();
