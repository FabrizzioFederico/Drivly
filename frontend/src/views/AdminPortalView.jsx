import { useEffect, useState } from 'react';
import {
  AppBar, Avatar, Box, Card, CardContent, Chip, Divider, Drawer, IconButton, List, ListItemButton, ListItemIcon,
  ListItemText, Menu, MenuItem, Skeleton, Toolbar, Tooltip, Typography, useMediaQuery,
} from '@mui/material';
import { useTheme } from '@mui/material/styles';
import AccountBalanceWalletOutlined from '@mui/icons-material/AccountBalanceWalletOutlined';
import BarChartOutlined from '@mui/icons-material/BarChartOutlined';
import GroupsOutlined from '@mui/icons-material/GroupsOutlined';
import LocalParkingOutlined from '@mui/icons-material/LocalParkingOutlined';
import MenuIcon from '@mui/icons-material/Menu';
import ReceiptLongOutlined from '@mui/icons-material/ReceiptLongOutlined';
import TuneOutlined from '@mui/icons-material/TuneOutlined';
import { authService } from '../api/authService';
import { USE_MOCKS } from '../api/client';
import { garajesService } from '../api/garajesService';
import CobrosPanel from './admin/CobrosPanel';
import DeudasPanel from './admin/DeudasPanel';
import EquipoPanel from './admin/EquipoPanel';
import GarajePanel from './admin/GarajePanel';
import MonitorPanel from './admin/MonitorPanel';
import TarifasPanel from './admin/TarifasPanel';

const ANCHO_MENU = 272;
const ANCHO_ICONOS = 72;

const NAV = [
  { id: 'garaje', label: 'Mi Garaje', Icono: LocalParkingOutlined },
  { id: 'tarifas', label: 'Capacidad y Tarifas', Icono: TuneOutlined },
  { id: 'equipo', label: 'Equipo (Playeros)', Icono: GroupsOutlined },
  { id: 'cobros', label: 'Cobros (Mercado Pago)', Icono: AccountBalanceWalletOutlined },
  { id: 'deudas', label: 'Deudas', Icono: ReceiptLongOutlined },
  { id: 'reportes', label: 'Reportes y Caja', Icono: BarChartOutlined },
];

const iniciales = (nombre) => (nombre || 'A').split(' ').map((w) => w[0]).join('').slice(0, 2).toUpperCase();

export default function AdminPortalView({ user }) {
  const theme = useTheme();
  const escritorio = useMediaQuery(theme.breakpoints.up('lg'), { noSsr: true });
  const movil = useMediaQuery(theme.breakpoints.down('sm'), { noSsr: true });
  // Escritorio: menú completo. Tablet: sólo íconos, y la hamburguesa lo expande. Celular: drawer cerrado que tapa el contenido.
  const [expandido, setExpandido] = useState(escritorio);
  const [menuCelular, setMenuCelular] = useState(false);
  const [cuenta, setCuenta] = useState(null);
  const abierto = movil ? menuCelular : expandido;
  const anchoMenu = movil ? 0 : expandido ? ANCHO_MENU : ANCHO_ICONOS;
  const soloIconos = !movil && !expandido;

  useEffect(() => { setExpandido(escritorio); }, [escritorio]);

  const [garaje, setGaraje] = useState(null);
  const [sinGaraje, setSinGaraje] = useState(false);
  // Al volver de autorizar en Mercado Pago el backend redirige a /?mp_conexion=ok|error
  const [retornoMP] = useState(() => new URLSearchParams(window.location.search).get('mp_conexion'));
  const [section, setSection] = useState(retornoMP ? 'cobros' : 'garaje');

  useEffect(() => {
    if (retornoMP) window.history.replaceState({}, '', '/');
  }, [retornoMP]);

  useEffect(() => {
    garajesService.list()
      .then((gs) => {
        if (gs.length) setGaraje(gs[0]);
        else setSinGaraje(true);
      })
      .catch(() => setSinGaraje(true));
  }, []);

  const alternarMenu = () => (movil ? setMenuCelular((a) => !a) : setExpandido((a) => !a));
  const elegir = (id) => { setSection(id); setMenuCelular(false); };
  const garajeId = garaje?.id;

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh' }}>
      {/* Por encima del menú: la hamburguesa queda siempre a mano */}
      <AppBar position="fixed" sx={{ zIndex: theme.zIndex.drawer + 1 }}>
        <Toolbar sx={{ gap: 1 }}>
          <IconButton color="inherit" edge="start" onClick={alternarMenu} aria-label={abierto ? 'Cerrar menú' : 'Abrir menú'} aria-expanded={abierto}>
            <MenuIcon />
          </IconButton>
          <Avatar variant="rounded" sx={{ width: 32, height: 32, bgcolor: 'var(--accent)', color: 'var(--bg)', fontSize: 16, fontWeight: 700 }}>D</Avatar>
          <Typography sx={{ fontWeight: 700 }}>Drivly</Typography>
          {USE_MOCKS && <Chip label="DATOS SIMULADOS" size="small" color="warning" sx={{ fontWeight: 700 }} />}
          <Box sx={{ flexGrow: 1 }} />
          <IconButton onClick={(e) => setCuenta(e.currentTarget)} aria-label="Cuenta" sx={{ p: 0.5 }}>
            <Avatar sx={{ width: 36, height: 36, fontSize: 14, fontWeight: 600, bgcolor: 'var(--surface-2)', color: 'var(--text-primary)', border: '1px solid var(--border)' }}>{iniciales(user?.nombre)}</Avatar>
          </IconButton>
          <Menu anchorEl={cuenta} open={Boolean(cuenta)} onClose={() => setCuenta(null)}>
            <Box sx={{ px: 2, py: 1 }}>
              <Typography variant="body2" sx={{ fontWeight: 700 }}>{user?.nombre ?? 'Administrador'}</Typography>
              <Typography variant="caption" sx={{ color: 'text.secondary' }}>{user?.email ?? 'Propietario'}</Typography>
            </Box>
            <Divider />
            <MenuItem onClick={() => authService.logout()}>Salir</MenuItem>
          </Menu>
        </Toolbar>
      </AppBar>

      <Drawer
        variant={movil ? 'temporary' : 'permanent'}
        open={movil ? menuCelular : true}
        onClose={() => setMenuCelular(false)}
        ModalProps={{ keepMounted: true }}
        sx={{
          '& .MuiDrawer-paper': {
            width: movil ? ANCHO_MENU : anchoMenu,
            boxSizing: 'border-box',
            overflowX: 'hidden',
            transition: theme.transitions.create('width', { duration: theme.transitions.duration.enteringScreen }),
          },
        }}
      >
        <Toolbar />
        {garaje && !soloIconos && (
          <Box sx={{ px: 3, pt: 3, pb: 1 }}>
            <Typography variant="overline" sx={{ display: 'block', color: 'text.secondary', letterSpacing: '0.1em', lineHeight: 1.6 }}>Garaje</Typography>
            <Typography sx={{ fontWeight: 600 }} noWrap>{garaje.nombre}</Typography>
          </Box>
        )}
        <List component="nav" aria-label="Secciones" sx={{ px: 1.5 }}>
          {NAV.map(({ id, label, Icono }) => (
            <Tooltip key={id} title={soloIconos ? label : ''} placement="right">
              <ListItemButton selected={section === id} onClick={() => elegir(id)} aria-current={section === id ? 'page' : undefined} aria-label={label}
                sx={{ mb: 0.5, justifyContent: soloIconos ? 'center' : 'flex-start' }}>
                <ListItemIcon sx={{ minWidth: soloIconos ? 0 : 40 }}><Icono /></ListItemIcon>
                {!soloIconos && <ListItemText primary={label} slotProps={{ primary: { variant: 'body2', sx: { fontWeight: section === id ? 600 : 400 } } }} />}
              </ListItemButton>
            </Tooltip>
          ))}
        </List>
      </Drawer>

      <Box
        component="main"
        sx={{
          flexGrow: 1,
          minWidth: 0,
          ml: `${anchoMenu}px`,
          transition: theme.transitions.create('margin-left', { duration: theme.transitions.duration.enteringScreen }),
        }}
      >
        <Toolbar />
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3, p: { xs: 2, sm: 3, md: 4 } }}>
          {sinGaraje ? (
            <Card>
              <CardContent sx={{ p: 4 }}>
                <Typography variant="h2" gutterBottom>No tenés ningún garaje registrado</Typography>
                <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                  Contactá a soporte de Drivly para dar de alta tu establecimiento, o ejecutá <code>python manage.py seed_dev</code> en el servidor para cargar datos de prueba.
                </Typography>
              </CardContent>
            </Card>
          ) : !garajeId ? (
            <Skeleton variant="rounded" height={192} />
          ) : (
            <>
              {section === 'tarifas' && <TarifasPanel garajeId={garajeId} />}
              {section === 'reportes' && <MonitorPanel garajeId={garajeId} />}
              {section === 'garaje' && <GarajePanel garajeId={garajeId} />}
              {section === 'equipo' && <EquipoPanel garajeId={garajeId} />}
              {section === 'cobros' && <CobrosPanel garajeId={garajeId} retorno={retornoMP} />}
              {section === 'deudas' && <DeudasPanel garajeId={garajeId} />}
            </>
          )}
        </Box>
      </Box>
    </Box>
  );
}
