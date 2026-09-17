// Vietnamese display conventions (prompt §7): 1.234.567,89 / 12,50% / dd/mm/yyyy.
// Never render NaN/undefined — every formatter below falls back to an en-dash.

export function fmtNumber(v: number | null | undefined, dec = 0): string {
  if (v === null || v === undefined || Number.isNaN(v) || !Number.isFinite(v)) return '–';
  if (v === 0) return '-';
  return v.toLocaleString('vi-VN', { minimumFractionDigits: dec, maximumFractionDigits: dec });
}

export function fmtPercent(v: number | null | undefined, dec = 2): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return '–';
  return v.toLocaleString('vi-VN', { minimumFractionDigits: dec, maximumFractionDigits: dec }) + '%';
}

export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return '–';
  const d = new Date(iso + (iso.length === 10 ? 'T00:00:00' : ''));
  if (Number.isNaN(d.getTime())) return '–';
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${pad(d.getDate())}/${pad(d.getMonth() + 1)}/${d.getFullYear()}`;
}

export function parseVNNumber(s: string): number | null {
  if (s === null || s === undefined) return null;
  let t = String(s).trim().replace(/\s/g, '').replace(/%/g, '');
  if (t === '' || t === '-' || t === '–') return null;
  const neg = /^\(.*\)$/.test(t);
  if (neg) t = t.slice(1, -1);
  const hasComma = t.includes(','), hasDot = t.includes('.');
  if (hasComma && hasDot) t = t.replace(/\./g, '').replace(',', '.');
  else if (hasComma) t = t.replace(',', '.');
  else if (hasDot) {
    const parts = t.split('.');
    const allThousand = parts.slice(1).every((p) => p.length === 3);
    if (parts.length > 2 || (allThousand && parts[0].length <= 3 && parts[1]?.length === 3)) t = parts.join('');
  }
  t = t.replace(/[^0-9.-]/g, '');
  const n = parseFloat(t);
  if (!Number.isFinite(n)) return null;
  return neg ? -n : n;
}

const ROMAN: [number, string][] = [
  [1000, 'M'], [900, 'CM'], [500, 'D'], [400, 'CD'], [100, 'C'], [90, 'XC'],
  [50, 'L'], [40, 'XL'], [10, 'X'], [9, 'IX'], [5, 'V'], [4, 'IV'], [1, 'I'],
];
export function toRoman(n: number): string {
  let out = '';
  let rem = n;
  for (const [v, s] of ROMAN) {
    while (rem >= v) {
      out += s;
      rem -= v;
    }
  }
  return out || String(n);
}

export function monthKeyLabel(key: string): string {
  const [, m] = key.split('-');
  return `Th${Number(m)}`;
}
