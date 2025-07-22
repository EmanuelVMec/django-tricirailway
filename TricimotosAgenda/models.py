from django.db import models
from django.contrib.auth.models import User

class Driver(models.Model):
    clerk_user_id = models.CharField(max_length=255, unique=True)  # Reemplazo de ForeignKey a User
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    profile_image_url = models.TextField(blank=True, null=True)
    car_image_url = models.TextField(blank=True, null=True)
    car_seats = models.PositiveIntegerField()
    rating = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class Ride(models.Model):
    origin_address = models.CharField(max_length=255)
    destination_address = models.CharField(max_length=255)
    origin_latitude = models.DecimalField(max_digits=9, decimal_places=6)
    origin_longitude = models.DecimalField(max_digits=9, decimal_places=6)
    destination_latitude = models.DecimalField(null=True, blank=True,max_digits=9, decimal_places=6)
    destination_longitude = models.DecimalField(null=True, blank=True,max_digits=9, decimal_places=6)
    ride_time = models.IntegerField()  # duración en minutos
    fare_price = models.DecimalField(max_digits=10, decimal_places=2)
    payment_status = models.CharField(max_length=20)
    driver = models.ForeignKey(Driver, on_delete=models.SET_NULL, null=True, blank=True)
    clerk_user_id = models.CharField(max_length=255)  # en lugar de ForeignKey a User
    created_at = models.DateTimeField(auto_now_add=True)
    cliente_clerk_id = models.CharField(max_length=255,null=True)  # cliente
    estado = models.CharField(
        max_length=20,
        choices=[('encamino', 'En camino'), ('hallegado', 'Ha llegado')],
        default='encamino'
    )

    def __str__(self):
        return f"Ride from {self.origin_address} to {self.destination_address}"


class Solicitud(models.Model):
    cliente_clerk_id = models.CharField(max_length=255)  # ID del cliente (Clerk)
    cliente_full_name = models.CharField(max_length=511, null=True, blank=True)  # Nuevo campo para el nombre completo
    origen = models.CharField(max_length=255)
    destino = models.CharField(max_length=255)
    hora_programada = models.DateTimeField()
    estado = models.CharField(
        max_length=20,
        choices=[('pendiente', 'Pendiente'), ('aceptada', 'Aceptada')],
        default='pendiente'
    )
    tricimotero_clerk_id = models.CharField(max_length=255, null=True, blank=True)  # opcional hasta que se asigne

    def __str__(self):
        return f"Solicitud de {self.cliente_clerk_id} ({self.cliente_full_name}) - Estado: {self.estado}"



class Aceptacion(models.Model):
    solicitud = models.OneToOneField(Solicitud, on_delete=models.CASCADE)
    tricimotero_clerk_id = models.CharField(max_length=255)
    aceptada_en = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Aceptación de parte {self.tricimotero_clerk_id} para solicitud {self.solicitud_id}"


class Ubicacion(models.Model):
    clerk_user_id = models.CharField(max_length=255, unique=True)
    latitud = models.FloatField()
    longitud = models.FloatField()
    actualizado = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Ubicación de {self.clerk_user_id}"

class UbicacionTricimotero(models.Model):
    clerk_user_id = models.CharField(max_length=255, unique=True)
    latitud = models.FloatField()
    longitud = models.FloatField()
    actualizado = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Ubicación del tricimotero {self.clerk_user_id}"
