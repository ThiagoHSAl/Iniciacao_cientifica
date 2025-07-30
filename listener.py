# feedback_listener.py
# Um script simples para se conectar a uma Pixhawk via USB e escutar
# apenas por mensagens MAVLink do tipo CAMERA_FEEDBACK.

import sys
from pymavlink import mavutil

# --- CONFIGURAÇÕES ---
# Verifique a porta serial correta com o comando 'ls /dev/ttyACM*' no terminal
PIXHAWK_PORT = '/dev/ttyACM0'
BAUD_RATE = 115200

# --- CONEXÃO ---
master = None
try:
    print(f"Conectando à Pixhawk na porta {PIXHAWK_PORT} a {BAUD_RATE} baud...")
    # Tenta estabelecer a conexão
    master = mavutil.mavlink_connection(PIXHAWK_PORT, baud=BAUD_RATE)

    # Espera por uma mensagem de 'heartbeat' para confirmar que a conexão está viva
    master.wait_heartbeat()

    print(">>> Conexão estabelecida com sucesso!")
    print(">>> Aguardando por mensagens 'CAMERA_FEEDBACK'...")

except Exception as e:
    print(f"FALHA na conexão: {e}")
    print("Verifique se a porta está correta, se o cabo USB está conectado e se a Pixhawk está ligada.")
    sys.exit(1) # Encerra o script se a conexão falhar


# --- LOOP PRINCIPAL ---
try:
    while True:
        # Espera (bloqueia) até que uma mensagem do tipo 'CAMERA_FEEDBACK' chegue.
        # Ignora todas as outras mensagens.
        msg = master.recv_match(type='CAMERA_FEEDBACK', blocking=True)

        # Se uma mensagem for recebida (o que sempre será verdade com blocking=True)
        if msg:
            print("\n-----------------------------------------")
            print(">>> MENSAGEM 'CAMERA_FEEDBACK' RECEBIDA! <<<")
            print(f"    Timestamp: {msg.time_usec}")
            print(f"    Índice da Imagem: {msg.img_idx}")
            print(f"    Latitude: {msg.lat / 1e7}")
            print(f"    Longitude: {msg.lng / 1e7}")
            print(f"    Altitude Relativa: {msg.alt_rel} m")
            print("-----------------------------------------")

except KeyboardInterrupt:
    print("\nPrograma encerrado pelo usuário.")
except Exception as e:
    print(f"Ocorreu um erro: {e}")