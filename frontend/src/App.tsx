import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Navigate, Route, BrowserRouter as Router, Routes } from 'react-router-dom';
import Layout from './components/Layout';
import ProtectedRoute from './components/ProtectedRoute';
import { AuthProvider } from './lib/auth';
import { ToastProvider } from './lib/toast';
import BondDetailPage from './pages/BondDetailPage';
import BondsListPage from './pages/BondsListPage';
import ControlPage from './pages/ControlPage';
import LoginPage from './pages/LoginPage';
import PlaceholderPage from './pages/PlaceholderPage';
import UsersPage from './pages/UsersPage';

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <Router>
          <AuthProvider>
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route
                path="/"
                element={
                  <ProtectedRoute>
                    <Layout />
                  </ProtectedRoute>
                }
              >
                <Route index element={<PlaceholderPage title="Dashboard" phase="Phase 4" />} />
                <Route path="control" element={<ControlPage />} />
                <Route path="contracts" element={<PlaceholderPage title="Sổ Hợp đồng" phase="Phase 4" />} />
                <Route path="ir" element={<PlaceholderPage title="Dịch vụ IR" phase="Phase 4" />} />
                <Route path="weekly" element={<PlaceholderPage title="Theo dõi DM tuần" phase="Phase 5" />} />
                <Route path="bonds" element={<BondsListPage />} />
                <Route path="bonds/:bondId" element={<BondDetailPage />} />
                <Route path="audit" element={<PlaceholderPage title="Audit Log" phase="Phase 6" />} />
                <Route
                  path="users"
                  element={
                    <ProtectedRoute roles={['Admin']}>
                      <UsersPage />
                    </ProtectedRoute>
                  }
                />
              </Route>
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </AuthProvider>
        </Router>
      </ToastProvider>
    </QueryClientProvider>
  );
}
