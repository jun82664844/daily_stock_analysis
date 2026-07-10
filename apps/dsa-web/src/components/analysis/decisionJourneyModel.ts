import type { BasicStockSnapshot } from '../../api/stocks';

export type DecisionJourneyLanguage = 'zh' | 'en';
export type DecisionEvidenceTabKey = 'price' | 'technical' | 'events' | 'fundamentals' | 'sources';

export type DecisionEvidenceItem = {
  label: string;
  value: string;
  detail: string;
};

export type DecisionEvidenceTab = {
  key: DecisionEvidenceTabKey;
  label: string;
  summary: string;
  items: DecisionEvidenceItem[];
};

export type DecisionJourneyModel = {
  language: DecisionJourneyLanguage;
  labels: {
    eyebrow: string;
    title: string;
    subtitle: string;
    conclusion: string;
    opportunity: string;
    risk: string;
    evidence: string;
    evidenceLibrary: string;
    free: string;
    premium: string;
    sourceTrust: string;
    noAi: string;
  };
  summary: {
    conclusion: string;
    score: number;
    opportunity: string;
    risk: string;
    evidence: string;
  };
  technical: {
    ma5: number | null;
    ma10: number | null;
    ma20: number | null;
    ma60: number | null;
    rsi14: number | null;
    macd: number | null;
    trendState: string;
    volumeState: string;
  };
  chart: {
    label: string;
    points: Array<{ label: string; value: number }>;
    min: number | null;
    max: number | null;
  };
  marketFocus: {
    label: string;
    benchmark: string;
    items: string[];
  };
  trust: {
    quoteSource: string;
    historySource: string;
    profileSource: string;
    freshness: string;
    updatedAt: string;
    routeLane: string;
    elapsed: string;
  };
  tabs: DecisionEvidenceTab[];
  comparison: {
    free: string[];
    premium: string[];
  };
  boundary: {
    aiUsed: boolean;
    disclaimer: string;
  };
};

export type BuildDecisionJourneyModelInput = {
  snapshot: BasicStockSnapshot;
  language: DecisionJourneyLanguage;
  conclusion: string;
  score: number;
  risk: string;
  support: string;
  resistance: string;
};

const finiteNumber = (value: unknown): number | null => (
  typeof value === 'number' && Number.isFinite(value) ? value : null
);

const formatNumber = (value: unknown): string => {
  const numberValue = finiteNumber(value);
  return numberValue === null
    ? '-'
    : numberValue.toLocaleString(undefined, { maximumFractionDigits: 4 });
};

const formatPercent = (value: unknown): string => {
  const numberValue = finiteNumber(value);
  if (numberValue === null) return '-';
  const sign = numberValue > 0 ? '+' : '';
  return `${sign}${numberValue.toLocaleString(undefined, { maximumFractionDigits: 2 })}%`;
};

const pickIndicator = (indicators: Record<string, unknown>, ...keys: string[]): number | null => {
  for (const key of keys) {
    const value = finiteNumber(indicators[key]);
    if (value !== null) return value;
  }
  return null;
};

const average = (values: number[], period: number): number | null => {
  if (values.length < period) return null;
  const sample = values.slice(-period);
  return sample.reduce((sum, value) => sum + value, 0) / period;
};

const emaSeries = (values: number[], period: number): number[] => {
  if (values.length === 0) return [];
  const multiplier = 2 / (period + 1);
  const result = [values[0]];
  for (let index = 1; index < values.length; index += 1) {
    result.push((values[index] * multiplier) + (result[index - 1] * (1 - multiplier)));
  }
  return result;
};

const calculateRsi = (values: number[], period = 14): number | null => {
  if (values.length <= period) return null;
  const changes = values.slice(-(period + 1)).slice(1).map((value, index) => value - values.slice(-(period + 1))[index]);
  const gains = changes.reduce((sum, value) => sum + Math.max(value, 0), 0) / period;
  const losses = changes.reduce((sum, value) => sum + Math.max(-value, 0), 0) / period;
  if (losses === 0) return gains === 0 ? 50 : 100;
  const relativeStrength = gains / losses;
  return Math.round((100 - (100 / (1 + relativeStrength))) * 10) / 10;
};

const calculateMacd = (values: number[]): number | null => {
  if (values.length < 26) return null;
  const ema12 = emaSeries(values, 12);
  const ema26 = emaSeries(values, 26);
  return Math.round((ema12[ema12.length - 1] - ema26[ema26.length - 1]) * 10000) / 10000;
};

const normalizeMarket = (market: string): 'cn' | 'us' | 'hk' | 'crypto' => {
  const value = String(market || '').toLowerCase();
  if (['cn', 'a', 'a_share', 'ashare', 'china'].includes(value)) return 'cn';
  if (['hk', 'hong_kong', 'hongkong'].includes(value)) return 'hk';
  if (['crypto', 'cryptocurrency', 'digital_asset'].includes(value)) return 'crypto';
  return 'us';
};

const marketFocusFor = (
  market: ReturnType<typeof normalizeMarket>,
  language: DecisionJourneyLanguage,
): DecisionJourneyModel['marketFocus'] => {
  const zh = {
    cn: { label: 'A股重点', benchmark: '沪深300 / 所属板块', items: ['公告与监管披露', '资金流与成交结构', '板块联动与估值位置'] },
    us: { label: '美股重点', benchmark: 'SPY / QQQ / 所属行业', items: ['财报与 SEC 文件', '估值及盈利预期', '指数与同业对比'] },
    hk: { label: '港股重点', benchmark: '恒生指数 / 所属行业', items: ['港交所公告与南向资金', '汇率与流动性', 'A/H 股及同业对比'] },
    crypto: { label: '加密市场重点', benchmark: 'BTC / ETH / 市场总量', items: ['流动性与全天候波动', '成交量和资金费率', '链上与监管事件'] },
  };
  const en = {
    cn: { label: 'A-share focus', benchmark: 'CSI 300 / sector', items: ['Filings and regulatory disclosure', 'Capital flow and volume structure', 'Sector linkage and valuation'] },
    us: { label: 'US market focus', benchmark: 'SPY / QQQ / industry', items: ['Earnings and SEC filings', 'Valuation and earnings expectations', 'Index and peer comparison'] },
    hk: { label: 'Hong Kong market focus', benchmark: 'Hang Seng / industry', items: ['HKEX filings and southbound flow', 'FX and liquidity', 'A/H and peer comparison'] },
    crypto: { label: 'Crypto market focus', benchmark: 'BTC / ETH / total market', items: ['Liquidity and 24/7 volatility', 'Volume and funding rates', 'On-chain and regulatory events'] },
  };
  return language === 'en' ? en[market] : zh[market];
};

const localizeFreshness = (freshness: string, language: DecisionJourneyLanguage): string => {
  const value = String(freshness || '').toLowerCase();
  if (language === 'en') {
    if (value === 'fresh') return 'Fresh';
    if (value === 'stale') return 'Stale';
    if (value === 'cached') return 'Cached';
    return freshness || 'Unknown';
  }
  if (value === 'fresh') return '新鲜';
  if (value === 'stale') return '过期';
  if (value === 'cached') return '缓存';
  return freshness || '未知';
};

export const buildDecisionJourneyModel = ({
  snapshot,
  language,
  conclusion,
  score,
  risk,
  support,
  resistance,
}: BuildDecisionJourneyModelInput): DecisionJourneyModel => {
  const isEnglish = language === 'en';
  const market = normalizeMarket(snapshot.market);
  const closes = (snapshot.trend?.points ?? [])
    .map((point) => finiteNumber(point.close))
    .filter((value): value is number => value !== null);
  const indicators = snapshot.indicators ?? {};
  const ma5 = pickIndicator(indicators, 'ma5', 'MA5') ?? average(closes, 5);
  const ma10 = pickIndicator(indicators, 'ma10', 'MA10') ?? average(closes, 10);
  const ma20 = pickIndicator(indicators, 'ma20', 'MA20') ?? average(closes, 20);
  const ma60 = pickIndicator(indicators, 'ma60', 'MA60') ?? average(closes, 60);
  const rsi14 = pickIndicator(indicators, 'rsi14', 'RSI14', 'rsi') ?? calculateRsi(closes);
  const macd = pickIndicator(indicators, 'macd', 'MACD') ?? calculateMacd(closes);
  const currentPrice = finiteNumber(snapshot.quote.currentPrice);
  const volumeChange = pickIndicator(indicators, 'volumeChangeVsMa5', 'volume_change_vs_ma5');
  const trendState = currentPrice !== null && ma20 !== null
    ? currentPrice >= ma20
      ? (isEnglish ? 'Constructive' : '偏强')
      : (isEnglish ? 'Under pressure' : '承压')
    : (isEnglish ? 'Needs history' : '等待历史数据');
  const volumeState = volumeChange === null
    ? (isEnglish ? 'Incomplete' : '数据不完整')
    : volumeChange >= 20
      ? (isEnglish ? 'Expanding' : '量能放大')
      : volumeChange <= -20
        ? (isEnglish ? 'Contracting' : '量能收缩')
        : (isEnglish ? 'Neutral' : '量能中性');
  const chartPoints = (snapshot.trend?.points ?? [])
    .map((point, index) => ({
      label: String(point.date || index + 1),
      value: finiteNumber(point.close),
    }))
    .filter((point): point is { label: string; value: number } => point.value !== null);
  const chartValues = chartPoints.map((point) => point.value);
  const newsItems = snapshot.intelligence?.newsCenter?.items ?? [];
  const comparisonTargets = snapshot.intelligence?.comparisonTargets ?? [];
  const profile = snapshot.profile;
  const quoteSource = snapshot.quote.source || snapshot.route?.quoteSources?.[0] || '-';
  const historySource = snapshot.trend?.source || snapshot.route?.historySources?.[0] || '-';
  const profileSource = profile?.source || snapshot.route?.profileSources?.[0] || '-';
  const routeLane = snapshot.route?.dataSourceLane || snapshot.route?.channel || snapshot.diagnostics?.routeLane || '-';
  const marketFocus = marketFocusFor(market, language);
  const evidence = isEnglish
    ? `Last ${formatNumber(currentPrice)}, MA20 ${formatNumber(ma20)}, RSI14 ${formatNumber(rsi14)}.`
    : `最新价 ${formatNumber(currentPrice)}，MA20 ${formatNumber(ma20)}，RSI14 ${formatNumber(rsi14)}。`;
  const opportunity = isEnglish
    ? `Support ${support}; resistance ${resistance}.`
    : `支撑 ${support}；压力 ${resistance}。`;
  const eventHeadline = newsItems[0]?.title || (isEnglish ? 'No verified event headline in the free snapshot' : '免费快照暂无已核验事件标题');
  const eventDetail = newsItems[0]?.summary || (isEnglish ? 'Use public filings and news as confirmation, not as a standalone signal.' : '将公告和资讯作为确认依据，不把单条消息当作独立信号。');
  const peerSymbols = comparisonTargets.map((item) => item.symbol).filter(Boolean).slice(0, 3);

  const tabs: DecisionEvidenceTab[] = [
    {
      key: 'price',
      label: isEnglish ? 'Price & volume' : '行情量价',
      summary: isEnglish ? 'Current price structure and volume confirmation.' : '当前价格结构及成交量确认。',
      items: [
        { label: isEnglish ? 'Last / change' : '最新价 / 涨跌', value: `${formatNumber(currentPrice)} / ${formatPercent(snapshot.quote.changePercent)}`, detail: isEnglish ? `Open ${formatNumber(snapshot.quote.open)}, high ${formatNumber(snapshot.quote.high)}, low ${formatNumber(snapshot.quote.low)}.` : `开盘 ${formatNumber(snapshot.quote.open)}，最高 ${formatNumber(snapshot.quote.high)}，最低 ${formatNumber(snapshot.quote.low)}。` },
        { label: isEnglish ? 'Support / resistance' : '支撑 / 压力', value: `${support} / ${resistance}`, detail: isEnglish ? 'Treat levels as observation zones, not execution instructions.' : '价位仅作为观察区间，不是交易指令。' },
        { label: isEnglish ? 'Volume state' : '量价状态', value: volumeState, detail: isEnglish ? `Volume versus MA5 ${formatPercent(volumeChange)}.` : `成交量相对 MA5 ${formatPercent(volumeChange)}。` },
      ],
    },
    {
      key: 'technical',
      label: isEnglish ? 'Technical' : '技术证据',
      summary: isEnglish ? 'Locally calculated trend and momentum evidence.' : '使用历史行情在本地计算趋势与动量证据。',
      items: [
        { label: 'MA5 / MA20', value: `${formatNumber(ma5)} / ${formatNumber(ma20)}`, detail: trendState },
        { label: 'MA10 / MA60', value: `${formatNumber(ma10)} / ${formatNumber(ma60)}`, detail: isEnglish ? 'Longer averages appear only when enough history exists.' : '只有历史长度充足时才显示长期均线。' },
        { label: 'RSI14 / MACD', value: `${formatNumber(rsi14)} / ${formatNumber(macd)}`, detail: isEnglish ? 'Momentum confirms context; it does not predict outcomes.' : '动量指标用于确认背景，不能保证未来结果。' },
      ],
    },
    {
      key: 'events',
      label: isEnglish ? 'News & events' : '资讯事件',
      summary: isEnglish ? 'Material-event checkpoints for the selected market.' : '针对当前市场的重大事件核对清单。',
      items: [
        { label: marketFocus.items[0], value: eventHeadline, detail: eventDetail },
        { label: isEnglish ? 'Peer references' : '同业参照', value: peerSymbols.join(' / ') || marketFocus.benchmark, detail: isEnglish ? 'Compare the move with market and sector references.' : '与大盘、行业和同业参照比较本次波动。' },
        { label: isEnglish ? 'Event freshness' : '事件新鲜度', value: newsItems[0]?.updatedAt || '-', detail: snapshot.intelligence?.newsCenter?.source || (isEnglish ? 'Free local rules' : '免费本地规则') },
      ],
    },
    {
      key: 'fundamentals',
      label: isEnglish ? 'Fundamentals' : '基本面',
      summary: isEnglish ? 'Company profile and valuation context from the current snapshot.' : '当前快照中的公司资料与估值背景。',
      items: [
        { label: isEnglish ? 'Sector / industry' : '板块 / 行业', value: `${profile?.sector || '-'} / ${profile?.industry || '-'}`, detail: marketFocus.items[2] },
        { label: isEnglish ? 'Market cap / P/E' : '市值 / 市盈率', value: `${formatNumber(profile?.marketCap)} / ${formatNumber(profile?.peRatio)}`, detail: isEnglish ? 'Compare valuation with history and peers.' : '估值需要与历史区间和同业共同比较。' },
        { label: isEnglish ? 'Revenue / net profit' : '营收 / 净利润', value: `${formatNumber(profile?.revenue)} / ${formatNumber(profile?.netProfit)}`, detail: isEnglish ? 'Missing fields stay missing instead of being estimated.' : '缺失字段保持缺失，不进行虚构估算。' },
      ],
    },
    {
      key: 'sources',
      label: isEnglish ? 'Sources' : '来源可信度',
      summary: isEnglish ? 'Source, freshness, route, and timing are visible before interpretation.' : '解读前先核对来源、新鲜度、路由和耗时。',
      items: [
        { label: isEnglish ? 'Quote source' : '行情来源', value: quoteSource, detail: `${localizeFreshness(snapshot.quote.freshness, language)} / ${snapshot.quote.updateTime || '-'}` },
        { label: isEnglish ? 'History / profile' : '历史 / 资料来源', value: `${historySource} / ${profileSource}`, detail: routeLane },
        { label: isEnglish ? 'Response time' : '响应耗时', value: `${snapshot.diagnostics?.elapsedMs ?? 0} ms`, detail: isEnglish ? 'Free web/local route, no AI quota used.' : '免费网络/本地通道，未使用 AI 额度。' },
      ],
    },
  ];

  return {
    language,
    labels: {
      eyebrow: isEnglish ? 'V91 professional free view' : 'V91 专业免费研判',
      title: isEnglish ? 'Decision journey' : '用户决策闭环',
      subtitle: isEnglish ? 'Conclusion first, then evidence, risks, and what better data changes.' : '先看结论，再核对证据、风险和更强数据能改变什么。',
      conclusion: isEnglish ? 'Conclusion' : '结论',
      opportunity: isEnglish ? 'Price map' : '价位地图',
      risk: isEnglish ? 'Risk boundary' : '风险边界',
      evidence: isEnglish ? 'Key evidence' : '关键证据',
      evidenceLibrary: isEnglish ? 'Evidence library' : '证据库',
      free: isEnglish ? 'Free includes' : '免费版包含',
      premium: isEnglish ? 'Premium improves' : '高级版增强',
      sourceTrust: isEnglish ? 'Source trust' : '来源可信度',
      noAi: isEnglish ? 'No AI, no quota' : '未用 AI，不扣额度',
    },
    summary: {
      conclusion,
      score: Math.max(0, Math.min(100, Math.round(score))),
      opportunity,
      risk,
      evidence,
    },
    technical: { ma5, ma10, ma20, ma60, rsi14, macd, trendState, volumeState },
    chart: {
      label: isEnglish ? 'Closing-price trend' : '收盘价趋势',
      points: chartPoints,
      min: chartValues.length > 0 ? Math.min(...chartValues) : null,
      max: chartValues.length > 0 ? Math.max(...chartValues) : null,
    },
    marketFocus,
    trust: {
      quoteSource,
      historySource,
      profileSource,
      freshness: localizeFreshness(snapshot.quote.freshness, language),
      updatedAt: snapshot.quote.updateTime || '-',
      routeLane,
      elapsed: `${snapshot.diagnostics?.elapsedMs ?? 0} ms`,
    },
    tabs,
    comparison: {
      free: isEnglish
        ? ['Complete decision structure', 'Price and local technical calculations', 'Market-specific checklist', 'Source and freshness disclosure']
        : ['完整决策结构', '行情与本地技术计算', '分市场核对清单', '来源和新鲜度披露'],
      premium: isEnglish
        ? ['Realtime API freshness', 'Original news and filing links', 'Longer history and model validation', 'Continuous watchlist alerts']
        : ['实时 API 新鲜度', '资讯和公告原文链接', '更长历史与模型验证', '自选股持续提醒'],
    },
    boundary: {
      aiUsed: Boolean(snapshot.aiUsed || snapshot.intelligence?.aiUsed),
      disclaimer: isEnglish ? 'Information analysis only, not investment advice.' : '仅作信息分析，不构成投资建议。',
    },
  };
};
