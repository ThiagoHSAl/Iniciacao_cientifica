from ultralytics import YOLO

# Carrega o modelo
model = YOLO("/ultralytics/yolo12s.pt")  # Carrega um modelo pré-treinado 
results = model.train(
    data="/usr/src/ultralytics/dados/data.yaml",
    epochs=200,
    hsv_v=0.4,
    erasing=0.4, # bom para pequenos objetos
    mosaic=0.5,
    fliplr=0.4, # inverte direção horizontal
    hsv_s=0.4, # saturação
    hsv_h=0.4, # matiz
    translate=0.2,
    scale=0.4,
    mixup=True, # mistura imagens + recall mais alto
    multi_scale=True,
    rect=False,
    imgsz=1024,
    batch=4, # batch size real por iteração
    lr0=0.0005, # taxa de aprendizado inicial
    lrf=0.02, # taxa de aprendizado final (multiplicador)    
    copy_paste=0.4,
    project="/home/yolo12s",
    name="yolo12s_better_augmentation",
    device=0, 
    workers=8,
    cache="ram",
    amp=True,
    patience=100,
    verbose=True
)

# Exporta o modelo treinado
path = model.export(format="onnx")
print(f"Modelo exportado para: {path}")

