export type SimpleModelOption = {
  optionId: string;
  label: string;
  source: 'platform' | 'byok' | 'user_local';
  providerLabel: string;
  speed: 'fast' | 'balanced' | 'strong';
  purpose: string;
  quotaType: 'flash' | 'pro' | null;
  costUnits: number;
  recommended: boolean;
};

type Props = {
  options: SimpleModelOption[];
  value: string;
  onChange: (optionId: string) => void;
  language: 'zh' | 'en';
};

export default function SimpleModelPickerV112({ options, value, onChange, language }: Props) {
  return (
    <section aria-label={language === 'zh' ? '模型选择' : 'Model selection'} className="grid gap-3">
      <div>
        <strong>{language === 'zh' ? '选择分析模型' : 'Choose analysis model'}</strong>
        <p className="text-sm text-muted-foreground">
          {language === 'zh' ? '只需按用途选择，无需填写模型名称或接口地址。' : 'Choose by purpose. No model name or endpoint is required.'}
        </p>
      </div>
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {options.map((option) => (
          <button
            type="button"
            key={option.optionId}
            aria-pressed={value === option.optionId}
            onClick={() => onChange(option.optionId)}
            className={`min-h-24 border p-3 text-left ${value === option.optionId ? 'border-cyan-400 bg-cyan-950/30' : 'border-border'}`}
          >
            <span className="block font-semibold">{option.label}</span>
            <span className="block text-sm text-muted-foreground">{option.providerLabel} · {option.purpose}</span>
            {option.quotaType ? <span className="mt-2 block text-xs">{option.costUnits} {option.quotaType === 'flash' ? 'Flash' : 'Pro'}</span> : null}
          </button>
        ))}
      </div>
    </section>
  );
}
