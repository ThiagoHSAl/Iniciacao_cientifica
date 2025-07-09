#!/bin/bash

# Adiciona a pausa de 10 segundos
sleep 10

# PRIMEIRO, ativa o venv usando o caminho absoluto correto
source /home/thiago-henrique/Iniciacao_cientifica/venv/bin/activate

# AGORA, navega para o diretório de trabalho do projeto
cd /home/thiago-henrique/Iniciacao_cientifica/PixTrigger/

# Executa o script python (o venv já está ativo)
# Certifique-se de que o nome do script (listener.py ou orquestrador.py) está correto
python3 build/listener.py
