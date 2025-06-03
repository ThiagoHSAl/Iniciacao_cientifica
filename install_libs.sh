#!/bin/bash

echo "Iniciando a instalação das bibliotecas na Raspberry Pi..."
echo "------------------------------------------------------"

# 1. Atualizar o sistema
echo "Atualizando o sistema..."
sudo apt update && sudo apt upgrade -y
if [ $? -eq 0 ]; then
    echo "Sistema atualizado com sucesso."
else
    echo "Erro ao atualizar o sistema. Verifique sua conexão com a internet."
    exit 1
fi
echo "------------------------------------------------------"

# 2. Instalar libgphoto2
echo "Instalando libgphoto2-dev..."
sudo apt install libgphoto2-dev -y
if [ $? -eq 0 ]; then
    echo "libgphoto2-dev instalada com sucesso."
else
    echo "Erro ao instalar libgphoto2-dev."
    exit 1
fi
echo "------------------------------------------------------"

# 3. Instalar MAVSDK
echo "Iniciando a instalação do MAVSDK..."
echo "Adicionando a chave GPG do repositório MAVSDK..."
sudo apt install curl -y
curl -s https://mavsdk.github.io/MAVSDK-repo/MAVSDK-repo.gpg | sudo gpg --dearmor -o /usr/share/keyrings/MAVSDK-repo.gpg
if [ $? -ne 0 ]; then
    echo "Erro ao adicionar a chave GPG do MAVSDK. Abortando instalação do MAVSDK."
    # Não sair aqui, pois outras instalações podem ter sucesso
else
    echo "Chave GPG do MAVSDK adicionada."

    echo "Adicionando o repositório MAVSDK aos seus sources.list..."
    echo "deb [signed-by=/usr/share/keyrings/MAVSDK-repo.gpg] https://mavsdk.github.io/MAVSDK-repo/debian stable main" | sudo tee /etc/apt/sources.list.d/MAVSDK-repo.list
    if [ $? -ne 0 ]; then
        echo "Erro ao adicionar o repositório MAVSDK. Abortando instalação do MAVSDK."
    else
        echo "Repositório MAVSDK adicionado."

        echo "Atualizando a lista de pacotes e instalando MAVSDK..."
        sudo apt update
        sudo apt install mavsdk mavsdk-dev -y
        if [ $? -eq 0 ]; then
            echo "MAVSDK e MAVSDK-dev instalados com sucesso."
        else
            echo "Erro ao instalar MAVSDK e MAVSDK-dev."
        fi
    fi
fi
echo "------------------------------------------------------"

# 4. Instalar ExifTool
echo "Instalando ExifTool..."
sudo apt install libimage-exiftool-perl -y
if [ $? -eq 0 ]; then
    echo "ExifTool instalado com sucesso."
else
    echo "Erro ao instalar ExifTool."
    exit 1
fi
echo "------------------------------------------------------"

# 5. Instalar wiringPi (Opcional - Remova se não for usar no seu código)
echo "Instalando wiringPi (OPCIONAL - Considere remover do seu código se não precisar)..."
sudo apt install wiringpi -y
if [ $? -eq 0 ]; then
    echo "wiringPi instalada com sucesso."
else
    echo "Aviso: Erro ao instalar wiringPi. Se você não a usa no seu código, ignore este aviso."
fi
echo "------------------------------------------------------"

echo "Instalação das bibliotecas concluída!"
echo "Lembre-se de configurar seu CMakeLists.txt e então compilar seu projeto."
