import paho.mqtt.client as mqtt
import json
import time
import random

BROKER_HOST = "13.220.161.147"  # IP público da EC2 broker
RESERVATORIO_ID = 1
INTERVALO = 30  # segundos entre cada envio

sensores = {
    "ph":            (6.0, 9.5),   # Portaria 5/2017: 6.0 a 9.5
    "turbidez":      (0.5, 5.0),   # NTU
    "condutividade": (100, 500),   # µS/cm
    "nivel":         (1.0, 10.0),  # metros
    "temperatura":   (15.0, 30.0)  # °C
}

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("[OK] Conectado ao broker MQTT")
    else:
        print(f"[ERRO] Falha na conexão: {rc}")

client = mqtt.Client()
client.on_connect = on_connect
client.connect(BROKER_HOST, 1883, 60)
client.loop_start()

print("[INFO] Simulador iniciado. Enviando dados a cada", INTERVALO, "segundos...")
print("[INFO] Ctrl+C para parar\n")

while True:
    for sensor, (minimo, maximo) in sensores.items():
        valor = round(random.uniform(minimo, maximo), 3)

        # Ocasionalmente gera valor fora do padrão para testar alertas
        if random.random() < 0.1:
            valor = round(maximo * 1.2, 3)

        payload = json.dumps({
            "reservatorio_id": RESERVATORIO_ID,
            "valor": valor
        })

        topico = f"aquatrack/reservatorio/{sensor}"
        client.publish(topico, payload)
        print(f"[MQTT] {topico} → {valor}")

    print("---")
    time.sleep(INTERVALO)
