# camTrigger.py - Versão final com LEDs de status e trigger.

import time
import subprocess
import os
import sys
from pymavlink import mavutil
from gpiozero import LED 

# --- CONFIGURAÇÕES ---
PIXHAWK_PORT = '/dev/ttyACM0'  # Verifique a porta com 'ls /dev/ttyACM*'
BAUD_RATE = 115200
COOLDOWN_SECONDS = 5
#Define os pinos GPIO para cada LED
LED_STATUS_PIN = 17
LED_TRIGGER_PIN = 27

BASE_PHOTO_DIR = os.path.join(os.path.expanduser('~'), 'Imagens_Capturadas')


# --- INICIALIZAÇÃO ---
last_trigger_time = 0
image_counter = 0
g_current_position = {'lat': 0, 'lon': 0, 'alt': 0}

#Inicializa os objetos dos LEDs
status_led = LED(LED_STATUS_PIN)
trigger_led = LED(LED_TRIGGER_PIN)
status_led.on() # Acende o LED de status para indicar que o script está iniciando
trigger_led.off() # Garante que o LED de trigger comece desligado

# Cria a pasta da sessão
session_folder_name = f"voo_{time.strftime('%Y%m%d-%H%M%S')}"
session_path = os.path.join(BASE_PHOTO_DIR, session_folder_name)
os.makedirs(session_path, exist_ok=True)
print(f"Imagens desta sessão serão salvas em: {session_path}")

# --- Conexão com a Pixhawk ---
try:
    print(f"Conectando à Pixhawk em {PIXHAWK_PORT}...")
    master = mavutil.mavlink_connection(PIXHAWK_PORT, baud=BAUD_RATE)
    master.wait_heartbeat()
    print(">>> Conexão estabelecida. Sistema pronto.")
    #Se a conexão for bem-sucedida, o LED de status começa a piscar
    status_led.blink(on_time=1, off_time=1) # Pisca a cada segundo
except Exception as e:
    print(f"FALHA na conexão: {e}")
    # NOVO: Se a conexão falhar, o LED de status permanece aceso solidamente como sinal de erro
    sys.exit(1)

# --- FUNÇÃO PRINCIPAL DE AÇÃO ---
def capture_and_geotag(full_path, gps_data):
    # Acende o LED de trigger antes de capturar
    trigger_led.on()
    
    print(f"--> Capturando imagem em: {full_path}")
    capture_command = ["libcamera-still", "-n", "-t", "200", "--width", "1920", "--height", "1080", "-o", full_path]
    
    try:
        subprocess.run(capture_command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("    ...Imagem capturada com sucesso.")
    except Exception as e:
        print(f"    ERRO ao capturar imagem: {e}")
        trigger_led.off() #Garante que o LED apague mesmo se houver erro
        return

    #Apaga o LED de trigger logo após a captura
    trigger_led.off()
    
    print(f"    ...Geotagging com: Lat {gps_data['lat']}, Lon {gps_data['lon']}, Alt {gps_data['alt']} m")
    geotag_command = ["exiftool", "-overwrite_original", f"-GPSLatitude={gps_data['lat']}", f"-GPSLongitude={gps_data['lon']}", f"-GPSAltitude={gps_data['alt']}", f"-GPSLatitudeRef={'N' if gps_data['lat'] >= 0 else 'S'}", f"-GPSLongitudeRef={'E' if gps_data['lon'] >= 0 else 'W'}", full_path]

    try:
        subprocess.run(geotag_command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("    ...Geotag concluído.")
    except Exception as e:
        print(f"    ERRO no geotag: {e}")

# --- LOOP PRINCIPAL ---
try:
    while True:
        msg = master.recv_match(type=['GLOBAL_POSITION_INT', 'VFR_HUD', 'CAMERA_FEEDBACK'], blocking=True, timeout=2)
        if not msg:
            continue

        msg_type = msg.get_type()

        if msg_type == 'GLOBAL_POSITION_INT':
            g_current_position['lat'] = msg.lat / 1e7
            g_current_position['lon'] = msg.lon / 1e7
            g_current_position['alt'] = msg.relative_alt / 1e3

        elif msg_type == 'CAMERA_FEEDBACK':
            current_time = time.time()
            if (current_time - last_trigger_time) > COOLDOWN_SECONDS:
                print("\n>>> Sinal de Trigger Recebido! <<<")
                image_counter += 1
                image_name = f"imagem_{image_counter:04d}.jpg"
                full_path = os.path.join(session_path, image_name)
                capture_and_geotag(full_path, g_current_position)
                print("--- Ação concluída. Aguardando próximo trigger ---")
                last_trigger_time = current_time

except KeyboardInterrupt:
    print("\nEncerrando o programa.")
    status_led.off()
    trigger_led.off()
