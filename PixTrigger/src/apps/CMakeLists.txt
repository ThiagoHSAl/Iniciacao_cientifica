# CMakeLists.txt - Versão Simplificada e Corrigida
# Remove dependências desnecessárias (MAVSDK, GPhoto2) e foca apenas
# nas tarefas do aplicativo "trabalhador": capturar e geotagear.

cmake_minimum_required(VERSION 3.16)
project(pixtrigger LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# --- Arquivos Fonte Essenciais ---
# Lista apenas os arquivos que estamos realmente usando na nova arquitetura.
set(PROJECT_SOURCES
    main.cpp
    ../modules/capture/capture.cpp
    ../modules/geotag/geotag.cpp
)

# Cria o executável com os fontes especificados.
add_executable(pixtrigger ${PROJECT_SOURCES})


# --- Diretórios de Inclusão (Headers) ---
# Adiciona os diretórios onde os arquivos .h estão localizados.
target_include_directories(pixtrigger
    PUBLIC
        ../include # Supondo que seus headers principais estão aqui
        # Adicione outros diretórios de include se necessário
)


# --- Dependências Externas ---
# A única dependência externa que nosso C++ precisa agora é a libexif para o geotag.
find_package(PkgConfig REQUIRED)
pkg_search_module(EXIF REQUIRED libexif)
message(STATUS "LibEXIF encontrada via pkg-config")


# --- Linkagem Final ---
# Linka o executável 'pixtrigger' apenas com a biblioteca libexif.
target_link_libraries(pixtrigger
    PRIVATE
        ${EXIF_LIBRARIES}
)


message(STATUS "Configuração do projeto simplificado 'pixtrigger' concluída.")
