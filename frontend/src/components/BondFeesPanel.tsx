import { useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { api, apiErrorMessage } from '../lib/api';
import { fmtDate, fmtPercent } from '../lib/format';
import { useToast } from '../lib/toast';

interface FeePeriod {
  id: string;
  effective_from: string;
  effective_to: string | null;
  fee_rate: number;
}
interface FeeConfig {
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
  periods: FeePeriod[];
}

const METHOD_LABEL: Record<string, string> = {
  once: 'Thu một lần',
  actual: 'Định kỳ Actual',
  flat: 'Định kỳ không Actual',
};

export default function BondFeesPanel({ bondId, feeConfigs, canEdit }: { bondId: string; feeConfigs: FeeConfig[]; canEdit: boolean }) {
  return (
    <div className="panel">
      <header>
        <h2>Phí — 6 loại</h2>
        <span className="hint spacer" style={{ textAlign: 'right' }}>
          % phí có thể thay đổi theo giai đoạn thời gian
        </span>
      </header>
      <div className="body">
        {feeConfigs.map((f) => (
          <FeeRow key={f.fee_type_key} bondId={bondId} fee={f} canEdit={canEdit} />
        ))}
      </div>
    </div>
  );
}

function FeeRow({ bondId, fee, canEdit }: { bondId: string; fee: FeeConfig; canEdit: boolean }) {
  const toast = useToast();
  const qc = useQueryClient();
  const [form, setForm] = useState(fee);
  useEffect(() => setForm(fee), [fee]);
  const [busy, setBusy] = useState(false);
  const [showAddPeriod, setShowAddPeriod] = useState(false);
  const [periodFrom, setPeriodFrom] = useState('');
  const [periodTo, setPeriodTo] = useState('');
  const [periodRate, setPeriodRate] = useState('');
  const [error, setError] = useState<string | null>(null);

  const refetch = () => qc.invalidateQueries({ queryKey: ['bond', bondId] });

  async function save() {
    setBusy(true);
    setError(null);
    try {
      await api.patch(`/bonds/${bondId}/fees/${fee.fee_type_key}`, {
        default_rate: form.default_rate,
        method: form.method,
        recognition_month: form.method === 'once' ? form.recognition_month : null,
        freq_months: form.freq_months,
        timing: form.timing,
        version: fee.version,
      });
      toast(`Đã lưu ${fee.name}`, 'ok');
      refetch();
    } catch (err) {
      setError(apiErrorMessage(err, 'Không lưu được.'));
    } finally {
      setBusy(false);
    }
  }

  async function addPeriod() {
    if (!periodFrom || periodRate === '') return;
    try {
      await api.post(`/bonds/${bondId}/fees/${fee.fee_type_key}/periods`, {
        effective_from: periodFrom,
        effective_to: periodTo || null,
        fee_rate: Number(periodRate),
      });
      toast('Đã thêm giai đoạn phí', 'ok');
      setShowAddPeriod(false);
      setPeriodFrom('');
      setPeriodTo('');
      setPeriodRate('');
      refetch();
    } catch (err) {
      toast(apiErrorMessage(err, 'Không thêm được giai đoạn.'), 'err');
    }
  }

  async function deletePeriod(periodId: string) {
    try {
      await api.delete(`/bonds/${bondId}/fees/${fee.fee_type_key}/periods/${periodId}`);
      refetch();
    } catch (err) {
      toast(apiErrorMessage(err), 'err');
    }
  }

  return (
    <div data-fee-row={fee.fee_type_key} style={{ borderTop: '1px solid var(--line-soft)', padding: '10px 0' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap' }}>
        <strong style={{ minWidth: 180 }}>{fee.name}</strong>
        <span className="hint">{fee.basis}</span>
      </div>
      <div className="infogrid" style={{ marginTop: 8 }}>
        <div className="field">
          <label>Phương pháp</label>
          <select value={form.method} disabled={!canEdit} onChange={(e) => setForm({ ...form, method: e.target.value })}>
            {fee.allowed_methods.map((m) => (
              <option key={m} value={m}>
                {METHOD_LABEL[m]}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label>% phí mặc định</label>
          <input className="numf" value={form.default_rate} disabled={!canEdit} onChange={(e) => setForm({ ...form, default_rate: Number(e.target.value) })} />
        </div>
        {form.method === 'once' && (
          <div className="field">
            <label>Tháng ghi nhận</label>
            <input placeholder="YYYY-MM" value={form.recognition_month ?? ''} disabled={!canEdit} onChange={(e) => setForm({ ...form, recognition_month: e.target.value })} />
          </div>
        )}
        {form.method !== 'once' && (
          <>
            <div className="field">
              <label>Tần suất (tháng/kỳ)</label>
              <input type="number" min={1} className="numf" value={form.freq_months} disabled={!canEdit} onChange={(e) => setForm({ ...form, freq_months: Number(e.target.value) })} />
            </div>
            <div className="field">
              <label>Thời điểm ghi nhận</label>
              <select value={form.timing} disabled={!canEdit} onChange={(e) => setForm({ ...form, timing: e.target.value })}>
                <option value="end">Cuối kỳ</option>
                <option value="begin">Đầu kỳ</option>
              </select>
            </div>
          </>
        )}
      </div>
      {error && <div className="field err">{error}</div>}
      {canEdit && (
        <button className="btn sm" style={{ marginTop: 6 }} disabled={busy} onClick={save}>
          Lưu
        </button>
      )}

      {fee.method !== 'once' && (
        <div style={{ marginTop: 10 }}>
          <div className="hint" style={{ marginBottom: 4 }}>
            Lịch % phí theo giai đoạn (mặc định {fmtPercent(fee.default_rate)} nếu chưa có giai đoạn nào áp dụng):
          </div>
          {fee.periods.length > 0 && (
            <table className="grid" style={{ width: 'auto', marginBottom: 6 }}>
              <thead>
                <tr className="r1">
                  <th>Từ ngày</th>
                  <th>Đến ngày</th>
                  <th>% phí</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {fee.periods.map((p) => (
                  <tr key={p.id}>
                    <td>{fmtDate(p.effective_from)}</td>
                    <td>{p.effective_to ? fmtDate(p.effective_to) : '—'}</td>
                    <td>{fmtPercent(p.fee_rate)}</td>
                    <td>
                      {canEdit && (
                        <button className="btn sm" onClick={() => deletePeriod(p.id)}>
                          ×
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {canEdit && !showAddPeriod && (
            <button className="btn sm" onClick={() => setShowAddPeriod(true)}>
              + Thêm giai đoạn phí
            </button>
          )}
          {canEdit && showAddPeriod && (
            <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
              <input type="date" value={periodFrom} onChange={(e) => setPeriodFrom(e.target.value)} />
              <span className="hint">đến</span>
              <input type="date" value={periodTo} onChange={(e) => setPeriodTo(e.target.value)} />
              <input className="numf" style={{ width: 80 }} placeholder="% phí" value={periodRate} onChange={(e) => setPeriodRate(e.target.value)} />
              <button className="btn sm primary" onClick={addPeriod}>
                Thêm
              </button>
              <button className="btn sm" onClick={() => setShowAddPeriod(false)}>
                Hủy
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
