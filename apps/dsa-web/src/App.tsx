import type React from 'react';
import { lazy, useEffect } from 'react';
import { BrowserRouter as Router, Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { ApiErrorAlert, Shell } from './components/common';
import {
  PageLoadingFallback,
  RouteOutletBoundary,
  StandaloneRouteBoundary,
} from './components/layout/RouteBoundary';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { UiLanguageProvider, useUiLanguage } from './contexts/UiLanguageContext';
import { useAgentChatStore } from './stores/agentChatStore';
import './App.css';

const HomePage = lazy(() => import('./pages/HomePage'));
const BacktestPage = lazy(() => import('./pages/BacktestPage'));
const SettingsPage = lazy(() => import('./pages/SettingsPage'));
const LoginPage = lazy(() => import('./pages/LoginPage'));
const NotFoundPage = lazy(() => import('./pages/NotFoundPage'));
const ChatPage = lazy(() => import('./pages/ChatPage'));
const PortfolioPage = lazy(() => import('./pages/PortfolioPage'));
const DecisionSignalsPage = lazy(() => import('./pages/DecisionSignalsPage'));
const AlertsPage = lazy(() => import('./pages/AlertsPage'));
const TokenUsagePage = lazy(() => import('./pages/TokenUsagePage'));
const AdminPage = lazy(() => import('./pages/AdminPage'));
const AccountPage = lazy(() => import('./pages/AccountPage'));
const StockScreeningPage = lazy(() => import('./pages/StockScreeningPage'));
const ResearchWorkflowsPage = lazy(() => import('./pages/ResearchWorkflowsPage'));
const MarketWorkspacePage = lazy(() => import('./pages/MarketWorkspacePage'));

const ADMIN_ONLY_ROUTE_PREFIXES = ['/admin', '/settings'];

function isAdminOnlyRoute(pathname: string): boolean {
  return ADMIN_ONLY_ROUTE_PREFIXES.some((routePath) => (
    pathname === routePath || pathname.startsWith(`${routePath}/`)
  ));
}

const AppContent: React.FC = () => {
  const location = useLocation();
  const { authEnabled, loggedIn, isLoading, loadError, refreshStatus } = useAuth();
  const { t } = useUiLanguage();

  useEffect(() => {
    useAgentChatStore.getState().setCurrentRoute(location.pathname);
  }, [location.pathname]);

  if (isLoading) {
    return <PageLoadingFallback />;
  }

  if (loadError) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-base px-4">
        <div className="w-full max-w-lg">
          <ApiErrorAlert error={loadError} />
        </div>
        <button
          type="button"
          className="btn-primary"
          onClick={() => void refreshStatus()}
        >
          {t('common.retry')}
        </button>
      </div>
    );
  }

  if (authEnabled && !loggedIn && location.pathname === '/login') {
    return (
      <StandaloneRouteBoundary>
        <LoginPage />
      </StandaloneRouteBoundary>
    );
  }

  if (authEnabled && !loggedIn && isAdminOnlyRoute(location.pathname)) {
    const redirect = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/login?redirect=${redirect}`} replace />;
  }

  if (location.pathname === '/login') {
    return <Navigate to="/" replace />;
  }

  return (
    <Routes>
      <Route
        element={(
          <Shell>
            <RouteOutletBoundary />
          </Shell>
        )}
      >
        <Route path="/" element={<HomePage />} />
        <Route path="/chat" element={<ChatPage />} />
        <Route path="/portfolio" element={<PortfolioPage />} />
        <Route path="/decision-signals" element={<DecisionSignalsPage />} />
        <Route path="/screening" element={<StockScreeningPage />} />
        <Route path="/research" element={<ResearchWorkflowsPage />} />
        <Route path="/market" element={<MarketWorkspacePage />} />
        <Route path="/backtest" element={<BacktestPage />} />
        <Route path="/alerts" element={<AlertsPage />} />
        <Route path="/usage" element={<TokenUsagePage />} />
        <Route path="/account" element={<AccountPage />} />
        <Route path="/admin" element={<AdminPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
};

const App: React.FC = () => {
  return (
    <UiLanguageProvider>
      <Router>
        <AuthProvider>
          <AppContent />
        </AuthProvider>
      </Router>
    </UiLanguageProvider>
  );
};

export default App;
