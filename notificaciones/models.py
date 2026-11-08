from django.conf import settings
from django.db import models


class Dispositivo(models.Model):
    """Teléfono con la app instalada: su token de Firebase Cloud Messaging recibe las notificaciones push."""

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="dispositivos")
    token = models.CharField(max_length=512, unique=True)  # un mismo teléfono puede cambiar de cuenta
    plataforma = models.CharField(max_length=16, default="android")
    actualizado_en = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.usuario} · {self.plataforma}"


class Canal(models.TextChoices):
    EMAIL = "EMAIL", "Email"
    PUSH = "PUSH", "Push"


class Aviso(models.Model):
    """
    Registro de cada aviso enviado: evita mandar dos veces el mismo comprobante o recordatorio
    (Mercado Pago notifica un pago varias veces y las tareas periódicas se superponen).
    """

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="avisos")
    tipo = models.CharField(max_length=40)   # reserva_confirmada, deuda_pagada, reembolso, inicio_proximo...
    clave = models.CharField(max_length=64)  # id de la reserva o del pago
    canal = models.CharField(max_length=5, choices=Canal.choices)
    enviado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-enviado_en"]
        constraints = [models.UniqueConstraint(fields=["tipo", "clave", "canal"], name="aviso_unico")]

    def __str__(self):
        return f"{self.tipo} {self.clave} ({self.canal})"
