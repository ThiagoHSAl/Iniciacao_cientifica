#include "usb.h"
#include <iostream>
#include <string>
#include <chrono>
#include <ctime>
#include <algorithm>
#include <cstdlib>      // Necessário para getenv("HOME")
#include <sys/stat.h>   // Necessário para mkdir

// Esta função agora faz todo o trabalho de forma segura.
std::string make_command() {
    // 1. Pega o diretório 'home' do usuário (ex: /home/thiago-henrique)
    const char* home_dir_c = getenv("HOME");
    if (home_dir_c == nullptr) {
        std::cerr << "[ERRO] Não foi possível encontrar o diretório HOME. Usando /tmp/.\n";
        home_dir_c = "/tmp";
    }
    std::string home_dir = home_dir_c;

    // 2. Define um caminho base para todas as imagens
    std::string base_path = home_dir + "/Iniciacao_cientifica/Imagens_Capturadas/";

    // 3. Garante que este diretório base exista
    // O mkdir com 0777 dá permissão total ao usuário para ler, escrever e executar.
    mkdir(base_path.c_str(), 0777); 

    // 4. Pede o nome da pasta para o teste
    std::cout << "Digite o nome da pasta para este teste (ex: 'voo1'): ";
    std::string run_name;
    std::cin >> run_name;

    // 5. Cria o nome final da pasta com data e hora formatada
    auto now = std::chrono::system_clock::now();
    std::time_t now_time = std::chrono::system_clock::to_time_t(now);
    char time_buf[21]; // Buffer para YYYY-MM-DD_HH-MM-SS
    strftime(time_buf, sizeof(time_buf), "%Y-%m-%d_%H-%M-%S", std::localtime(&now_time));
    
    std::string final_path = base_path + run_name + "_" + std::string(time_buf) + "/";

    // 6. Tenta criar o diretório final e VERIFICA se deu certo
    if (mkdir(final_path.c_str(), 0777) != 0) {
        perror("[ERRO] mkdir falhou"); // perror imprime a razão do erro (ex: Permission denied)
        return ""; // Retorna uma string vazia para indicar o erro ao main.cpp
    }

    return final_path;
}
