// main.cpp final - Recebe o caminho completo do arquivo e os dados de GPS.
#include <iostream>
#include <string>
#include <vector>

#include "capture.h"
#include "geotag.h"
// #include "path.h" // A lógica de path agora fica no Python

int main(int argc, char** argv) {
    // Esperamos 5 argumentos: [0]nome_programa, [1]caminho_completo, [2]lat, [3]lon, [4]alt
    if (argc != 5) {
        std::cerr << "[C++ ERRO] Número incorreto de argumentos recebido do Python.\n";
        return 1;
    }

    std::string full_image_path = argv[1];
    double latitude = std::stod(argv[2]);
    double longitude = std::stod(argv[3]);
    double altitude = std::stod(argv[4]);

    //std::cout << "[C++] Programa de captura iniciado com alvo: " << full_image_path << "\n";

    // A função capture_image agora usa o caminho completo que passamos.
    // O segundo argumento não é mais necessário, mas mantemos para não quebrar a declaração do header.
    std::string captured_path = capture_image(full_image_path);

    if (captured_path.empty()) {
        std::cerr << "[C++ ERRO] Falha ao capturar a imagem.\n";
        return 1;
    }

    std::cout << "[C++] Geotagging com: Lat " << latitude << ", Lon " << longitude << ", Alt " << altitude << " m\n";
    tag_exif(captured_path, latitude, longitude, altitude);

    //std::cout << "[C++] Tarefa concluída.\n";
    return 0;
}
