from rest_framework import serializers

from .models import Categoria, Vehiculo, normalizar_patente, validar_patente
from .services import puede_declarar


class VehiculoSerializer(serializers.ModelSerializer):
    # Acepta "AB 123 CD" o "AB-123-CD": se normaliza antes de validar el largo.
    patente = serializers.CharField(max_length=12)
    puede_declarar = serializers.SerializerMethodField()
    requiere_declaracion = serializers.SerializerMethodField()
    # Resultado de la última consulta a DataCar (OK, NO_ENCONTRADA, ERROR) o null si no se consultó (motos):
    # la app explica por qué no hay categoría.
    consulta_datacar = serializers.SerializerMethodField()

    class Meta:
        model = Vehiculo
        fields = [
            "id", "patente", "categoria", "categoria_origen", "estado_validacion",
            "requiere_declaracion", "puede_declarar", "validado_en", "creado_en",
            "marca", "modelo", "anio", "tipo", "consulta_datacar",
        ]
        # La categoría nunca se manda en el alta: se declara aparte y sólo si DataCar no la resolvió.
        # Marca, modelo, año y tipo los completa DataCar.
        read_only_fields = ["id", "categoria", "categoria_origen", "estado_validacion", "validado_en", "creado_en",
                            "marca", "modelo", "anio", "tipo"]

    def validate_patente(self, valor):
        patente = normalizar_patente(valor)
        validar_patente(patente)
        if Vehiculo.objects.filter(patente=patente).exists():
            raise serializers.ValidationError("Esta patente ya está registrada en Drivly.")
        return patente

    def get_puede_declarar(self, vehiculo):
        return puede_declarar(vehiculo)

    def get_requiere_declaracion(self, vehiculo):
        return vehiculo.categoria is None

    def get_consulta_datacar(self, vehiculo):
        ultima = vehiculo.consultas.first()  # ordenadas de la más nueva a la más vieja
        return ultima.resultado if ultima else None


class DeclararCategoriaSerializer(serializers.Serializer):
    # Sólo camioneta: "auto" lo determina DataCar (si no, cualquiera pagaría como auto)
    categoria = serializers.ChoiceField(
        choices=[Categoria.CAMIONETA],
        error_messages={"invalid_choice": "Sin dato del registro automotor sólo se puede reservar como camioneta."},
    )
