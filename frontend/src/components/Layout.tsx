import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { api } from '../lib/api';
import { useAuth } from '../lib/auth';

const SYSTEM_VIEWS = [
  { id: 'dashboard', name: 'Dashboard', ic: 'DB' },
  { id: 'control', name: 'Control', ic: 'CT' },
  { id: 'contracts', name: 'Sổ Hợp đồng', ic: 'HĐ' },
  { id: 'ir', name: 'Dịch vụ IR', ic: 'IR' },
  { id: 'weekly', name: 'Theo dõi DM tuần', ic: 'DM' },
];

interface BondNavItem {
  id: string;
  code: string;
  status_key: 'pre' | 'active' | 'matured';
}

export default function Layout() {
  const [collapsed, setCollapsed] = useState(false);
  const [search, setSearch] = useState('');
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const { data: bonds } = useQuery<BondNavItem[]>({
    queryKey: ['bonds'],
    queryFn: async () => (await api.get('/bonds')).data,
  });
  const filtered = (bonds ?? []).filter((b) => !search || b.code.toLowerCase().includes(search.toLowerCase()));
  const badgeFor = (k: string) => (k === 'active' ? 'A' : k === 'matured' ? 'M' : 'P');

  return (
    <div id="app">
      <aside id="sidebar" className={collapsed ? 'collapsed' : ''}>
        <div className="brand">
          <div className="mark">IB</div>
          <div className="txt">
            <b>TPS · Investment Banking</b>
            <span>Operating Dashboard</span>
          </div>
        </div>
        <div className="navsearch">
          <input placeholder="Tìm trái phiếu…" value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        <div className="navlist">
          <div className="navgroup">Hệ thống</div>
          {SYSTEM_VIEWS.map((v) => (
            <NavLink
              key={v.id}
              to={`/${v.id === 'dashboard' ? '' : v.id}`}
              end
              className={({ isActive }) => 'navitem' + (isActive ? ' active' : '')}
              title={v.name}
            >
              <span className="ic">{v.ic}</span>
              <span className="lbl">{v.name}</span>
            </NavLink>
          ))}
          <div className="navgroup">Trái phiếu ({bonds?.length ?? 0})</div>
          {filtered.length === 0 && (
            <div style={{ padding: '6px 14px', fontSize: 11, color: '#7d97b5' }} className="hide-c">
              {search ? 'Không có mã khớp' : 'Chưa có trái phiếu'}
            </div>
          )}
          {filtered.map((b) => (
            <NavLink
              key={b.id}
              to={`/bonds/${b.id}`}
              className={({ isActive }) => 'navitem' + (isActive ? ' active' : '')}
              title={b.code}
            >
              <span className="ic">TP</span>
              <span className="lbl">{b.code}</span>
              <span className="badge">{badgeFor(b.status_key)}</span>
            </NavLink>
          ))}
          {user?.roles.includes('Admin') && (
            <>
              <div className="navgroup">Quản trị</div>
              <NavLink to="/audit" className={({ isActive }) => 'navitem' + (isActive ? ' active' : '')} title="Audit Log">
                <span className="ic">AL</span>
                <span className="lbl">Audit Log</span>
              </NavLink>
              <NavLink to="/users" className={({ isActive }) => 'navitem' + (isActive ? ' active' : '')} title="Người dùng">
                <span className="ic">US</span>
                <span className="lbl">Người dùng</span>
              </NavLink>
            </>
          )}
        </div>
        <div className="navfoot">
          <div className="sv">
            <span className="dot" />
            <span>
              {user?.full_name} · {user?.roles.join(', ')}
            </span>
          </div>
          <button
            className="backlink"
            style={{ marginTop: 6 }}
            onClick={async () => {
              await logout();
              navigate('/login');
            }}
          >
            Đăng xuất
          </button>
        </div>
      </aside>
      <main id="main">
        <div className="topbar">
          <button className="btn icon" onClick={() => setCollapsed((c) => !c)} title="Thu gọn thanh điều hướng">
            ☰
          </button>
          <div>
            <h1>TPS IB Operating Dashboard</h1>
          </div>
          <div className="spacer" />
        </div>
        <div className="content">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
