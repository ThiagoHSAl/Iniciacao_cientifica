#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import subprocess
import os
import sys
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

    os.makedirs(BASE_PHOTO_DIR, exist_ok=True)

    max_mission_num = 0
    # ... (código de criação da pasta da missão sem alteração) ...
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

# --- FUNÇÃO ATUALIZADA: Geotag com ALTURA (relativa) ---
def capture_and_geotag(full_path, gps_data, image_name):
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
        subprocess.run(capture_command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        print("    ...Imagem capturada com sucesso.")

        # --- Etapa 2: Aplicar o Geotag com exiftool ---
        # Usamos o dicionário 'altura_relativa' que passamos
        print(f"    ...Aplicando geotag: Lat {gps_data['lat']:.6f}, Lon {gps_data['lon']:.6f}, Altura {gps_data['altura_relativa']:.2f}m")
        
        # --- MUDANÇA PRINCIPAL ---
        # O EXIF padrão espera -GPSAltitude como Absoluto (nível do mar).
        # A tag correta para "altura" (relativa) é -RelativeAltitude (ou XMP:RelativeAltitude).
        geotag_command = [
            "exiftool",
            f"-GPSLatitude={gps_data['lat']}",
            f"-GPSLongitude={gps_data['lon']}",
            
            # Salva a altura relativa na tag XMP (mais compatível)
            f"-XMP:RelativeAltitude={gps_data['altura_relativa']}",
            
            # Opcional: Salva a altitude absoluta (nível do mar) se ela existir
            # (Note que gps_data['altitude_abs'] foi adicionado no loop principal)
            f"-GPSAltitude={gps_data['altitude_abs']}",
            "-GPSAltitudeRef=0", # 0 = Altitude Acima do Nível do Mar
            
            "-overwrite_original",
            full_path
        ]
        # --- FIM DA MUDANÇA ---
        
        subprocess.run(geotag_command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        print("    ...Geotag aplicado com sucesso.")

    except subprocess.CalledProcessError as e:
        if e.cmd[0] == "rpicam-still":
            print(f"    ERRO ao capturar imagem: {e.stderr.decode('utf-8')}")
        elif e.cmd[0] == "exiftool":
            print(f"    ERRO ao aplicar geotag: {e.stderr.decode('utf-8')}")
        else:
            print(f"    ERRO de subprocesso: {e.stderr.decode('utf-8')}")
    except FileNotFoundError as e:
        if e.filename == "rpicam-still":
            print("    ERRO: 'rpicam-still' não encontrado.")
        elif e.filename == "exiftool":
            print("    ERRO: 'exiftool' não encontrado. Instale com 'sudo apt install libimage-exiftool-perl'")
    except Exception as e:
        print(f"    ERRO: {e}")
    finally:
        trigger_led.off()

# --- LOOP PRINCIPAL ---
try:
    while True:
        msg = master.recv_match(type='CAMERA_FEEDBACK', blocking=True, timeout=5)
        
        if not msg:
            continue

        current_time = time.time()
        if (current_time - last_trigger_time) > COOLDOWN_SECONDS:
            print("\n>>> Sinal de Trigger Recebido! <<<")

            # --- MUDANÇA PRINCIPAL ---
            # 1. Corrigido: msg.alt_rel e msg.alt_msl já estão em metros (float).
            # 2. Renomeado para clareza (altura vs altitude).
            gps_data_from_trigger = {
                'lat': msg.lat / 1e7,
                'lon': msg.lon / 1e7,
                'altura_relativa': msg.alt_rel, # Esta é a "altura" (AGL)
                'altitude_abs': msg.alt_msl    # Esta é a "altitude" (nível do mar)
            }
            # --- FIM DA MUDANÇA ---

            if gps_data_from_trigger['lat'] == 0 and gps_data_from_trigger['lon'] == 0:
                print("    ...AVISO: Trigger recebido, mas o GPS da Pixhawk é (0,0).")

            image_index = msg.img_idx
            image_name = f"imagem_{image_index:04d}.jpg"
            full_path = os.path.join(session_path, image_name)

            capture_and_geotag(full_path, gps_data_from_trigger, image_name)

            print("--- Ação concluída. Aguardando próximo trigger ---")
            last_trigger_time = current_time

except KeyboardInterrupt:
    print("\nEncerrando o programa.")
    status_led.off()
    trigger_led.off()