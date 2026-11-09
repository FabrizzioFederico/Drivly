import { useEffect, useState } from 'react';
import {
  Accordion, AccordionDetails, AccordionSummary, Alert, Box, Button, Card, Container, Link, Stack, TextField, Typography,
} from '@mui/material';
import AccountBalanceWallet from '@mui/icons-material/AccountBalanceWallet';
import Android from '@mui/icons-material/Android';
import CreditCard from '@mui/icons-material/CreditCard';
import EventAvailable from '@mui/icons-material/EventAvailable';
import ExpandMore from '@mui/icons-material/ExpandMore';
import Insights from '@mui/icons-material/Insights';
import PhoneAndroid from '@mui/icons-material/PhoneAndroid';
import QrCode2 from '@mui/icons-material/QrCode2';
import ReceiptLong from '@mui/icons-material/ReceiptLong';
import Search from '@mui/icons-material/Search';
import TrendingUp from '@mui/icons-material/TrendingUp';
import Undo from '@mui/icons-material/Undo';
import client from '../api/client';
import LogoDrivly from '../components/LogoDrivly';

const PANEL = '/panel';
const ENLACES = [['#como-funciona', 'Cómo funciona'], ['#garajes', 'Para garajes'], ['#preguntas', 'Preguntas'], ['#contacto', 'Contacto']];

function Marca({ tamano = 32 }) {
  return (
    <Stack direction="row" spacing={1.25} sx={{ alignItems: 'center' }}>
      <LogoDrivly tamano={tamano} />
      <Typography sx={{ fontWeight: 700, fontSize: tamano * 0.62 }}>Drivly</Typography>
    </Stack>
  );
}

function Cabecera() {
  return (
    <Box component="header" sx={{
      position: 'sticky', top: 0, zIndex: 10, borderBottom: '1px solid var(--border)',
      bgcolor: 'rgba(11,11,12,0.85)', backdropFilter: 'blur(10px)',
    }}>
      <Container maxWidth="lg" sx={{ display: 'flex', alignItems: 'center', gap: 3, height: 64 }}>
        <Link href="/" underline="none" color="inherit" aria-label="Drivly, inicio"><Marca /></Link>
        <Stack component="nav" aria-label="Secciones" direction="row" spacing={3} sx={{ display: { xs: 'none', md: 'flex' }, flex: 1, ml: 2 }}>
          {ENLACES.map(([href, texto]) => (
            <Link key={href} href={href} underline="none" sx={{ color: 'text.secondary', fontSize: 14, fontWeight: 500, '&:hover': { color: 'text.primary' } }}>{texto}</Link>
          ))}
        </Stack>
        <Box sx={{ flex: { xs: 1, md: 0 } }} />
        <Button href={PANEL} variant="contained" sx={{ whiteSpace: 'nowrap' }}>Ingresar</Button>
      </Container>
    </Box>
  );
}

/** Tarjeta ilustrativa de la app: así se ve una reserva. */
function MuestraApp() {
  return (
    <Card sx={{ p: 3, maxWidth: 360, width: '100%', mx: 'auto', bgcolor: 'var(--surface-1)' }} aria-hidden>
      <Typography variant="caption" sx={{ color: 'text.secondary' }}>Garaje cerca · 450 m</Typography>
      <Typography sx={{ fontSize: 20, fontWeight: 700, mt: 0.5 }}>Cochera Thames</Typography>
      <Typography variant="body2" sx={{ color: 'text.secondary' }}>Malabia 2200, Palermo</Typography>
      <Stack direction="row" sx={{ justifyContent: 'space-between', mt: 2 }}>
        <Typography sx={{ fontWeight: 700 }}>$9.000 / hora</Typography>
        <Typography sx={{ color: 'var(--accent)', fontWeight: 700 }}>18 libres</Typography>
      </Stack>
      <Box sx={{ mt: 3, p: 2.5, borderRadius: 2, bgcolor: 'var(--surface-2)', display: 'flex', alignItems: 'center', gap: 2 }}>
        <QrCode2 sx={{ fontSize: 64 }} />
        <Box>
          <Typography sx={{ fontWeight: 700 }}>Reserva confirmada</Typography>
          <Typography variant="body2" sx={{ color: 'text.secondary' }}>Hoy de 10:00 a 13:00 · AB 123 CD</Typography>
        </Box>
      </Box>
    </Card>
  );
}

function Portada() {
  return (
    <Container maxWidth="lg" sx={{ py: { xs: 7, md: 12 } }}>
      <Box sx={{ display: 'grid', gap: { xs: 6, md: 8 }, gridTemplateColumns: { xs: '1fr', md: '1.1fr 0.9fr' }, alignItems: 'center' }}>
        <Box>
          <Typography sx={{ color: 'var(--accent)', fontWeight: 600, fontSize: 14, mb: 2 }}>Estacionamiento en Buenos Aires</Typography>
          <Typography component="h1" sx={{ fontSize: { xs: 36, md: 52 }, fontWeight: 800, lineHeight: 1.1, letterSpacing: '-0.02em' }}>
            Reservá tu cochera antes de salir
          </Typography>
          <Typography sx={{ color: 'text.secondary', fontSize: { xs: 17, md: 19 }, mt: 2.5, maxWidth: 520, lineHeight: 1.6 }}>
            Elegí el garaje, pagá con Mercado Pago y entrá con un QR. Tu lugar te espera, sin dar vueltas buscando dónde dejar el auto.
          </Typography>
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} sx={{ mt: 4 }}>
            <Button variant="contained" size="large" startIcon={<Android />} disabled sx={{ '&.Mui-disabled': { opacity: 0.7 } }}>
              Próximamente en Google Play
            </Button>
            <Button variant="outlined" size="large" href="#garajes">Tengo un garaje</Button>
          </Stack>
        </Box>
        <MuestraApp />
      </Box>
    </Container>
  );
}

function Titulo({ id, sobre, titulo, detalle }) {
  return (
    <Box id={id} sx={{ scrollMarginTop: 88, mb: 5, maxWidth: 680 }}>
      <Typography sx={{ color: 'var(--accent)', fontWeight: 600, fontSize: 14, mb: 1 }}>{sobre}</Typography>
      <Typography component="h2" sx={{ fontSize: { xs: 28, md: 36 }, fontWeight: 800, letterSpacing: '-0.01em' }}>{titulo}</Typography>
      {detalle && <Typography sx={{ color: 'text.secondary', mt: 1.5, fontSize: 17, lineHeight: 1.6 }}>{detalle}</Typography>}
    </Box>
  );
}

function Grilla({ columnas = 3, children }) {
  return <Box sx={{ display: 'grid', gap: 2.5, gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)', md: `repeat(${columnas}, 1fr)` } }}>{children}</Box>;
}

function Item({ Icono, titulo, children, paso }) {
  return (
    <Card sx={{ p: 3, height: '100%' }}>
      <Stack direction="row" spacing={1.5} sx={{ alignItems: 'center', mb: 1.5 }}>
        <Box sx={{ width: 40, height: 40, borderRadius: 1.5, display: 'grid', placeItems: 'center', bgcolor: 'var(--accent-soft)', color: 'var(--accent)' }}>
          <Icono />
        </Box>
        {paso && <Typography sx={{ color: 'text.secondary', fontWeight: 600, fontSize: 14 }}>Paso {paso}</Typography>}
      </Stack>
      <Typography component="h3" sx={{ fontWeight: 700, fontSize: 18 }}>{titulo}</Typography>
      <Typography sx={{ color: 'text.secondary', mt: 1, lineHeight: 1.6 }}>{children}</Typography>
    </Card>
  );
}

function ComoFunciona() {
  return (
    <Container maxWidth="lg" sx={{ py: { xs: 7, md: 10 } }}>
      <Titulo id="como-funciona" sobre="Cómo funciona" titulo="Tres pasos y estacionaste" />
      <Grilla>
        <Item paso={1} Icono={Search} titulo="Buscá un garaje">Elegí el día, la hora y cuánto te quedás. Ves sólo los garajes que tienen lugar en ese horario, con el precio para tu vehículo.</Item>
        <Item paso={2} Icono={CreditCard} titulo="Pagá con Mercado Pago">Con tarjeta o dinero en cuenta. El lugar queda retenido mientras pagás y la reserva se confirma al instante.</Item>
        <Item paso={3} Icono={QrCode2} titulo="Entrá con tu QR">Mostralo al llegar y al salir. Funciona sin señal y también te llega por email con el comprobante.</Item>
      </Grilla>
    </Container>
  );
}

function Conductores() {
  return (
    <Box sx={{ bgcolor: 'var(--surface-1)', borderBlock: '1px solid var(--border)' }}>
      <Container maxWidth="lg" sx={{ py: { xs: 7, md: 10 } }}>
        <Titulo sobre="Para conductores" titulo="Tu lugar asegurado, al precio del garaje" />
        <Grilla columnas={4}>
          <Item Icono={EventAvailable} titulo="Lugar asegurado">Si reservaste, tenés lugar. Y si el garaje se llena, te mostramos los cercanos con lugar.</Item>
          <Item Icono={AccountBalanceWallet} titulo="Mismo precio">Pagás lo mismo que en la caja del garaje, con el tope de estadía: no cobra de más por quedarte.</Item>
          <Item Icono={Undo} titulo="Cancelás sin perder">Reembolso total hasta 2 horas antes del inicio, o en los 10 minutos después de pagar.</Item>
          <Item Icono={ReceiptLong} titulo="Por hora o abono">Reservá unas horas o contratá un abono semanal, mensual o anual sin papeles.</Item>
        </Grilla>
      </Container>
    </Box>
  );
}

function Garajes() {
  return (
    <Container maxWidth="lg" sx={{ py: { xs: 7, md: 10 } }}>
      <Titulo id="garajes" sobre="Para garajes" titulo="Llená los lugares que hoy quedan vacíos"
        detalle="Drivly te trae conductores que pagan por adelantado. Vos seguís atendiendo como siempre: el sistema convive con tus clientes sin reserva." />
      <Box sx={{ display: 'grid', gap: 2.5, gridTemplateColumns: { xs: '1fr', md: '2fr 1fr' }, alignItems: 'stretch' }}>
        <Grilla columnas={2}>
          <Item Icono={TrendingUp} titulo="Más ocupación">Tus horarios flojos aparecen para quien busca dónde estacionar cerca.</Item>
          <Item Icono={CreditCard} titulo="Cobro por adelantado">El pago entra directo en tu cuenta de Mercado Pago. Sin efectivo ni cuentas pendientes.</Item>
          <Item Icono={PhoneAndroid} titulo="Sin equipos especiales">El playero escanea el QR con su celular Android. No hace falta comprar nada.</Item>
          <Item Icono={Insights} titulo="Tu garaje en vivo">Ocupación por hora, reservas, excesos de permanencia y Excel desde el panel web.</Item>
        </Grilla>
        <Card sx={{ p: 4, display: 'flex', flexDirection: 'column', gap: 2, border: '1px solid var(--accent)', bgcolor: 'var(--surface-1)' }}>
          <Typography sx={{ color: 'text.secondary', fontWeight: 600 }}>Cuánto cuesta</Typography>
          <Typography sx={{ fontSize: 56, fontWeight: 800, lineHeight: 1 }}>10 %</Typography>
          <Typography sx={{ fontSize: 18, fontWeight: 600 }}>de cada reserva concretada</Typography>
          <Typography sx={{ color: 'text.secondary', lineHeight: 1.6 }}>
            Sin abono mensual ni costo de alta: si no hay reservas, no pagás nada. La comisión de Mercado Pago es la de tu cuenta, como hoy.
          </Typography>
          <Box sx={{ flex: 1 }} />
          <Button variant="contained" size="large" href="#contacto">Quiero sumar mi garaje</Button>
          <Button variant="text" href={PANEL}>Ya tengo cuenta: ingresar</Button>
        </Card>
      </Box>
    </Container>
  );
}

const PREGUNTAS = [
  ['¿Cómo pago la reserva?', 'Con Mercado Pago, con tarjeta o dinero en cuenta. Nunca cargás datos de tarjeta en Drivly.'],
  ['¿Puedo cancelar?', 'Sí. Hasta 2 horas antes del inicio, o en los 10 minutos posteriores al pago, te devolvemos el total por el mismo medio.'],
  ['¿Qué pasa si me quedo más tiempo?', 'El garaje cobra el tiempo extra con el recargo que tenga configurado. Te avisamos 15 minutos antes de que termine tu reserva.'],
  ['¿Cuánto le cuesta a un garaje?', 'El 10 % de cada reserva concretada. No hay abono mensual ni costo de alta.'],
  ['¿Cuándo cobra el garaje?', 'El pago se acredita en su propia cuenta de Mercado Pago, con los plazos que tenga configurados.'],
  ['¿Sirve si ya tengo clientes sin reserva o mensuales?', 'Sí. El panel te dice cuántos lugares podés dar sin dejar sin lugar a una reserva, y podés ofrecer abonos con el cupo que elijas.'],
];

function Preguntas() {
  return (
    <Box sx={{ bgcolor: 'var(--surface-1)', borderBlock: '1px solid var(--border)' }}>
      <Container maxWidth="md" sx={{ py: { xs: 7, md: 10 } }}>
        <Titulo id="preguntas" sobre="Preguntas frecuentes" titulo="Lo que más nos preguntan" />
        {PREGUNTAS.map(([p, r]) => (
          <Accordion key={p} disableGutters sx={{ bgcolor: 'transparent', boxShadow: 'none', borderBottom: '1px solid var(--border)', '&::before': { display: 'none' } }}>
            <AccordionSummary expandIcon={<ExpandMore />} sx={{ px: 0 }}>
              <Typography sx={{ fontWeight: 600, fontSize: 17 }}>{p}</Typography>
            </AccordionSummary>
            <AccordionDetails sx={{ px: 0, pt: 0 }}>
              <Typography sx={{ color: 'text.secondary', lineHeight: 1.6 }}>{r}</Typography>
            </AccordionDetails>
          </Accordion>
        ))}
      </Container>
    </Box>
  );
}

const VACIO = { nombre: '', email: '', telefono: '', garaje: '', zona: '', mensaje: '', sitio_web: '' };

function Contacto() {
  const [datos, setDatos] = useState(VACIO);
  const [enviando, setEnviando] = useState(false);
  const [resultado, setResultado] = useState(null);
  const [errores, setErrores] = useState({});
  const campo = (k) => ({
    value: datos[k], onChange: (e) => setDatos((d) => ({ ...d, [k]: e.target.value })),
    error: Boolean(errores[k]), helperText: errores[k]?.[0],
  });

  const enviar = async (e) => {
    e.preventDefault();
    setEnviando(true); setResultado(null); setErrores({});
    try {
      const { data } = await client.post('/notificaciones/contacto/', datos);
      setResultado({ ok: true, texto: data.detail });
      setDatos(VACIO);
    } catch (err) {
      setErrores(err.fields ?? {});
      setResultado({ ok: false, texto: err.status === 429 ? 'Mandaste varios mensajes seguidos. Probá de nuevo en un rato.' : err.message });
    } finally { setEnviando(false); }
  };

  return (
    <Container maxWidth="md" sx={{ py: { xs: 7, md: 10 } }}>
      <Titulo id="contacto" sobre="Sumá tu garaje" titulo="Hablemos"
        detalle="Dejanos tus datos y te escribimos para darte de alta. Configurás tarifas, capacidad y playeros desde el panel." />
      <Card component="form" onSubmit={enviar} sx={{ p: { xs: 3, md: 4 } }}>
        <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' } }}>
          <TextField label="Tu nombre" required {...campo('nombre')} />
          <TextField label="Email" type="email" required {...campo('email')} />
          <TextField label="Teléfono" {...campo('telefono')} />
          <TextField label="Nombre del garaje" required {...campo('garaje')} />
          <TextField label="Barrio o dirección" {...campo('zona')} sx={{ gridColumn: { sm: '1 / -1' } }} />
          <TextField label="¿Algo que quieras contarnos?" multiline minRows={3} {...campo('mensaje')} sx={{ gridColumn: { sm: '1 / -1' } }} />
          {/* Trampa para bots: invisible para las personas */}
          <Box aria-hidden sx={{ position: 'absolute', left: -10000, width: 1, height: 1, overflow: 'hidden' }}>
            <input tabIndex={-1} autoComplete="off" name="sitio_web" value={datos.sitio_web}
              onChange={(e) => setDatos((d) => ({ ...d, sitio_web: e.target.value }))} />
          </Box>
        </Box>
        {resultado && <Alert severity={resultado.ok ? 'success' : 'error'} sx={{ mt: 2 }}>{resultado.texto}</Alert>}
        <Button type="submit" variant="contained" size="large" disabled={enviando} sx={{ mt: 3, minWidth: 200 }}>
          {enviando ? 'Enviando…' : 'Enviar'}
        </Button>
      </Card>
    </Container>
  );
}

function Pie() {
  return (
    <Box component="footer" sx={{ borderTop: '1px solid var(--border)' }}>
      <Container maxWidth="lg" sx={{ py: 4, display: 'flex', flexWrap: 'wrap', gap: 2, alignItems: 'center', justifyContent: 'space-between' }}>
        <Stack spacing={0.5}>
          <Marca tamano={24} />
          <Typography variant="body2" sx={{ color: 'text.secondary' }}>© {new Date().getFullYear()} Drivly · Trabajo Final de Carrera, Escuela Da Vinci</Typography>
        </Stack>
        <Link href={PANEL} sx={{ color: 'text.secondary', fontSize: 14 }}>Panel para garajes</Link>
      </Container>
    </Box>
  );
}

/** Landing pública: qué es Drivly para conductores y garajes. El portal de los dueños está en /panel. */
export default function LandingView() {
  useEffect(() => { document.title = 'Drivly · Reservá tu cochera'; }, []);
  return (
    <Box sx={{ bgcolor: 'var(--bg)', minHeight: '100vh', scrollBehavior: 'smooth' }}>
      <Cabecera />
      <main>
        <Portada />
        <ComoFunciona />
        <Conductores />
        <Garajes />
        <Preguntas />
        <Contacto />
      </main>
      <Pie />
    </Box>
  );
}
