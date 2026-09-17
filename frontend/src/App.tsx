import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Navigate, Route, BrowserRouter as Router, Routes } from 'react-router-dom';
import Layout from './components/Layout';
import ProtectedRoute from './components/ProtectedRoute';
import { AuthProvider } from './lib/auth';
import { ToastProvider } from './lib/toast';
import AuditLogPage from './pages/AuditLogPage';
import BondDetailPage from './pages/BondDetailPage';
import BondsListPage from './pages/BondsListPage';
import ContractsPage from './pages/ContractsPage';
import ControlPage from './pages/ControlPage';
import DashboardPage from './pages/DashboardPage';
import IRPage from './pages/IRPage';
import LoginPage from './pages/LoginPage';
import UsersPage from './pages/UsersPage';
import WeeklyPage from './pages/WeeklyPage';

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
                <Route index element={<DashboardPage />} />
                <Route path="control" element={<ControlPage />} />
                <Route path="contracts" element={<ContractsPage />} />
                <Route path="ir" element={<IRPage />} />
                <Route path="weekly" element={<WeeklyPage />} />
                <Route path="bonds" element={<BondsListPage />} />
                <Route path="bonds/:bondId" element={<BondDetailPage />} />
                <Route
                  path="audit"
                  element={
                    <ProtectedRoute roles={['Admin', 'Manager']}>
                      <AuditLogPage />
                    </ProtectedRoute>
                  }
                />
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
