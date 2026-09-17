import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useMemo, useState } from 'react';
import Modal from '../components/Modal';
import { api, apiErrorMessage, isConflictError } from '../lib/api';
import { useAuth } from '../lib/auth';
import { fmtNumber } from '../lib/format';
import { monthGroups, monthShortLabel, monthsBetween } from '../lib/timeline';
import { useToast } from '../lib/toast';

interface IRJob {
  id: string;
  name: string;
  version: number;
  monthly_values: Record<string, { revenue: number; version: number }>;
}
interface TimelineRange {
  start: string;
  end: string;
}

export default function IRPage() {
  const toast = useToast();
  const qc = useQueryClient();
  const { hasRole } = useAuth();
  const canEdit = hasRole('Admin', 'Manager', 'Staff');
  const canDelete = hasRole('Admin', 'Manager');

  const { data: timeline } = useQuery<TimelineRange>({
    queryKey: ['timeline', 'monthly'],
    queryFn: async () => (await api.get('/system/timeline/monthly')).data,
  });
  const { data: jobs, isLoading } = useQuery<IRJob[]>({
    queryKey: ['ir-jobs'],
    queryFn: async () => (await api.get('/ir-jobs')).data,
  });
  const months = useMemo(() => (timeline ? monthsBetween(timeline.start, timeline.end) : []), [timeline]);
  const groups = useMemo(() => monthGroups(months), [months]);
  const [showAdd, setShowAdd] = useState(false);
  const [newName, setNewName] = useState('');

  const totalsByMonth = useMemo(() => {
    const t: Record<string, number> = {};
    months.forEach((m) => {
      t[m] = (jobs ?? []).reduce((s, j) => s + (j.monthly_values[m]?.revenue ?? 0), 0);
    });
    return t;
  }, [jobs, months]);

  async function saveCell(job: IRJob, monthKey: string, value: string) {
    const num = value.trim() === '' ? null : Number(value.replace(',', '.'));
    if (num === null || Number.isNaN(num)) return;
    const cell = job.monthly_values[monthKey];
    try {
      await api.put(`/ir-jobs/${job.id}/monthly/${monthKey}`, { revenue: num, version: cell?.version ?? null });
      qc.invalidateQueries({ queryKey: ['ir-jobs'] });
    } catch (err) {
      if (isConflictError(err)) toast(apiErrorMessage(err), 'err');
      else toast(apiErrorMessage(err), 'err');
    }
  }

  async function renameJob(job: IRJob) {
    const name = window.prompt('Tên công việc mới:', job.name);
    if (!name || name === job.name) return;
    try {
      await api.patch(`/ir-jobs/${job.id}`, { name, version: job.version });
      qc.invalidateQueries({ queryKey: ['ir-jobs'] });
    } catch (err) {
      toast(apiErrorMessage(err), 'err');
    }
  }

  async function deleteJob(job: IRJob) {
    if (!window.confirm(`Xóa công việc "${job.name}"?`)) return;
    try {
      await api.delete(`/ir-jobs/${job.id}`);
      qc.invalidateQueries({ queryKey: ['ir-jobs'] });
    } catch (err) {
      toast(apiErrorMessage(err), 'err');
    }
  }

  async function addJob() {
    try {
      await api.post('/ir-jobs', { name: newName.trim() });
      setShowAdd(false);
      setNewName('');
      qc.invalidateQueries({ queryKey: ['ir-jobs'] });
    } catch (err) {
      toast(apiErrorMessage(err), 'err');
    }
  }

  return (
    <div>
      <div className="toolbar">
        <div className="hint">Đơn vị: triệu đồng</div>
        <div className="spacer" />
        {canEdit && (
          <button className="btn primary" onClick={() => setShowAdd(true)}>
            + Add Job
          </button>
        )}
      </div>
      <div className="panel">
        <div className="body flush">
          {isLoading ? (
            <div className="empty">Đang tải…</div>
          ) : !jobs?.length ? (
            <div className="empty">Chưa có công việc IR nào.</div>
          ) : (
            <div className="tblwrap">
              <table className="grid">
                <thead>
                  <tr className="r1">
                    <th className="s1" rowSpan={2}></th>
                    <th className="s2" rowSpan={2} style={{ textAlign: 'left' }}>
                      Công việc
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
                  {jobs.map((job, i) => (
                    <tr key={job.id}>
                      <td className="s1">{i + 1}</td>
                      <td className="s2">
                        {job.name}
                        {canEdit && (
                          <button className="btn sm" style={{ marginLeft: 6 }} onClick={() => renameJob(job)}>
                            ✎
                          </button>
                        )}
                        {canDelete && (
                          <button className="btn sm" style={{ marginLeft: 4 }} onClick={() => deleteJob(job)}>
                            ×
                          </button>
                        )}
                      </td>
                      {months.map((m) => {
                        const cell = job.monthly_values[m];
                        return (
                          <td key={m}>
                            <input
                              className="cell"
                              defaultValue={cell ? String(cell.revenue) : ''}
                              disabled={!canEdit}
                              onBlur={(e) => {
                                if (e.target.value !== (cell ? String(cell.revenue) : '')) saveCell(job, m, e.target.value);
                              }}
                            />
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                  <tr className="total">
                    <td className="s1"></td>
                    <td className="s2">Doanh thu từ IR</td>
                    {months.map((m) => (
                      <td key={m} className="calc">
                        {fmtNumber(totalsByMonth[m], 2)}
                      </td>
                    ))}
                  </tr>
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
      {showAdd && (
        <Modal title="Add Job" onCancel={() => setShowAdd(false)} onOk={addJob} okText="Tạo" okDisabled={!newName.trim()}>
          <div className="field">
            <label>Tên công việc</label>
            <input value={newName} onChange={(e) => setNewName(e.target.value)} autoFocus />
          </div>
        </Modal>
      )}
    </div>
  );
}
