#!/usr/bin/env python3

import asyncio
from mavsdk import System

# --- CONFIGURAÇÕES ---
# O formato do endereço para MAVSDK é diferente
PIXHAWK_ADDRESS = "serial:///dev/ttyACM0:115200"

async def run():
    """
    Função principal que se conecta ao drone e escuta por informações de captura da câmera.
    """
    # Instancia o objeto principal do MAVSDK
    drone = System()

    print(f"Conectando à Pixhawk no endereço {PIXHAWK_ADDRESS}...")
    await drone.connect(system_address=PIXHAWK_ADDRESS)

    # Aguarda a conexão ser estabelecida
    print("Aguardando o drone se conectar...")
    async for state in drone.core.connection_state():
        if state.is_connected:
            print(">>> Drone conectado com sucesso!")
            break

    print(">>> Aguardando por informações de captura da câmera (CAMERA_FEEDBACK)...")

    # Assina (subscribes) o fluxo de dados de "CaptureInfo",
    # que corresponde à mensagem CAMERA_FEEDBACK.
    async for info in drone.camera.capture_info():
        print("\n-----------------------------------------")
        print(">>> INFORMAÇÃO DE CAPTURA RECEBIDA! <<<")
        print(f"    Timestamp: {info.time_utc_us} us")
        print(f"    Índice da Imagem: {info.index}")
        # MAVSDK já fornece os dados de posição em um objeto aninhado
        print(f"    Latitude: {info.position.latitude_deg}")
        print(f"    Longitude: {info.position.longitude_deg}")
        print(f"    Altitude Relativa: {info.position.relative_altitude_m} m")
        print("-----------------------------------------")


if __name__ == "__main__":
    try:
        # Inicia o loop de eventos assíncrono para rodar a função run()
        asyncio.run(run())
    except asyncio.CancelledError:
        # Ocorre quando o programa é interrompido (Ctrl+C)
        print("\nPrograma encerrado pelo usuário.")
    except Exception as e:
        print(f"Ocorreu um erro: {e}")