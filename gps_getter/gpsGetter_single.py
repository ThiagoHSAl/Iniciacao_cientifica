#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pymavlink import mavutil
import time
import json
import sys

# --- Configurações da Conexão ---
connection_string = '/dev/ttyACM0'
baud_rate = 57600

# Imprime logs de status para o 'stderr'
# Isso é IMPORTANTE. O 'stdout' será usado APENAS para o JSON final.
def log_status(message):
    print(f"[PyMAVLink] {message}", file=sys.stderr)

log_status(f"Conectando a {connection_string} com baud {baud_rate}...")

try:
    master = mavutil.mavlink_connection(connection_string, baud=baud_rate, source_system=255)
except Exception as e:
    log_status(f"Erro ao conectar: {e}")
    sys.exit(1)

log_status("Esperando pelo heartbeat da controladora...")
master.wait_heartbeat()
log_status("Heartbeat recebido! Conexão estabelecida.")

master.mav.request_data_stream_send(
    master.target_system,
    master.target_component,
    mavutil.mavlink.MAV_DATA_STREAM_POSITION,
    2, # 2 Hz
    1
)
log_status("Solicitando stream de GPS... Esperando por um 'fix' válido...")

# Loop para esperar por um 'fix' VÁLIDO (não 0,0)
while True:
    try:
        msg = master.recv_match(type='GLOBAL_POSITION_INT', blocking=True, timeout=10)
        
        if msg is None:
            log_status("Nenhuma mensagem GPS recebida em 10s. Tentando de novo...")
            continue

        lat = msg.lat / 1e7
        lon = msg.lon / 1e7
        alt = msg.alt / 1000.0

        # --- A VERIFICAÇÃO MAIS IMPORTANTE ---
        # Ignora coordenadas 0,0 (que significam 'sem fix')
        if lat == 0 and lon == 0:
            log_status("GPS fix ainda é (0,0)... Esperando...")
            time.sleep(1) # Espera 1s antes de tentar de novo
            continue
        
        # --- SUCESSO! ---
        # Temos um fix válido.
        log_status(f"Fix VÁLIDO recebido: Lat={lat}, Lon={lon}")
        
        # 1. Prepara o dicionário de dados
        data = {
            "latitude": lat,
            "longitude": lon,
            "altitude": alt
        }
        
        # 2. Imprime o JSON para 'stdout'.
        # Este print é a *única* coisa que o script da base vai capturar.
        print(json.dumps(data)) 
        
        # 3. Sai do loop para encerrar o script
        break

    except KeyboardInterrupt:
        log_status("Encerrado pelo usuário.")
        break
    except Exception as e:
        log_status(f"Erro no loop: {e}")
        break

# Fecha a conexão
master.close()
log_status("Conexão fechada. Script encerrado.")