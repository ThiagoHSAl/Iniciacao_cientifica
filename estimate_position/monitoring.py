import subprocess
import time
import os
import re
import sys
from pymavlink import mavutil # Usando apenas pymavlink

# --- CONFIGURAÇÕES ---
DRONE_USER = "thiago-henrique"
DRONE_IP = "192.168.100.113" # Substitua pelo IP correto
DRONE_BASE_DIR = "/home/thiago-henrique/Imagens_Capturadas" 
LOCAL_DIR = "./dados_recebidos"
ESTIMATE_SCRIPT = "detect_and_estimate_position.py"

POLLING_INTERVAL = 3
LOG_RETRY_ATTEMPTS = 5  # Quantas vezes tentar baixar o log antes de desistir
LOG_RETRY_DELAY = 1     # Segundos entre tentativas

last_processed_index = -1

def enviar_comando_drone_pymavlink(lat, lon, alt=20):
    """
    Conecta no Mission Planner localmente via MAVLink e envia comando GUIDED para Lat/Lon.
    """
    # 'udpin:0.0.0.0:14550' cria um servidor que escuta o Mission Planner (que deve ser UDP Client)
    connection_string = 'udpin:0.0.0.0:14550' 
    
    print(f"Conectando ao fluxo MAVLink em {connection_string}...")
    
    try:
        # Cria a conexão
        master = mavutil.mavlink_connection(connection_string)
        
        # Espera o primeiro heartbeat para confirmar conexão e identificar o sistema
        print("Aguardando Heartbeat do drone (via Mission Planner)...")
        master.wait_heartbeat(timeout=10)
        
        if not master.target_system:
            print("ERRO: Heartbeat não recebido. Verifique se o Mission Planner está conectado e encaminhando Mavlink.")
            return False
            
        print(f"Conectado ao Drone (System {master.target_system}, Component {master.target_component})")

        # 1. Mudar para modo GUIDED
        # Verifica se já está em GUIDED para não reenviar à toa (opcional, mas boa prática)
        # Mapeamento de modos para ArduCopter
        mode_id = master.mode_mapping().get('GUIDED')
        if mode_id is None:
            print("ERRO: Modo GUIDED não encontrado no mapeamento.")
            return False

        print("Mudando modo de voo para GUIDED...")
        master.mav.set_mode_send(
            master.target_system,
            mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
            mode_id
        )

        # Pequena pausa para garantir a troca de modo
        time.sleep(0.5)

        # 2. Enviar comando de posição (Go To)
        print(f"Enviando comando: Ir para Lat {lat}, Lon {lon}, Alt {alt}m")
        
        # Máscara de bits para ignorar velocidades, acelerações e yaw (focar apenas em posição)
        # 0b0000111111111000 = Ignora YAW, YAW_RATE, AX, AY, AZ, VX, VY, VZ
        type_mask = 0b0000111111111000

        master.mav.set_position_target_global_int_send(
            0, # time_boot_ms (0 = usar tempo do sistema)
            master.target_system,
            master.target_component,
            mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT, # Altitude relativa ao home (mais seguro)
            type_mask,
            int(lat * 1e7), # Lat (em inteiros de 7 casas decimais)
            int(lon * 1e7), # Lon
            alt,            # Alt (em metros)
            0, 0, 0, # Velocidades X,Y,Z (ignoradas pela máscara)
            0, 0, 0, # Acelerações X,Y,Z (ignoradas)
            0, 0     # Yaw, Yaw Rate (ignorados)
        )
        
        print("Comando enviado com sucesso!")
        return True

    except Exception as e:
        print(f"ERRO ao enviar comando MAVLink: {e}")
        return False

def get_latest_mission_dir():
    """Conecta via SSH e retorna o diretório da missão mais recente."""
    # ... (Código da função get_latest_mission_dir permanece igual) ...
    print(f"Buscando a missão mais recente em {DRONE_BASE_DIR}...")
    try:
        cmd = [
            "ssh", "-o", "ConnectTimeout=5", "-o", "BatchMode=yes",
            f"{DRONE_USER}@{DRONE_IP}", f"ls -d {DRONE_BASE_DIR}/missao*" 
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0: return None
        dirs = result.stdout.strip().split('\n')
        max_num = -1
        latest_dir = None
        pattern = re.compile(r'missao(\d+)$')
        for d in dirs:
            match = pattern.search(d.strip())
            if match:
                num = int(match.group(1))
                if num > max_num:
                    max_num = num
                    latest_dir = d.strip()
        if latest_dir: print(f"Missão mais recente encontrada: {latest_dir}"); return latest_dir
        else: return None
    except Exception as e: print(f"Erro ao buscar diretório: {e}"); return None

def get_remote_files_indices(mission_dir):
    """Lista os arquivos imagem*.jpg no drone."""
    # ... (Código da função get_remote_files_indices permanece igual) ...
    try:
        cmd = ["ssh", "-o", "ConnectTimeout=5", "-o", "BatchMode=yes", f"{DRONE_USER}@{DRONE_IP}", f"ls {mission_dir}/imagem*.jpg"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0: return []
        file_list = result.stdout.strip().split('\n')
        indices = []
        pattern = re.compile(r'imagem(\d+)\.jpg$')
        for filepath in file_list:
            match = pattern.search(filepath.strip())
            if match: indices.append(int(match.group(1)))
        return sorted(indices)
    except Exception: return []

def pull_and_process(index, mission_dir):
    """
    Baixa JPG e LOG, e executa a estimativa.
    Retorna True se processou com sucesso (ou se desistiu após erro para não travar).
    Retorna False apenas se quiser tentar o MESMO índice novamente na próxima iteração.
    """
    filename_jpg = f"imagem{index}.jpg"
    filename_log = f"imagem{index}.log.csv" # Ajustado conforme seu log anterior
    
    local_jpg_path = os.path.join(LOCAL_DIR, filename_jpg)
    local_log_path = os.path.join(LOCAL_DIR, filename_log)

    print(f"--> Detectada nova imagem Baixando...")

    # 1. Baixar JPG (Essencial)
    try:
        subprocess.run(["scp", f"{DRONE_USER}@{DRONE_IP}:{mission_dir}/{filename_jpg}", local_jpg_path], check=True)
    except subprocess.CalledProcessError:
        print(f"    ERRO FATAL: Não foi possível baixar {filename_jpg}. Pulando este índice.")
        return True # Retorna True para avançar e não ficar preso tentando baixar algo que falhou

    # 2. Baixar LOG (Com Retries)
    log_downloaded = False
    for attempt in range(LOG_RETRY_ATTEMPTS):
        try:
            subprocess.run(
                ["scp", f"{DRONE_USER}@{DRONE_IP}:{mission_dir}/{filename_log}", local_log_path], 
                check=True, 
                stderr=subprocess.DEVNULL # Silencia erro no terminal durante tentativas
            )
            log_downloaded = True
            break # Sucesso!
        except subprocess.CalledProcessError:
            # Falhou, espera um pouco e tenta de novo (o drone pode estar escrevendo ainda)
            time.sleep(LOG_RETRY_DELAY)
    
    if not log_downloaded:
        print(f"    AVISO: Log {filename_log} não encontrado após {LOG_RETRY_ATTEMPTS} tentativas.")
        # Decisão: Processar sem log ou pular?
        # Se o estimate_position.py precisa OBRIGATORIAMENTE do log e falha sem ele, 
        # não podemos rodar o script de estimativa.
        # Vamos pular a estimativa mas retornar True para não travar o loop de download das próximas fotos.
        print("    PULANDO estimativa para este índice devido à falta de log.")
        return True 

    print(f"    Download concluído. Executando detecção...")
    
    # 3. Executar estimate_position.py
    # CORREÇÃO: Usando --source <arquivo_jpg>
    try:
        proc = subprocess.run(
            [sys.executable, ESTIMATE_SCRIPT, "--source", local_jpg_path],
            capture_output=True,
            text=True
        )
        
        print(f"    [Resultado Detecção]:\n{proc.stdout}")
        if proc.stderr:
            print(f"    [Erros Detecção]:\n{proc.stderr}")

    except Exception as e:
        print(f"    Erro ao executar script de detecção: {e}")
    
    """output_do_script = proc.stdout 
    # Regex procura por algo como: "GPS do Objeto: (-19.8698034, -43.9584576)"
    match_coords = re.search(r'GPS do Objeto:\s*\(\s*([-+]?\d+\.\d+)\s*,\s*([-+]?\d+\.\d+)\s*\)', output_do_script)
    
    if match_coords:
        lat_alvo = float(match_coords.group(1))
        lon_alvo = float(match_coords.group(2))
        
        print(f"--> ALVO DETECTADO! Lat: {lat_alvo}, Lon: {lon_alvo}")
        print("--> Iniciando comando de retorno autônomo...")
        
        # Chama a função PyMavlink
        enviar_comando_drone_pymavlink(lat_alvo, lon_alvo)

    return True # Sucesso (ou erro tratado), pode avançar para o próximo índice
    """

# --- LOOP PRINCIPAL ---
if __name__ == "__main__":
    os.makedirs(LOCAL_DIR, exist_ok=True)
    
    print("Iniciando monitoramento...")
    current_mission_dir = get_latest_mission_dir()
    
    if not current_mission_dir:
        print("Não foi possível determinar a pasta da missão.")
        sys.exit(1)

    print(f"Monitorando pasta: {current_mission_dir}")

    try:
        while True:
            current_indices = get_remote_files_indices(current_mission_dir)
            
            # Filtra apenas índices novos
            new_indices = [i for i in current_indices if i > last_processed_index]
            
            for idx in new_indices:
                # Tenta processar.
                # A função agora retorna True mesmo se falhar o log, para garantir
                # que o loop continue para as próximas fotos.
                pull_and_process(idx, current_mission_dir)
                
                # Atualiza o último processado. 
                # Mesmo se a estimativa falhar, consideramos processado para não travar.
                last_processed_index = idx 
            
            time.sleep(POLLING_INTERVAL)

    except KeyboardInterrupt:
        print("\nMonitoramento encerrado.")