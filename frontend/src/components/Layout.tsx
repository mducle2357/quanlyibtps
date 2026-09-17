import { useState } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../lib/auth';

const SYSTEM_VIEWS = [
  { id: 'dashboard', name: 'Dashboard', ic: 'DB' },
  { id: 'control', name: 'Control', ic: 'CT' },
  { id: 'contracts', name: 'Sổ Hợp đồng', ic: 'HĐ' },
  { id: 'ir', name: 'Dịch vụ IR', ic: 'IR' },
  { id: 'weekly', name: 'Theo dõi DM tuần', ic: 'DM' },
];

export default function Layout() {
  const [collapsed, setCollapsed] = useState(false);
  const { user, logout } = useAuth();
  const navigate = useNavigate();

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
          <div className="navgroup">Bond &amp; Quản trị</div>
          <NavLink to="/bonds" className={({ isActive }) => 'navitem' + (isActive ? ' active' : '')} title="Danh sách trái phiếu">
            <span className="ic">TP</span>
            <span className="lbl">Danh sách Trái phiếu</span>
          </NavLink>
          {user?.roles.includes('Admin') && (
            <>
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
            <span>{user?.full_name} · {user?.roles.join(', ')}</span>
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
