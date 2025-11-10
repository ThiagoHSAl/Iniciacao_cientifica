#!/usr/bin/env python3

import subprocess
import json
import math
import sys
import re  # Importado para extrair o resultado do ping
import argparse

# --- Configurações ---

# Configs da Base (Netcat)
BASE_PORT = 8080
NC_TIMEOUT = 5.0
PING_DURATION = 10 # Duração do ping em segundos

# Configs do Drone (SSH)
DRONE_USER_HOST = "thiago-henrique@192.168.100.113"
DRONE_PATH = "'Iniciacao_cientifica'" # Use aspas extras p/ shell
DRONE_SCRIPT = "gpsGetter_single.py"

# --- Configurar e Ler Argumentos ---
parser = argparse.ArgumentParser(
    description="Executa teste de distância e latência (Ping) entre Base e Drone."
)
parser.add_argument(
    "--base-ip",
    required=True,
    help="O IP da Base Station (para o netcat)."
)
args = parser.parse_args()
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
    print(f"  -> Conectando à base local ({BASE_HOST}:{BASE_PORT}) por {NC_TIMEOUT}s...")
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
            timeout=60
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
        raise e

def run_ping_test():
    """
    Executa 'ping' contra o drone por 10 segundos e retorna a latência média (ms).
    """
    print(f"  -> Executando ping para {DRONE_IP} por {PING_DURATION} segundos...")
    
    # Comando 'ping' para Linux:
    # -w <segundos>: Define um "deadline". O ping para após N segundos.
    command = ["ping", "-w", str(PING_DURATION), DRONE_IP]
    
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=PING_DURATION + 5 # Um timeout de segurança um pouco maior
        )
        
        # A saída completa do ping
        ping_output = result.stdout
        
        if result.returncode != 0:
            if "Destination Host Unreachable" in ping_output:
                raise Exception("Ping falhou: Host de destino inacessível.")
            raise Exception(f"Ping falhou com código {result.returncode}: {ping_output}")
        
        # Procura pela linha de sumário (rtt min/avg/max/mdev)
        # Este regex procura por 4 números separados por '/' na linha de sumário
        match = re.search(r"([\d\.]+)/([\d\.]+)/([\d\.]+)/([\d\.]+) ms", ping_output)
        
        if match:
            # O grupo 2 é o valor 'avg' (média)
            avg_latency = float(match.group(2))
            return avg_latency
        else:
            # Isso pode acontecer se o ping não tiver recebido *nenhuma* resposta
            if "0 packets received" in ping_output:
                raise Exception("Ping falhou: 100% de perda de pacotes.")
            raise Exception(f"Não foi possível extrair a média do ping. Saída:\n{ping_output}")

    except FileNotFoundError:
        raise Exception("Comando 'ping' não encontrado. (Isto é muito incomum)")
    except Exception as e:
        raise e

# --- Execução Principal ---
if __name__ == "__main__":
    print(f"--- Teste de Correlação (Distância x Latência) ---")
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

        # Passo 4: Executar Ping
        print("\n[4/4] Testando Latência (Ping)...")
        avg_latency = run_ping_test()
        print(f"  -> SUCESSO (Latência): {avg_latency:.3f} ms (média)")
        
        # Relatório Final
        print("\n" + "="*50)
        print("            RELATÓRIO DE TESTE FINAL")
        print("="*50)
        print(f"Distância Base-Drone:  {distancia:.2f} metros")
        print(f"Latência Média (Ping): {avg_latency:.3f} ms")
        print("-" * 50)

    except Exception as e:
        print(f"\n--- ERRO ---")
        print(f"Ocorreu um erro: {e}")
        print("Verifique as conexões, IPs e se os scripts estão nos locais corretos.")
        sys.exit(1)
