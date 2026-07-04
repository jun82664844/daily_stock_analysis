import { fireEvent, render, screen } from '@testing-library/react';
import { lazy } from 'react';
import type React from 'react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { buildRouteRecoveryUrl, RouteErrorBoundary, RouteOutletBoundary } from '../RouteBoundary';
import { Shell } from '../Shell';

vi.mock('../../../contexts/AuthContext', () => ({
  useAuth: () => ({
    authEnabled: false,
    logout: vi.fn().mockResolvedValue(undefined),
  }),
}));

vi.mock('../../../stores/agentChatStore', () => {
  const state = { completionBadge: false };

  return {
    useAgentChatStore: (selector?: (value: typeof state) => unknown) => (
      selector ? selector(state) : state
    ),
  };
});

describe('RouteOutletBoundary', () => {
  it('builds a cache-busting route recovery URL for stale frontend bundles', () => {
    expect(buildRouteRecoveryUrl('http://127.0.0.1:8018/?foo=bar#panel', 12345)).toBe(
      'http://127.0.0.1:8018/?foo=bar&dsa_route_reload=12345#panel',
    );
  });

  it('auto reloads once when a lazy route chunk cannot be fetched after a build swap', async () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => undefined);
    const reloadSpy = vi.fn();
    sessionStorage.clear();
    const BrokenChunkRoute = () => {
      throw new TypeError(
        'Failed to fetch dynamically imported module: http://127.0.0.1:8018/assets/HomePage-old.js',
      );
    };

    try {
      render(
        <RouteErrorBoundary
          resetKey="/"
          fullPage={false}
          reloadPage={reloadSpy}
          text={{
            title: '加载页面失败',
            description: '页面版本已更新。',
            reload: '重新加载页面',
            backHome: '返回首页',
          }}
        >
          <BrokenChunkRoute />
        </RouteErrorBoundary>,
      );

      expect(await screen.findByRole('heading', { name: '加载页面失败' })).toBeInTheDocument();
      expect(reloadSpy).toHaveBeenCalledTimes(1);
    } finally {
      sessionStorage.clear();
      consoleError.mockRestore();
    }
  });

  it('catches rejected lazy route imports inside the shell and resets on navigation', async () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => undefined);
    const BrokenLazyRoute = lazy(() => (
      Promise.reject(new Error('chunk load failed')) as Promise<{ default: React.ComponentType }>
    ));

    try {
      render(
        <MemoryRouter initialEntries={['/chat']}>
          <Routes>
            <Route
              element={(
                <Shell>
                  <RouteOutletBoundary />
                </Shell>
              )}
            >
              <Route path="/chat" element={<BrokenLazyRoute />} />
              <Route path="/portfolio" element={<div data-testid="portfolio-page">Portfolio</div>} />
            </Route>
          </Routes>
        </MemoryRouter>,
      );

      expect(screen.getByRole('navigation', { name: '主导航' })).toBeInTheDocument();
      expect(await screen.findByRole('heading', { name: '页面加载失败' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '重新加载页面' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '返回首页' })).toBeInTheDocument();

      fireEvent.click(screen.getByRole('link', { name: '持仓' }));

      expect(await screen.findByTestId('portfolio-page')).toBeInTheDocument();
      expect(screen.queryByRole('heading', { name: '页面加载失败' })).not.toBeInTheDocument();
    } finally {
      consoleError.mockRestore();
    }
  });
});
