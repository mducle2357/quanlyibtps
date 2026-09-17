import type { ReactNode } from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../lib/auth';

export default function ProtectedRoute({ children, roles }: { children: ReactNode; roles?: string[] }) {
  const { status, hasRole } = useAuth();

  if (status === 'loading') return <div className="empty">Đang tải…</div>;
  if (status === 'unauthenticated') return <Navigate to="/login" replace />;
  if (roles && !hasRole(...roles)) return <div className="empty">Bạn không có quyền truy cập trang này.</div>;
  return <>{children}</>;
}
