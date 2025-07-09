import time
import os
from pymavlink import mavutil
from picamera2 import Picamera2

# --- CONFIGURAÇÕES ---
# Verifique a porta com 'ls /dev/ttyACM*'
PIXHAWK_PORT = '/dev/ttyACM1'  # ATENÇÃO: Verifique se a porta ainda é esta!
BAUD_RATE = 115200
PHOTO_DIR = os.path.join(os.path.expanduser('~'), 'Imagens_Capturadas')

# --- INICIALIZAÇÃO ---
os.makedirs(PHOTO_DIR, exist_ok=True)

try:
    print("Inicializando a câmera...")
    picam2 = Picamera2()
    config = picam2.create_still_configuration()
    picam2.configure(config)
    picam2.start()
    time.sleep(2)
    print(">>> Câmera pronta!")
except Exception as e:
    print(f"FALHA ao inicializar a câmera: {e}")
    exit()

try:
    print(f"Conectando à Pixhawk em {PIXHAWK_PORT}...")
    master = mavutil.mavlink_connection(PIXHAWK_PORT, baud=BAUD_RATE)
    master.wait_heartbeat()
    print(">>> Conexão estabelecida. Aguardando sinal 'CAMERA_FEEDBACK'...")
except Exception as e:
    print(f"FALHA ao conectar à Pixhawk: {e}")
    exit()

# --- FUNÇÃO DE CAPTURA ---
def take_photo():
    """Tira e salva uma foto."""
    try:
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        filename = os.path.join(PHOTO_DIR, f"foto_{timestamp}.jpg")
        print(f">>> SINAL RECEBIDO! Capturando foto: {filename}")
        picam2.capture_file(filename)
        print("    ...Foto salva!")
    except Exception as e:
        print(f"    ERRO ao capturar foto: {e}")

# --- LOOP PRINCIPAL ---
try:
    while True:
        # Espera especificamente pela mensagem CAMERA_FEEDBACK
        msg = master.recv_match(type='CAMERA_FEEDBACK', blocking=True)
        if msg:
            # Ao receber a mensagem, dispara a câmera.
            take_photo()

except KeyboardInterrupt:
    print("\nEncerrando o programa.")
    picam2.stop()
