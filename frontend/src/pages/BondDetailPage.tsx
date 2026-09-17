import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import BondFeesPanel from '../components/BondFeesPanel';
import { api, apiErrorMessage, isConflictError } from '../lib/api';
import { useAuth } from '../lib/auth';
import { fmtNumber, fmtPercent } from '../lib/format';
import { monthShortLabel, monthsBetween } from '../lib/timeline';
import { useToast } from '../lib/toast';

interface InterestConfig {
  rate_type: string;
  fixed_rate: number | null;
  spread: number | null;
  reference_rate_id: string | null;
  first4_rate: number | null;
  floor_rate: number | null;
  cap_rate: number | null;
  version: number;
}
interface MonthlyDataRow {
  advised_volume: number | null;
  buyback_volume: number | null;
  invested_volume: number | null;
  sold_volume: number | null;
  version: number;
}
interface BondDetail {
  id: string;
  code: string;
  issue_date: string | null;
  maturity_date: string | null;
  first_fee_date: string | null;
  pay_freq_months: number;
  xhtn: string | null;
  par_value: number;
  status_key: string;
  status_label: string;
  version: number;
  interest_config: InterestConfig;
  monthly_data: Record<string, MonthlyDataRow>;
  fee_configs: FeeConfigLite[];
}
interface FeeConfigLite {
  fee_type_key: string;
  name: string;
  basis: string;
  allowed_methods: string[];
  default_rate: number;
  method: string;
  recognition_month: string | null;
  freq_months: number;
  timing: string;
  version: number;
  periods: { id: string; effective_from: string; effective_to: string | null; fee_rate: number }[];
}
interface ComputedMonth {
  month_key: string;
  outstanding: number | null;
  holding: number | null;
  coupon: number | null;
  reference_value: number | null;
  fees: Record<string, number>;
  fee_total: number;
  coupon_revenue: number;
  total_revenue: number;
}
interface ReferenceRate {
  id: string;
  name: string;
  rate_type: string;
}

export default function BondDetailPage() {
  const { bondId } = useParams<{ bondId: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { hasRole } = useAuth();
  const canEdit = hasRole('Admin', 'Manager', 'Staff');

  const { data: bond, isLoading } = useQuery<BondDetail>({
    queryKey: ['bond', bondId],
    queryFn: async () => (await api.get(`/bonds/${bondId}`)).data,
    enabled: !!bondId,
  });
  const { data: refRates } = useQuery<ReferenceRate[]>({
    queryKey: ['reference-rates'],
    queryFn: async () => (await api.get('/reference-rates')).data,
  });
  const { data: timeline } = useQuery<{ start: string; end: string }>({
    queryKey: ['timeline', 'monthly'],
    queryFn: async () => (await api.get('/system/timeline/monthly')).data,
  });
  const months = useMemo(() => (timeline ? monthsBetween(timeline.start, timeline.end) : []), [timeline]);
  const { data: computed } = useQuery<ComputedMonth[]>({
    queryKey: ['bond-computed', bondId, timeline?.start, timeline?.end],
    queryFn: async () =>
      (await api.get(`/bonds/${bondId}/computed`, { params: { start: timeline!.start, end: timeline!.end } })).data,
    enabled: !!bondId && !!timeline,
  });
  const computedByMonth = useMemo(() => {
    const m: Record<string, ComputedMonth> = {};
    computed?.forEach((c) => (m[c.month_key] = c));
    return m;
  }, [computed]);

  const refetchBond = () => {
    qc.invalidateQueries({ queryKey: ['bond', bondId] });
    qc.invalidateQueries({ queryKey: ['bond-computed', bondId] });
  };

  if (isLoading || !bond) return <div className="empty">Đang tải…</div>;

  return (
    <div>
      <button className="backlink" onClick={() => navigate('/bonds')}>
        ← Back to Bonds
      </button>
      <div className="bondhead">
        <h1>{bond.code}</h1>
        <span className={`tag ${bond.status_key === 'active' ? 'active' : bond.status_key === 'matured' ? 'matured' : 'pre'}`}>
          {bond.status_label}
        </span>
      </div>

      <BasicInfoPanel bond={bond} canEdit={canEdit} onSaved={refetchBond} />
      <InterestConfigPanel bond={bond} refRates={refRates ?? []} canEdit={canEdit} onSaved={refetchBond} />
      <BondFeesPanel bondId={bond.id} feeConfigs={bond.fee_configs} canEdit={canEdit} />

      <div className="panel">
        <header>
          <h2>Bảng quản lý trái phiếu theo tháng</h2>
        </header>
        <div className="body flush">
          <div className="tblwrap">
            <table className="grid">
              <thead>
                <tr className="r1">
                  <th className="s1" rowSpan={2}></th>
                  <th className="s2" rowSpan={2} style={{ textAlign: 'left' }}>
                    Chỉ tiêu
                  </th>
                  {months.map((m) => (
                    <th key={m}>{monthShortLabel(m)}</th>
                  ))}
                </tr>
                <tr className="r2" style={{ display: 'none' }} />
              </thead>
              <tbody>
                <VolumeRow label="1.1 Khối lượng tư vấn" idx="1" field="advised_volume" months={months} bond={bond} canEdit={canEdit} onSaved={refetchBond} />
                <VolumeRow label="1.2 TCPH mua lại" idx="2" field="buyback_volume" months={months} bond={bond} canEdit={canEdit} onSaved={refetchBond} negRed />
                <CalcRow label="Khối lượng lưu hành" idx="3" months={months} data={computedByMonth} pick={(c) => c.outstanding} />
                <VolumeRow label="2.1 Khối lượng đầu tư" idx="4" field="invested_volume" months={months} bond={bond} canEdit={canEdit} onSaved={refetchBond} />
                <VolumeRow label="2.2 Khối lượng bán ra" idx="5" field="sold_volume" months={months} bond={bond} canEdit={canEdit} onSaved={refetchBond} negRed />
                <CalcRow label="Khối lượng nắm giữ" idx="6" months={months} data={computedByMonth} pick={(c) => c.holding} />
                <CalcRow label="Lãi suất Coupon (%)" idx="7" months={months} data={computedByMonth} pick={(c) => c.coupon} pct />
                <CalcRow label="LS tham chiếu (%)" idx="8" months={months} data={computedByMonth} pick={(c) => c.reference_value} pct missing />
                {bond.fee_configs.map((f) => (
                  <CalcRow key={f.fee_type_key} label={f.name} idx="·" months={months} data={computedByMonth} pick={(c) => c.fees[f.fee_type_key]} sub />
                ))}
                <CalcRow label="Doanh thu Phí (1)" idx="9" months={months} data={computedByMonth} pick={(c) => c.fee_total} sum />
                <CalcRow label="Doanh thu Coupon" idx="10" months={months} data={computedByMonth} pick={(c) => c.coupon_revenue} />
                <CalcRow label="Tổng doanh thu (3)" idx="11" months={months} data={computedByMonth} pick={(c) => c.total_revenue} total />
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

function BasicInfoPanel({ bond, canEdit, onSaved }: { bond: BondDetail; canEdit: boolean; onSaved: () => void }) {
  const toast = useToast();
  const [form, setForm] = useState(bond);
  useEffect(() => setForm(bond), [bond]);
  const [busy, setBusy] = useState(false);

  async function save() {
    setBusy(true);
    try {
      await api.patch(`/bonds/${bond.id}`, {
        code: form.code,
        issue_date: form.issue_date || null,
        maturity_date: form.maturity_date || null,
        first_fee_date: form.first_fee_date || null,
        pay_freq_months: form.pay_freq_months,
        xhtn: form.xhtn || null,
        par_value: form.par_value,
        version: bond.version,
      });
      toast('Đã lưu thông tin cơ bản', 'ok');
      onSaved();
    } catch (err) {
      if (isConflictError(err)) toast(apiErrorMessage(err), 'err');
      else toast(apiErrorMessage(err), 'err');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="panel">
      <header>
        <h2>Thông tin cơ bản</h2>
      </header>
      <div className="body">
        <div className="infogrid">
          <div className="field">
            <label>Mã trái phiếu</label>
            <input value={form.code} disabled={!canEdit} onChange={(e) => setForm({ ...form, code: e.target.value })} />
          </div>
          <div className="field">
            <label>Ngày phát hành</label>
            <input type="date" value={form.issue_date ?? ''} disabled={!canEdit} onChange={(e) => setForm({ ...form, issue_date: e.target.value })} />
          </div>
          <div className="field">
            <label>Ngày đáo hạn</label>
            <input type="date" value={form.maturity_date ?? ''} disabled={!canEdit} onChange={(e) => setForm({ ...form, maturity_date: e.target.value })} />
          </div>
          <div className="field">
            <label>Ngày đầu thu phí định kỳ</label>
            <input type="date" value={form.first_fee_date ?? ''} disabled={!canEdit} onChange={(e) => setForm({ ...form, first_fee_date: e.target.value })} />
          </div>
          <div className="field">
            <label>Trả lãi (tháng/lần)</label>
            <input type="number" min={1} className="numf" value={form.pay_freq_months} disabled={!canEdit} onChange={(e) => setForm({ ...form, pay_freq_months: Number(e.target.value) })} />
          </div>
          <div className="field">
            <label>XHTN</label>
            <input value={form.xhtn ?? ''} disabled={!canEdit} onChange={(e) => setForm({ ...form, xhtn: e.target.value })} />
          </div>
          <div className="field">
            <label>Mệnh giá (triệu đồng)</label>
            <input type="number" className="numf" value={form.par_value} disabled={!canEdit} onChange={(e) => setForm({ ...form, par_value: Number(e.target.value) })} />
          </div>
        </div>
        {canEdit && (
          <button className="btn primary" style={{ marginTop: 12 }} disabled={busy} onClick={save}>
            Lưu thông tin cơ bản
          </button>
        )}
      </div>
    </div>
  );
}

function InterestConfigPanel({
  bond,
  refRates,
  canEdit,
  onSaved,
}: {
  bond: BondDetail;
  refRates: ReferenceRate[];
  canEdit: boolean;
  onSaved: () => void;
}) {
  const toast = useToast();
  const [form, setForm] = useState(bond.interest_config);
  useEffect(() => setForm(bond.interest_config), [bond.interest_config]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save() {
    setBusy(true);
    setError(null);
    try {
      await api.patch(`/bonds/${bond.id}/interest-config`, { ...form, version: bond.interest_config.version });
      toast('Đã lưu cấu trúc lãi suất', 'ok');
      onSaved();
    } catch (err) {
      setError(apiErrorMessage(err, 'Không lưu được cấu trúc lãi suất.'));
    } finally {
      setBusy(false);
    }
  }

  const num = (v: string) => (v === '' ? null : Number(v));

  return (
    <div className="panel">
      <header>
        <h2>Cấu trúc lãi suất trái phiếu</h2>
      </header>
      <div className="body">
        <div className="field" style={{ marginBottom: 12 }}>
          <label>Loại lãi suất</label>
          <select value={form.rate_type} disabled={!canEdit} onChange={(e) => setForm({ ...form, rate_type: e.target.value })}>
            <option value="fixed">LS cố định</option>
            <option value="floating">LS thả nổi</option>
            <option value="combined">LS kết hợp</option>
            <option value="conditional">LS kết hợp có điều kiện</option>
          </select>
        </div>
        <div className="infogrid">
          {form.rate_type === 'fixed' && (
            <div className="field">
              <label>Lãi suất các kỳ (%)</label>
              <input className="numf" value={form.fixed_rate ?? ''} disabled={!canEdit} onChange={(e) => setForm({ ...form, fixed_rate: num(e.target.value) })} />
            </div>
          )}
          {form.rate_type === 'floating' && (
            <>
              <div className="field">
                <label>Biên độ (%)</label>
                <input className="numf" value={form.spread ?? ''} disabled={!canEdit} onChange={(e) => setForm({ ...form, spread: num(e.target.value) })} />
              </div>
              <div className="field">
                <label>Lãi suất tham chiếu</label>
                <select value={form.reference_rate_id ?? ''} disabled={!canEdit} onChange={(e) => setForm({ ...form, reference_rate_id: e.target.value || null })}>
                  <option value="">— chọn benchmark —</option>
                  {refRates.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.name}
                    </option>
                  ))}
                </select>
              </div>
            </>
          )}
          {(form.rate_type === 'combined' || form.rate_type === 'conditional') && (
            <>
              <div className="field">
                <label>Lãi suất 4 kỳ đầu (%)</label>
                <input className="numf" value={form.first4_rate ?? ''} disabled={!canEdit} onChange={(e) => setForm({ ...form, first4_rate: num(e.target.value) })} />
              </div>
              <div className="field">
                <label>Biên độ (%)</label>
                <input className="numf" value={form.spread ?? ''} disabled={!canEdit} onChange={(e) => setForm({ ...form, spread: num(e.target.value) })} />
              </div>
              <div className="field">
                <label>Lãi suất tham chiếu</label>
                <select value={form.reference_rate_id ?? ''} disabled={!canEdit} onChange={(e) => setForm({ ...form, reference_rate_id: e.target.value || null })}>
                  <option value="">— chọn benchmark —</option>
                  {refRates.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.name}
                    </option>
                  ))}
                </select>
              </div>
            </>
          )}
          {form.rate_type === 'conditional' && (
            <>
              <div className="field">
                <label>Không dưới (Floor) %</label>
                <input className="numf" value={form.floor_rate ?? ''} disabled={!canEdit} onChange={(e) => setForm({ ...form, floor_rate: num(e.target.value) })} />
              </div>
              <div className="field">
                <label>Không quá (Cap) %</label>
                <input className="numf" value={form.cap_rate ?? ''} disabled={!canEdit} onChange={(e) => setForm({ ...form, cap_rate: num(e.target.value) })} />
              </div>
            </>
          )}
        </div>
        {error && <div className="field err">{error}</div>}
        {canEdit && (
          <button className="btn primary" style={{ marginTop: 12 }} disabled={busy} onClick={save}>
            Lưu cấu trúc lãi suất
          </button>
        )}
      </div>
    </div>
  );
}

function VolumeRow({
  label,
  idx,
  field,
  months,
  bond,
  canEdit,
  onSaved,
  negRed,
}: {
  label: string;
  idx: string;
  field: 'advised_volume' | 'buyback_volume' | 'invested_volume' | 'sold_volume';
  months: string[];
  bond: BondDetail;
  canEdit: boolean;
  onSaved: () => void;
  negRed?: boolean;
}) {
  const toast = useToast();

  async function save(monthKey: string, value: string) {
    const num = value.trim() === '' ? null : Number(value.replace(',', '.'));
    if (value.trim() !== '' && Number.isNaN(num)) return;
    const row = bond.monthly_data[monthKey];
    try {
      await api.put(`/bonds/${bond.id}/monthly/${monthKey}`, {
        advised_volume: field === 'advised_volume' ? num : row?.advised_volume ?? null,
        buyback_volume: field === 'buyback_volume' ? num : row?.buyback_volume ?? null,
        invested_volume: field === 'invested_volume' ? num : row?.invested_volume ?? null,
        sold_volume: field === 'sold_volume' ? num : row?.sold_volume ?? null,
        version: row?.version ?? null,
      });
      onSaved();
    } catch (err) {
      if (isConflictError(err)) toast(apiErrorMessage(err), 'err');
      else toast(apiErrorMessage(err), 'err');
    }
  }

  return (
    <tr>
      <td className="s1">{idx}</td>
      <td className="s2 lvl2">{label}</td>
      {months.map((m) => {
        const row = bond.monthly_data[m];
        const val = row?.[field];
        return (
          <td key={m} className={negRed && val !== null && val !== undefined && val < 0 ? 'neg' : ''}>
            <input
              className="cell"
              defaultValue={val === null || val === undefined ? '' : String(val)}
              disabled={!canEdit}
              onBlur={(e) => {
                const current = val === null || val === undefined ? '' : String(val);
                if (e.target.value !== current) save(m, e.target.value);
              }}
            />
          </td>
        );
      })}
    </tr>
  );
}

function CalcRow({
  label,
  idx,
  months,
  data,
  pick,
  pct,
  missing,
  total,
  sub,
  sum,
}: {
  label: string;
  idx: string;
  months: string[];
  data: Record<string, ComputedMonth>;
  pick: (c: ComputedMonth) => number | null | undefined;
  pct?: boolean;
  missing?: boolean;
  total?: boolean;
  sub?: boolean;
  sum?: boolean;
}) {
  return (
    <tr className={total ? 'total' : sum ? 'sub' : undefined}>
      <td className="s1">{idx}</td>
      <td className={`s2 ${sub ? 'lvl3' : 'lvl2'}`}>{label}</td>
      {months.map((m) => {
        const c = data[m];
        const v = c ? pick(c) : undefined;
        const isMissing = missing && (v === null || v === undefined);
        return (
          <td key={m} className={`calc${isMissing ? ' missing' : ''}`} title={isMissing ? 'Chưa cập nhật lãi suất tham chiếu' : ''}>
            {v === null || v === undefined ? '–' : pct ? fmtPercent(v) : fmtNumber(v, 2)}
          </td>
        );
      })}
    </tr>
  );
}
