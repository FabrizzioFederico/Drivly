from rest_framework import serializers

from .models import Vehiculo, normalizar_patente, validar_patente


class VehiculoSerializer(serializers.ModelSerializer):
    # Acepta "AB 123 CD" o "AB-123-CD": se normaliza antes de validar el largo.
    patente = serializers.CharField(max_length=12)

    class Meta:
        model = Vehiculo
        fields = ["id", "patente", "categoria", "estado_validacion", "validado_en", "creado_en"]
        # La categoría nunca la manda el cliente (regla 3: anti-fraude).
        read_only_fields = ["id", "categoria", "estado_validacion", "validado_en", "creado_en"]

    def validate_patente(self, valor):
        patente = normalizar_patente(valor)
        validar_patente(patente)
        if Vehiculo.objects.filter(patente=patente).exists():
            raise serializers.ValidationError("Esta patente ya está registrada en Drivly.")
        return patente
