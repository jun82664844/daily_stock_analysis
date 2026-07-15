import { Bell, X } from 'lucide-react';
import { useMemo, useState } from 'react';

import type { ScreeningLanguage } from './screeningModelV104';

export type ScreeningReminderSavePayload = {
  stockCode: string;
  ruleType: string;
  threshold: number | null;
};

export type ScreeningReminderState = 'idle' | 'saving' | 'saved' | 'login-required' | 'error';

type Props = {
  stockCode: string;
  language: ScreeningLanguage;
  state: ScreeningReminderState;
  onClose: () => void;
  onSave: (payload: ScreeningReminderSavePayload) => void;
};

const THRESHOLD_RULES = new Set(['price_move', 'volume_change']);

export default function ScreeningReminderPanelV104({ stockCode, language, state, onClose, onSave }: Props) {
  const en = language === 'en';
  const [ruleType, setRuleType] = useState('price_move');
  const [thresholdText, setThresholdText] = useState('3');
  const needsThreshold = THRESHOLD_RULES.has(ruleType);
  const threshold = Number(thresholdText);
  const canSave = !needsThreshold || (Number.isFinite(threshold) && threshold > 0);
  const statusText = useMemo(() => ({
    idle: '',
    saving: en ? 'Saving alert' : '正在保存提醒',
    saved: en ? 'Alert saved' : '提醒已保存',
    'login-required': en ? 'Login to save a private alert.' : '登录后可保存个人提醒。',
    error: en ? 'Alert could not be saved.' : '提醒保存失败。',
  })[state], [en, state]);

  return (
    <section data-testid="screening-reminder-panel-v104" className="rounded-lg border border-primary/35 bg-card p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 text-base font-semibold text-foreground"><Bell className="h-4 w-4 text-cyan" />{en ? 'Condition alert' : '条件提醒'}</h2>
          <p className="mt-1 text-sm text-secondary-text">{stockCode} · {en ? 'Notification only when the user-defined condition is met.' : '仅在用户设置的条件满足时通知。'}</p>
        </div>
        <button className="grid h-9 w-9 place-items-center rounded-lg border border-border text-secondary-text" type="button" aria-label={en ? 'Close' : '关闭'} onClick={onClose}><X className="h-4 w-4" /></button>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto] sm:items-end">
        <label className="text-sm text-secondary-text">
          <span className="mb-1 block">{en ? 'Alert type' : '提醒类型'}</span>
          <select className="min-h-10 w-full rounded-lg border border-border bg-surface px-3 text-foreground" aria-label={en ? 'Alert type' : '提醒类型'} value={ruleType} onChange={(event) => setRuleType(event.target.value)}>
            <option value="price_move">{en ? 'Absolute price move (%)' : '涨跌幅绝对值 (%)'}</option>
            <option value="volume_change">{en ? 'Volume change (%)' : '成交量变化 (%)'}</option>
            <option value="ma20_cross">{en ? 'MA20 crossing event' : '穿越 MA20'}</option>
            <option value="source_update">{en ? 'Traceable source update' : '可追溯来源更新'}</option>
            <option value="data_quality">{en ? 'Data state change' : '数据状态变化'}</option>
          </select>
        </label>
        <label className="text-sm text-secondary-text">
          <span className="mb-1 block">{en ? 'User-defined threshold' : '用户设置阈值'}</span>
          <input className="min-h-10 w-full rounded-lg border border-border bg-surface px-3 text-foreground disabled:opacity-50" aria-label={en ? 'User-defined threshold' : '用户设置阈值'} type="number" min="0.01" step="0.01" disabled={!needsThreshold} value={needsThreshold ? thresholdText : ''} onChange={(event) => setThresholdText(event.target.value)} />
        </label>
        <button data-testid="screening-reminder-save" className="inline-flex min-h-10 items-center justify-center gap-2 rounded-lg border border-primary/50 bg-primary/10 px-4 font-semibold text-cyan disabled:cursor-not-allowed disabled:opacity-45" type="button" disabled={!canSave || state === 'saving' || state === 'saved'} onClick={() => onSave({ stockCode, ruleType, threshold: needsThreshold ? threshold : null })}><Bell className="h-4 w-4" />{en ? 'Save alert' : '保存提醒'}</button>
      </div>
      {statusText ? <p className="mt-3 text-sm text-secondary-text" role="status">{statusText}</p> : null}
      <p className="mt-3 text-xs text-secondary-text">{en ? 'Alerts report observed data events and do not contain trading instructions.' : '提醒只报告已观测的数据事件，不包含交易指令。'}</p>
    </section>
  );
}
