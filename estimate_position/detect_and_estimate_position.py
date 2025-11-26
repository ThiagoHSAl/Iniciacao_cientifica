from ultralytics import YOLO
import csv
import math
import os
import argparse
from pathlib import Path

OUTPUT_DIR = Path("predictions")
# --- Constantes da Câmera e Mundo (Baseadas nas Especificações) ---
# Resolução do Sensor (pixels)
IMG_WIDTH_PX = 2592
IMG_HEIGHT_PX = 1944
CENTER_X_PX = IMG_WIDTH_PX / 2
CENTER_Y_PX = IMG_HEIGHT_PX / 2

# Especificações Físicas do Sensor (mm)
FOCAL_LENGTH_MM = 3.6     # Distância Focal (f=3.6 mm)
SENSOR_WIDTH_MM = 3.67    # Tamanho do sensor (3.67 x 2.74 mm)
SENSOR_HEIGHT_MM = 2.74

# Constantes Geográficas
METERS_PER_DEGREE_LATITUDE = 111139.0 # Valor aprox. para metros por grau de latitude

# -------------------------------------------

# --- 3. CONFIGURAR E LER ARGUMENTOS ---
# Configura o parser de argumentos
parser = argparse.ArgumentParser(
    description="Estima a posição GPS de objetos detectados em imagens de drones."
)
parser.add_argument(
    "--source",
    required=True, # <-- Torna o argumento obrigatório
    help="Caminho para a imagem ou diretório de imagens.",
)
# Analisa os argumentos passados na linha de comando
args = parser.parse_args()

# O caminho da imagem ou diretório fornecido
SOURCE_PATH = args.source
# ----------------------------------------

def get_drone_telemetry(image_path):
    """
    Encontra e lê o arquivo .log.csv correspondente à imagem.
    Assume que 'imagem.jpg' tem um 'imagem.log.csv'.
    """
    base_name = os.path.splitext(image_path)[0]
    log_path = base_name + ".log.csv" # Ajuste se o nome for diferente

    if not os.path.exists(log_path):
        print(f"AVISO: Arquivo de log não encontrado: {log_path}")
        return None

    try:
        with open(log_path, 'r') as f:
            reader = csv.reader(f)
            # Assumindo que o CSV *não* tem cabeçalho. 
            # Se tiver, adicione: next(reader, None)
            data = next(reader) 
            
            # ATUALIZADO: Lendo 4 colunas: [latitude, longitude, altitude_agl, yaw]
            # Assumindo que Yaw está em graus, onde 0=Norte, 90=Leste
            drone_lat = float(data[0])
            drone_lon = float(data[1])
            drone_alt_agl = float(data[2]) # Altitude Acima do Solo (AGL)
            drone_yaw_deg = float(data[3]) # Yaw (Bússola) em graus
            
            return drone_lat, drone_lon, drone_alt_agl, drone_yaw_deg
            
    except Exception as e:
        print(f"Erro ao ler o arquivo de log {log_path}: {e}")
        return None

# --- Script Principal ---

# Carrega o modelo
model = YOLO('/home/thiagonote/Iniciacao_cientifica/YOLO_Drone/yolo11m_better_augmentation/weights/best.pt') # Use o caminho do seu modelo treinado

# Roda a predição no diretório
results = model.predict(source=SOURCE_PATH, verbose=False)

for r in results:
    if not r.boxes:
        print(f"Nenhuma detecção encontrada em: {r.path}")
        continue
    
    print(f"--- Processando Imagem: {r.path} ---")
    img_h, img_w = r.orig_shape

    # 1. Obter telemetria do drone (agora com Yaw)
    telemetry = get_drone_telemetry(r.path)
    if telemetry is None:
        print("Não foi possível obter telemetria. Pulando para a próxima imagem.")
        continue
    
    drone_lat, drone_lon, drone_alt, drone_yaw = telemetry
    print(f"  Drone GPS: ({drone_lat}, {drone_lon}), Altura: {drone_alt} m, Yaw: {drone_yaw}°")

    # Itera sobre cada detecção (bounding box) na imagem
    for box in r.boxes:
        
        # 2. Calcular o centro da Bounding Box (em pixels)
        xyxy = box.xyxy[0].tolist() # [x1, y1, x2, y2]
        obj_px_x = (xyxy[0] + xyxy[2]) / 2
        obj_px_y = (xyxy[1] + xyxy[3]) / 2
        
        # 3. Calcular o Offset em Pixels (distância do centro da imagem)
        offset_x_pix = obj_px_x - CENTER_X_PX
        offset_y_pix = obj_px_y - CENTER_Y_PX
        
        # 4. Calcular GSD (Metros por Pixel) - SEM 'K' HARDCODED
        # GSD = (Tamanho_Sensor_mm * Altitude_m) / (Distancia_Focal_mm * Tamanho_Imagem_px)
        gsd_x_m_per_px = (SENSOR_WIDTH_MM * drone_alt) / (FOCAL_LENGTH_MM * IMG_WIDTH_PX)
        gsd_y_m_per_px = (SENSOR_HEIGHT_MM * drone_alt) / (FOCAL_LENGTH_MM * IMG_HEIGHT_PX)

        # 5. Calcular Offset em Metros (NÃO ROTACIONADO - Referência do Sensor)
        # Eixo X (Direita/Esquerda do sensor)
        delta_east_unrotated = offset_x_pix * gsd_x_m_per_px
        
        # Eixo Y (Frente/Trás do sensor)
        # O eixo Y da imagem é invertido (cresce para baixo).
        # Um offset_y_pix positivo (abaixo do centro) é "Sul" no sensor.
        # Invertemos o sinal para que positivo signifique "Norte" no sensor.
        delta_north_unrotated = -offset_y_pix * gsd_y_m_per_px
        
        # 6. Aplicar Rotação de YAW
        # Converte o Yaw do drone (graus) para radianos
        yaw_rad = math.radians(drone_yaw)
        cos_yaw = math.cos(yaw_rad)
        sin_yaw = math.sin(yaw_rad)
        
        # Fórmula da Matriz de Rotação 2D
        # (Converte do quadro de referência do sensor para o quadro da Terra)
        delta_north_meters = (delta_north_unrotated * cos_yaw) - (delta_east_unrotated * sin_yaw)
        delta_east_meters = (delta_north_unrotated * sin_yaw) + (delta_east_unrotated * cos_yaw)
        
        # 7. Converter Offset em Metros para Offset em Graus (Lat/Lon)
        
        # Cálculo do offset de Latitude (simples)
        offset_lat_deg = delta_north_meters / METERS_PER_DEGREE_LATITUDE
        
        # Cálculo do offset de Longitude (depende da latitude)
        meters_per_degree_longitude = METERS_PER_DEGREE_LATITUDE * math.cos(math.radians(drone_lat))
        offset_lon_deg = delta_east_meters / meters_per_degree_longitude
        
        # 8. Calcular o GPS final do Objeto!
        object_lat = drone_lat + offset_lat_deg
        object_lon = drone_lon + offset_lon_deg

        print("\n  [DETECÇÃO ENCONTRADA]")
        print(f"    Centro do Pixel: ({obj_px_x:.2f}, {obj_px_y:.2f})")
        print(f"    GSD (m/px): (X: {gsd_x_m_per_px:.4f}, Y: {gsd_y_m_per_px:.4f})")
        print(f"    Offset Não Rotacionado (N, E): ({delta_north_unrotated:.2f} m, {delta_east_unrotated:.2f} m)")
        print(f"    Offset Rotacionado (N, E):   ({delta_north_meters:.2f} m, {delta_east_meters:.2f} m)")
        print(f"    ==> GPS do Objeto: ({object_lat:.7f}, {object_lon:.7f})\n")
        x1, y1, x2, y2 = map(int, box.xyxy[0])
    # Garante que o diretório existe
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    # Define o caminho final do arquivo de saída
    output_filename = Path(r.path).name
    output_path = OUTPUT_DIR / output_filename
    # Usa o método .save() do próprio objeto de resultado da Ultralytics
    # Ele desenha as caixas e salva no caminho especificado.
    r.save(filename=str(output_path))
print("--- Processamento Concluído --- \n Monitorando...")