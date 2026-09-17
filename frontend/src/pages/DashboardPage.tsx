import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { api, apiErrorMessage, isConflictError } from '../lib/api';
import { fmtNumber, fmtPercent } from '../lib/format';
import { ymAdd } from '../lib/timeline';
import { useToast } from '../lib/toast';

interface PortfolioRow {
  bond_id: string;
  code: string;
  volume: number;
  value: number;
}
interface DashboardResponse {
  month_key: string;
  equity: number | null;
  limit: number | null;
  holding_value: number;
  remaining_capacity: number | null;
  usage_ratio: number | null;
  invested_bonds: PortfolioRow[];
  advised_bonds: PortfolioRow[];
  advised_volume_total: number;
  fee_total: number;
  coupon_revenue: number;
  ir_revenue: number;
  total_revenue: number;
  compliance_done: number;
  compliance_total: number;
}
interface AlertItem {
  kind: 'd' | 'w' | 'i';
  category: string;
  title: string;
  detail: string;
}

function curMonthKey(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
}

export default function DashboardPage() {
  const toast = useToast();
  const qc = useQueryClient();
  const [month, setMonth] = useState(curMonthKey());

  const { data, isLoading } = useQuery<DashboardResponse>({
    queryKey: ['dashboard', month],
    queryFn: async () => (await api.get(`/dashboard/${month}`)).data,
  });
  const { data: alerts } = useQuery<AlertItem[]>({
    queryKey: ['dashboard-alerts'],
    queryFn: async () => (await api.get('/dashboard/alerts/upcoming')).data,
  });

  const [equityInput, setEquityInput] = useState('');
  const [equityVersion, setEquityVersion] = useState<number | null>(null);

  useQuery({
    queryKey: ['equity', month],
    queryFn: async () => {
      const { data } = await api.get(`/dashboard/equity/${month}`);
      setEquityInput(data.value === null ? '' : String(data.value));
      setEquityVersion(data.version);
      return data;
    },
  });

  async function saveEquity() {
    const num = equityInput.trim() === '' ? null : Number(equityInput);
    if (num === null || Number.isNaN(num)) return;
    try {
      await api.put(`/dashboard/equity/${month}`, { value: num, version: equityVersion });
      toast('Đã lưu VCSH', 'ok');
      qc.invalidateQueries({ queryKey: ['dashboard', month] });
      qc.invalidateQueries({ queryKey: ['equity', month] });
    } catch (err) {
      if (isConflictError(err)) toast(apiErrorMessage(err), 'err');
      else toast(apiErrorMessage(err), 'err');
    }
  }

  if (isLoading || !data) return <div className="empty">Đang tải…</div>;

  const usageKpiClass = data.usage_ratio === null ? '' : data.usage_ratio >= 1 ? 'bad' : data.usage_ratio >= 0.9 ? 'warn' : 'good';
  const chartData = [
    { name: 'Phí', value: data.fee_total },
    { name: 'Coupon', value: data.coupon_revenue },
    { name: 'IR', value: data.ir_revenue },
  ];
  const COLORS = ['#1b4f8a', '#0a7d46', '#c47b00'];

  return (
    <div>
      <div className="toolbar">
        <button className="btn sm" onClick={() => setMonth(ymAdd(month, -1))}>
          ← Tháng trước
        </button>
        <strong style={{ minWidth: 70, textAlign: 'center' }}>{month}</strong>
        <button className="btn sm" onClick={() => setMonth(ymAdd(month, 1))}>
          Tháng sau →
        </button>
        <div className="spacer" />
        <div className="field" style={{ maxWidth: 260 }}>
          <label>VCSH TPS (tr.đ)</label>
          <input className="numf" value={equityInput} onChange={(e) => setEquityInput(e.target.value)} onBlur={saveEquity} />
        </div>
      </div>

      <div className="kpigrid">
        <div className={`kpi ${usageKpiClass}`}>
          <div className="k">Tổng Giá trị TP nắm giữ</div>
          <div className="v">{fmtNumber(data.holding_value, 2)}</div>
          <div className="m">Giới hạn (70% VCSH): {fmtNumber(data.limit, 2)}</div>
        </div>
        <div className={`kpi ${usageKpiClass}`}>
          <div className="k">% Limit Used</div>
          <div className="v">{data.usage_ratio === null ? '–' : fmtPercent(data.usage_ratio * 100)}</div>
          <div className="m">Remaining Capacity: {fmtNumber(data.remaining_capacity, 2)}</div>
        </div>
        <div className="kpi">
          <div className="k">Doanh thu tháng {month}</div>
          <div className="v">{fmtNumber(data.total_revenue, 2)}</div>
          <div className="m">
            Fee {fmtNumber(data.fee_total, 2)} · Coupon {fmtNumber(data.coupon_revenue, 2)} · IR {fmtNumber(data.ir_revenue, 2)}
          </div>
        </div>
        <div className="kpi">
          <div className="k">Compliance (Phase 5)</div>
          <div className="v">
            {data.compliance_done}/{data.compliance_total}
          </div>
          <div className="m">Chưa wiring — xem README trạng thái phase</div>
        </div>
      </div>

      <div className="panel">
        <header>
          <h2>Doanh thu theo nguồn</h2>
        </header>
        <div className="body">
          <div className="chartbox">
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e9edf2" />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 10 }} />
                <Tooltip formatter={(v) => fmtNumber(Number(v), 2)} />
                <Bar dataKey="value">
                  {chartData.map((_, i) => (
                    <Cell key={i} fill={COLORS[i]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="panel">
        <header>
          <h2>Upcoming 30 Days</h2>
        </header>
        <div className="body">
          {!alerts?.length ? (
            <div className="empty">Không có cảnh báo nào.</div>
          ) : (
            <div className="alerts">
              {alerts.map((a, i) => (
                <div key={i} className={`alert ${a.kind}`}>
                  <div>
                    <div className="t">{a.title}</div>
                    <div className="s">{a.detail}</div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="panel">
        <header>
          <h2>A. Trái phiếu TPS đầu tư</h2>
        </header>
        <div className="body flush">
          <PortfolioTable rows={data.invested_bonds} totalLabel="Tổng Giá trị TP nắm giữ" />
        </div>
      </div>

      <div className="panel">
        <header>
          <h2>B. Trái phiếu TPS tư vấn phát hành</h2>
        </header>
        <div className="body flush">
          <PortfolioTable rows={data.advised_bonds} totalLabel="Tổng khối lượng tư vấn" volumeOnly />
        </div>
      </div>
    </div>
  );
}

function PortfolioTable({ rows, totalLabel, volumeOnly }: { rows: PortfolioRow[]; totalLabel: string; volumeOnly?: boolean }) {
  if (!rows.length) return <div className="empty">Chưa có dữ liệu.</div>;
  const totalVolume = rows.reduce((s, r) => s + r.volume, 0);
  const totalValue = rows.reduce((s, r) => s + r.value, 0);
  return (
    <table className="grid" style={{ width: '100%' }}>
      <thead>
        <tr className="r1">
          <th style={{ textAlign: 'left' }}>Mã trái phiếu</th>
          <th>Khối lượng</th>
          {!volumeOnly && <th>Giá trị (tr.đ)</th>}
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.bond_id}>
            <td style={{ textAlign: 'left' }}>{r.code}</td>
            <td>{fmtNumber(r.volume, 2)}</td>
            {!volumeOnly && <td>{fmtNumber(r.value, 2)}</td>}
          </tr>
        ))}
        <tr className="total">
          <td style={{ textAlign: 'left' }}>{totalLabel}</td>
          <td>{fmtNumber(totalVolume, 2)}</td>
          {!volumeOnly && <td>{fmtNumber(totalValue, 2)}</td>}
        </tr>
      </tbody>
    </table>
  );
}
