#!/usr/bin/env python3

import subprocess
import json
import math
import sys
import re
import argparse # <-- 1. IMPORTADO

# --- Configurações ---

# 2. REMOVIDO o BASE_HOST daqui

# Configs da Base (Netcat)
BASE_PORT = 8080
NC_TIMEOUT = 5.0

# Configs do Drone (SSH)
DRONE_USER_HOST = "thiago-henrique@192.168.100.113"
DRONE_PATH = "'Iniciacao_cientifica'" # Use aspas extras p/ shell
DRONE_SCRIPT = "gpsGetter_single.py"

# --- 3. CONFIGURAR E LER ARGUMENTOS ---
# Configura o parser de argumentos
parser = argparse.ArgumentParser(
    description="Executa teste de distância e largura de banda entre Base e Drone."
)
parser.add_argument(
    "--base-ip",
    required=True, # <-- Torna o argumento obrigatório
    help="O IP da Base Station (para o netcat)."
)
# Analisa os argumentos passados na linha de comando
args = parser.parse_args()

# O IP da base agora vem dos argumentos
BASE_HOST = args.base_ip
# ----------------------------------------

# Extrai o IP do drone para o iperf3
try:
    DRONE_IP = DRONE_USER_HOST.split('@')[1]
except IndexError:
    print(f"Erro: Formato de DRONE_USER_HOST ('{DRONE_USER_HOST}') inválido. Deve ser 'usuario@ip'.")
    sys.exit(1)

# Comando SSH completo
SSH_COMMAND = [
    "ssh", "-t", DRONE_USER_HOST,
    f"cd {DRONE_PATH} && source venv/bin/activate && python {DRONE_SCRIPT}"
]
# ---------------------

def haversine(lat1, lon1, lat2, lon2):
    """Calcula a distância (em metros) entre dois pontos."""
    R = 6371000  # Raio da Terra em metros
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    dlon = lon2_rad - lon1_rad
    dlat = lat2_rad - lat1_rad
    a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def get_base_gps():
    """Executa 'nc' localmente para obter o GPS da base."""
    # A variável BASE_HOST agora é lida dos argumentos
    print(f"  -> Conectando à base local ({BASE_HOST}:{BASE_PORT}) por {NC_TIMEOUT}s...")
    
    # 4. USA A VARIÁVEL BASE_HOST (dos argumentos) AQUI
    command = ["nc", BASE_HOST, str(BASE_PORT)] 
    
    try:
        result = subprocess.run(command, capture_output=True, timeout=NC_TIMEOUT)
        raw_output_bytes = result.stdout
    except subprocess.TimeoutExpired as e:
        raw_output_bytes = e.stdout if e.stdout else b""
    except FileNotFoundError:
        raise Exception("Comando 'nc' (netcat) não encontrado.")
    
    raw_output = raw_output_bytes.decode('utf-8', errors='ignore')
    
    if not raw_output:
        raise Exception("Nenhum dado recebido do netcat (base).")

    first_brace = raw_output.find('{')
    if first_brace == -1:
        raise Exception("Nenhum JSON encontrado na saída do netcat (base).")
    
    decoder = json.JSONDecoder()
    json_obj, _ = decoder.raw_decode(raw_output[first_brace:])
    
    return json_obj['latitude'], json_obj['longitude']

def get_drone_gps():
    """Executa 'ssh' para obter o GPS do drone."""
    print(f"  -> Conectando ao drone ({DRONE_USER_HOST}) via SSH...")
    print(f"  -> Comando: {' '.join(SSH_COMMAND)}")
    
    try:
        result = subprocess.run(
            SSH_COMMAND,
            capture_output=True,
            text=True,
            timeout=60 # Timeout de 60 segundos
        )

        if result.returncode != 0:
            print("\n--- ERRO NO SCRIPT DO DRONE (stderr) ---")
            print(result.stderr)
            print("------------------------------------------")
            raise Exception("Falha ao executar script no drone.")
        
        json_output = result.stdout.strip()
        json_line = [line for line in json_output.splitlines() if line.startswith('{')][-1]
        json_obj = json.loads(json_line)
        return json_obj['latitude'], json_obj['longitude']

    except subprocess.TimeoutExpired:
        raise Exception("Timeout - O script SSH demorou mais de 60s para responder.")
    except Exception as e:
        raise e # Re-lança a exceção

def run_iperf_test():
    """Executa 'iperf3 -c' contra o drone e retorna a largura de banda em Mbits/s."""
    print(f"  -> Conectando ao iperf3 server no drone ({DRONE_IP})...")
    
    command = ["iperf3", "-c", DRONE_IP, "-J"]
    
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=30 # iperf3 pode demorar, damos 30s
        )
        
        if result.returncode != 0:
            if "Connection refused" in result.stdout:
                raise Exception("Conexão recusada. O servidor 'iperf3 -s' está rodando no drone?")
            raise Exception(f"iperf3 falhou: {result.stdout} {result.stderr}")
        
        iperf_data = json.loads(result.stdout)
        
        bandwidth_bps = iperf_data["end"]["sum_sent"]["bits_per_second"]
        bandwidth_mbps = bandwidth_bps / 1_000_000
        
        return bandwidth_mbps
        
    except FileNotFoundError:
        raise Exception("Comando 'iperf3' não encontrado. Instale o iperf3 na sua Base Station.")
    except json.JSONDecodeError:
        raise Exception(f"Falha ao decodificar a saída JSON do iperf3. Saída: {result.stdout}")
    except Exception as e:
        raise e

# --- Execução Principal ---
if __name__ == "__main__":
    print(f"--- Teste de Correlação (Distância x Largura de Banda) ---")
    print(f"IP da Base Station definido como: {BASE_HOST}")
    
    try:
        # Passo 1: Obter GPS da Base
        print("\n[1/4] Obtendo localização da Base Station...")
        base_lat, base_lon = get_base_gps()
        print(f"  -> SUCESSO (Base): Lat={base_lat:.6f}, Lon={base_lon:.6f}")
        
        # Passo 2: Obter GPS do Drone
        print("\n[2/4] Obtendo localização do Drone...")
        drone_lat, drone_lon = get_drone_gps()
        print(f"  -> SUCESSO (Drone): Lat={drone_lat:.6f}, Lon={drone_lon:.6f}")
        
        # Passo 3: Calcular Distância
        print("\n[3/4] Calculando distância...")
        distancia = haversine(base_lat, base_lon, drone_lat, drone_lon)
        print(f"  -> SUCESSO (Distância): {distancia:.2f} metros")

        # Passo 4: Executar iperf3
        print("\n[4/4] Testando Largura de Banda...")
        largura_banda = run_iperf_test()
        print(f"  -> SUCESSO (Largura de Banda): {largura_banda:.2f} Mbits/sec")
        
        # Relatório Final
        print("\n" + "="*50)
        print("            RELATÓRIO DE TESTE FINAL")
        print("="*50)
        print(f"Distância Base-Drone:  {distancia:.2f} metros")
        print(f"Largura de Banda (UL): {largura_banda:.2f} Mbits/sec")
        print("-" * 50)
        
        if distancia > 0:
            ratio = largura_banda / distancia
            print(f"Relação (Largura/Distância): {ratio:.3f} Mbits/s por metro")
        else:
            print("Distância é zero, não é possível calcular a relação.")

    except Exception as e:
        print(f"\n--- ERRO ---")
        print(f"Ocorreu um erro: {e}")
        print("Verifique as conexões, IPs e se os scripts/servidores estão nos locais corretos.")
        sys.exit(1)
