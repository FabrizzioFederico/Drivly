from django.core.management.base import BaseCommand

from integraciones import imagenes
from vehiculos.models import Vehiculo


class Command(BaseCommand):
    help = ("Busca la foto ilustrativa de los vehículos que tienen marca y modelo de DataCar pero todavía no tienen foto. "
            "No consulta DataCar (no gasta créditos): usa los datos ya guardados.")

    def add_arguments(self, parser):
        parser.add_argument("--todas", action="store_true", help="Vuelve a buscar también las que ya tienen foto.")

    def handle(self, *args, todas=False, **opciones):
        vehiculos = Vehiculo.objects.exclude(marca="").exclude(modelo="").exclude(marca="SIMULADA")
        if not todas:
            vehiculos = vehiculos.filter(imagen_url="")
        vehiculos = list(vehiculos)
        encontradas = 0
        for v in vehiculos:
            foto = imagenes.buscar(v.marca, v.modelo, v.anio)
            if foto:
                v.imagen_url, v.imagen_credito = foto.url, foto.credito
                v.save(update_fields=["imagen_url", "imagen_credito"])
                encontradas += 1
            self.stdout.write(f"{v.patente}: {v.marca} {v.modelo} -> {'con foto' if foto else 'sin foto'}")
        self.stdout.write(self.style.SUCCESS(f"Listo: {encontradas} de {len(vehiculos)} vehículos con foto."))
