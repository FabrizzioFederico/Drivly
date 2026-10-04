import { useEffect, useRef, useState } from 'react';

const fmt = (s) => `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;

/** Calcula los segundos restantes contra el reloj real (sobrevive a pestañas en segundo plano). */
export function useCountdown(expiresAt, onExpire) {
  const target = expiresAt ? new Date(expiresAt).getTime() : null;
  const calc = () => (target ? Math.max(0, Math.round((target - Date.now()) / 1000)) : 0);
  const [left, setLeft] = useState(calc);
  const fired = useRef(false);

  useEffect(() => {
    fired.current = false;
    setLeft(calc());
    if (!target) return undefined;
    const id = setInterval(() => {
      const s = calc();
      setLeft(s);
      if (s === 0 && !fired.current) { fired.current = true; onExpire?.(); }
    }, 250);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [target]);

  return left;
}

/**
 * Contador regresivo del estado HOLD (CU-04).
 * <HoldTimer expiresAt={reserva.hold_expira_en} totalSeconds={300} onExpire={...} />
 */
export default function HoldTimer({ expiresAt, totalSeconds = 300, onExpire, size = 84 }) {
  const left = useCountdown(expiresAt, onExpire);
  const deg = (left / totalSeconds) * 360;
  const urgent = left <= 60;
  const color = urgent ? '#FF5252' : '#FF9F43';

  return (
    <div
      className="flex shrink-0 items-center justify-center rounded-full"
      style={{ width: size, height: size, background: `conic-gradient(${color} ${deg}deg, #2E3A4D 0)` }}
      role="timer"
      aria-live="polite"
      aria-label={`Tiempo restante ${fmt(left)}`}
    >
      <div
        className="flex items-center justify-center rounded-full bg-ink font-mono text-lg font-bold"
        style={{ width: size - 14, height: size - 14, color }}
      >
        {fmt(left)}
      </div>
    </div>
  );
}

HoldTimer.format = fmt;
