import { beforeEach, describe, expect, it, vi } from 'vitest';
import { stocksApi } from '../stocks';

const get = vi.hoisted(() => vi.fn());
const post = vi.hoisted(() => vi.fn());

vi.mock('../index', () => ({
  default: { get, post },
}));

describe('stocksApi', () => {
  beforeEach(() => {
    get.mockReset();
    post.mockReset();
  });

  it('loads no-AI stock snapshots as camelCase data', async () => {
    get.mockResolvedValueOnce({
      data: {
        stock_code: 'AAPL',
        stock_name: 'Apple Inc.',
        market: 'us',
        quote: {
          current_price: 200,
          change_percent: 1.5,
          source: 'yahoo_chart',
          freshness: 'fresh',
        },
        indicators: { ma5: 198, ma20: 190 },
        intelligence: {
          mode: 'no_ai_low_cost',
          ai_used: false,
          news_center: {
            title: 'Local news center',
            summary: 'AAPL information lanes for Technology.',
            source: 'no_ai_news_center_rules',
            ai_used: false,
            public_search_used: false,
            premium_unlock: 'Premium can add realtime news.',
            boundary: 'Information analysis only; not investment advice.',
            items: [
              {
                category: 'news',
                title: 'Market-moving news lane',
                summary: 'Realtime public news/search is off.',
                status: 'degraded',
                source: 'no_ai_news_center_rules',
                action: 'Use deep analysis for realtime links.',
                updated_at: '2026-07-01T09:30:00',
              },
            ],
          },
          kline_forecast: {
            title: 'K-line forecast lab',
            horizon: 'next_5_bars',
            direction: 'upside_bias',
            confidence: 72,
            support: 190,
            resistance: 205,
            adapter_status: 'Kronos adapter ready; local rules preview only.',
            source: 'local_kline_rules_kronos_ready',
            ai_used: false,
            kronos_model_used: false,
            premium_unlock: 'Premium can run a configured Kronos lane.',
            boundary: 'Experimental model preview; information analysis only; not investment advice.',
            scenarios: [
              {
                label: 'Upside-biased preview',
                direction: 'upside_bias',
                probability: 70,
                trigger: 'Hold above MA20.',
                detail: 'Local rules preview only.',
              },
            ],
          },
          items: [],
        },
        route: {
          input_code: 'AAPL',
          normalized_code: 'AAPL',
          market: 'us',
          channel: 'us_equity',
          data_source_lane: 'us_market_data',
          quote_sources: ['us_realtime'],
          history_sources: ['us_history'],
          ai_required: false,
        },
        warnings: [
          { code: 'stale_quote', severity: 'warning', message: 'Quote is stale' },
        ],
        degradation: { status: 'degraded', severity: 'warning', message: 'Quote is stale' },
        diagnostics: {
          elapsed_ms: 12,
          quote_elapsed_ms: 5,
          history_elapsed_ms: 7,
          cache: { quote: 'miss', history: 'miss' },
          sources: { quote: 'yahoo_chart', history: 'yfinance' },
          freshness: { quote: 'fresh', history: 'fresh' },
          timeouts: { quote: false, history: false },
          errors: { quote: null, history: null },
          fallback: { quote: 'live', history: 'live' },
          source_health: {
            quote: { source: 'unit_quote', status: 'ok', consecutive_failures: 0 },
            history: { source: 'unit_history', status: 'ok', consecutive_failures: 0 },
          },
          persistent_cache: { quote: 'disk', history: 'memory', mode: 'local_json' },
          refresh: { mode: 'cache_first', requested: false },
          route_lane: 'us_market_data',
          performance: { status: 'ok', slow_threshold_ms: 3000 },
        },
        ai_used: false,
      },
    });

    const result = await stocksApi.snapshot('AAPL');

    expect(get).toHaveBeenCalledWith('/api/v1/stocks/AAPL/snapshot');
    expect(result.stockCode).toBe('AAPL');
    expect(result.quote.currentPrice).toBe(200);
    expect(result.route?.dataSourceLane).toBe('us_market_data');
    expect(result.intelligence?.newsCenter?.publicSearchUsed).toBe(false);
    expect(result.intelligence?.newsCenter?.items[0].updatedAt).toBe('2026-07-01T09:30:00');
    expect(result.intelligence?.klineForecast?.adapterStatus).toContain('Kronos');
    expect(result.intelligence?.klineForecast?.kronosModelUsed).toBe(false);
    expect(result.warnings?.[0].code).toBe('stale_quote');
    expect(result.degradation?.status).toBe('degraded');
    expect(result.diagnostics?.elapsedMs).toBe(12);
    expect(result.diagnostics?.quoteElapsedMs).toBe(5);
    expect(result.diagnostics?.cache.quote).toBe('miss');
    expect(result.diagnostics?.fallback?.quote).toBe('live');
    expect(result.diagnostics?.timeouts?.quote).toBe(false);
    expect(result.diagnostics?.sourceHealth?.quote.status).toBe('ok');
    expect(result.diagnostics?.sourceHealth?.quote.consecutiveFailures).toBe(0);
    expect(result.diagnostics?.persistentCache?.quote).toBe('disk');
    expect(result.diagnostics?.persistentCache?.mode).toBe('local_json');
    expect(result.diagnostics?.refresh?.mode).toBe('cache_first');
    expect(result.diagnostics?.routeLane).toBe('us_market_data');
    expect(result.aiUsed).toBe(false);
  });

  it('loads A-share enrichment channels as camelCase snapshot data', async () => {
    get.mockResolvedValueOnce({
      data: {
        stock_code: '600519.SH',
        stock_name: '贵州茅台',
        market: 'cn',
        quote: {
          current_price: 1210,
          source: 'a_share_realtime',
          freshness: 'fresh',
        },
        indicators: {},
        intelligence: {
          mode: 'no_ai_low_cost',
          ai_used: false,
          a_share_enrichment: {
            title: 'A股增强数据',
            summary: '贵州茅台本地增强数据通道已就绪。',
            status: 'available',
            source: 'a_stock_data_poc_adapter',
            updated_at: '2026-07-07T09:30:00Z',
            ai_used: false,
            public_search_used: false,
            premium_unlock: '高级版可展开公告原文、研报 PDF、资金流历史、板块联动和龙虎榜席位明细。',
            boundary: 'Information analysis only; not investment advice.',
            channels: [
              {
                category: 'capital_flow',
                title: '资金流通道',
                summary: '主力资金净流入 1.2亿。',
                status: 'available',
                source: 'a_stock_data_eastmoney_fund_flow',
                action: '观察近几日主力净流入是否连续。',
                updated_at: '2026-07-07T09:31:00Z',
              },
            ],
          },
          items: [],
        },
        ai_used: false,
      },
    });

    const result = await stocksApi.snapshot('600519.SH');

    expect(result.intelligence?.aShareEnrichment?.aiUsed).toBe(false);
    expect(result.intelligence?.aShareEnrichment?.publicSearchUsed).toBe(false);
    expect(result.intelligence?.aShareEnrichment?.updatedAt).toBe('2026-07-07T09:30:00Z');
    expect(result.intelligence?.aShareEnrichment?.channels[0].category).toBe('capital_flow');
    expect(result.intelligence?.aShareEnrichment?.channels[0].updatedAt).toBe('2026-07-07T09:31:00Z');
  });

  it('loads force-refresh no-AI stock snapshots with refresh diagnostics', async () => {
    get.mockResolvedValueOnce({
      data: {
        stock_code: 'AAPL',
        market: 'us',
        quote: {
          current_price: 210,
          source: 'yahoo_chart',
          freshness: 'fresh',
        },
        indicators: {},
        diagnostics: {
          elapsed_ms: 30,
          quote_elapsed_ms: 14,
          history_elapsed_ms: 16,
          cache: { quote: 'refresh', history: 'refresh' },
          sources: { quote: 'yahoo_chart', history: 'yfinance' },
          freshness: { quote: 'fresh', history: 'fresh' },
          fallback: { quote: 'live', history: 'live' },
          persistent_cache: { quote: 'none', history: 'none', mode: 'local_json' },
          refresh: { mode: 'force_refresh', requested: true, quote: true, history: true },
          route_lane: 'us_market_data',
          performance: { status: 'ok' },
        },
        ai_used: false,
      },
    });

    const result = await stocksApi.snapshot('AAPL', { refresh: true });

    expect(get).toHaveBeenCalledWith('/api/v1/stocks/AAPL/snapshot?refresh=true');
    expect(result.quote.currentPrice).toBe(210);
    expect(result.diagnostics?.cache.quote).toBe('refresh');
    expect(result.diagnostics?.refresh?.mode).toBe('force_refresh');
    expect(result.diagnostics?.refresh?.requested).toBe(true);
    expect(result.aiUsed).toBe(false);
  });

  it('loads A-share snapshots with a selected enrichment source mode', async () => {
    get.mockResolvedValueOnce({
      data: {
        stock_code: '600519',
        market: 'cn',
        quote: {
          current_price: 1188.8,
          source: 'unit_quote',
          freshness: 'fresh',
        },
        indicators: {},
        intelligence: {
          mode: 'no_ai_low_cost',
          ai_used: false,
          a_share_enrichment: {
            title: 'A-share enrichment',
            summary: 'adapter mode',
            status: 'degraded',
            source: 'a_stock_data_skill_adapter',
            source_mode: 'a_stock_data',
            skill: { revision: 'bcda405' },
            diagnostics: { cache: { hits: 1, misses: 0 }, rate_limited_channels: [] },
            ai_used: false,
            public_search_used: false,
            channels: [],
            premium_unlock: 'Premium can add sources.',
            boundary: 'Information analysis only; not investment advice.',
          },
          items: [],
        },
        ai_used: false,
      },
    });

    const result = await stocksApi.snapshot('600519', { aShareSourceMode: 'a_stock_data' });

    expect(get).toHaveBeenCalledWith('/api/v1/stocks/600519/snapshot?a_share_source_mode=a_stock_data');
    expect(result.intelligence?.aShareEnrichment?.sourceMode).toBe('a_stock_data');
    expect(result.intelligence?.aShareEnrichment?.skill?.revision).toBe('bcda405');
  });

  it('prewarms no-AI market cache as camelCase data', async () => {
    post.mockResolvedValueOnce({
      data: {
        requested: 2,
        warmed: 2,
        degraded: 0,
        symbols: ['AAPL', 'BTC-USD'],
        results: {},
        elapsed_ms: 15,
        ai_used: false,
      },
    });

    const result = await stocksApi.prewarm(['AAPL', 'BTC-USD']);

    expect(post).toHaveBeenCalledWith('/api/v1/stocks/prewarm', { symbols: ['AAPL', 'BTC-USD'] });
    expect(result.requested).toBe(2);
    expect(result.elapsedMs).toBe(15);
    expect(result.aiUsed).toBe(false);
  });

  it('loads local Kronos forecast sandbox results as camelCase data', async () => {
    get.mockResolvedValueOnce({
      data: {
        stock_code: 'AAPL',
        stock_name: 'Apple Inc.',
        market: 'us',
        mode: 'kronos_sandbox',
        status: 'model_unavailable',
        provider: 'kronos',
        source: 'local_kline_rules_kronos_unavailable',
        horizon: 'next_5_bars',
        lookback: 120,
        direction: 'upside_bias',
        confidence: 64,
        support: 190,
        resistance: 205,
        adapter_status: 'Kronos dependencies missing.',
        enabled: true,
        kronos_model_used: false,
        model_id: 'NeoQuasar/Kronos-small',
        tokenizer_id: 'NeoQuasar/Kronos-Tokenizer-base',
        device: 'auto',
        dependency_status: { pandas: true, torch: false, einops: true, safetensors: true, huggingface_hub: true, model: false },
        missing_dependencies: ['torch', 'model'],
        scenarios: [
          {
            label: 'Upside-biased preview',
            direction: 'upside_bias',
            probability: 64,
            trigger: 'Hold above support.',
            detail: 'Local fallback.',
          },
        ],
        forecast_points: [{ timestamp: '2026-07-07', close: 201 }],
        backtest_summary: { records: 1, evaluated: 1, hits: 1, hit_rate: 1, last_evaluated_at: '2026-07-06T09:00:00' },
        warnings: ['Kronos model unavailable.'],
        elapsed_ms: 12,
        cache_hit: false,
        record_id: 'unit-kronos',
        ai_used: false,
        public_search_used: false,
        boundary: 'Experimental model preview; information analysis only; not investment advice.',
      },
    });

    const result = await stocksApi.kronosForecast('AAPL', { lookback: 120, horizon: 5, requireModel: true });

    expect(get).toHaveBeenCalledWith('/api/v1/stocks/AAPL/kronos-forecast?lookback=120&horizon=5&require_model=true');
    expect(result.status).toBe('model_unavailable');
    expect(result.kronosModelUsed).toBe(false);
    expect(result.dependencyStatus.huggingfaceHub).toBe(true);
    expect(result.missingDependencies).toContain('torch');
    expect(result.backtestSummary.hitRate).toBe(1);
    expect(result.aiUsed).toBe(false);
    expect(result.publicSearchUsed).toBe(false);
  });

  it('loads local market source health as camelCase data', async () => {
    get.mockResolvedValueOnce({
      data: {
        mode: 'local_only',
        ai_used: false,
        cache: { mode: 'local_json', storage: 'local_market_cache' },
        lanes: [
          {
            market: 'hk',
            channel: 'hk_equity',
            route_lane: 'hk_market_data',
            quote_sources: [
              {
                source: 'hk_realtime',
                priority_rank: 1,
                status: 'cooling_down',
                consecutive_failures: 2,
                last_error: 'timeout',
                last_latency_ms: 4200,
                cooldown_remaining_sec: 55,
              },
            ],
            history_sources: [
              {
                source: 'hk_history',
                priority_rank: 1,
                status: 'ok',
                consecutive_failures: 0,
                last_error: null,
                last_latency_ms: null,
                cooldown_remaining_sec: 0,
              },
            ],
          },
        ],
      },
    });

    const result = await stocksApi.marketSourceHealth();

    expect(get).toHaveBeenCalledWith('/api/v1/stocks/sources/health');
    expect(result.aiUsed).toBe(false);
    expect(result.cache.mode).toBe('local_json');
    expect(result.lanes[0].routeLane).toBe('hk_market_data');
    expect(result.lanes[0].quoteSources[0].priorityRank).toBe(1);
    expect(result.lanes[0].quoteSources[0].cooldownRemainingSec).toBe(55);
  });

  it('recovers local market sources as admin-only no-AI camelCase data', async () => {
    post.mockResolvedValueOnce({
      data: {
        mode: 'local_only',
        action: 'reset_source_health',
        market: 'all',
        reset_sources: ['hk_realtime'],
        reset_count: 1,
        prewarm: {
          requested: 4,
          warmed: 4,
          degraded: 0,
          symbols: ['600519', 'AAPL', 'HK00700', 'BTC-USD'],
          results: {},
          elapsed_ms: 18,
          ai_used: false,
        },
        health: {
          mode: 'local_only',
          ai_used: false,
          cache: { mode: 'local_json', storage: 'local_market_cache' },
          lanes: [],
        },
        ai_used: false,
      },
    });

    const result = await stocksApi.recoverMarketSources({
      market: 'all',
      symbols: ['600519', 'AAPL', 'HK00700', 'BTC-USD'],
      prewarm: true,
    });

    expect(post).toHaveBeenCalledWith('/api/v1/stocks/sources/recovery', {
      market: 'all',
      symbols: ['600519', 'AAPL', 'HK00700', 'BTC-USD'],
      prewarm: true,
    });
    expect(result.aiUsed).toBe(false);
    expect(result.resetSources).toEqual(['hk_realtime']);
    expect(result.prewarm.elapsedMs).toBe(18);
  });
});
