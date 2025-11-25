#!/bin/bash
#
# install_from_scratch.sh
# Script de instalação atualizado para o projeto final de gatilho de câmera.
# Instala apenas as dependências necessárias para a arquitetura com Python Orquestrador.
#

# Encerra o script imediatamente se qualquer comando falhar
set -e

echo "------------------------------------------------------------------"
echo "Iniciando a instalação do ambiente para o projeto de Gatilho de Câmera"
echo "------------------------------------------------------------------"

# --- PARTE 1: DEPENDÊNCIAS DO SISTEMA (APT) ---
echo "[PASSO 1/3] Instalando dependências do sistema com APT..."

# Atualiza a lista de pacotes
sudo apt update

# Instala as ferramentas essenciais:
# git: para controle de versão
# python3-pip: para instalar pacotes Python
# python3-venv: para criar ambientes virtuais
# libimage-exiftool-perl: fornece o comando 'exiftool' para geotagging
# python3-gpiozero: biblioteca moderna para controlar os LEDs
# libcamera-apps: fornece o comando 'libcamera-still' (geralmente já instalado)
sudo apt install -y git python3-pip python3-venv libimage-exiftool-perl python3-gpiozero libcamera-apps watchdog paramiko

echo "Dependências do sistema instaladas com sucesso."
echo "------------------------------------------------------------------"


# --- PARTE 2: CONFIGURAÇÃO DO PROJETO E AMBIENTE VIRTUAL (VENV) ---
echo "[PASSO 2/3] Configurando o projeto e o ambiente virtual Python..."

# Navega para o diretório 'home' do usuário atual
cd ~

# Cria o diretório do projeto (se não existir) e entra nele
PROJECT_DIR="Iniciacao_cientifica"
mkdir -p "$PROJECT_DIR"
cd "$PROJECT_DIR"

echo "Diretório do projeto está em: $(pwd)"

# Cria o ambiente virtual
python3 -m venv venv

echo "Ambiente virtual 'venv' criado com sucesso."
echo "------------------------------------------------------------------"


# --- PARTE 3: DEPENDÊNCIAS PYTHON (PIP DENTRO DO VENV) ---
echo "[PASSO 3/3] Instalando bibliotecas Python (pymavlink) dentro do venv..."

# Ativa o venv e instala as bibliotecas necessárias
# Usamos 'source' para ativar o venv no contexto deste script
source venv/bin/activate

# Instala o pymavlink (e suas dependências como pyserial)
pip install pymavlink pyserial

# Desativa o venv ao final da instalação
deactivate

echo "Bibliotecas Python instaladas com sucesso no venv."
echo "------------------------------------------------------------------"
echo ">>> INSTALAÇÃO CONCLUÍDA! <<<"
echo
echo "Próximos passos:"
echo "1. Coloque seus scripts ('camTrigger.py', 'start.sh', etc.) dentro da pasta ~/$PROJECT_DIR/"
echo "2. Configure o serviço systemd para rodar o 'start.sh' no boot."
echo "3. Garanta que a variável PIXHAWK_PORT no seu script está correta ('/dev/ttyACM0' ou '/dev/ttyACM1')."
echo