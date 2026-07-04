import { beforeEach, describe, expect, it, vi } from 'vitest';

const requestUse = vi.hoisted(() => vi.fn());
const responseUse = vi.hoisted(() => vi.fn());
const create = vi.hoisted(() => vi.fn());

vi.mock('axios', () => ({
  default: { create },
}));

describe('apiClient csrf interceptor', () => {
  const assignMock = vi.fn();

  beforeEach(() => {
    vi.resetModules();
    requestUse.mockReset();
    responseUse.mockReset();
    create.mockReset();
    create.mockReturnValue({
      interceptors: {
        request: { use: requestUse },
        response: { use: responseUse },
      },
    });
    document.cookie = 'dsa_csrf_token=; Max-Age=0; path=/';
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: {
        pathname: '/',
        search: '',
        assign: assignMock,
      },
    });
    assignMock.mockReset();
  });

  it('adds csrf header to unsafe requests when csrf cookie exists', async () => {
    document.cookie = 'dsa_csrf_token=csrf-123; path=/';

    await import('../index');

    expect(requestUse).toHaveBeenCalledTimes(1);
    const interceptor = requestUse.mock.calls[0][0];
    const config = interceptor({ method: 'post', headers: {} });

    expect(config.headers['X-DSA-CSRF']).toBe('csrf-123');
  });

  it('does not redirect ordinary platform entry to admin login on platform 401 responses', async () => {
    await import('../index');

    const onRejected = responseUse.mock.calls[0][1];
    await expect(onRejected({
      response: { status: 401, data: { detail: 'not authenticated' } },
      config: { url: '/api/v1/platform/account' },
    })).rejects.toBeTruthy();

    expect(assignMock).not.toHaveBeenCalled();
  });

  it('redirects admin-only routes to admin login on 401 responses', async () => {
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: {
        pathname: '/admin',
        search: '',
        assign: assignMock,
      },
    });

    await import('../index');

    const onRejected = responseUse.mock.calls[0][1];
    await expect(onRejected({
      response: { status: 401, data: { detail: 'not authenticated' } },
      config: { url: '/api/v1/platform/admin/summary' },
    })).rejects.toBeTruthy();

    expect(assignMock).toHaveBeenCalledWith('/login?redirect=%2Fadmin');
  });
});
