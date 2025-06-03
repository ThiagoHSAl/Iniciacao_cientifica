/*
This code creates a folder on the USB device, capture one image and geotags it.
It now triggers the camera based on MAVLink commands received from the Pixhawk,
instead of GPIO interrupts.
*/
#include "capture.h"
#include "geotag.h"
#include "path.h"
#include "usb.h"
#include <iostream>
#include <chrono>
#include <cstdint>
#include <mavsdk/mavsdk.h>
#include <mavsdk/plugins/action/action.h>
#include <mavsdk/plugins/telemetry/telemetry.h>
#include <mavsdk/plugins/camera/camera.h> // NOVO: Inclui o plugin Camera
#include <iostream>
#include <thread>
// #include <wiringPi.h> // REMOVIDO: Não usaremos mais wiringPi para o trigger

using namespace mavsdk;
using namespace std::this_thread;
using namespace std::chrono;
using namespace std;

std::string path;
int i = 0;
// REMOVIDO: Definições de BUTTON_PIN_X não são mais necessárias para trigger GPIO

#define ERROR_CONSOLE_TEXT "\033[31m" // Turn text on console red
#define TELEMETRY_CONSOLE_TEXT "\033[34m" // Turn text on console blue
#define NORMAL_CONSOLE_TEXT "\033[0m" // Restore normal console colour

Telemetry::Position pose;

// REMOVIDO: myInterrupt() não é mais usada como callback de GPIO
// A lógica de disparo da câmera será movida para um callback MAVSDK.

void usage(std::string bin_name)
{
    std::cout << NORMAL_CONSOLE_TEXT << "Usage : " << bin_name << " <connection_url>" << std::endl
              << "Connection URL format should be :" << std::endl
              << " For TCP : tcp://[server_host][:server_port]" << std::endl
              << " For UDP : udp://[bind_host][:bind_port]" << std::endl
              << " For Serial : serial:///path/to/serial/dev[:baudrate]" << std::endl
              << "For example, to connect to the simulator use URL: udp://:14540" << std::endl;
}

void component_discovered(ComponentType component_type)
{
    std::cout << NORMAL_CONSOLE_TEXT << "Discovered a component with type "
              << unsigned(component_type) << std::endl;
}

int main(int argc, char** argv){
	
    Mavsdk mavsdk;
    Mavsdk::Configuration configuration(Mavsdk::Configuration::UsageType::CompanionComputer);
    mavsdk.set_configuration(configuration);
    std::string connection_url;
    ConnectionResult connection_result;

    bool discovered_system = false;
    if (argc == 2) {
        connection_url = argv[1];
        connection_result = mavsdk.add_any_connection(connection_url);
    } else {
        usage(argv[0]);
        return 1;
    }

    if (connection_result != ConnectionResult::Success) {
        std::cout << ERROR_CONSOLE_TEXT << "Connection failed: " << connection_result
                  << NORMAL_CONSOLE_TEXT << std::endl;
        return 1;
    }

    std::cout << "Waiting to discover system..." << std::endl;
    mavsdk.subscribe_on_new_system([&mavsdk, &discovered_system]() {
        const auto system = mavsdk.systems().at(0);

        if (system->is_connected()) {
            std::cout << "Discovered system" << std::endl;
            discovered_system = true;
        }
    });

    // We usually receive heartbeats at 1Hz, therefore we should find a system after around 2
    // seconds.
    sleep_for(seconds(2));

    if (!discovered_system) {
        std::cout << ERROR_CONSOLE_TEXT << "No system found, exiting." << NORMAL_CONSOLE_TEXT
                  << std::endl;
        return 1;
    }

    const auto system1 = mavsdk.systems().at(0);

    // Register a callback so we get told when components (camera, gimbal) etc
    // are found.
    system1->register_component_discovered_callback(component_discovered);

    auto telemetry = std::make_shared<Telemetry>(system1);

    // We want to listen to the altitude of the drone at 1 Hz.
    const Telemetry::Result set_rate_result = telemetry->set_rate_position(1.0);
    if (set_rate_result != Telemetry::Result::Success) {
        std::cout << ERROR_CONSOLE_TEXT << "Setting rate failed:" << set_rate_result
                  << NORMAL_CONSOLE_TEXT << std::endl;
        return 1;
    }
    telemetry->subscribe_position([&pose](Telemetry::Position position) {
        pose = position;
    });

    sleep_for(seconds(1));

    std::cout << TELEMETRY_CONSOLE_TEXT 
              << "Latitude: " << pose.latitude_deg 
              << " Longitude: " << pose.longitude_deg
              << " Altitude: " << pose.relative_altitude_m << " m"
              << NORMAL_CONSOLE_TEXT
              << std::endl;
    
    path = make_command(); // Cria o diretório para salvar as imagens no USB

    // NOVO: Setup do plugin Camera e assinatura para eventos de captura
    auto camera = std::make_shared<Camera>(system1);

    // Assina informações de captura da câmera.
    // Este callback será acionado quando a Pixhawk enviar um comando de captura
    // via MAVLink que o MAVSDK reconheça como um evento de captura.
    camera->subscribe_capture_info([&](Camera::CaptureInfo capture_info) {
        std::cout << NORMAL_CONSOLE_TEXT << "MAVLink Camera Command Received! Triggering camera..." << '\n';
        std::string image_path;
        // Captura a imagem usando o caminho global e o contador
        image_path = capture_image(path, std::to_string(i));
        std::cout << "Captured image: " << image_path << '\n';
        
        // Usa a última posição recebida via telemetria para geotagging
        std::cout << TELEMETRY_CONSOLE_TEXT
                  << "Geotagging with: Lat " << pose.latitude_deg
                  << ", Lon " << pose.longitude_deg
                  << ", Alt " << pose.relative_altitude_m << " m"
                  << NORMAL_CONSOLE_TEXT
                  << std::endl;
        tag_exif(image_path, pose.latitude_deg, pose.longitude_deg, pose.relative_altitude_m);
        i++;
    });

    std::cout << NORMAL_CONSOLE_TEXT << "Listening for MAVLink camera commands (via USB/Serial connection)..." << std::endl;

    // Loop infinito para manter o programa rodando e recebendo mensagens MAVLink
    while(true){
        sleep_for(seconds(1)); // Pequena pausa para evitar CPU em 100%
    }
	
    // As linhas comentadas abaixo são a lógica antiga que foi substituída
	//~ std::string path; // Path of the folder where the image will be saved
	//~ std::string image_path; //Path of the image. This is fed to the geotagging function
	//~ path = make_command();
	//~ cout << path << "\n";
	//~ image_path = capture_image(path, "foo"); //foo here is the image name. Replace it with suitable name
	//~ tag_exif(image_path, pose.latitude_deg, pose.longitude_deg, pose.relative_altitude_m);
    
    return 0; // Esta linha não será alcançada em um loop infinito, mas é boa prática
}