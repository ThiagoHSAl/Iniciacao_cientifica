/*
 * capture.cpp - Versão Corrigida e Robusta
 *
 * ERRO CORRIGIDO: O código original usava a biblioteca libgphoto2, que não é
 * compatível com a câmera nativa do Raspberry Pi (Raspicam).
 *
 * SOLUÇÃO: Esta versão utiliza a ferramenta de linha de comando oficial
 * `libcamera-still`, que é o método correto e mais confiável para
 * capturar imagens no Raspberry Pi. A função agora recebe o caminho completo
 * do arquivo a ser salvo, tornando-a mais modular.
 */

#include <string>
#include <cstdlib> // Para a função system()
#include <iostream>

// Inclua o seu header correspondente, se necessário
#include "capture.h"

// A função agora recebe o caminho completo do arquivo onde a imagem deve ser salva.
std::string capture_image(const std::string& full_image_path) {

    // Constrói o comando para a ferramenta libcamera-still
    // -o: define o arquivo de saída (output)
    // -t 500: timeout de 500ms para o sensor focar e ajustar a exposição
    // --width 1920 --height 1080: define a resolução (ajuste se necessário)
    // -n: --nopreview, não exibe uma janela de pré-visualização gráfica
    std::string command = "libcamera-still -n -t 500 --width 1920 --height 1080 -o " + full_image_path + " > /dev/null 2>&1";

    //std::cout << "[C++] Executando comando de captura: " << command << std::endl;

    // Executa o comando no terminal do sistema
    int result = system(command.c_str());

    // A função system() retorna 0 em caso de sucesso
    if (result == 0) {
        // Se a captura foi bem-sucedida, retorna o caminho do arquivo criado
        return full_image_path;
    } else {
        // Se houve um erro, informa no console e retorna uma string vazia
        std::cerr << "[C++ ERRO] Falha ao executar o comando libcamera-still. Código de retorno: " << result << std::endl;
        return "";
    }
}
