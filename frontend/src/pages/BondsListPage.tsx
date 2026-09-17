import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import AddBondModal from '../components/AddBondModal';
import { api } from '../lib/api';
import { useAuth } from '../lib/auth';
import { fmtDate } from '../lib/format';

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

