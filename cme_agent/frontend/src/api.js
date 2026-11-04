const BASE = import.meta.env.DEV ? '' : ''; // vite proxy handles /api in both modes

async function request(path, opts = {}) {
  const res = await fetch(`/api${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  });
  const text = await res.text();
  let data;
  try {
    data = JSON.parse(text);
  } catch (_) {
    if (!res.ok) {
      throw new Error(`API error (${res.status}): ${res.statusText}`);
    }
    throw new Error(`API returned non-JSON response (${res.status}). Verify API routing.`);
  }
  if (!res.ok) {
    const detail = data?.detail || res.statusText;
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
  }
  return data;
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
