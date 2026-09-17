// Mirrors backend/app/services/dates.py — kept intentionally tiny and dependency-free
// so the month-column headers render instantly without a round trip per cell.

export function ymParse(key: string): { y: number; m: number } {
  const [y, m] = key.split('-').map(Number);
  return { y, m };
}

export function ymAdd(key: string, n: number): string {
  const { y, m } = ymParse(key);
  const total = y * 12 + (m - 1) + n;
  const ny = Math.floor(total / 12);
  const nm = (total % 12) + 1;
  return `${String(ny).padStart(4, '0')}-${String(nm).padStart(2, '0')}`;
}

export function ymDiff(a: string, b: string): number {
  const A = ymParse(a), B = ymParse(b);
  return B.y * 12 + B.m - (A.y * 12 + A.m);
}

export function monthsBetween(start: string, end: string): string[] {
  const n = ymDiff(start, end);
  const out: string[] = [];
  for (let i = 0; i <= n && i < 600; i++) out.push(ymAdd(start, i));
  return out;
}

export function monthGroups(months: string[]): { year: number; months: string[] }[] {
  const groups: { year: number; months: string[] }[] = [];
  for (const k of months) {
    const { y } = ymParse(k);
    const last = groups[groups.length - 1];
    if (!last || last.year !== y) groups.push({ year: y, months: [k] });
    else last.months.push(k);
  }
  return groups;
}

export function monthShortLabel(key: string): string {
  const { m } = ymParse(key);
  return `Th${m}`;
}

export function curMonthKey(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
}
