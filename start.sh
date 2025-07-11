#!/bin/bash
# Script de inicialização para o orquestrador de gatilho da câmera

# Pausa de 15 segundos para garantir que a rede e todos os 
# dispositivos USB (como a Pixhawk) estejam prontos e estáveis após o boot.
sleep 15

# Define os caminhos para evitar erros
PROJECT_DIR="/home/thiago-henrique/Iniciacao_cientifica"
VENV_ACTIVATE="/home/thiago-henrique/Iniciacao_cientifica/venv/bin/activate"
MAIN_SCRIPT="${PROJECT_DIR}/camTrigger.py" # Use o nome correto do seu script final!

echo "Iniciando o servico de gatilho..."

# Ativa o ambiente virtual
source "${VENV_ACTIVATE}"

# Executa o script Python final
python3 "${MAIN_SCRIPT}"
