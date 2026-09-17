import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Modal from '../components/Modal';
import { api, apiErrorMessage } from '../lib/api';
import { useAuth } from '../lib/auth';
import { fmtDate } from '../lib/format';
import { useToast } from '../lib/toast';

interface BondListItem {
  id: string;
  code: string;
  issue_date: string | null;
  maturity_date: string | null;
  par_value: number;
  status_key: 'pre' | 'active' | 'matured';
  status_label: string;
}

export default function BondsListPage() {
  const { hasRole } = useAuth();
  const navigate = useNavigate();
  const [showAdd, setShowAdd] = useState(false);
  const { data: bonds, isLoading } = useQuery<BondListItem[]>({
    queryKey: ['bonds'],
    queryFn: async () => (await api.get('/bonds')).data,
  });

  return (
    <div>
      <div className="toolbar">
        <div className="hint">Gõ mã ví dụ "VHM" để lọc trên thanh điều hướng bên trái.</div>
        <div className="spacer" />
        {hasRole('Admin', 'Manager', 'Staff') && (
          <button className="btn primary" onClick={() => setShowAdd(true)}>
            + Thêm trái phiếu
          </button>
        )}
      </div>
      <div className="panel">
        <div className="body flush">
          {isLoading ? (
            <div className="empty">Đang tải…</div>
          ) : !bonds?.length ? (
            <div className="empty">Chưa có trái phiếu nào.</div>
          ) : (
            <div className="tblwrap">
              <table className="grid" style={{ width: '100%' }}>
                <thead>
                  <tr className="r1">
                    <th style={{ textAlign: 'left' }}>Mã trái phiếu</th>
                    <th>Trạng thái</th>
                    <th>Ngày phát hành</th>
                    <th>Ngày đáo hạn</th>
                    <th>Mệnh giá (tr.đ)</th>
                  </tr>
                </thead>
                <tbody>
                  {bonds.map((b) => (
                    <tr key={b.id} style={{ cursor: 'pointer' }} onClick={() => navigate(`/bonds/${b.id}`)}>
                      <td style={{ textAlign: 'left', fontWeight: 600 }}>{b.code}</td>
                      <td>
                        <span className={`tag ${b.status_key === 'active' ? 'active' : b.status_key === 'matured' ? 'matured' : 'pre'}`}>
                          {b.status_label}
                        </span>
                      </td>
                      <td>{fmtDate(b.issue_date)}</td>
                      <td>{fmtDate(b.maturity_date)}</td>
                      <td>{b.par_value}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
      {showAdd && <AddBondModal onClose={() => setShowAdd(false)} />}
    </div>
  );
}

function AddBondModal({ onClose }: { onClose: () => void }) {
  const toast = useToast();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [code, setCode] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      const { data } = await api.post('/bonds', { code: code.trim() });
      toast(`Đã tạo trái phiếu ${data.code}`, 'ok');
      qc.invalidateQueries({ queryKey: ['bonds'] });
      onClose();
      navigate(`/bonds/${data.id}`);
    } catch (err) {
      setError(apiErrorMessage(err, 'Không tạo được trái phiếu.'));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title="Thêm trái phiếu" onCancel={onClose} onOk={submit} okText="Tạo" okDisabled={busy || !code.trim()}>
      <div className="field">
        <label>Mã trái phiếu</label>
        <input value={code} onChange={(e) => setCode(e.target.value.toUpperCase())} autoFocus placeholder="VD: VHML12617" />
      </div>
      {error && <div className="field err">{error}</div>}
    </Modal>
  );
}
