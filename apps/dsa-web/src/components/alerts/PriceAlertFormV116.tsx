import { BellRing } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';

export type ExactPriceRuleType = 'price_above' | 'price_below';

export type PriceAlertDraft = {
  stockCode: string;
  stockName: string;
  ruleType: ExactPriceRuleType;
  threshold: number;
  currency?: string | null;
};

type Props = {
  language: 'zh' | 'en';
  stockCode: string;
  stockName: string;
  currentPrice?: number | null;
  currency?: string | null;
  onSave: (draft: PriceAlertDraft) => Promise<void>;
  notice?: string;
  initialRuleType?: ExactPriceRuleType;
};

export default function PriceAlertFormV116({
  language,
  stockCode,
  stockName,
  currentPrice,
  currency,
  onSave,
  notice,
  initialRuleType = 'price_above',
}: Props) {
  const en = language === 'en';
  const [ruleType, setRuleType] = useState<ExactPriceRuleType>(initialRuleType);
  const [threshold, setThreshold] = useState(String(currentPrice ?? ''));
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setThreshold(String(currentPrice ?? ''));
    setRuleType(initialRuleType);
  }, [currentPrice, initialRuleType, stockCode]);

  const thresholdNumber = Number(threshold);
  const valid = useMemo(
    () => Number.isFinite(thresholdNumber) && thresholdNumber > 0 && thresholdNumber <= 1_000_000_000,
    [thresholdNumber],
  );

  const save = async () => {
    if (!valid || saving) return;
    setSaving(true);
    try {
      await onSave({ stockCode, stockName, ruleType, threshold: thresholdNumber, currency });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex min-w-0 flex-1 flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end">
      <label className="flex min-w-0 flex-col gap-1 text-sm text-secondary-text">
        {en ? 'Price direction' : '到价方向'}
        <select
          aria-label={en ? 'Price direction' : '到价方向'}
          className="h-10 rounded-lg border border-border bg-surface px-3 text-foreground"
          value={ruleType}
          onChange={(event) => setRuleType(event.target.value as ExactPriceRuleType)}
        >
          <option value="price_above">{en ? 'At or above' : '价格达到或高于'}</option>
          <option value="price_below">{en ? 'At or below' : '价格达到或低于'}</option>
        </select>
      </label>
      <label className="flex min-w-0 flex-col gap-1 text-sm text-secondary-text">
        {en ? 'Price threshold' : '到价阈值'}
        <input
          aria-label={en ? 'Price threshold' : '到价阈值'}
          type="number"
          min="0"
          max="1000000000"
          step="any"
          className="h-10 rounded-lg border border-border bg-surface px-3 text-foreground"
          value={threshold}
          onChange={(event) => setThreshold(event.target.value)}
        />
      </label>
      <button
        type="button"
        className="btn-secondary"
        disabled={!valid || saving}
        aria-label={saving ? (en ? 'Saving price alert' : '正在保存到价提醒') : (en ? 'Save price alert' : '保存到价提醒')}
        onClick={() => void save()}
      >
        <BellRing className="h-4 w-4" />
        {saving ? (en ? 'Saving...' : '保存中...') : (en ? 'Save price alert' : '保存到价提醒')}
      </button>
      {notice ? <p className="text-sm text-secondary-text" role="status">{notice}</p> : null}
    </div>
  );
}
