import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { api } from '../lib/api';
import { fmtDate } from '../lib/format';

interface AuditLogItem {
  id: string;
  user_email: string | null;
  timestamp: string;
  module: string;
  record_id: string;
  field: string | null;
  old_value: string | null;
  new_value: string | null;
  action: string;
}
interface AuditLogPage {
  items: AuditLogItem[];
  total: number;
  limit: number;
  offset: number;
}

const ACTIONS = ['create', 'update', 'delete', 'restore'];

export default function AuditLogPage() {
  const [module, setModule] = useState('');
  const [action, setAction] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [offset, setOffset] = useState(0);
  const limit = 50;

  const { data, isLoading } = useQuery<AuditLogPage>({
    queryKey: ['audit-logs', module, action, dateFrom, dateTo, offset],
    queryFn: async () =>
      (
        await api.get('/audit-logs', {
          params: {
            module: module || undefined,
            action: action || undefined,
            date_from: dateFrom || undefined,
            date_to: dateTo || undefined,
            limit,
            offset,
          },
        })
      ).data,
  });

  return (
    <div>
      <div className="toolbar">
        <div className="field" style={{ maxWidth: 200 }}>
          <label>Module</label>
          <input value={module} onChange={(e) => { setModule(e.target.value); setOffset(0); }} placeholder="vd: bonds" />
        </div>
        <div className="field" style={{ maxWidth: 160 }}>
          <label>Action</label>
          <select value={action} onChange={(e) => { setAction(e.target.value); setOffset(0); }}>
            <option value="">Tất cả</option>
            {ACTIONS.map((a) => (
              <option key={a} value={a}>
                {a}
              </option>
            ))}
          </select>
        </div>
        <div className="field" style={{ maxWidth: 160 }}>
          <label>Từ ngày</label>
          <input type="date" value={dateFrom} onChange={(e) => { setDateFrom(e.target.value); setOffset(0); }} />
        </div>
        <div className="field" style={{ maxWidth: 160 }}>
          <label>Đến ngày</label>
          <input type="date" value={dateTo} onChange={(e) => { setDateTo(e.target.value); setOffset(0); }} />
        </div>
      </div>

      <div className="panel">
        <div className="body flush">
          {isLoading ? (
            <div className="empty">Đang tải…</div>
          ) : !data?.items.length ? (
            <div className="empty">Không có bản ghi audit nào khớp bộ lọc.</div>
          ) : (
            <>
              <table className="grid" style={{ width: '100%' }}>
                <thead>
                  <tr className="r1">
                    <th>Thời gian</th>
                    <th style={{ textAlign: 'left' }}>Người dùng</th>
                    <th style={{ textAlign: 'left' }}>Module</th>
                    <th style={{ textAlign: 'left' }}>Record</th>
                    <th style={{ textAlign: 'left' }}>Field</th>
                    <th style={{ textAlign: 'left' }}>Giá trị cũ</th>
                    <th style={{ textAlign: 'left' }}>Giá trị mới</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((item) => (
                    <tr key={item.id}>
                      <td style={{ whiteSpace: 'nowrap' }}>{fmtDate(item.timestamp.slice(0, 10))} {item.timestamp.slice(11, 19)}</td>
                      <td style={{ textAlign: 'left' }}>{item.user_email ?? '—'}</td>
                      <td style={{ textAlign: 'left' }}>{item.module}</td>
                      <td style={{ textAlign: 'left', fontFamily: 'var(--mono)', fontSize: 10.5 }}>{item.record_id}</td>
                      <td style={{ textAlign: 'left' }}>{item.field ?? '—'}</td>
                      <td style={{ textAlign: 'left', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis' }}>{item.old_value ?? '—'}</td>
                      <td style={{ textAlign: 'left', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis' }}>{item.new_value ?? '—'}</td>
                      <td>
                        <span className={`tag ${item.action === 'delete' ? 'denied' : item.action === 'create' ? 'done' : 'ongoing'}`}>{item.action}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="toolbar" style={{ padding: 10 }}>
                <div className="hint">
                  {offset + 1}–{Math.min(offset + limit, data.total)} / {data.total}
                </div>
                <div className="spacer" />
                <button className="btn sm" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - limit))}>
                  ← Trước
                </button>
                <button className="btn sm" disabled={offset + limit >= data.total} onClick={() => setOffset(offset + limit)}>
                  Sau →
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
