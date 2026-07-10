import { useMemo, useState } from 'react';
import {
  BarChart3,
  Building2,
  Database,
  FileSearch,
  Gauge,
  LineChart,
  Newspaper,
  ShieldAlert,
  Sparkles,
} from 'lucide-react';
import { Button } from '../common';
import type { DecisionEvidenceTabKey, DecisionJourneyModel } from './decisionJourneyModel';

type DecisionJourneyTarget = 'events' | 'kline' | 'upgrade';

type DecisionJourneyV91Props = {
  model: DecisionJourneyModel;
  onJump: (target: DecisionJourneyTarget) => void;
};

const metricValue = (value: number | null): string => (
  value === null
    ? '-'
    : value.toLocaleString(undefined, { maximumFractionDigits: 4 })
);

const chartPolyline = (values: number[]): string => {
  if (values.length === 0) return '';
  const width = 520;
  const height = 128;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = Math.max(max - min, 1);
  return values.map((value, index) => {
    const x = values.length === 1 ? width / 2 : (index / (values.length - 1)) * width;
    const y = height - (((value - min) / range) * (height - 16)) - 8;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');
};

const tabIcon = (key: DecisionEvidenceTabKey) => {
  if (key === 'price') return BarChart3;
  if (key === 'technical') return Gauge;
  if (key === 'events') return Newspaper;
  if (key === 'fundamentals') return Building2;
  return Database;
};

export const DecisionJourneyV91 = ({ model, onJump }: DecisionJourneyV91Props) => {
  const [activeTab, setActiveTab] = useState<DecisionEvidenceTabKey>('price');
  const isEnglish = model.language === 'en';
  const selectedTab = model.tabs.find((tab) => tab.key === activeTab) ?? model.tabs[0];
  const polyline = useMemo(
    () => chartPolyline(model.chart.points.map((point) => point.value)),
    [model.chart.points],
  );
  const summaryCards = [
    { key: 'conclusion', label: model.labels.conclusion, value: model.summary.conclusion, icon: LineChart },
    { key: 'opportunity', label: model.labels.opportunity, value: model.summary.opportunity, icon: BarChart3 },
    { key: 'risk', label: model.labels.risk, value: model.summary.risk, icon: ShieldAlert },
    { key: 'evidence', label: model.labels.evidence, value: model.summary.evidence, icon: FileSearch },
  ];

  return (
    <section
      data-testid="basic-query-decision-journey-v91"
      className="mb-4 overflow-hidden rounded-lg border border-primary/50 bg-surface/80 shadow-soft-card"
    >
      <div className="border-b border-subtle/80 bg-primary/8 p-4">
        <div className="flex min-w-0 flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2 text-[11px]">
              <span className="rounded-md border border-primary/45 bg-primary/12 px-2 py-1 font-semibold text-primary">
                {model.labels.eyebrow}
              </span>
              <span className="rounded-md border border-primary/35 bg-background/35 px-2 py-1 text-primary">
                {model.labels.noAi}
              </span>
              <span className="rounded-md border border-subtle/75 bg-background/35 px-2 py-1 text-secondary-text">
                {model.marketFocus.label}
              </span>
            </div>
            <h3 className="mt-2 text-xl font-semibold text-foreground">{model.labels.title}</h3>
            <p className="mt-1 max-w-4xl text-sm leading-relaxed text-secondary-text">{model.labels.subtitle}</p>
          </div>
          <div className="flex shrink-0 flex-wrap gap-2">
            <Button type="button" variant="secondary" size="sm" onClick={() => onJump('events')}>
              <Newspaper className="h-4 w-4" aria-hidden="true" />
              {isEnglish ? 'View news & events' : '查看资讯事件'}
            </Button>
            <Button type="button" variant="secondary" size="sm" onClick={() => onJump('kline')}>
              <LineChart className="h-4 w-4" aria-hidden="true" />
              {isEnglish ? 'View K-line scenarios' : '查看K线情景'}
            </Button>
            <Button type="button" variant="secondary" size="sm" onClick={() => onJump('upgrade')}>
              <Sparkles className="h-4 w-4" aria-hidden="true" />
              {isEnglish ? 'View upgrade gap' : '查看升级差异'}
            </Button>
          </div>
        </div>

        <div className="mt-4 grid gap-2 lg:grid-cols-4">
          {summaryCards.map((card) => {
            const Icon = card.icon;
            return (
              <article key={card.key} className="min-w-0 rounded-md border border-subtle/80 bg-background/40 p-3">
                <div className="flex items-center gap-2 text-xs font-semibold text-primary">
                  <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                  {card.label}
                </div>
                <p className="mt-2 line-clamp-4 text-sm font-medium leading-relaxed text-foreground">{card.value}</p>
              </article>
            );
          })}
        </div>
      </div>

      <div className="grid gap-4 p-4 xl:grid-cols-[minmax(0,1.55fr)_minmax(260px,0.75fr)]">
        <div className="min-w-0">
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="text-xs font-semibold text-primary">{model.chart.label}</div>
              <div className="mt-1 text-sm text-secondary-text">
                {model.technical.trendState} · MA20 {metricValue(model.technical.ma20)} · RSI14 {metricValue(model.technical.rsi14)}
              </div>
            </div>
            <span className="rounded-md border border-primary/35 bg-primary/8 px-2 py-1 text-sm font-semibold text-primary">
              {model.summary.score}/100
            </span>
          </div>
          <div className="mt-3 h-40 overflow-hidden rounded-md border border-subtle/80 bg-background/35 p-2">
            {polyline ? (
              <svg
                data-testid="decision-journey-price-chart"
                role="img"
                aria-label={model.chart.label}
                viewBox="0 0 520 128"
                preserveAspectRatio="none"
                className="h-full w-full"
              >
                <line x1="0" y1="32" x2="520" y2="32" className="stroke-subtle" strokeWidth="1" />
                <line x1="0" y1="64" x2="520" y2="64" className="stroke-subtle" strokeWidth="1" />
                <line x1="0" y1="96" x2="520" y2="96" className="stroke-subtle" strokeWidth="1" />
                <polyline
                  points={polyline}
                  fill="none"
                  className="stroke-primary"
                  strokeWidth="3"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            ) : (
              <div className="flex h-full items-center justify-center text-sm text-secondary-text">
                {isEnglish ? 'Price history is not complete yet.' : '价格历史暂不完整。'}
              </div>
            )}
          </div>
          <div className="mt-2 flex flex-wrap gap-2 text-[11px] text-secondary-text">
            <span className="rounded-md border border-subtle/75 px-2 py-1">Min {metricValue(model.chart.min)}</span>
            <span className="rounded-md border border-subtle/75 px-2 py-1">Max {metricValue(model.chart.max)}</span>
            <span className="rounded-md border border-subtle/75 px-2 py-1">MACD {metricValue(model.technical.macd)}</span>
            <span className="rounded-md border border-subtle/75 px-2 py-1">{model.technical.volumeState}</span>
          </div>
        </div>

        <aside className="min-w-0 border-t border-subtle/80 pt-4 xl:border-l xl:border-t-0 xl:pl-4 xl:pt-0">
          <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
            <FileSearch className="h-4 w-4 text-primary" aria-hidden="true" />
            {model.marketFocus.label}
          </div>
          <div className="mt-2 text-xs text-secondary-text">
            {isEnglish ? 'Benchmark' : '参考基准'}：{model.marketFocus.benchmark}
          </div>
          <ul className="mt-3 space-y-2 text-sm text-secondary-text">
            {model.marketFocus.items.map((item) => (
              <li key={item} className="flex gap-2">
                <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" aria-hidden="true" />
                <span>{item}</span>
              </li>
            ))}
          </ul>
          <div className="mt-4 border-t border-subtle/80 pt-3">
            <div className="flex items-center gap-2 text-xs font-semibold text-primary">
              <Database className="h-4 w-4" aria-hidden="true" />
              {model.labels.sourceTrust}
            </div>
            <div className="mt-2 space-y-1 text-xs leading-relaxed text-secondary-text">
              <div>{model.trust.quoteSource} · {model.trust.freshness}</div>
              <div className="break-all">{model.trust.updatedAt}</div>
              <div>{model.trust.elapsed}</div>
            </div>
          </div>
        </aside>
      </div>

      <div data-testid="decision-journey-evidence-library" className="border-t border-subtle/80 p-4">
        <div className="flex min-w-0 flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="text-sm font-semibold text-foreground">{model.labels.evidenceLibrary}</div>
            <p className="mt-1 text-xs text-secondary-text">
              {isEnglish ? 'Switch evidence without starting AI or spending quota.' : '切换证据不会启动 AI，也不会消耗额度。'}
            </p>
          </div>
          <div role="tablist" aria-label={model.labels.evidenceLibrary} className="flex max-w-full gap-1 overflow-x-auto pb-1">
            {model.tabs.map((tab) => {
              const Icon = tabIcon(tab.key);
              const isActive = selectedTab?.key === tab.key;
              return (
                <button
                  key={tab.key}
                  type="button"
                  role="tab"
                  aria-selected={isActive}
                  aria-controls={`decision-evidence-panel-${tab.key}`}
                  onClick={() => setActiveTab(tab.key)}
                  className={`inline-flex h-9 shrink-0 items-center gap-1.5 rounded-md border px-3 text-xs font-medium transition-colors ${
                    isActive
                      ? 'border-primary/55 bg-primary/12 text-primary'
                      : 'border-subtle/80 bg-background/35 text-secondary-text hover:text-foreground'
                  }`}
                >
                  <Icon className="h-3.5 w-3.5" aria-hidden="true" />
                  {tab.label}
                </button>
              );
            })}
          </div>
        </div>

        {selectedTab ? (
          <div
            id={`decision-evidence-panel-${selectedTab.key}`}
            role="tabpanel"
            className="mt-3 border-t border-subtle/80 pt-3"
          >
            <p className="text-xs leading-relaxed text-secondary-text">{selectedTab.summary}</p>
            <div className="mt-3 grid gap-2 md:grid-cols-3">
              {selectedTab.items.map((item) => (
                <article key={`${selectedTab.key}-${item.label}`} className="min-w-0 rounded-md border border-subtle/80 bg-background/35 p-3">
                  <div className="text-xs font-semibold text-primary">{item.label}</div>
                  <div className="mt-1 break-words text-sm font-semibold text-foreground">{item.value}</div>
                  <p className="mt-2 text-xs leading-relaxed text-secondary-text">{item.detail}</p>
                </article>
              ))}
            </div>
            {selectedTab.key === 'sources' ? (
              <div className="mt-3 rounded-md border border-primary/30 bg-primary/8 p-3 text-xs leading-relaxed text-secondary-text">
                {model.trust.historySource} / {model.trust.profileSource} · {model.trust.routeLane}
              </div>
            ) : null}
          </div>
        ) : null}
      </div>

      <div className="grid border-t border-subtle/80 lg:grid-cols-2">
        <div className="p-4 lg:border-r lg:border-subtle/80">
          <div className="text-xs font-semibold text-primary">{model.labels.free}</div>
          <div className="mt-2 flex flex-wrap gap-1.5 text-xs text-secondary-text">
            {model.comparison.free.map((item) => (
              <span key={item} className="rounded-md border border-primary/30 bg-primary/8 px-2 py-1">{item}</span>
            ))}
          </div>
        </div>
        <div className="border-t border-subtle/80 p-4 lg:border-t-0">
          <div className="text-xs font-semibold text-warning">{model.labels.premium}</div>
          <div className="mt-2 flex flex-wrap gap-1.5 text-xs text-secondary-text">
            {model.comparison.premium.map((item) => (
              <span key={item} className="rounded-md border border-warning/30 bg-warning/8 px-2 py-1">{item}</span>
            ))}
          </div>
        </div>
      </div>

      <div className="border-t border-subtle/80 px-4 py-3 text-xs leading-relaxed text-secondary-text">
        {model.boundary.disclaimer}
      </div>
    </section>
  );
};
