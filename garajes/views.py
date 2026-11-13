from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from cuentas.models import Rol, Usuario
from cuentas.perfil import imagen_a_jpeg
from cuentas.permissions import EsAdminGaraje
from reportes.informe import informe as informe_de_caja
from reportes.informe import pdf as pdf_de_informe
from reportes.services import metricas_del_dia
from reservas.disponibilidad import cercanos_a, garajes_con_disponibilidad
from reservas.models import MODALIDADES_ABONO, EstadoReserva, Modalidad
from reservas.ocupacion import ocupantes, pico, sin_lugar_por_overstay
from reservas.serializers import GarajeDisponibleSerializer

from .geo import caja_alrededor, distancia_m
from .models import Garaje, Tarifa
from .serializers import (
    GarajePublicoSerializer,
    GarajeSerializer,
    PlayeroSerializer,
    TarifaSerializer,
)


class GarajeViewSet(viewsets.ModelViewSet):
    """
    /api/garajes/
      Conductor: lista y detalle de garajes activos. Con ?lat=&lng=&radio= ordena por cercanía.
      Admin: CRUD de sus garajes (borrar = desactivar).
      Playero: sólo su garaje.
    """

    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        u = self.request.user
        qs = Garaje.objects.prefetch_related("tarifas")
        if u.rol == Rol.ADMIN_GARAJE:
            return qs.filter(admin=u)
        if u.rol == Rol.PLAYERO:
            return qs.filter(id=u.garaje_id)
        return qs.filter(activo=True)

    def get_serializer_class(self):
        return GarajePublicoSerializer if self.request.user.rol == Rol.CONDUCTOR else GarajeSerializer

    def get_permissions(self):
        # Lectura para todos los roles; la ocupación filtra su propio rol adentro.
        if self.action not in ("list", "retrieve", "disponibles", "cercanos", "ocupacion"):
            return [IsAuthenticated(), EsAdminGaraje()]
        return super().get_permissions()

    def list(self, request, *args, **kwargs):
        lat, lng = request.query_params.get("lat"), request.query_params.get("lng")
        if lat is None or lng is None:
            return super().list(request, *args, **kwargs)
        try:
            lat, lng = Decimal(lat), Decimal(lng)
            radio = int(request.query_params.get("radio", settings.DRIVLY_RADIO_CERCANOS_M))
        except (InvalidOperation, ValueError):
            raise ValidationError("lat, lng y radio deben ser numéricos.")
        lat_min, lat_max, lng_min, lng_max = caja_alrededor(lat, lng, radio)
        candidatos = self.get_queryset().filter(
            lat__range=(lat_min, lat_max), lng__range=(lng_min, lng_max)
        )
        cercanos = []
        for garaje in candidatos:
            garaje.distancia_m = distancia_m(lat, lng, garaje.lat, garaje.lng)
            if garaje.distancia_m <= radio:
                cercanos.append(garaje)
        cercanos.sort(key=lambda g: g.distancia_m)
        return Response(self.get_serializer(cercanos, many=True).data)

    def perform_create(self, serializer):
        serializer.save(admin=self.request.user)

    def destroy(self, request, *args, **kwargs):
        garaje = self.get_object()
        garaje.activo = False  # nunca se borra: tiene reservas e historial asociados
        garaje.save(update_fields=["activo"])
        return Response(status=status.HTTP_204_NO_CONTENT)

    # ---------- Disponibilidad (reglas 1, 5 y 6) ----------

    @action(detail=False, methods=["get"])
    def disponibles(self, request):
        """
        GET /api/garajes/disponibles/?lat&lng&radio&inicio&fin&modalidad
        Garajes que ofrecen la modalidad, con lugares libres en TODO el intervalo. Los llenos vienen
        con lugares_libres = 0 para que la app ofrezca los cercanos.
        """
        p = request.query_params
        try:
            lat, lng = Decimal(p["lat"]), Decimal(p["lng"])
            radio = int(p.get("radio", settings.DRIVLY_RADIO_CERCANOS_M))
        except (KeyError, InvalidOperation, ValueError):
            raise ValidationError("lat y lng son obligatorios y numéricos.")
        modalidad, ini, fin = _intervalo(p)
        datos = garajes_con_disponibilidad(lat, lng, ini, fin, modalidad, radio, categoria=_categoria(request))
        return Response(GarajeDisponibleSerializer(datos, many=True).data)

    @action(detail=True, methods=["get"])
    def cercanos(self, request, pk=None):
        """GET /api/garajes/{id}/cercanos/?inicio&fin&modalidad — garajes con lugar cerca de uno lleno."""
        modalidad, ini, fin = _intervalo(request.query_params)
        datos = cercanos_a(self.get_object(), ini, fin, modalidad, categoria=_categoria(request))
        return Response(GarajeDisponibleSerializer(datos, many=True).data)

    @action(detail=True, methods=["get"])
    def ocupacion(self, request, pk=None):
        """
        GET /api/garajes/{id}/ocupacion/ — semáforo del playero y monitor del admin (regla 6).
        libres_presencial: cuántos clientes sin reserva pueden entrar ahora sin dejar sin lugar a las
        reservas que llegan dentro de la ventana (la salida estimada por defecto del garaje).
        """
        if request.user.rol not in (Rol.ADMIN_GARAJE, Rol.PLAYERO):
            raise PermissionDenied("Sólo para el garaje.")
        return Response(_ocupacion(self.get_object()))

    @action(detail=True, methods=["post"])
    def activar(self, request, pk=None):
        garaje = self.get_object()
        garaje.activo = True
        garaje.save(update_fields=["activo"])
        return Response(GarajeSerializer(garaje).data)

    @action(detail=True, methods=["get"])
    def metricas(self, request, pk=None):
        """GET /api/garajes/{id}/metricas/?fecha=YYYY-MM-DD — por defecto, hoy (CU-10)."""
        texto = request.query_params.get("fecha")
        fecha = parse_date(texto) if texto else None
        if texto and fecha is None:
            raise ValidationError({"fecha": "Usá el formato YYYY-MM-DD."})
        return Response(metricas_del_dia(self.get_object(), fecha))

    def _periodo_de_informe(self, request):
        """?desde=AAAA-MM-DD&hasta=AAAA-MM-DD (las dos incluidas). Sin fechas: hoy. Hasta un año."""
        if request.user.rol != Rol.ADMIN_GARAJE:
            raise PermissionDenied("El informe es sólo para el administrador del garaje.")
        hoy = timezone.localdate()
        fechas = {}
        for clave in ("desde", "hasta"):
            texto = request.query_params.get(clave)
            try:
                fechas[clave] = parse_date(texto) if texto else hoy
            except ValueError:  # bien formada pero inexistente (mes 13, 31 de abril)
                fechas[clave] = None
            if fechas[clave] is None:
                raise ValidationError({clave: "Usá una fecha válida con el formato AAAA-MM-DD."})
        if fechas["desde"] > fechas["hasta"]:
            raise ValidationError({"desde": "Tiene que ser anterior a la fecha hasta."})
        if (fechas["hasta"] - fechas["desde"]).days > 366:
            raise ValidationError({"desde": "El período puede ser de hasta un año."})
        return self.get_object(), fechas["desde"], fechas["hasta"]

    @action(detail=True, methods=["get"])
    def informe(self, request, pk=None):
        """GET /api/garajes/{id}/informe/?desde&hasta — ingresos por medio, comisión y cierres de caja."""
        garaje, desde, hasta = self._periodo_de_informe(request)
        return Response(informe_de_caja(garaje, desde, hasta))

    @action(detail=True, methods=["get"], url_path="informe/pdf")
    def informe_pdf(self, request, pk=None):
        """GET /api/garajes/{id}/informe/pdf/?desde&hasta — el mismo informe en PDF para imprimir o mandar."""
        garaje, desde, hasta = self._periodo_de_informe(request)
        contenido = pdf_de_informe(informe_de_caja(garaje, desde, hasta))
        nombre = f"drivly-informe-{desde:%Y-%m-%d}" + ("" if desde == hasta else f"-al-{hasta:%Y-%m-%d}") + ".pdf"
        respuesta = HttpResponse(contenido, content_type="application/pdf")
        respuesta["Content-Disposition"] = f'attachment; filename="{nombre}"'
        return respuesta

    @action(detail=True, methods=["put", "delete"], parser_classes=[MultiPartParser])
    def foto(self, request, pk=None):
        """PUT /api/garajes/{id}/foto/ (multipart, campo `foto`) la reemplaza; DELETE la quita. Sólo su admin."""
        garaje = self.get_object()
        anterior = garaje.foto.name
        if request.method == "DELETE":
            garaje.foto = ""
            garaje.save(update_fields=["foto"])
        else:
            archivo = request.FILES.get("foto")
            if archivo is None:
                raise ValidationError({"foto": "Elegí una imagen."})
            # 16:9 como la tarjeta de la app; hasta 8 MB porque suele ser una foto de cámara sin achicar
            contenido = imagen_a_jpeg(archivo, (1280, 720), max_mb=8)
            garaje.foto.save("foto.jpg", ContentFile(contenido), save=False)
            garaje.save(update_fields=["foto"])
        if anterior and anterior != garaje.foto.name:
            garaje.foto.storage.delete(anterior)
        return Response(GarajeSerializer(garaje).data)

    @action(detail=True, methods=["get", "put"])
    def tarifas(self, request, pk=None):
        """
        GET  /api/garajes/{id}/tarifas/ — lista las tarifas del garaje.
        PUT  /api/garajes/{id}/tarifas/ — reemplaza la lista completa (bulk replace).
        Las modalidades ausentes dejan de ofrecerse.
        """
        garaje = self.get_object()
        if request.method == "GET":
            return Response(TarifaSerializer(garaje.tarifas.all(), many=True, context={"request": request}).data)
        if not isinstance(request.data, list):
            raise ValidationError("Se espera una lista de tarifas.")
        with transaction.atomic():
            garaje.tarifas.all().delete()
            creadas = []
            for dato in request.data:
                s = TarifaSerializer(data={**dato, "garaje": str(garaje.id)}, context={"request": request})
                s.is_valid(raise_exception=True)
                creadas.append(s.save())
        return Response(TarifaSerializer(creadas, many=True).data)

    @action(detail=True, methods=["get", "post"])
    def playeros(self, request, pk=None):
        garaje = self.get_object()
        if request.method == "GET":
            return Response(PlayeroSerializer(garaje.playeros.all(), many=True).data)
        datos = PlayeroSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        with transaction.atomic():
            playero = Usuario.objects.filter(email=datos.validated_data["email"]).first()
            if playero:  # conductor que pasa a playero, o playero que quedó sin garaje
                playero.rol, playero.garaje, playero.is_active = Rol.PLAYERO, garaje, True
                playero.nombre = datos.validated_data.get("nombre") or playero.nombre
                playero.save(update_fields=["rol", "garaje", "is_active", "nombre"])
            else:
                playero = Usuario.objects.create_user(
                    email=datos.validated_data["email"],
                    nombre=datos.validated_data.get("nombre", ""),
                    rol=Rol.PLAYERO,
                    garaje=garaje,
                )
        return Response(PlayeroSerializer(playero).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["delete"], url_path=r"playeros/(?P<usuario_id>[0-9a-f-]+)")
    def quitar_playero(self, request, pk=None, usuario_id=None):
        garaje = self.get_object()
        playero = get_object_or_404(garaje.playeros, id=usuario_id)
        # Vuelve a ser conductor: puede seguir usando la app, pero ya no opera el garaje
        playero.rol, playero.garaje = Rol.CONDUCTOR, None
        playero.save(update_fields=["rol", "garaje"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class TarifaViewSet(viewsets.ModelViewSet):
    """/api/tarifas/?garaje=<id> — sólo el admin, sobre sus propios garajes."""

    serializer_class = TarifaSerializer
    permission_classes = [IsAuthenticated, EsAdminGaraje]

    def get_queryset(self):
        qs = Tarifa.objects.filter(garaje__admin=self.request.user).select_related("garaje")
        garaje = self.request.query_params.get("garaje")
        return qs.filter(garaje_id=garaje) if garaje else qs

    def perform_update(self, serializer):
        if "garaje" in serializer.validated_data and serializer.validated_data["garaje"] != serializer.instance.garaje:
            raise PermissionDenied("Una tarifa no puede cambiar de garaje.")
        serializer.save()


def _categoria(request):
    """
    Categoría del vehículo `?vehiculo=<id>` del conductor (opcional): con ella los precios son los que va a
    pagar y no aparecen garajes sin tarifa para su vehículo. Un id ajeno o sin validar se ignora.
    """
    vehiculo_id = request.query_params.get("vehiculo")
    if not vehiculo_id or request.user.rol != Rol.CONDUCTOR:
        return None
    try:
        vehiculo = request.user.vehiculos.filter(pk=vehiculo_id).first()
    except DjangoValidationError:  # id que no es un UUID
        return None
    return vehiculo.categoria if vehiculo and vehiculo.validado else None


def _intervalo(params):
    """modalidad, inicio y fin desde la query. Por defecto: por hora, desde ahora y por 2 horas."""
    modalidad = params.get("modalidad", Modalidad.HORA)
    if modalidad not in (Modalidad.HORA, *MODALIDADES_ABONO):
        raise ValidationError({"modalidad": "Usá HORA, SEMANAL, MENSUAL o ANUAL."})
    ini = parse_datetime(params["inicio"]) if params.get("inicio") else timezone.now()
    if ini is None or timezone.is_naive(ini):
        raise ValidationError({"inicio": "Fecha ISO 8601 con zona horaria, ej. 2026-10-23T14:00:00-03:00."})
    if modalidad in MODALIDADES_ABONO:
        from reservas.periodos import fin_de_abono
        return modalidad, ini, fin_de_abono(ini, modalidad)
    fin = parse_datetime(params["fin"]) if params.get("fin") else ini + timedelta(hours=2)
    if fin is None or timezone.is_naive(fin) or fin <= ini:
        raise ValidationError({"fin": "Debe ser una fecha ISO 8601 con zona horaria, posterior al inicio."})
    return modalidad, ini, fin


def _ocupacion(garaje):
    ahora = timezone.now()
    ventana = garaje.salida_estimada_default_min
    hasta = ahora + timedelta(minutes=ventana)

    en_ventana = ocupantes(garaje.id, ahora, hasta, ahora)
    ahora_mismo = [o for o in en_ventana if o.inicio <= ahora < o.fin]
    ocupados_app = sum(o.modalidad == Modalidad.HORA for o in ahora_mismo)
    ocupados_abonos = sum(o.modalidad in MODALIDADES_ABONO for o in ahora_mismo)
    ocupados_presencial = sum(o.modalidad == Modalidad.PRESENCIAL for o in ahora_mismo)
    proximas_app = sum(
        o.modalidad == Modalidad.HORA and o.estado in (EstadoReserva.HOLD, EstadoReserva.CONFIRMADA)
        and ahora < o.inicio <= hasta
        for o in en_ventana
    )

    # Franjas horarias de hoy (06 a 23, hora de Argentina) para el monitor del admin
    local = timezone.localtime(ahora)
    dia = local.replace(hour=6, minute=0, second=0, microsecond=0)
    del_dia = ocupantes(garaje.id, dia, dia + timedelta(hours=18), ahora)
    franjas = []
    for h in range(18):
        t = dia + timedelta(hours=h)
        activos = [o for o in del_dia if o.inicio <= t < o.fin]
        franjas.append({
            "hora": t.hour,
            "app": sum(o.modalidad != Modalidad.PRESENCIAL for o in activos),
            "presencial": sum(o.modalidad == Modalidad.PRESENCIAL for o in activos),
            "proyectada": t > ahora,
        })

    return {
        "capacidad": garaje.capacidad,
        "ocupados_app": ocupados_app,
        "ocupados_abonos": ocupados_abonos,
        "ocupados_presencial": ocupados_presencial,
        "proximas_app": proximas_app,
        "ventana_min": ventana,
        "libres": max(0, garaje.capacidad - len(ahora_mismo)),
        "libres_presencial": max(0, garaje.capacidad - pico(en_ventana, ahora, hasta)),
        "umbral_alerta": 0.9,
        "alertas_overstay": [
            {"reserva_id": r.id, "patente": r.patente, "inicio": r.inicio}
            for r in sin_lugar_por_overstay(garaje, ahora, hasta)
        ],
        "franjas": franjas,
    }
