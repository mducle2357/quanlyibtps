import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { api, apiErrorMessage } from '../lib/api';
import { useToast } from '../lib/toast';

interface UserRow {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  roles: string[];
  must_reset_password: boolean;
}

const ALL_ROLES = ['Admin', 'Manager', 'Staff', 'Viewer'];

export default function UsersPage() {
  const toast = useToast();
  const qc = useQueryClient();
  const { data: users, isLoading } = useQuery<UserRow[]>({
    queryKey: ['users'],
    queryFn: async () => (await api.get('/users')).data,
  });

  const [form, setForm] = useState({ email: '', full_name: '', password: '', roles: ['Staff'] });
  const [busy, setBusy] = useState(false);

  async function createUser() {
    setBusy(true);
    try {
      await api.post('/users', form);
      toast('Đã tạo người dùng', 'ok');
      setForm({ email: '', full_name: '', password: '', roles: ['Staff'] });
      qc.invalidateQueries({ queryKey: ['users'] });
    } catch (err) {
      toast(apiErrorMessage(err, 'Không tạo được người dùng.'), 'err');
    } finally {
      setBusy(false);
    }
  }

  async function toggleActive(u: UserRow) {
    try {
      await api.patch(`/users/${u.id}/active`, { is_active: !u.is_active });
      qc.invalidateQueries({ queryKey: ['users'] });
    } catch (err) {
      toast(apiErrorMessage(err), 'err');
    }
  }

  async function resetPassword(u: UserRow) {
    const pw = window.prompt(`Mật khẩu mới cho ${u.email} (tối thiểu 8 ký tự):`);
    if (!pw) return;
    try {
      await api.post(`/users/${u.id}/reset-password`, { new_password: pw });
      toast('Đã đặt lại mật khẩu', 'ok');
    } catch (err) {
      toast(apiErrorMessage(err), 'err');
    }
  }

  return (
    <div>
      <div className="panel">
        <header>
          <h2>Tạo người dùng mới</h2>
        </header>
        <div className="body">
          <div className="infogrid">
            <div className="field">
              <label>Email</label>
              <input value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
            </div>
            <div className="field">
              <label>Họ tên</label>
              <input value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
            </div>
            <div className="field">
              <label>Mật khẩu tạm</label>
              <input type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
            </div>
            <div className="field">
              <label>Role</label>
              <select
                value={form.roles[0]}
                onChange={(e) => setForm({ ...form, roles: [e.target.value] })}
              >
                {ALL_ROLES.map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <button className="btn primary" style={{ marginTop: 12 }} disabled={busy} onClick={createUser}>
            + Thêm người dùng
          </button>
        </div>
      </div>

      <div className="panel">
        <header>
          <h2>Danh sách người dùng</h2>
        </header>
        <div className="body flush">
          {isLoading ? (
            <div className="empty">Đang tải…</div>
          ) : (
            <div className="tblwrap">
              <table className="grid" style={{ width: '100%' }}>
                <thead>
                  <tr className="r1">
                    <th style={{ textAlign: 'left' }}>Email</th>
                    <th style={{ textAlign: 'left' }}>Họ tên</th>
                    <th>Role</th>
                    <th>Trạng thái</th>
                    <th>Hành động</th>
                  </tr>
                </thead>
                <tbody>
                  {users?.map((u) => (
                    <tr key={u.id}>
                      <td style={{ textAlign: 'left' }}>{u.email}</td>
                      <td style={{ textAlign: 'left' }}>{u.full_name}</td>
                      <td style={{ textAlign: 'left' }}>{u.roles.join(', ')}</td>
                      <td>
                        <span className={`tag ${u.is_active ? 'done' : 'denied'}`}>{u.is_active ? 'Active' : 'Disabled'}</span>
                      </td>
                      <td style={{ textAlign: 'left' }}>
                        <button className="btn sm" onClick={() => toggleActive(u)}>
                          {u.is_active ? 'Vô hiệu hóa' : 'Kích hoạt'}
                        </button>{' '}
                        <button className="btn sm" onClick={() => resetPassword(u)}>
                          Đặt lại mật khẩu
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
