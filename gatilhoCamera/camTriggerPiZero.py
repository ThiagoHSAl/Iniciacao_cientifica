#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import subprocess
import os
import sys
import csv  # Para salvar o log
import math # Para calcular o YAW
from pymavlink import mavutil
from gpiozero import LED

# --- CONFIGURAÇÕES ---
PIXHAWK_PORT = '/dev/ttyACM0'
BAUD_RATE = 57600
COOLDOWN_SECONDS = 2
LED_STATUS_PIN = 17
LED_TRIGGER_PIN = 27

BASE_PHOTO_DIR = os.path.join(os.path.expanduser('~'), 'Imagens_Capturadas')

# --- INICIALIZAÇÃO ---
last_trigger_time = 0
session_path = ""
image_counter = 0

# Variável global atualizada para armazenar a telemetria necessária
current_telemetry = {
    'lat': 0.0,
    'lon': 0.0,
    'altitude_agl': 0.0,  # Acima do Solo
    'yaw': 0.0
}

status_led = LED(LED_STATUS_PIN)
trigger_led = LED(LED_TRIGGER_PIN)
status_led.on()
trigger_led.off()

# --- Conexão e Criação da Pasta ---
try:
    print(f"Conectando à Pixhawk em {PIXHAWK_PORT}...")
    master = mavutil.mavlink_connection(PIXHAWK_PORT, baud=BAUD_RATE)
    master.wait_heartbeat()
    print(">>> Conexão estabelecida. Sistema pronto.")
    print("Solicitando stream de dados de GPS (GLOBAL_POSITION_INT)...")
    master.mav.request_data_stream_send(
        master.target_system, master.target_component,
        mavutil.mavlink.MAV_DATA_STREAM_POSITION, # Tipo de stream
        4, # Taxa em Hz (4 vezes por segundo é bom)
        1  # Iniciar stream
    )
    # Opcional: Solicitar também ATTITUDE para o YAW, se quiser
    master.mav.request_data_stream_send(
        master.target_system, master.target_component,
        mavutil.mavlink.MAV_DATA_STREAM_EXTRA1, 4, 1
        )
    time.sleep(1) # Dá um tempo para a Pixhawk começar a enviar

    os.makedirs(BASE_PHOTO_DIR, exist_ok=True)

    max_mission_num = 0
    for folder_name in os.listdir(BASE_PHOTO_DIR):
        if folder_name.startswith("missao"):
            try:
                num = int(folder_name[6:])
                if num > max_mission_num:
                    max_mission_num = num
            except ValueError:
                continue

    new_mission_num = max_mission_num + 1
    session_folder_name = f"missao{new_mission_num}"
    session_path = os.path.join(BASE_PHOTO_DIR, session_folder_name)
    os.makedirs(session_path)

    print(f"Iniciando nova missão. Imagens em: {session_path}")
    
    status_led.blink(on_time=1, off_time=1)

except Exception as e:
    print(f"FALHA na conexão: {e}")
    sys.exit(1)

# --- FUNÇÃO ATUALIZADA: Salva Log CSV (com AGL e vírgula) ---
def capture_and_log(full_path, telemetry_data, image_name):
    trigger_led.on()
    print(f"--> Capturando imagem: {image_name}")

    capture_command = [
        "rpicam-still",
        "--nopreview",
        "-t", "500",
        "--width", "2592",
        "--height", "1944",
        "--sharpness", "1.5",
        "--denoise", "cdn_hq",
        "-o", full_path
    ]

    try:
        # --- Etapa 1: Capturar a imagem ---
        start_capture_time = time.monotonic()
        subprocess.run(capture_command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=5)
        end_capture_time = time.monotonic()
        print(f"    ...Imagem capturada com sucesso em {end_capture_time - start_capture_time:.2f}s.")

        # --- Etapa 2: Salvar o log CSV ---
        base_name = os.path.splitext(image_name)[0]
        log_name = base_name + ".log.csv"
        log_path = os.path.join(os.path.dirname(full_path), log_name)

        print(f"    ...Salvando log em: {log_path}")
        # (MUDANÇA 1) Print atualizado para mostrar altitude AGL
        print(f"    ...Dados: Lat {telemetry_data['lat']:.6f}, Lon {telemetry_data['lon']:.6f}, Alt_AGL {telemetry_data['altitude_agl']:.2f}m, Yaw {telemetry_data['yaw']:.2f}°")
        
        try:
            with open(log_path, 'w', newline='') as f:
                writer = csv.writer(f, delimiter=',')
                
                writer.writerow([
                    telemetry_data['lat'],
                    telemetry_data['lon'],
                    telemetry_data['altitude_agl'],
                    telemetry_data['yaw']
                ])
            print(f"    ...Log CSV salvo com sucesso.")
        
        except Exception as e:
            print(f"    ...ERRO AO SALVAR O LOG CSV: {e}")

    except subprocess.CalledProcessError as e:
        if e.cmd[0] == "rpicam-still":
            print(f"    ERRO ao capturar imagem: {e.stderr.decode('utf-8')}")
        else:
            print(f"    ERRO de subprocesso: {e.stderr.decode('utf-8')}")
    except FileNotFoundError as e:
        if e.filename == "rpicam-still":
            print("    ERRO: 'rpicam-still' não encontrado. Certifique-se de que a câmera está conectada e os drivers estão ok.")
    except Exception as e:
        print(f"    ERRO: {e}")
    finally:
        trigger_led.off()

# --- LOOP PRINCIPAL (ATUALIZADO PARA CAPTURAR YAW E ALTURA AGL) ---
try:
    while True:
        # Tenta receber qualquer uma das TRÊS mensagens
        msg = master.recv_match(type=['GLOBAL_POSITION_INT', 'ATTITUDE', 'CAMERA_FEEDBACK'], blocking=False, timeout=0.05)
        
        if msg:
            msg_type = msg.get_type() # Obtém o tipo da mensagem recebida

            if msg_type == 'GLOBAL_POSITION_INT':
                current_telemetry['lat'] = msg.lat / 1e7
                current_telemetry['lon'] = msg.lon / 1e7
                current_telemetry['altitude_agl'] = msg.relative_alt / 1000.0
                
                # debug print(f"[GPS_INT] Atualizado: Lat {current_telemetry['lat']:.6f}, Lon {current_telemetry['lon']:.6f}, Alt_AGL {current_telemetry['altitude_agl']:.2f}m")
            
            elif msg_type == 'ATTITUDE':
                # Atualiza o YAW
                yaw_deg = math.degrees(msg.yaw)
                if yaw_deg < 0:
                    yaw_deg += 360
                current_telemetry['yaw'] = yaw_deg
                # debug print(f"[ATTITUDE] Yaw atualizado: {current_telemetry['yaw']:.2f}°")

            elif msg_type == 'CAMERA_FEEDBACK':
                current_time = time.time()
                if (current_time - last_trigger_time) > COOLDOWN_SECONDS:
                    print("\n>>> Sinal de Trigger da Câmera Recebido! <<<")
                    
                    if current_telemetry['lat'] == 0.0 and current_telemetry['lon'] == 0.0:
                        print("    ...AVISO: GPS da GLOBAL_POSITION_INT é (0,0). Log pode ser impreciso.")

                    image_index = msg.img_idx 
                    image_name = f"imagem{image_index}.jpg"
                    full_path = os.path.join(session_path, image_name)

                    # Chama a função ATUALIZADA
                    capture_and_log(full_path, current_telemetry, image_name)

                    print("--- Ação concluída. Aguardando próximo trigger ---")
                    last_trigger_time = current_time
        
        time.sleep(0.01)

except KeyboardInterrupt:
    print("\nEncerrando o programa.")
finally:
    status_led.off()
    trigger_led.off()