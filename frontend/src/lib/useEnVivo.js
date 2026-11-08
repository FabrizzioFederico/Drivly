import { useEffect, useRef } from 'react';

/**
 * Vuelve a llamar a `cargar` cada `ms` mientras la pestaña está a la vista, y enseguida al volver a ella.
 * Con la pestaña oculta no consulta: no gasta servidor ni batería. Nunca superpone dos consultas.
 */
export function useEnVivo(cargar, ms = 5000) {
  const ultima = useRef(cargar);
  useEffect(() => { ultima.current = cargar; }, [cargar]);

  useEffect(() => {
    let enCurso = false;
    const consultar = async () => {
      if (enCurso || document.visibilityState !== 'visible') return;
      enCurso = true;
      try { await ultima.current(); } catch { /* el próximo intento vuelve a probar */ } finally { enCurso = false; }
    };
    const id = setInterval(consultar, ms);
    const alVolver = () => { if (document.visibilityState === 'visible') consultar(); };
    document.addEventListener('visibilitychange', alVolver);
    window.addEventListener('focus', alVolver);
    return () => {
      clearInterval(id);
      document.removeEventListener('visibilitychange', alVolver);
      window.removeEventListener('focus', alVolver);
    };
  }, [ms]);
}
