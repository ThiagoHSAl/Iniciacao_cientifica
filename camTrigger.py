import time
import subprocess
import os
import sys
from pymavlink import mavutil
from gpiozero import LED

# --- CONFIGURAÇÕES ---
PIXHAWK_PORT = '/dev/ttyACM0'
BAUD_RATE = 115200
COOLDOWN_SECONDS = 5
LED_STATUS_PIN = 17
LED_TRIGGER_PIN = 27

BASE_PHOTO_DIR = os.path.join(os.path.expanduser('~'), 'Imagens_Capturadas')

# --- INICIALIZAÇÃO ---
last_trigger_time = 0
image_counter = 0
g_current_position = {'lat': 0, 'lon': 0, 'alt': 0}
session_path = "" 

status_led = LED(LED_STATUS_PIN)
trigger_led = LED(LED_TRIGGER_PIN)
status_led.on() 
trigger_led.off() 

# --- Conexão com a Pixhawk e Criação da Pasta ---
try:
    print(f"Conectando à Pixhawk em {PIXHAWK_PORT}...")
    master = mavutil.mavlink_connection(PIXHAWK_PORT, baud=BAUD_RATE)
    master.wait_heartbeat()
    print(">>> Conexão estabelecida. Sistema pronto.")
    
    # Garante que o diretório base de imagens exista
    os.makedirs(BASE_PHOTO_DIR, exist_ok=True)
    
    # Procura pela missão com o número mais alto
    max_mission_num = 0
    for folder_name in os.listdir(BASE_PHOTO_DIR):
        if folder_name.startswith("missao"):
            try:
                # Extrai o número do nome da pasta (ex: de "missao12", extrai 12)
                num = int(folder_name[6:])
                if num > max_mission_num:
                    max_mission_num = num
            except ValueError:
                # Ignora pastas que não seguem o padrão, ex: "missao_teste"
                continue

    new_mission_num = max_mission_num + 1
    session_folder_name = f"missao{new_mission_num}"
    
    # Junta com o caminho base para formar o caminho final
    session_path = os.path.join(BASE_PHOTO_DIR, session_folder_name)
    
    # Cria a nova pasta da missão
    os.makedirs(session_path)
    
    print(f"Iniciando nova missão. Imagens serão salvas em: {session_path}")

    # Se a conexão for bem-sucedida, o LED de status começa a piscar
    status_led.blink(on_time=1, off_time=1) 
    
except Exception as e:
    print(f"FALHA na conexão: {e}")
    sys.exit(1)

# --- FUNÇÃO PRINCIPAL DE AÇÃO (sem alterações) ---
def capture_and_geotag(full_path, gps_data):
    trigger_led.on()
    print(f"--> Capturando imagem em: {full_path}")
    capture_command = [
    "libcamera-still",
    "-n",
    "-t", "2000",
    "--width", "2592",
    "--height", "1944",
    "--sharpness", "1.5",
    "--denoise", "cdn_hq",
    "-o", full_path
    ]   
    try:
        subprocess.run(capture_command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("    ...Imagem capturada com sucesso.")
    except Exception as e:
        print(f"    ERRO ao capturar imagem: {e}")
        trigger_led.off() 
        return
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
        elif msg_type == 'VFR_HUD':
            g_current_position['alt'] = msg.alt

        elif msg_type == 'CAMERA_FEEDBACK':
            current_time = time.time()
            if (current_time - last_trigger_time) > COOLDOWN_SECONDS:
                print("\n>>> Sinal de Trigger Recebido! <<<")
                image_counter += 1
                
                # MUDANÇA AQUI: Nome da imagem volta a ser sequencial simples
                image_name = f"imagem_{image_counter:04d}.jpg" # Ex: imagem_0001.jpg
                
                full_path = os.path.join(session_path, image_name)
                capture_and_geotag(full_path, g_current_position)
                print("--- Ação concluída. Aguardando próximo trigger ---")
                last_trigger_time = current_time

except KeyboardInterrupt:
    print("\nEncerrando o programa.")
    status_led.off()
    trigger_led.off()