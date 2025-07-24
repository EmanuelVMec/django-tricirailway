from rest_framework.decorators import api_view, authentication_classes
from rest_framework.response import Response
from rest_framework import status
from .models import Solicitud, Aceptacion, Ubicacion,Ride,UbicacionTricimotero
from .serializers import SolicitudSerializer, SolicitudConUbicacionSerializer
from .authentication import ClerkAuthentication
from django.utils import timezone
from django.db import connection
from django.db import models
from geopy.distance import geodesic
@api_view(['POST'])
@authentication_classes([ClerkAuthentication])
def crear_solicitud(request):
    # Extraemos el ID de Clerk desde el JWT decodificado en la autenticación
    clerk_user_id = request.user  # `request.user` debería ser el `clerk_user_id` si estás usando ClerkAuthentication
    
    # Agregamos el ID de Clerk a los datos recibidos desde el frontend
    data = request.data.copy()
    data['cliente_clerk_id'] = clerk_user_id  # Asignamos el `clerk_user_id` al campo adecuado
    
    # Concatenar los nombres
    first_name = request.data.get('cliente_first_name', '')
    last_name = request.data.get('cliente_last_name', '')
    cliente_full_name = f"{first_name} {last_name}"
    
    # Asignamos el nombre completo al campo cliente_full_name
    data['cliente_full_name'] = cliente_full_name
    
    # Ahora pasamos esos datos al serializer
    serializer = SolicitudSerializer(data=data)
    
    if serializer.is_valid():
        # Guardamos la solicitud
        solicitud = serializer.save()
        return Response({
            "message": "Solicitud creada", 
            "id": solicitud.id, 
            "clerk-id": solicitud.cliente_clerk_id
        }, status=status.HTTP_201_CREATED)
    
    # Si hay errores, los devolvemos
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@authentication_classes([ClerkAuthentication])
def estado_solicitud(request):
    clerk_user_id = request.user
    try:
        solicitud = Solicitud.objects.filter(cliente_clerk_id=clerk_user_id).latest('hora_programada')
        return Response({
            "estado": solicitud.estado,
            "asignado": solicitud.tricimotero_clerk_id,
        })
    except Solicitud.DoesNotExist:
        return Response({"detail": "No hay solicitudes activas"}, status=status.HTTP_404)

@api_view(['GET'])
@authentication_classes([ClerkAuthentication])
def listar_solicitudes_pendientes(request):
    solicitudes = Solicitud.objects.filter(estado='pendiente')
     # Consultar el nombre del cliente desde la tabla `users` en Neon DB
    def obtener_nombre_cliente(cliente_clerk_id):
        with connection.cursor() as cursor:
            try:
                # Ejecuta la consulta SQL para obtener el nombre del cliente desde la tabla `users`
                cursor.execute("SELECT name FROM users WHERE clerk_id = %s", [cliente_clerk_id])
                result = cursor.fetchone()  # Solo obtenemos el primer resultado
                return result[0] if result else "Desconocido"
            except Exception as e:
                print(f"Error al ejecutar la consulta: {str(e)}")
                return "Error"

    # Agregar el nombre del cliente a cada solicitud
    for solicitud in solicitudes:
        cliente_nombre = obtener_nombre_cliente(solicitud.cliente_clerk_id)
        solicitud.cliente_nombre = cliente_nombre  # Añadir el nombre del cliente
    
    serializer = SolicitudSerializer(solicitudes, many=True)
    return Response(serializer.data)

@api_view(['POST'])
@authentication_classes([ClerkAuthentication])
def aceptar_solicitud(request, solicitud_id):
    # Obtén el ID del tricimotero autenticado
    tricimotero_clerk_id = request.user  # El ID del tricimotero autenticado
    
    try:
        solicitud = Solicitud.objects.get(id=solicitud_id, estado='pendiente')
    except Solicitud.DoesNotExist:
        return Response({"error": "Solicitud no encontrada o ya está aceptada."}, status=status.HTTP_404_NOT_FOUND)
 # Actualizar el estado de la solicitud a 'aceptada' y asignar el tricimotero
    solicitud.estado = 'aceptada'
    solicitud.tricimotero_clerk_id = tricimotero_clerk_id
    solicitud.save()

    # Crear la aceptación
    aceptacion = Aceptacion.objects.create(
        solicitud=solicitud,
        tricimotero_clerk_id=tricimotero_clerk_id,
        aceptada_en=timezone.now()
    )

    # Verificar si ya existe una ubicación para el cliente (solicitud.cliente_clerk_id)
    ubicacion_cliente, created = Ubicacion.objects.get_or_create(
        clerk_user_id=solicitud.cliente_clerk_id
    )

    ride = Ride.objects.create(
    origin_address=solicitud.origen,
    destination_address=solicitud.destino,
    origin_latitude=ubicacion_cliente.latitud,
    origin_longitude=ubicacion_cliente.longitud,
    ride_time=30,
    fare_price=100.00,
    payment_status='pendiente',
    driver=None,
    clerk_user_id=tricimotero_clerk_id,        # Tricimotero
    cliente_clerk_id=solicitud.cliente_clerk_id,  # Cliente
    created_at=timezone.now()
)

    # Retornar la respuesta
    return Response({
        "message": "Solicitud aceptada exitosamente y viaje agendado.",
        "solicitud_id": solicitud.id,
        "tricimotero_clerk_id": solicitud.tricimotero_clerk_id,
        "cliente_clerk_id": solicitud.cliente_clerk_id,
        "ride_id": ride.id
    }, status=status.HTTP_200_OK)
    
@api_view(['POST'])
@authentication_classes([ClerkAuthentication])
def actualizar_ubicacion(request):
    clerk_user_id = request.user
    data = request.data
    lat = data.get("latitud")
    lng = data.get("longitud")

    if lat is None or lng is None:
        return Response({"detail": "Coordenadas faltantes."}, status=400)

    ubicacion, created = Ubicacion.objects.update_or_create(
        clerk_user_id=clerk_user_id,
        defaults={"latitud": lat, "longitud": lng}
    )
    return Response({"message": "Ubicación actualizada"})

@api_view(['GET'])
@authentication_classes([ClerkAuthentication])
def solicitudes_con_ubicacion(request):
    solicitudes = Solicitud.objects.filter(estado="pendiente")
    datos_con_ubicacion = []

    for solicitud in solicitudes:
        ubicacion = Ubicacion.objects.filter(clerk_user_id=solicitud.cliente_clerk_id).first()
        if ubicacion:
            datos_con_ubicacion.append({
                "id": solicitud.id,
                "cliente_clerk_id": solicitud.cliente_clerk_id,
                "origen": solicitud.origen,
                "destino": solicitud.destino,
                "hora_programada": solicitud.hora_programada,
                "estado": solicitud.estado,
                "tricimotero_clerk_id": solicitud.tricimotero_clerk_id,
                "latitud": ubicacion.latitud,
                "longitud": ubicacion.longitud,
            })

    return Response(SolicitudConUbicacionSerializer(datos_con_ubicacion, many=True).data)

@api_view(['GET'])
@authentication_classes([ClerkAuthentication])
def listar_carreras_aceptadas(request):
    # Obtén el clerk_user_id del tricimotero autenticado
    tricimotero_clerk_id = request.user
    
    # Buscar todas las solicitudes que están aceptadas y asignadas al tricimotero
    solicitudes_aceptadas = Solicitud.objects.filter(
        tricimotero_clerk_id=tricimotero_clerk_id, estado='aceptada'
    )
    
    # Serializamos las solicitudes aceptadas
    solicitudes_serializer = SolicitudSerializer(solicitudes_aceptadas, many=True)
    
    # Retornamos la respuesta con los datos de las solicitudes aceptadas
    return Response(solicitudes_serializer.data)

@api_view(['GET'])
@authentication_classes([ClerkAuthentication])
def ubicacion_conductor(request):
    clerk_id = request.GET.get("id")
    if not clerk_id:
        return Response({"detail": "ID requerido"}, status=400)
    
    ubicacion = Ubicacion.objects.filter(clerk_user_id=clerk_id).first()
    if not ubicacion:
        return Response({"detail": "Ubicación no encontrada"}, status=404)

    return Response({
        "latitud": ubicacion.latitud,
        "longitud": ubicacion.longitud,
        "actualizado": ubicacion.actualizado,
    })

@api_view(['POST'])
@authentication_classes([ClerkAuthentication])
def actualizar_ubicacion_tricimotero(request):
    clerk_user_id = request.user
    data = request.data
    lat = data.get("latitud")
    lng = data.get("longitud")

    if lat is None or lng is None:
        return Response({"detail": "Coordenadas faltantes."}, status=400)

    ubicacion, created = UbicacionTricimotero.objects.update_or_create(
        clerk_user_id=clerk_user_id,
        defaults={"latitud": lat, "longitud": lng}
    )
    return Response({"message": "Ubicación del tricimotero actualizada"})

@api_view(['GET'])
@authentication_classes([ClerkAuthentication])
def ubicacion_tricimotero(request):
    clerk_id = request.GET.get("id")
    if not clerk_id:
        return Response({"detail": "ID requerido"}, status=400)

    from .models import UbicacionTricimotero
    ubicacion = UbicacionTricimotero.objects.filter(clerk_user_id=clerk_id).first()
    if not ubicacion:
        return Response({"detail": "Ubicación no encontrada"}, status=404)

    return Response({
        "latitud": ubicacion.latitud,
        "longitud": ubicacion.longitud,
        "actualizado": ubicacion.actualizado,
    })
@api_view(['GET'])
@authentication_classes([ClerkAuthentication])
def ubicacion_cliente(request):
    clerk_id = request.GET.get("id")
    if not clerk_id:
        return Response({"detail": "ID requerido"}, status=400)

    ubicacion = Ubicacion.objects.filter(clerk_user_id=clerk_id).first()
    if not ubicacion:
        return Response({"detail": "Ubicación no encontrada"}, status=404)

    return Response({
        "latitud": ubicacion.latitud,
        "longitud": ubicacion.longitud,
        "actualizado": ubicacion.actualizado,
    })

@api_view(['GET'])
@authentication_classes([ClerkAuthentication])
def obtener_rides_en_camino(request):
    user_id = request.user  # Clerk ID del usuario autenticado
    rides = Ride.objects.filter(
        models.Q(clerk_user_id=user_id) | models.Q(cliente_clerk_id=user_id),
        estado='encamino'
    )

    data = [
        {
            'ride_id': ride.id,
            'origin': ride.origin_address,
            'destination': ride.destination_address,
            'estado': ride.estado,
            'conductor_clerk_id': ride.clerk_user_id,
            'cliente_clerk_id': ride.cliente_clerk_id,
        }
        for ride in rides
    ]
    return Response(data, status=status.HTTP_200_OK)
from math import radians, sin, cos, sqrt, atan2
@api_view(['GET'])
@authentication_classes([ClerkAuthentication])
def distancia_entre_cliente_y_tricimotero(request):
    ride_id = request.GET.get("ride_id")
    if not ride_id:
        return Response({"detail": "ride_id es requerido"}, status=400)

    try:
        ride = Ride.objects.get(id=ride_id)
    except Ride.DoesNotExist:
        return Response({"detail": "Ride no encontrado"}, status=404)

    # Extraer Clerk IDs del cliente y tricimotero desde el modelo Ride
    cliente_id = ride.cliente_clerk_id
    tricimotero_id = ride.clerk_user_id
    # Buscar ubicaciones más recientes
    ubicacion_cliente = Ubicacion.objects.filter(clerk_user_id=cliente_id).first()
    ubicacion_tricimotero = UbicacionTricimotero.objects.filter(clerk_user_id=tricimotero_id).first()

    if not ubicacion_cliente or not ubicacion_tricimotero:
        return Response({"detail": "No se encontraron ubicaciones para ambos usuarios"}, status=404)

    # Función de cálculo de distancia (fórmula Haversine)
    def calcular_distancia(lat1, lon1, lat2, lon2):
        R = 6371000  # Radio de la Tierra en metros
        φ1, φ2 = radians(lat1), radians(lat2)
        Δφ = radians(lat2 - lat1)
        Δλ = radians(lon2 - lon1)

        a = sin(Δφ / 2)**2 + cos(φ1) * cos(φ2) * sin(Δλ / 2)**2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        return R * c  # Distancia en metros

    distancia = calcular_distancia(
        ubicacion_cliente.latitud, ubicacion_cliente.longitud,
        ubicacion_tricimotero.latitud, ubicacion_tricimotero.longitud
    )

    return Response({
        "distancia_metros": round(distancia, 2),
        "cliente": {
            "lat": ubicacion_cliente.latitud,
            "lng": ubicacion_cliente.longitud,
            "actualizado": ubicacion_cliente.actualizado,
        },
        "tricimotero": {
            "lat": ubicacion_tricimotero.latitud,
            "lng": ubicacion_tricimotero.longitud,
            "actualizado": ubicacion_tricimotero.actualizado,
        }
    })
@api_view(["POST"])
@authentication_classes([ClerkAuthentication])
def marcar_ha_llegado(request):
    ride_id = request.data.get("ride_id")
    
    if not ride_id:
        return Response({"detail": "Falta ride_id"}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        ride = Ride.objects.get(id=ride_id)
    except Ride.DoesNotExist:
        return Response({"detail": "Ride no encontrado"}, status=status.HTTP_404_NOT_FOUND)
    
    ride.estado = "hallegado"
    ride.save()

    return Response({"detail": "Estado actualizado a 'ha_llegado'"}, status=status.HTTP_200_OK)
@api_view(['GET'])
@authentication_classes([ClerkAuthentication])
def obtener_estado_ride(request):
    ride_id = request.GET.get("ride_id")
    if not ride_id:
        return Response({"detail": "Falta ride_id"}, status=400)

    try:
        ride = Ride.objects.get(id=ride_id)
    except Ride.DoesNotExist:
        return Response({"detail": "Ride no encontrado"}, status=404)

    return Response({"estado": ride.estado})
@api_view(['GET'])
@authentication_classes([ClerkAuthentication])
def carreras_halllegado_conductor(request):
    user_id = request.user  # Clerk ID del tricimotero autenticado
    print(user_id)
    rides = Ride.objects.filter(
        clerk_user_id=user_id,
        estado='hallegado'
    )

    data = [
        {
            "id": ride.id,
            "origen": ride.origin_address,
            "destino": ride.destination_address,
            "estado": ride.estado,
            "hora_programada": ride.created_at
        }
        for ride in rides
    ]
    return Response(data, status=status.HTTP_200_OK)

@api_view(['PATCH'])
@authentication_classes([ClerkAuthentication])
def cancelar_solicitud(request, solicitud_id):
    user_id = request.user  # Clerk ID del cliente

    try:
        solicitud = Solicitud.objects.get(id=solicitud_id, cliente_clerk_id=user_id)
    except Solicitud.DoesNotExist:
        return Response({"detail": "Solicitud no encontrada o no pertenece al usuario."}, status=status.HTTP_404_NOT_FOUND)

    if solicitud.estado in ['cancelada', 'aceptada']:
        return Response({"detail": "No se puede cancelar una solicitud ya aceptada o cancelada."}, status=status.HTTP_400_BAD_REQUEST)

    solicitud.estado = 'cancelada'
    solicitud.cancelled_at = timezone.now()
    solicitud.save()

    return Response({"detail": "Solicitud cancelada correctamente."}, status=status.HTTP_200_OK)


@api_view(['PATCH'])
@authentication_classes([ClerkAuthentication])
def cancelar_ride(request, ride_id):
    try:
        ride = Ride.objects.get(id=ride_id)
    except Ride.DoesNotExist:
        return Response({"detail": "Ride no encontrado."}, status=status.HTTP_404_NOT_FOUND)

    if ride.estado in ['cancelado', 'hallegado']:
        return Response({"detail": "No se puede cancelar un ride ya cancelado o que ya ha llegado."}, status=status.HTTP_400_BAD_REQUEST)

    ride.estado = 'cancelado'
    ride.save()

    return Response({"detail": "Ride cancelado correctamente."}, status=status.HTTP_200_OK)

