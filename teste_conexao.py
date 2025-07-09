import time
from pymavlink import mavutil

# Confirme que a porta e a velocidade estão corretas
PIXHAWK_PORT = '/dev/ttyACM1' 
BAUD_RATE = 115200

try:
    print(f"Teste Python: Conectando à Pixhawk em {PIXHAWK_PORT}...")
    master = mavutil.mavlink_connection(PIXHAWK_PORT, baud=BAUD_RATE)
    master.wait_heartbeat()
    print(">>> Teste Python: Conexão estabelecida. Aguardando 'CAMERA_FEEDBACK'...")
except Exception as e:
    print(f"FALHA na conexão: {e}")
    exit()

try:
    while True:
        msg = master.recv_match(type='CAMERA_FEEDBACK', blocking=True, timeout=5)
        if msg:
            print("\n>>> SUCESSO! Sinal 'CAMERA_FEEDBACK' detectado pelo Python! <<<\n")
        else:
            print("(Aguardando...)")

except KeyboardInterrupt:
    print("\nEncerrando teste.")
