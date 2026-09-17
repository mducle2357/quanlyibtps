import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import Modal from '../components/Modal';
import { api, apiErrorMessage } from '../lib/api';
import { useAuth } from '../lib/auth';
import { toRoman } from '../lib/format';
import { useToast } from '../lib/toast';

interface ContractRow {
  id: string;
  contract_date: string | null;
  title: string;
  contract_number: string | null;
  status: string;
  parties: string | null;
  version: number;
}
interface Project {
  id: string;
  roman_index: number;
  name: string;
  version: number;
  contracts: ContractRow[];
}

const STATUSES = ['Dự thảo', 'Ongoing', 'Done', 'Denied'];
const STATUS_CLASS: Record<string, string> = { 'Dự thảo': 'draft', Ongoing: 'ongoing', Done: 'done', Denied: 'denied' };

export default function ContractsPage() {
  const toast = useToast();
  const qc = useQueryClient();
  const { hasRole } = useAuth();
  const canEdit = hasRole('Admin', 'Manager', 'Staff');
  const canDelete = hasRole('Admin', 'Manager');

  const { data: projects, isLoading } = useQuery<Project[]>({
    queryKey: ['contract-projects'],
    queryFn: async () => (await api.get('/contracts/projects')).data,
  });

  const [showAddProject, setShowAddProject] = useState(false);
  const [newProjectName, setNewProjectName] = useState('');

  const refetch = () => qc.invalidateQueries({ queryKey: ['contract-projects'] });

  async function addProject() {
    try {
      await api.post('/contracts/projects', { name: newProjectName.trim() });
      setShowAddProject(false);
      setNewProjectName('');
      refetch();
    } catch (err) {
      toast(apiErrorMessage(err), 'err');
    }
  }

  async function renameProject(p: Project) {
    const name = window.prompt('Tên dự án/khách hàng mới:', p.name);
    if (!name || name === p.name) return;
    try {
      await api.patch(`/contracts/projects/${p.id}`, { name, version: p.version });
      refetch();
    } catch (err) {
      toast(apiErrorMessage(err), 'err');
    }
  }

  async function deleteProject(p: Project) {
    if (!window.confirm(`Xóa dự án "${p.name}" và toàn bộ hợp đồng bên trong?`)) return;
    try {
      await api.delete(`/contracts/projects/${p.id}`);
      refetch();
    } catch (err) {
      toast(apiErrorMessage(err), 'err');
    }
  }

  async function addContract(projectId: string) {
    try {
      await api.post(`/contracts/projects/${projectId}/contracts`, { title: '', status: 'Dự thảo' });
      refetch();
    } catch (err) {
      toast(apiErrorMessage(err), 'err');
    }
  }

  if (isLoading) return <div className="empty">Đang tải…</div>;

  return (
    <div>
      <div className="toolbar">
        <div className="hint">STT Level 1 = số La Mã (dự án/khách hàng/bond); Level 2 = số thứ tự hợp đồng.</div>
        <div className="spacer" />
        {canEdit && (
          <button className="btn primary" onClick={() => setShowAddProject(true)}>
            + Thêm dự án/khách hàng
          </button>
        )}
      </div>

      {!projects?.length ? (
        <div className="empty">Chưa có dự án nào.</div>
      ) : (
        projects.map((p) => (
          <div className="panel" key={p.id}>
            <header>
              <h2>
                {toRoman(p.roman_index)}. {p.name}
              </h2>
              <div className="spacer" />
              {canEdit && (
                <button className="btn sm" onClick={() => renameProject(p)}>
                  Sửa tên
                </button>
              )}
              {canEdit && (
                <button className="btn sm" onClick={() => addContract(p.id)} style={{ marginLeft: 6 }}>
                  + Thêm hợp đồng
                </button>
              )}
              {canDelete && (
                <button className="btn sm danger" onClick={() => deleteProject(p)} style={{ marginLeft: 6 }}>
                  Xóa dự án
                </button>
              )}
            </header>
            <div className="body flush">
              {!p.contracts.length ? (
                <div className="empty">Chưa có hợp đồng nào trong dự án này.</div>
              ) : (
                <table className="grid" style={{ width: '100%' }}>
                  <thead>
                    <tr className="r1">
                      <th>STT</th>
                      <th style={{ minWidth: 100 }}>Ngày</th>
                      <th style={{ textAlign: 'left', minWidth: 220 }}>Đầu mục dự án/Tên hợp đồng</th>
                      <th style={{ minWidth: 120 }}>Số hợp đồng</th>
                      <th style={{ minWidth: 110 }}>Tình trạng</th>
                      <th style={{ textAlign: 'left', minWidth: 180 }}>Các bên ký</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {p.contracts.map((c, i) => (
                      <ContractRowEditor key={c.id} projectId={p.id} contract={c} idx={`${toRoman(p.roman_index)}/${i + 1}`} canEdit={canEdit} canDelete={canDelete} onSaved={refetch} />
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        ))
      )}

      {showAddProject && (
        <Modal title="Thêm dự án/khách hàng" onCancel={() => setShowAddProject(false)} onOk={addProject} okText="Tạo" okDisabled={!newProjectName.trim()}>
          <div className="field">
            <label>Tên dự án/khách hàng</label>
            <input value={newProjectName} onChange={(e) => setNewProjectName(e.target.value)} autoFocus />
          </div>
        </Modal>
      )}
    </div>
  );
}

function ContractRowEditor({
  projectId,
  contract,
  idx,
  canEdit,
  canDelete,
  onSaved,
}: {
  projectId: string;
  contract: ContractRow;
  idx: string;
  canEdit: boolean;
  canDelete: boolean;
  onSaved: () => void;
}) {
  const toast = useToast();
  const [form, setForm] = useState(contract);
  useEffect(() => setForm(contract), [contract]);
  const [dirty, setDirty] = useState(false);

  function set<K extends keyof ContractRow>(k: K, v: ContractRow[K]) {
    setForm((f) => ({ ...f, [k]: v }));
    setDirty(true);
  }

  async function save() {
    try {
      await api.patch(`/contracts/projects/${projectId}/contracts/${contract.id}`, {
        contract_date: form.contract_date || null,
        title: form.title,
        contract_number: form.contract_number || null,
        status: form.status,
        parties: form.parties || null,
        version: contract.version,
      });
      setDirty(false);
      onSaved();
    } catch (err) {
      toast(apiErrorMessage(err), 'err');
    }
  }

  async function remove() {
    if (!window.confirm('Xóa hợp đồng này?')) return;
    try {
      await api.delete(`/contracts/projects/${projectId}/contracts/${contract.id}`);
      onSaved();
    } catch (err) {
      toast(apiErrorMessage(err), 'err');
    }
  }

  return (
    <tr>
      <td>{idx}</td>
      <td>
        <input type="date" className="cell" value={form.contract_date ?? ''} disabled={!canEdit} onChange={(e) => set('contract_date', e.target.value)} />
      </td>
      <td style={{ textAlign: 'left' }}>
        <input className="cell txt" value={form.title} disabled={!canEdit} onChange={(e) => set('title', e.target.value)} />
      </td>
      <td>
        <input className="cell txt" value={form.contract_number ?? ''} disabled={!canEdit} onChange={(e) => set('contract_number', e.target.value)} />
      </td>
      <td>
        {canEdit ? (
          <select value={form.status} onChange={(e) => set('status', e.target.value)}>
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        ) : (
          <span className={`tag ${STATUS_CLASS[form.status]}`}>{form.status}</span>
        )}
      </td>
      <td style={{ textAlign: 'left' }}>
        <input className="cell txt" value={form.parties ?? ''} disabled={!canEdit} onChange={(e) => set('parties', e.target.value)} />
      </td>
      <td style={{ textAlign: 'left', whiteSpace: 'nowrap' }}>
        {canEdit && dirty && (
          <button className="btn sm primary" onClick={save}>
            Lưu
          </button>
        )}
        {canDelete && (
          <button className="btn sm" style={{ marginLeft: 4 }} onClick={remove}>
            ×
          </button>
        )}
      </td>
    </tr>
  );
}
