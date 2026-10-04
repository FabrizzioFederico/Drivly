const STYLES = {
  light: {
    HOLD: 'bg-hold-soft text-hold-ink',
    CONFIRMADA: 'bg-success-soft text-success-ink',
    EN_CURSO: 'bg-brand-soft text-brand-ink',
    CON_DEUDA: 'bg-debt-soft text-debt-ink',
    FINALIZADA: 'bg-ink-soft text-ink-muted',
    SIN_LUGAR: 'bg-debt-soft text-debt-ink',
  },
  dark: {
    HOLD: 'bg-hold/15 text-hold',
    CONFIRMADA: 'bg-action/15 text-action',
    EN_CURSO: 'bg-brand/20 text-[#7FB2FF]',
    CON_DEUDA: 'bg-debt/15 text-debt-light',
    FINALIZADA: 'bg-ink-subtle/15 text-ink-subtle',
    SIN_LUGAR: 'bg-debt/15 text-debt-light',
  },
};

const DOT = {
  HOLD: 'bg-hold', CONFIRMADA: 'bg-success', EN_CURSO: 'bg-brand', CON_DEUDA: 'bg-debt', FINALIZADA: 'bg-ink-subtle', SIN_LUGAR: 'bg-debt',
};

const LABEL = {
  HOLD: 'HOLD', CONFIRMADA: 'CONFIRMADA', EN_CURSO: 'EN CURSO', CON_DEUDA: 'CON DEUDA', FINALIZADA: 'FINALIZADA',
  EXPIRADA: 'EXPIRADA', CANCELADA: 'CANCELADA', NO_SHOW: 'NO SE PRESENTÓ', SIN_LUGAR: 'SIN LUGAR',
};

/**
 * <StatusBadge estado="HOLD" suffix="04:59" />
 * HOLD y CON_DEUDA llevan punto pulsante para llamar la atención.
 */
export default function StatusBadge({ estado, variant = 'light', suffix, className = '' }) {
  const pulse = estado === 'HOLD' || estado === 'CON_DEUDA';
  return (
    <span
      role="status"
      className={`inline-flex h-7 items-center gap-2 rounded-full px-3 text-[11px] font-extrabold tracking-wider ${STYLES[variant][estado] ?? STYLES[variant].FINALIZADA} ${className}`}
    >
      <span className="relative flex h-2 w-2">
        {pulse && <span className={`absolute inline-flex h-full w-full animate-ping rounded-full opacity-75 ${DOT[estado]}`} />}
        <span className={`relative inline-flex h-2 w-2 rounded-full ${DOT[estado] ?? DOT.FINALIZADA}`} />
      </span>
      {LABEL[estado] ?? estado}
      {suffix && <span className="font-mono">{suffix}</span>}
    </span>
  );
}
