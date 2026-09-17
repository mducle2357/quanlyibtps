import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useMemo } from 'react';
import { api, apiErrorMessage, isConflictError } from '../lib/api';
import { useAuth } from '../lib/auth';
import { fmtNumber, fmtPercent } from '../lib/format';
import { allWeekKeysBetween, currentWeekKey, daysUntilFriday, weekGroups, weekKeyIndex } from '../lib/timeline';
import { useToast } from '../lib/toast';

interface WeeklyCell {
  volume: number | null;
  version: number | null;
  coupon: number | null;
  accrual: number | null;
}
interface WeeklyGridBondRow {
  bond_id: string;
  code: string;
  par_value: number;
  cells: Record<string, WeeklyCell>;
}
interface WeeklyGridResponse {
  weeks: string[];
  bonds: WeeklyGridBondRow[];
  totals: Record<string, number | null>;
  latest_week_with_data: string | null;
}
interface TimelineRange {
  start: string;
  end: string;
}

export default function WeeklyPage() {
  const toast = useToast();
  const qc = useQueryClient();
  const { hasRole } = useAuth();
  const canEdit = hasRole('Admin', 'Manager', 'Staff');

  const { data: timeline } = useQuery<TimelineRange>({
    queryKey: ['timeline', 'weekly'],
    queryFn: async () => (await api.get('/system/timeline/weekly')).data,
  });
  const weeks = useMemo(() => (timeline ? allWeekKeysBetween(timeline.start + '-W1', timeline.end + '-W5').filter((w) => w >= `${timeline.start}-W1`) : []), [timeline]);
  const groups = useMemo(() => weekGroups(weeks), [weeks]);

  const { data: grid, isLoading } = useQuery<WeeklyGridResponse>({
    queryKey: ['weekly-grid', timeline?.start, timeline?.end],
    queryFn: async () =>
      (await api.get('/weekly', { params: { start: `${timeline!.start}-W1`, end: weeks[weeks.length - 1] } })).data,
    enabled: !!timeline && weeks.length > 0,
  });

  const curWeek = currentWeekKey();
  const daysLeft = daysUntilFriday();

  async function saveCell(bondId: string, weekKey: string, cell: WeeklyCell | undefined, value: string) {
    const num = value.trim() === '' ? null : Number(value.replace(',', '.'));
    if (num === null || Number.isNaN(num)) return;
    try {
      await api.put(`/weekly/${weekKey}/bonds/${bondId}`, { volume: num, version: cell?.version ?? null });
      qc.invalidateQueries({ queryKey: ['weekly-grid'] });
    } catch (err) {
      if (isConflictError(err)) toast(apiErrorMessage(err), 'err');
      else toast(apiErrorMessage(err), 'err');
    }
  }

  async function carryForwardToCurrentWeek() {
    const idx = weeks.indexOf(curWeek);
    if (idx <= 0) {
      toast('Không có tuần liền trước trong khung thời gian để copy.', 'err');
      return;
    }
    const prevWeek = weeks[idx - 1];
    try {
      await api.post('/weekly/carry-forward', { from_week: prevWeek, to_week: curWeek });
      toast(`Đã copy khối lượng từ ${prevWeek} sang ${curWeek}`, 'ok');
      qc.invalidateQueries({ queryKey: ['weekly-grid'] });
    } catch (err) {
      toast(apiErrorMessage(err), 'err');
    }
  }

  return (
    <div>
      <div className={`reminder ${daysLeft === 0 ? 'due' : ''}`}>
        <div className="big">{daysLeft === 0 ? 'Đến ngày cập nhật danh mục tuần' : `Còn ${daysLeft} ngày`}</div>
        <div>đến ngày cập nhật danh mục tuần (deadline Thứ 6 hàng tuần)</div>
      </div>

      <div className="toolbar">
        <div className="hint">
          {grid?.latest_week_with_data ? `Latest updated: ${grid.latest_week_with_data}` : 'Chưa có dữ liệu tuần nào'}
        </div>
        <div className="spacer" />
        {canEdit && (
          <button className="btn" onClick={carryForwardToCurrentWeek}>
            Carry Forward Previous Week → {curWeek}
          </button>
        )}
      </div>

      <div className="panel">
        <header>
          <h2>Lãi coupon dự thu theo danh mục tuần</h2>
        </header>
        <div className="body flush">
          {isLoading ? (
            <div className="empty">Đang tải…</div>
          ) : !grid?.bonds.length ? (
            <div className="empty">Chưa có trái phiếu TPS đầu tư nào.</div>
          ) : (
            <div className="tblwrap">
              <table className="grid">
                <thead>
                  <tr className="r1">
                    <th className="s1" rowSpan={3}></th>
                    <th className="s2" rowSpan={3} style={{ textAlign: 'left' }}>
                      Trái phiếu
                    </th>
                    {groups.map((g) => (
                      <th key={g.month} colSpan={g.weeks.length}>
                        {g.year} · Th{Number(g.month.slice(5))}
                      </th>
                    ))}
                  </tr>
                  <tr className="r2">
                    {weeks.map((w) => (
                      <th key={w} className={w === curWeek ? 'cur' : ''}>
                        W{weekKeyIndex(w)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {grid.bonds.map((b, i) => (
                    <tr key={b.bond_id}>
                      <td className="s1">{i + 1}</td>
                      <td className="s2">{b.code}</td>
                      {weeks.map((w) => {
                        const cell = b.cells[w];
                        return (
                          <td key={w} className={w === curWeek ? 'cur' : ''} title={`Coupon: ${fmtPercent(cell?.coupon ?? null)}`}>
                            <input
                              className="cell"
                              defaultValue={cell?.volume === null || cell?.volume === undefined ? '' : String(cell.volume)}
                              disabled={!canEdit}
                              onBlur={(e) => {
                                const current = cell?.volume === null || cell?.volume === undefined ? '' : String(cell.volume);
                                if (e.target.value !== current) saveCell(b.bond_id, w, cell, e.target.value);
                              }}
                            />
                            <div className="hint" style={{ fontSize: 9, lineHeight: 1 }}>
                              {fmtPercent(cell?.coupon ?? null)}
                            </div>
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                  <tr className="total">
                    <td className="s1"></td>
                    <td className="s2">Lãi coupon dự thu — Tổng danh mục</td>
                    {weeks.map((w) => (
                      <td key={w} className="calc">
                        {fmtNumber(grid.totals[w], 2)}
                      </td>
                    ))}
                  </tr>
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
