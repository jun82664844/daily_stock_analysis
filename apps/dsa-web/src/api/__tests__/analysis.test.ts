import { beforeEach, describe, expect, it, vi } from 'vitest';
import { analysisApi } from '../analysis';

const post = vi.hoisted(() => vi.fn());

vi.mock('../index', () => ({
  default: { post },
}));

describe('analysisApi', () => {
  beforeEach(() => {
    post.mockReset();
  });

  it('serializes stock analysis requests with fast depth by default', async () => {
    post.mockResolvedValueOnce({
      data: {
        task_id: 'task-1',
        status: 'pending',
        analysis_depth: 'fast',
      },
    });

    const result = await analysisApi.analyzeAsync({ stockCode: 'AAPL' });

    expect(post).toHaveBeenCalledWith(
      '/api/v1/analysis/analyze',
      expect.objectContaining({
        stock_code: 'AAPL',
        report_type: 'detailed',
        async_mode: true,
        analysis_depth: 'fast',
      }),
      expect.any(Object),
    );
    expect('accepted' in result).toBe(false);
    if ('accepted' in result) {
      throw new Error('expected a single task response');
    }
    expect(result.analysisDepth).toBe('fast');
  });

  it('serializes explicit deep analysis depth', async () => {
    post.mockResolvedValueOnce({
      data: {
        task_id: 'task-2',
        status: 'pending',
        analysis_depth: 'deep',
      },
    });

    await analysisApi.analyzeAsync({
      stockCode: '600519',
      reportType: 'detailed',
      analysisDepth: 'deep',
    });

    expect(post).toHaveBeenCalledWith(
      '/api/v1/analysis/analyze',
      expect.objectContaining({
        stock_code: '600519',
        report_type: 'detailed',
        analysis_depth: 'deep',
      }),
      expect.any(Object),
    );
  });

  it('serializes user-owned API key mode', async () => {
    post.mockResolvedValueOnce({
      data: {
        task_id: 'task-3',
        status: 'pending',
      },
    });

    await analysisApi.analyzeAsync({
      stockCode: '600519',
      apiKeyMode: 'user',
    });

    expect(post).toHaveBeenCalledWith(
      '/api/v1/analysis/analyze',
      expect.objectContaining({
        stock_code: '600519',
        api_key_mode: 'user',
      }),
      expect.any(Object),
    );
  });

  it('serializes local model API key mode', async () => {
    post.mockResolvedValueOnce({
      data: {
        task_id: 'task-local',
        status: 'pending',
      },
    });

    await analysisApi.analyzeAsync({
      stockCode: '600519',
      apiKeyMode: 'local',
    });

    expect(post).toHaveBeenCalledWith(
      '/api/v1/analysis/analyze',
      expect.objectContaining({
        stock_code: '600519',
        api_key_mode: 'local',
      }),
      expect.any(Object),
    );
  });
});
