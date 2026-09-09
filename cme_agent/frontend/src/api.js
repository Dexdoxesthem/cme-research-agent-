const BASE = import.meta.env.DEV ? '' : ''; // vite proxy handles /api in both modes

async function request(path, opts = {}) {
  const res = await fetch(`/api${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch (_) { /* noop */ }
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
  }
  return res.json();
}

export const api = {
  get: (path) => request(path),
  post: (path, body) => request(path, { method: 'POST', body: JSON.stringify(body) }),
};

export function fmt(x, d = 2) {
  if (x === null || x === undefined || Number.isNaN(Number(x))) return '—';
  return Number(x).toFixed(d);
}

export function fmtUsd(x, d = 0) {
  if (x === null || x === undefined) return '—';
  const s = Number(x).toLocaleString('en-US', { maximumFractionDigits: d, minimumFractionDigits: d });
  return Number(x) >= 0 ? `$${s}` : `-$${s.slice(1)}`;
}
