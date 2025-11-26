#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Importa a biblioteca principal
from pymavlink import mavutil
import time

# --- Configurações da Conexão ---
connection_string = '/dev/ttyACM0'
baud_rate = 57600

print(f"[PyMAVLink] Conectando a {connection_string} com baud {baud_rate}...")

# Tenta iniciar a conexão
try:
    # O 'source_system=255' nos identifica como uma Ground Station (GCS)
    master = mavutil.mavlink_connection(connection_string, baud=baud_rate, source_system=255)
except Exception as e:
    print(f"Erro ao conectar: {e}")
    print("Verifique se o dispositivo está conectado em /dev/ttyACM0 e se o baud rate está correto.")
    exit(1)

# 1. Espera pelo primeiro "heartbeat" para confirmar a conexão
print("[PyMAVLink] Esperando pelo heartbeat da controladora...")
master.wait_heartbeat()
print("[PyMAVLink] Heartbeat recebido! Conexão estabelecida.")

# 2. (Opcional, mas boa prática) Solicita o stream de dados de GPS
# Isso garante que a controladora nos envie os dados de posição.
# MAV_DATA_STREAM_POSITION = 6
# 10 = 10Hz (10 mensagens por segundo). Mude para 1 ou 2 se for muito.
master.mav.request_data_stream_send(
    master.target_system,    # target_system
    master.target_component, # target_component
    mavutil.mavlink.MAV_DATA_STREAM_POSITION, # req_stream_id
    2, # req_message_rate (Hz) - Pedindo 2 mensagens por segundo
    1  # start_stop (1 para começar)
)
print("[PyMAVLink] Solicitando stream de GPS (GLOBAL_POSITION_INT)...")


# 3. Loop principal para ler as mensagens
while True:
    try:
        # Espera por uma mensagem específica (GLOBAL_POSITION_INT)
        # 'blocking=True' faz com que ele espere até a mensagem chegar
        msg = master.recv_match(type='GLOBAL_POSITION_INT', blocking=True, timeout=5)
        
        if msg is None:
            print("[PyMAVLink] Nenhuma mensagem GLOBAL_POSITION_INT recebida em 5s. Verificando conexão...")
            master.wait_heartbeat() # Verifica se a conexão ainda está ativa
            continue

        # Se a mensagem chegou, decodifica os valores
        # Os valores vêm como inteiros e precisam ser divididos
        lat = msg.lat / 1e7  # Latitude (em graus)
        lon = msg.lon / 1e7  # Longitude (em graus)
        alt = msg.alt / 1000.0 # Altitude acima do nível do mar (em metros)

        print(f"--> Lat: {lat:.6f}, Lon: {lon:.6f}, Alt: {alt:.2f} m")
        
        # Não precisa de time.sleep() aqui, pois o recv_match já gerencia o tempo

    except KeyboardInterrupt:
        print("\n[PyMAVLink] Encerrando a pedido do usuário...")
        break
    except Exception as e:
        print(f"[PyMAVLink] Erro no loop: {e}")
        break

# 4. (Opcional) Para o stream de dados antes de fechar
master.mav.request_data_stream_send(
    master.target_system,
    master.target_component,
    mavutil.mavlink.MAV_DATA_STREAM_POSITION,
    0, # 0Hz para parar
    0  # 0 para parar
)
master.close()
print("[PyMAVLink] Conexão fechada.")