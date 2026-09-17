import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useMemo, useState } from 'react';
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import Modal from '../components/Modal';
import { api, apiErrorMessage, isConflictError } from '../lib/api';
import { useAuth } from '../lib/auth';
import { fmtPercent } from '../lib/format';
import { monthGroups, monthShortLabel, monthsBetween } from '../lib/timeline';
import { useToast } from '../lib/toast';

interface MonthlyCell {
  rate: number;
  version: number;
}
interface ReferenceRate {
  id: string;
  name: string;
  rate_type: 'manual' | 'calculated';
  calc_method: string | null;
  component_ids: string[];
  monthly_values: Record<string, MonthlyCell>;
  version: number;
}
interface TimelineRange {
  start: string;
  end: string;
}

const SERIES_COLORS = ['#1b4f8a', '#c47b00', '#0a7d46', '#8e44ad', '#c02b2b', '#0a8ea0', '#5d6d7e', '#b8860b'];

export default function ControlPage() {
  const toast = useToast();
  const qc = useQueryClient();
  const { hasRole } = useAuth();
  const canEdit = hasRole('Admin', 'Manager', 'Staff');
  const canDelete = hasRole('Admin', 'Manager');

  const { data: timeline } = useQuery<TimelineRange>({
    queryKey: ['timeline', 'monthly'],
    queryFn: async () => (await api.get('/system/timeline/monthly')).data,
  });
  const { data: rates, isLoading } = useQuery<ReferenceRate[]>({
    queryKey: ['reference-rates'],
    queryFn: async () => (await api.get('/reference-rates')).data,
  });
  const { data: resolved } = useQuery<Record<string, Record<string, number | null>>>({
    queryKey: ['reference-rates-resolved', timeline?.start, timeline?.end],
    queryFn: async () =>
      (await api.get('/reference-rates/resolved', { params: { start: timeline!.start, end: timeline!.end } })).data,
    enabled: !!timeline,
  });

  const months = useMemo(() => (timeline ? monthsBetween(timeline.start, timeline.end) : []), [timeline]);
  const groups = useMemo(() => monthGroups(months), [months]);

  const [showAdd, setShowAdd] = useState(false);
  const [hidden, setHidden] = useState<Record<string, boolean>>({});

  async function saveCell(rate: ReferenceRate, monthKey: string, value: string) {
    const num = value.trim() === '' ? null : Number(value.replace(',', '.'));
    if (num === null || Number.isNaN(num)) return;
    const cell = rate.monthly_values[monthKey];
    try {
      await api.put(`/reference-rates/${rate.id}/monthly/${monthKey}`, {
        rate: num,
        version: cell?.version ?? null,
      });
      qc.invalidateQueries({ queryKey: ['reference-rates'] });
      qc.invalidateQueries({ queryKey: ['reference-rates-resolved'] });
    } catch (err) {
      if (isConflictError(err)) {
        toast('Dữ liệu đã được thay đổi bởi người dùng khác. Vui lòng tải lại.', 'err');
        qc.invalidateQueries({ queryKey: ['reference-rates'] });
      } else {
        toast(apiErrorMessage(err), 'err');
      }
    }
  }

  async function deleteRate(rate: ReferenceRate) {
    if (!window.confirm(`Xóa benchmark "${rate.name}"? Thao tác này không thể hoàn tác.`)) return;
    try {
      await api.delete(`/reference-rates/${rate.id}`);
      toast('Đã xóa benchmark', 'ok');
      qc.invalidateQueries({ queryKey: ['reference-rates'] });
    } catch (err) {
      toast(apiErrorMessage(err), 'err');
    }
  }

  const chartData = months.map((m) => {
    const row: Record<string, string | number | null> = { month: monthShortLabel(m) + '/' + m.slice(2, 4) };
    rates?.forEach((r) => {
      row[r.name] = resolved?.[r.id]?.[m] ?? null;
    });
    return row;
  });

  return (
    <div>
      <div className="toolbar">
        <div className="hint">GROUP A: Single Rate (nhập tay) · GROUP B: Calculated Rate (tính từ benchmark khác)</div>
        <div className="spacer" />
        {canEdit && (
          <button className="btn primary" onClick={() => setShowAdd(true)}>
            + Add Reference Rate
          </button>
        )}
      </div>

      <div className="panel">
        <header>
          <h2>Biểu đồ lãi suất tham chiếu</h2>
        </header>
        <div className="body">
          {chartData.length > 0 && rates && rates.length > 0 ? (
            <div className="chartbox">
              <ResponsiveContainer width="100%" height={280}>
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e9edf2" />
                  <XAxis dataKey="month" tick={{ fontSize: 10 }} />
                  <YAxis tick={{ fontSize: 10 }} unit="%" />
                  <Tooltip formatter={(v) => fmtPercent(typeof v === 'number' ? v : Number(v))} />
                  <Legend
                    onClick={(e) => setHidden((h) => ({ ...h, [e.dataKey as string]: !h[e.dataKey as string] }))}
                  />
                  {rates.map((r, i) => (
                    <Line
                      key={r.id}
                      dataKey={r.name}
                      stroke={SERIES_COLORS[i % SERIES_COLORS.length]}
                      dot={false}
                      hide={hidden[r.name]}
                      connectNulls
                    />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="empty">Chưa có dữ liệu benchmark để vẽ biểu đồ.</div>
          )}
        </div>
      </div>

      <div className="panel">
        <header>
          <h2>Bảng lãi suất tham chiếu theo tháng</h2>
        </header>
        <div className="body flush">
          {isLoading ? (
            <div className="empty">Đang tải…</div>
          ) : !rates?.length ? (
            <div className="empty">Chưa có benchmark nào. Bấm "+ Add Reference Rate" để tạo mới.</div>
          ) : (
            <div className="tblwrap">
              <table className="grid">
                <thead>
                  <tr className="r1">
                    <th className="s1" rowSpan={2}></th>
                    <th className="s2" rowSpan={2} style={{ textAlign: 'left' }}>
                      Benchmark
                    </th>
                    {groups.map((g) => (
                      <th key={g.year} colSpan={g.months.length}>
                        {g.year}
                      </th>
                    ))}
                  </tr>
                  <tr className="r2">
                    {months.map((m) => (
                      <th key={m}>{monthShortLabel(m)}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rates.map((r, i) => (
                    <tr key={r.id}>
                      <td className="s1">{i + 1}</td>
                      <td className="s2">
                        {r.name}{' '}
                        <span className={`tag ${r.rate_type === 'manual' ? 'ongoing' : 'pre'}`} style={{ marginLeft: 4 }}>
                          {r.rate_type === 'manual' ? 'A' : 'B'}
                        </span>
                        {canDelete && (
                          <button className="btn sm" style={{ marginLeft: 6 }} onClick={() => deleteRate(r)}>
                            ×
                          </button>
                        )}
                      </td>
                      {months.map((m) => {
                        if (r.rate_type === 'calculated') {
                          const v = resolved?.[r.id]?.[m];
                          return (
                            <td key={m} className="calc">
                              {v === null || v === undefined ? '–' : fmtPercent(v)}
                            </td>
                          );
                        }
                        const cell = r.monthly_values[m];
                        return (
                          <td key={m} className={cell ? '' : 'missing'} title={cell ? '' : 'Chưa cập nhật lãi suất tham chiếu'}>
                            <input
                              className="cell"
                              defaultValue={cell ? String(cell.rate) : ''}
                              disabled={!canEdit}
                              onBlur={(e) => {
                                if (e.target.value !== (cell ? String(cell.rate) : '')) saveCell(r, m, e.target.value);
                              }}
                            />
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {showAdd && <AddRateModal rates={rates ?? []} onClose={() => setShowAdd(false)} />}
    </div>
  );
}

function AddRateModal({ rates, onClose }: { rates: ReferenceRate[]; onClose: () => void }) {
  const toast = useToast();
  const qc = useQueryClient();
  const [name, setName] = useState('');
  const [rateType, setRateType] = useState<'manual' | 'calculated'>('manual');
  const [calcMethod, setCalcMethod] = useState('average');
  const [componentIds, setComponentIds] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      await api.post('/reference-rates', {
        name,
        rate_type: rateType,
        calc_method: rateType === 'calculated' ? calcMethod : null,
        component_ids: rateType === 'calculated' ? componentIds : [],
      });
      toast('Đã tạo benchmark', 'ok');
      qc.invalidateQueries({ queryKey: ['reference-rates'] });
      onClose();
    } catch (err) {
      setError(apiErrorMessage(err, 'Không tạo được benchmark.'));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title="Add Reference Rate" onCancel={onClose} onOk={submit} okText="Tạo" okDisabled={busy || !name.trim()}>
      <div className="field">
        <label>Tên benchmark</label>
        <input value={name} onChange={(e) => setName(e.target.value)} autoFocus />
      </div>
      <div className="field">
        <label>Loại</label>
        <select value={rateType} onChange={(e) => setRateType(e.target.value as 'manual' | 'calculated')}>
          <option value="manual">Manual Rate (GROUP A)</option>
          <option value="calculated">Calculated Rate (GROUP B)</option>
        </select>
      </div>
      {rateType === 'calculated' && (
        <>
          <div className="field">
            <label>Phương pháp tính</label>
            <select value={calcMethod} onChange={(e) => setCalcMethod(e.target.value)}>
              <option value="average">Average</option>
              <option value="min">Min</option>
              <option value="max">Max</option>
            </select>
          </div>
          <div className="field" style={{ alignItems: 'flex-start' }}>
            <label style={{ paddingTop: 4 }}>Benchmark thành phần</label>
            <div>
              {rates.length === 0 && <div className="hint">Chưa có benchmark khác để chọn.</div>}
              {rates.map((r) => (
                <label key={r.id} style={{ display: 'block', fontSize: 12, marginBottom: 3 }}>
                  <input
                    type="checkbox"
                    checked={componentIds.includes(r.id)}
                    onChange={(e) =>
                      setComponentIds((ids) => (e.target.checked ? [...ids, r.id] : ids.filter((x) => x !== r.id)))
                    }
                  />{' '}
                  {r.name}
                </label>
              ))}
            </div>
          </div>
        </>
      )}
      {error && <div className="field err">{error}</div>}
    </Modal>
  );
}
