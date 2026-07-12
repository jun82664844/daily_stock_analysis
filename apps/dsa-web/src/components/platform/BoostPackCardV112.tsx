import { CreditCard } from 'lucide-react';

export type BoostPackProduct = {
  productCode: string;
  priceHkd: number;
  flash: number;
  pro: number;
  balance: { flash: number; pro: number };
  expiresAt: string | null;
  canPurchase: boolean;
  unavailableReason?: string | null;
};

type Props = { language: 'zh' | 'en'; product: BoostPackProduct; onPurchase: () => void };

export default function BoostPackCardV112({ language, product, onPurchase }: Props) {
  return (
    <section className="grid gap-4 border p-4" aria-label={language === 'zh' ? 'API 加油包' : 'API boost pack'}>
      <div className="flex items-start justify-between gap-4">
        <div>
          <strong>{language === 'zh' ? 'API 加油包' : 'API boost pack'}</strong>
          <p className="text-sm text-muted-foreground">{product.flash} Flash + {product.pro} Pro</p>
        </div>
        <strong>HK${product.priceHkd}</strong>
      </div>
      <p className="text-sm">
        {language === 'zh' ? `当前余额：Flash ${product.balance.flash}，Pro ${product.balance.pro}` : `Balance: ${product.balance.flash} Flash, ${product.balance.pro} Pro`}
      </p>
      <p className="text-xs text-muted-foreground">
        {language === 'zh' ? `随本会员周期失效：${product.expiresAt || '-'}；不退款、不结转。` : `Expires with this membership period: ${product.expiresAt || '-'}; no refunds or rollover.`}
      </p>
      <button type="button" disabled={!product.canPurchase} onClick={onPurchase} className="inline-flex items-center justify-center gap-2 border px-4 py-2">
        <CreditCard size={18} /> {language === 'zh' ? '购买加油包' : 'Buy boost pack'}
      </button>
    </section>
  );
}
