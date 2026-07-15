import { ExternalLink, Trash2, X } from 'lucide-react';

import type { AlphaSiftCandidate } from '../../api/alphasift';
import { dataCompletenessLabel, dataFreshnessLabel, type ScreeningLanguage } from './screeningModelV104';

type Props = {
  candidates: AlphaSiftCandidate[];
  selectedCodes: string[];
  language: ScreeningLanguage;
  onRemove: (code: string) => void;
  onClear: () => void;
  onOpenData: (code: string) => void;
};

const formatNumber = (value?: number | null) =>
  typeof value === 'number' && Number.isFinite(value)
    ? new Intl.NumberFormat('en-US', { maximumFractionDigits: 4 }).format(value)
    : '-';

export default function ScreeningCompareTrayV104({
  candidates,
  selectedCodes,
  language,
  onRemove,
  onClear,
  onOpenData,
}: Props) {
  const en = language === 'en';
  const selected = selectedCodes
    .map((code) => candidates.find((candidate) => candidate.code.toUpperCase() === code.toUpperCase()))
    .filter((candidate): candidate is AlphaSiftCandidate => Boolean(candidate));

  if (selected.length < 2) return null;

  return (
    <section data-testid="screening-compare-tray-v104" className="mb-4 rounded-lg border border-primary/35 bg-card p-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-foreground">{en ? 'Data comparison' : '数据横向比较'}</h2>
          <p className="mt-1 text-xs text-secondary-text">{selected.length}/5</p>
        </div>
        <button
          data-testid="screening-compare-clear"
          className="inline-flex min-h-9 items-center gap-2 rounded-lg border border-border px-3 text-sm text-secondary-text"
          type="button"
          onClick={onClear}
        >
          <Trash2 className="h-4 w-4" />
          {en ? 'Clear' : '清空'}
        </button>
      </div>

      <div className="mt-4 grid gap-3 lg:hidden">
        {selected.map((candidate) => (
          <article key={candidate.code} className="rounded-lg border border-border bg-surface p-3">
            <div className="flex items-start justify-between gap-2">
              <strong className="font-mono text-foreground">{candidate.code}</strong>
              <button
                data-testid={`screening-compare-remove-${candidate.code}`}
                className="grid h-8 w-8 place-items-center rounded-lg border border-border text-secondary-text"
                type="button"
                aria-label={en ? 'Remove from comparison' : '移出比较'}
                onClick={() => onRemove(candidate.code)}
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <dl className="mt-3 grid grid-cols-2 gap-2 text-sm">
              <div><dt className="text-xs text-secondary-text">{en ? 'Price' : '价格'}</dt><dd data-testid={`screening-compare-price-${candidate.code}`} className="text-foreground">{formatNumber(candidate.price)}</dd></div>
              <div><dt className="text-xs text-secondary-text">{en ? 'Change' : '涨跌幅'}</dt><dd className="text-foreground">{formatNumber(candidate.changePct)}{typeof candidate.changePct === 'number' ? '%' : ''}</dd></div>
              <div><dt className="text-xs text-secondary-text">{en ? 'Freshness' : '新鲜度'}</dt><dd className="text-foreground">{dataFreshnessLabel(candidate.screeningBrief?.dataFreshness || 'unavailable', language)}</dd></div>
              <div><dt className="text-xs text-secondary-text">{en ? 'Coverage' : '完整度'}</dt><dd className="text-foreground">{dataCompletenessLabel(candidate.screeningBrief?.dataCompleteness || 0, language)}</dd></div>
            </dl>
          </article>
        ))}
      </div>

      <div className="mt-4 hidden max-w-full overflow-x-auto lg:block">
        <table className="w-full border-collapse text-sm">
          <thead><tr className="border-b border-border text-left text-xs text-secondary-text"><th className="px-2 py-2">{en ? 'Symbol' : '代码'}</th><th className="px-2 py-2">{en ? 'Price' : '价格'}</th><th className="px-2 py-2">{en ? 'Change' : '涨跌幅'}</th><th className="px-2 py-2">{en ? 'Industry' : '行业'}</th><th className="px-2 py-2">{en ? 'Data state' : '数据状态'}</th><th className="w-24 px-2 py-2">{en ? 'Actions' : '操作'}</th></tr></thead>
          <tbody>
            {selected.map((candidate) => (
              <tr key={candidate.code} className="border-b border-border/70">
                <td className="px-2 py-3 font-mono text-foreground">{candidate.code}</td>
                <td className="px-2 py-3 text-foreground">{formatNumber(candidate.price)}</td>
                <td className="px-2 py-3 text-foreground">{formatNumber(candidate.changePct)}{typeof candidate.changePct === 'number' ? '%' : ''}</td>
                <td className="px-2 py-3 text-secondary-text">{candidate.industry || '-'}</td>
                <td className="px-2 py-3 text-secondary-text">{dataFreshnessLabel(candidate.screeningBrief?.dataFreshness || 'unavailable', language)}</td>
                <td className="px-2 py-3">
                  <div className="flex gap-2">
                    <button className="grid h-8 w-8 place-items-center rounded-lg border border-border" type="button" aria-label={en ? 'Open data' : '打开数据'} onClick={() => onOpenData(candidate.code)}><ExternalLink className="h-4 w-4" /></button>
                    <button className="grid h-8 w-8 place-items-center rounded-lg border border-border" type="button" aria-label={en ? 'Remove' : '移出比较'} onClick={() => onRemove(candidate.code)}><X className="h-4 w-4" /></button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
