import matplotlib.pyplot as plt
import pandas as pd
import io

# Dados do usuário (fornecidos no prompt anterior)
bandwidth_data = """
Distância Base-Drone: 42.23 metros
Largura de Banda (UL): 12.68 Mbits/sec

Distância Base-Drone: 68.15 metros
Largura de Banda (UL): 10.16 Mbits/sec

Distância Base-Drone: 114.33 metros
Largura de Banda (UL): 5.45 Mbits/sec

Distância Base-Drone: 172.36 metros
Largura de Banda (UL): 6.70 Mbits/sec

Distância Base-Drone: 221.17 metros
Largura de Banda (UL): 3.45 Mbits/sec

Distância Base-Drone: 272.02 metros
Largura de Banda (UL): 0.94 Mbits/sec

Distância Base-Drone: 341.67 metros
Largura de Banda (UL): 0.63 Mbits/sec

Distância Base-Drone: 429.21 metros
Largura de Banda (UL): 0.63 Mbits/sec

Distância Base-Drone: 633.46 metros
Largura de Banda (UL): 0.10 Mbits/sec

Distância Base-Drone: 742.91 metros
Largura de Banda (UL): 0.31 Mbits/sec
"""

ping_data = """
Distância Base-Drone: 47.57 metros
Latência Média (Ping): 118.678 ms

Distância Base-Drone: 115.21 metros
Latência Média (Ping): 63.695 ms

Distância Base-Drone: 169.36 metros
Latência Média (Ping): 85.732 ms

Distância Base-Drone: 219.61 metros
Latência Média (Ping): 66.951 ms

Distância Base-Drone: 273.06 metros
Latência Média (Ping): 58.915 ms

Distância Base-Drone: 347.09 metros
Latência Média (Ping): 106.106 ms

Distância Base-Drone: 395.21 metros
Latência Média (Ping): 77.861 ms

Distância Base-Drone: 428.55 metros
Latência Média (Ping): 102.641 ms

Distância Base-Drone: 623.95 metros
Latência Média (Ping): 126.053 ms

Distância Base-Drone: 743.72 metros
Latência Média (Ping): 95.429 ms
"""

def parse_data(data_string, value_type):
    distances = []
    values = []
    lines = data_string.strip().split('\n')
    for i in range(0, len(lines), 3):
        try:
            dist_line = lines[i].strip()
            val_line = lines[i+1].strip()
            
            dist = float(dist_line.split(':')[1].strip().split(' ')[0])
            
            if value_type == 'bandwidth':
                val = float(val_line.split(':')[1].strip().split(' ')[0])
            elif value_type == 'ping':
                val = float(val_line.split(':')[1].strip().split(' ')[0])
            
            distances.append(dist)
            values.append(val)
        except (IndexError, ValueError) as e:
            print(f"Erro ao processar linhas: {lines[i]} e {lines[i+1]}. Erro: {e}")
            continue
            
    return pd.DataFrame({'distance': distances, 'value': values})

# Processa os dados
df_bw = parse_data(bandwidth_data, 'bandwidth')
df_ping = parse_data(ping_data, 'ping')

# Ordena os DataFrames pela distância
df_bw = df_bw.sort_values('distance')
df_ping = df_ping.sort_values('distance')

# Configurações de Fonte
font_size_title = 16
font_size_labels = 14
font_size_ticks = 12
font_size_legend = 12

# Criação do gráfico
fig, ax1 = plt.subplots(figsize=(12, 7))

# Eixo Y1: Largura de Banda (Azul)
color_bw = 'tab:blue'
ax1.set_xlabel('Distance (meters)', fontsize=font_size_labels)
ax1.set_ylabel('Bandwidth (Mbps)', color=color_bw, fontsize=font_size_labels)
line1 = ax1.plot(df_bw['distance'], df_bw['value'], marker='o', color=color_bw, linewidth=2, label='Bandwidth (Mbps)')
ax1.tick_params(axis='y', labelcolor=color_bw, labelsize=font_size_ticks)
ax1.tick_params(axis='x', labelsize=font_size_ticks)
ax1.grid(True, linestyle='--', alpha=0.7)
ax1.set_ylim(bottom=0)

# Eixo Y2: Latência (Vermelho) - Compartilha o eixo X
ax2 = ax1.twinx()
color_ping = 'tab:red'
ax2.set_ylabel('Average Latency (ms)', color=color_ping, fontsize=font_size_labels)
line2 = ax2.plot(df_ping['distance'], df_ping['value'], marker='s', color=color_ping, linewidth=2, linestyle='--', label='Latency (ms)')
ax2.tick_params(axis='y', labelcolor=color_ping, labelsize=font_size_ticks)
ax2.set_ylim(bottom=0)

# Legenda Combinada
lines = line1 + line2
labels = [l.get_label() for l in lines]
ax1.legend(lines, labels, loc='center right', fontsize=font_size_legend)

# Ajuste de layout e salvamento
plt.tight_layout()
output_filename = 'hallow_performance.png'
plt.savefig(output_filename, dpi=300)
print(f"Gráfico salvo com sucesso como '{output_filename}'")
# plt.show() # Descomente para mostrar a janela interativa