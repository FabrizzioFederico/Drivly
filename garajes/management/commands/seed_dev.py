"""
python manage.py seed_dev

Carga los 4 garajes de Palermo (los mismos del mock del frontend) en la DB de desarrollo.
Idempotente: si ya existe el admin o los garajes, no los duplica.
Solo disponible con DEBUG=True.
"""
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from cuentas.models import Rol, Usuario
from garajes.models import Garaje, Tarifa


ADMIN_EMAIL = "admin@drivly.local"

GARAJES = [
    {
        "nombre": "Garage Plaza Serrano",
        "cuit": "30-12345678-1",
        "direccion": "Honduras 4870, Palermo",
        "lat": Decimal("-34.588900"),
        "lng": Decimal("-58.430600"),
        "capacidad": 80,
        "cupo_abonos": 10,
        "tolerancia_min": 15,
        "salida_estimada_default_min": 120,
        "recargo_overstay": Decimal("0.50"),
    },
    {
        "nombre": "Estacionamiento Gurruchaga",
        "cuit": "30-23456789-2",
        "direccion": "Gurruchaga 1650, Palermo",
        "lat": Decimal("-34.587200"),
        "lng": Decimal("-58.429100"),
        "capacidad": 50,
        "cupo_abonos": 5,
        "tolerancia_min": 10,
        "salida_estimada_default_min": 120,
        "recargo_overstay": Decimal("0.50"),
    },
    {
        "nombre": "Parking Armenia",
        "cuit": "30-34567890-1",
        "direccion": "Armenia 1420, Palermo",
        "lat": Decimal("-34.590100"),
        "lng": Decimal("-58.428500"),
        "capacidad": 60,
        "cupo_abonos": 0,
        "tolerancia_min": 15,
        "salida_estimada_default_min": 90,
        "recargo_overstay": Decimal("0.50"),
    },
    {
        "nombre": "Cochera Thames",
        "cuit": "30-45678901-9",
        "direccion": "Thames 1580, Palermo",
        "lat": Decimal("-34.587800"),
        "lng": Decimal("-58.433400"),
        "capacidad": 30,
        "cupo_abonos": 6,
        "tolerancia_min": 10,
        "salida_estimada_default_min": 120,
        "recargo_overstay": Decimal("0.50"),
    },
]

# Tarifas por garaje (nombre → lista de tarifas)
TARIFAS = {
    "Garage Plaza Serrano": [
        {"categoria": "AUTO",      "modalidad": "HORA",    "precio_fraccion": Decimal("320"), "fraccion_min": 15, "minimo_fracciones": 4},
        {"categoria": "MOTO",      "modalidad": "HORA",    "precio_fraccion": Decimal("160"), "fraccion_min": 15, "minimo_fracciones": 2},
        {"categoria": "CAMIONETA", "modalidad": "HORA",    "precio_fraccion": Decimal("450"), "fraccion_min": 15, "minimo_fracciones": 4},
        {"categoria": "AUTO",      "modalidad": "SEMANAL", "precio_periodo": Decimal("42000")},
        {"categoria": "AUTO",      "modalidad": "MENSUAL", "precio_periodo": Decimal("150000")},
        {"categoria": "AUTO",      "modalidad": "ANUAL",   "precio_periodo": Decimal("1550000")},
        {"categoria": "MOTO",      "modalidad": "MENSUAL", "precio_periodo": Decimal("70000")},
        {"categoria": "CAMIONETA", "modalidad": "MENSUAL", "precio_periodo": Decimal("210000")},
    ],
    "Estacionamiento Gurruchaga": [
        {"categoria": "AUTO",      "modalidad": "HORA",    "precio_fraccion": Decimal("280"), "fraccion_min": 15, "minimo_fracciones": 1},
        {"categoria": "MOTO",      "modalidad": "HORA",    "precio_fraccion": Decimal("140"), "fraccion_min": 15, "minimo_fracciones": 1},
        {"categoria": "CAMIONETA", "modalidad": "HORA",    "precio_fraccion": Decimal("400"), "fraccion_min": 15, "minimo_fracciones": 1},
        {"categoria": "AUTO",      "modalidad": "MENSUAL", "precio_periodo": Decimal("135000")},
        {"categoria": "MOTO",      "modalidad": "MENSUAL", "precio_periodo": Decimal("60000")},
    ],
    "Parking Armenia": [
        {"categoria": "AUTO",      "modalidad": "HORA",    "precio_fraccion": Decimal("300"), "fraccion_min": 15, "minimo_fracciones": 1},
        {"categoria": "MOTO",      "modalidad": "HORA",    "precio_fraccion": Decimal("150"), "fraccion_min": 15, "minimo_fracciones": 1},
        {"categoria": "CAMIONETA", "modalidad": "HORA",    "precio_fraccion": Decimal("420"), "fraccion_min": 15, "minimo_fracciones": 1},
    ],
    "Cochera Thames": [
        {"categoria": "AUTO",      "modalidad": "HORA",    "precio_fraccion": Decimal("340"), "fraccion_min": 15, "minimo_fracciones": 1},
        {"categoria": "MOTO",      "modalidad": "HORA",    "precio_fraccion": Decimal("170"), "fraccion_min": 15, "minimo_fracciones": 1},
        {"categoria": "CAMIONETA", "modalidad": "HORA",    "precio_fraccion": Decimal("470"), "fraccion_min": 15, "minimo_fracciones": 1},
        {"categoria": "AUTO",      "modalidad": "SEMANAL", "precio_periodo": Decimal("45000")},
        {"categoria": "AUTO",      "modalidad": "MENSUAL", "precio_periodo": Decimal("160000")},
        {"categoria": "AUTO",      "modalidad": "ANUAL",   "precio_periodo": Decimal("1600000")},
    ],
}


class Command(BaseCommand):
    help = "Carga garajes de prueba (equivalentes al mock del frontend). Solo para desarrollo."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("seed_dev solo está disponible con DEBUG=True.")

        with transaction.atomic():
            admin, created = Usuario.objects.get_or_create(
                email=ADMIN_EMAIL,
                defaults={"nombre": "Admin Garaje (Dev)", "rol": Rol.ADMIN_GARAJE},
            )
            if created:
                self.stdout.write(f"  Usuario admin creado: {ADMIN_EMAIL}")
            else:
                self.stdout.write(f"  Usuario admin ya existe: {ADMIN_EMAIL}")

            for datos in GARAJES:
                garaje, creado = Garaje.objects.get_or_create(
                    nombre=datos["nombre"],
                    defaults={**datos, "admin": admin},
                )
                if creado:
                    self.stdout.write(f"  Garaje creado: {garaje.nombre}")
                    for t in TARIFAS[garaje.nombre]:
                        Tarifa.objects.create(garaje=garaje, **t)
                    self.stdout.write(f"    Tarifas: {len(TARIFAS[garaje.nombre])}")
                else:
                    self.stdout.write(f"  Garaje ya existe: {garaje.nombre}")

        self.stdout.write(self.style.SUCCESS("\nseed_dev completado."))
