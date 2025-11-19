import json
import paho.mqtt.client as mqtt
from django.utils import timezone
from django.db import transaction
from app.models import Juez, Equipo, RegistroTiempo

# Configuración del broker local (Mosquitto)
BROKER = "localhost"
PORT = 1883
TOPICO_BASE = "carrera/registro/#"

def on_connect(client, userdata, flags, rc):
    """Callback al conectarse al broker."""
    if rc == 0:
        print(" Conectado al broker MQTT correctamente.")
        client.subscribe(TOPICO_BASE)
        print(f"Suscrito al tópico: {TOPICO_BASE}")
    else:
        print(f" Error al conectar al broker. Código: {rc}")

def on_message(client, userdata, msg):
    """Procesa los mensajes recibidos en los tópicos MQTT."""
    print(f"\n📥 Mensaje recibido en {msg.topic}: {msg.payload.decode()}")
    try:
        data = json.loads(msg.payload.decode())

        # Obtener nombre o ID del juez desde el tópico
        # Ej: carrera/registro/juez1 → juez1
        topic_parts = msg.topic.split('/')
        juez_identificador = topic_parts[-1]

        juez = Juez.objects.filter(nombre__iexact=juez_identificador, activo=True).first()
        if not juez:
            print(f" Juez '{juez_identificador}' no encontrado o inactivo.")
            return

        dorsal = data.get("dorsal")
        tiempo = data.get("tiempo")
        timestamp = data.get("timestamp", timezone.now())

        equipo = Equipo.objects.filter(juez_asignado=juez, dorsal=dorsal).first()
        if not equipo:
            print(f" Equipo con dorsal {dorsal} no encontrado para el juez {juez_identificador}.")
            return

        # Crear registro de tiempo de forma atómica con la competencia
        with transaction.atomic():
            RegistroTiempo.objects.create(
                equipo=equipo,
                competencia=juez.competencia,  # Asignar la competencia del juez
                tiempo=tiempo,
                timestamp=timestamp
            )

        print(f" Tiempo registrado correctamente para {equipo.nombre} ({dorsal})")

        # Publicar confirmación
        confirm_topic = f"carrera/confirmacion/{juez_identificador}"
        confirm_msg = json.dumps({
            "dorsal": dorsal,
            "estado": "recibido",
            "timestamp_servidor": timezone.now().isoformat()
        })
        client.publish(confirm_topic, confirm_msg)
        print(f"✅ Confirmación enviada a {confirm_topic}")

    except Exception as e:
        print(" Error procesando mensaje:", e)

def start_mqtt():
    """Inicia el cliente MQTT y queda escuchando los mensajes."""
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(BROKER, PORT)
    print(" Cliente MQTT iniciado y en escucha...")
    client.loop_forever()
