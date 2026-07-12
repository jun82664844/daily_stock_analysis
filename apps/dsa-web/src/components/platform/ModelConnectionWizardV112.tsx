import { useEffect, useState } from 'react';
import { KeyRound } from 'lucide-react';

type Provider = 'openai' | 'anthropic' | 'deepseek';
type ConnectorOs = 'windows' | 'macos';

type Props = {
  language: 'zh' | 'en';
  onConnect: (payload: { provider: Provider; apiKey: string }) => Promise<void> | void;
  onCreatePairing?: () => Promise<{ code: string; expiresAt: string }>;
  onRefreshModels?: () => Promise<void> | void;
};

export default function ModelConnectionWizardV112({ language, onConnect, onCreatePairing, onRefreshModels }: Props) {
  const [provider, setProvider] = useState<Provider>('deepseek');
  const [apiKey, setApiKey] = useState('');
  const [busy, setBusy] = useState(false);
  const [connectorOs, setConnectorOs] = useState<ConnectorOs>('windows');
  const [pairing, setPairing] = useState<{ code: string; expiresAt: string } | null>(null);
  const [remainingSeconds, setRemainingSeconds] = useState(0);
  const providers: Array<{ id: Provider; label: string }> = [
    { id: 'deepseek', label: 'DeepSeek' },
    { id: 'openai', label: 'OpenAI' },
    { id: 'anthropic', label: 'Claude' },
  ];

  useEffect(() => {
    if (!pairing) return undefined;
    const tick = () => {
      const remaining = Math.max(0, Math.ceil((new Date(pairing.expiresAt).getTime() - Date.now()) / 1000));
      setRemainingSeconds(remaining);
    };
    tick();
    const timer = window.setInterval(tick, 1000);
    const refreshTimer = onRefreshModels ? window.setInterval(() => void onRefreshModels(), 3000) : undefined;
    return () => {
      window.clearInterval(timer);
      if (refreshTimer !== undefined) window.clearInterval(refreshTimer);
    };
  }, [onRefreshModels, pairing]);

  const submit = async () => {
    if (!apiKey.trim()) return;
    setBusy(true);
    try {
      await onConnect({ provider, apiKey: apiKey.trim() });
      setApiKey('');
    } finally {
      setBusy(false);
    }
  };
  const countdown = `${Math.floor(remainingSeconds / 60)}:${String(remainingSeconds % 60).padStart(2, '0')}`;

  return (
    <section className="grid gap-4" aria-label={language === 'zh' ? '连接我的 API' : 'Connect my API'}>
      <div>
        <strong>{language === 'zh' ? '三步连接我的 API' : 'Connect my API in three steps'}</strong>
        <p className="text-sm text-muted-foreground">
          {language === 'zh' ? '选择服务商，粘贴 Key，然后连接测试。测试可能产生极少量服务商费用。' : 'Choose a provider, paste the key, then connect and test. The test may incur a tiny provider charge.'}
        </p>
      </div>
      <div className="flex flex-wrap gap-2">
        {providers.map((item) => (
          <button type="button" key={item.id} aria-pressed={provider === item.id} onClick={() => setProvider(item.id)} className="border px-3 py-2">
            {item.label}
          </button>
        ))}
      </div>
      <label className="grid gap-1">
        <span>API Key</span>
        <input aria-label="API Key" type="password" autoComplete="off" value={apiKey} onChange={(event) => setApiKey(event.target.value)} className="border bg-transparent px-3 py-2" />
      </label>
      <button type="button" onClick={submit} disabled={busy || !apiKey.trim()} className="inline-flex items-center justify-center gap-2 border px-4 py-2">
        <KeyRound size={18} /> {busy ? (language === 'zh' ? '连接中' : 'Connecting') : (language === 'zh' ? '连接并测试' : 'Connect and test')}
      </button>
      {onCreatePairing ? (
        <div className="grid gap-3 border-t pt-4">
          <strong>{language === 'zh' ? '连接我的 Ollama' : 'Connect my Ollama'}</strong>
          <p className="text-sm text-muted-foreground">
            {language === 'zh' ? '这是轻量连接器，不是 DSA 桌面版；它只主动连接 DSA，不开放公网端口。' : 'This is a lightweight connector, not the DSA desktop app. It makes outbound connections only and opens no public port.'}
          </p>
          <div className="inline-flex w-fit overflow-hidden border" aria-label={language === 'zh' ? '连接器系统' : 'Connector operating system'}>
            <button type="button" aria-pressed={connectorOs === 'windows'} onClick={() => setConnectorOs('windows')} className="px-3 py-2">Windows</button>
            <button type="button" aria-pressed={connectorOs === 'macos'} onClick={() => setConnectorOs('macos')} className="px-3 py-2">macOS</button>
          </div>
          <p className="text-xs text-muted-foreground">
            {language === 'zh' ? '当前仅提供未签名的本地开发包；正式下载必须通过代码签名、公证和真机验收。' : 'Only unsigned local development builds are available. Production downloads require signing, notarization, and physical-device acceptance.'}
          </p>
          {connectorOs === 'windows' ? (
            <a href="/downloads/DSA-Local-Connector-Windows-x64.exe" className="w-fit border px-3 py-2">{language === 'zh' ? '下载 Windows x64 开发包' : 'Download Windows x64 development build'}</a>
          ) : (
            <div className="flex flex-wrap gap-2">
              <a href="/downloads/DSA-Local-Connector-macOS-arm64.dmg" className="border px-3 py-2">Apple Silicon</a>
              <a href="/downloads/DSA-Local-Connector-macOS-x64.dmg" className="border px-3 py-2">Intel</a>
            </div>
          )}
          <button type="button" className="w-fit border px-4 py-2" onClick={async () => setPairing(await onCreatePairing())}>
            {language === 'zh' ? '生成配对码' : 'Generate pairing code'}
          </button>
          {pairing ? (
            <div className="flex flex-wrap items-center gap-3">
              <strong className="font-mono text-lg">{pairing.code}</strong>
              <span>{language === 'zh' ? `剩余 ${countdown}` : `${countdown} remaining`}</span>
            </div>
          ) : null}
          <p className="text-xs text-muted-foreground">WINDOWS_LOCAL_DEV_VERIFIED · LOCAL_CONNECTOR_SIGNING_NOT_READY · REAL_USER_OLLAMA_MACOS_NOT_VERIFIED</p>
        </div>
      ) : null}
    </section>
  );
}
