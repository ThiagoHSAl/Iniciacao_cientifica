# socket_bw_ping – Guia de Execução e Parâmetros

Este guia resume todos os parâmetros disponíveis para os papéis **Base** e **Drone**
e explica as diferentes formas de rodar o sistema (wrapper com subcomandos,
arquivos dedicados e execução via `uv`).

## Visão geral dos arquivos

| Caminho | Papel | Descrição |
| --- | --- | --- |
| `src/testes_socket/common.py` | Compartilhado | Funções utilitárias (GPS, ping, iperf), dataclasses e helpers de CLI. |
| `src/testes_socket/base.py` | Base | Controlador que agenda testes, grava CSV e calcula distâncias. |
| `src/testes_socket/drone.py` | Drone | Executor rodando no Raspberry Pi Zero (ou similar) que responde aos comandos. |
| `src/testes_socket/socket_bw_ping.py` | Wrapper | CLI com subcomandos `base`/`drone` para manter compatibilidade com o fluxo antigo. |

Use o wrapper quando quiser uma experiência única com subcomandos. Use `base.py`
ou `drone.py` diretamente quando for criar serviços separados (`uv run`, `systemd`, etc.).

## Dependências gerais

- Python 3.10+ (testado com `uv` gerenciando o ambiente virtual).
- A Base precisa ter `nc` (netcat), `ping` e `iperf3` instalados.
- O Drone precisa do script de GPS acessível por um comando shell (`--gps-command`),
além de `ping` e `iperf3` para executar os testes quando solicitado.

---

## Parâmetros do papel Base

Comando principal (via wrapper):

```bash
python src/testes_socket/socket_bw_ping.py base [opções]
```

Ou execução direta:

```bash
python src/testes_socket/base.py [opções]
```

| Parâmetro | Default | Descrição |
| --- | --- | --- |
| `--listen-host` | `0.0.0.0` | IP onde o servidor TCP da Base vai escutar. |
| `--listen-port` | `5555` | Porta TCP para comunicação com o Drone. |
| `--base-ip` | **obrigatório** | IP usado pelo Netcat para obter o GPS local. Normalmente o IP da Base. |
| `--nc-port` | `8080` | Porta onde o serviço de GPS da Base responde via netcat. |
| `--nc-timeout` | `5.0` | Timeout (s) para a chamada `nc`. |
| `--csv-path` | `runs/socket_bw_ping/measurements.csv` | Caminho do arquivo CSV onde os resultados serão salvos. O diretório é criado automaticamente. |
| `--sample-distance-m` | `10.0` | Distância mínima (metros) para acionar um novo teste com base em deslocamento. |
| `--sample-interval-s` | `120.0` | Intervalo máximo (segundos) para garantir testes mesmo parado. |
| `--ping-duration` | `10` | Duração do ping (segundos) solicitada ao Drone. |
| `--iperf-duration` | `5` | Duração do iperf3 (segundos) solicitada ao Drone. |
| `--iperf-udp` | desativado | Se setado, solicita iperf3 em UDP. |
| `--iperf-reverse` | desativado | Solicita iperf3 no modo reverse. |
| `--iperf-bandwidth` | vazio | Valor passado a `iperf3 -b` (ex.: `10M`). Útil com UDP. |
| `--disable-ping` | desativado | Se presente, nunca solicitar ping nos testes. |
| `--disable-iperf` | desativado | Se presente, nunca solicitar iperf3 nos testes. |
| `--heartbeat-timeout` | `30.0` | Tempo máximo sem heartbeat antes de descartar um pedido pendente. |
| `--log-level` | `INFO` | Nível de log padrão (`DEBUG`, `INFO`, `WARNING`, etc.). |

### Exemplo (Base)

```bash
python src/testes_socket/base.py \
  --base-ip 192.168.0.10 \
  --listen-port 6000 \
  --csv-path runs/socket_bw_ping/session_$(date +%s).csv \
  --sample-distance-m 8 --sample-interval-s 90 \
  --iperf-udp --iperf-bandwidth 10M
```

---

## Parâmetros do papel Drone

Via wrapper:

```bash
python src/testes_socket/socket_bw_ping.py drone [opções]
```

Execução direta (recomendada na Raspberry Pi Zero):

```bash
python src/testes_socket/drone.py [opções]
```

| Parâmetro | Default | Descrição |
| --- | --- | --- |
| `--base-host` | **obrigatório** | IP/hostname do controlador. |
| `--base-port` | `5555` | Porta usada pela Base. Deve coincidir com `--listen-port`. |
| `--control-retry-start` | `5.0` | Tempo inicial de retry ao reconectar (segundos). |
| `--control-retry-max` | `60.0` | Tempo máximo entre tentativas após backoff exponencial. |
| `--heartbeat-interval` | `10.0` | Frequência (s) dos heartbeats enviados ao controlador. |
| `--gps-command` | **obrigatório** | Comando shell que imprime JSON com `latitude` e `longitude`. Ex.: `python3 ./gpsGetter_single.py`. |
| `--gps-timeout` | `30.0` | Timeout do comando de GPS. |
| `--ping-target` | **obrigatório** | IP usado nas medições de ping (normalmente o IP da Base). |
| `--ping-duration` | `10` | Duração do ping. Pode ser sobrescrito pela Base a cada `RUN_TEST`. |
| `--iperf-target` | **obrigatório** | IP usado no iperf3 (servidor rodando na Base). |
| `--iperf-duration` | `5` | Duração do iperf3. Também pode ser sobrescrito pela Base. |
| `--iperf-udp` | desativado | Se presente, roda iperf3 em UDP. |
| `--iperf-reverse` | desativado | Roda iperf3 no modo reverse. |
| `--iperf-bandwidth` | vazio | Define `-b` ao usar UDP. |
| `--disable-ping` | desativado | Não executa ping mesmo se solicitado. |
| `--disable-iperf` | desativado | Não executa iperf3 mesmo se solicitado. |
| `--log-level` | `INFO` | Nível de log do executor. |

### Exemplo (Drone)

```bash
python src/testes_socket/drone.py \
  --base-host 192.168.0.10 --base-port 6000 \
  --ping-target 192.168.0.10 --iperf-target 192.168.0.10 \
  --gps-command "python3 ~/Iniciacao_cientifica/gpsGetter_single.py" \
  --gps-timeout 45 --heartbeat-interval 8 \
  --disable-iperf
```

---

## Wrapper `socket_bw_ping.py`

Se você preferir manter o paradigma antigo (um único arquivo com subcomandos), use:

```bash
python src/testes_socket/socket_bw_ping.py base [parâmetros-do-base]
python src/testes_socket/socket_bw_ping.py drone [parâmetros-do-drone]
```

O wrapper simplesmente chama `base.py` ou `drone.py` por baixo, então as opções são idênticas.

---

## Dicas de execução com `uv`

Supondo que você já criou e ativou um ambiente com `uv`:

```bash
uv python src/testes_socket/base.py --base-ip 192.168.0.10 --csv-path runs/socket_bw_ping/out.csv
uv python src/testes_socket/drone.py --base-host 192.168.0.10 --ping-target 192.168.0.10 --gps-command "python3 ./gpsGetter_single.py"
```

Se preferir subcomandos:

```bash
uv python src/testes_socket/socket_bw_ping.py base --base-ip 192.168.0.10 --csv-path runs/socket_bw_ping/out.csv
uv python src/testes_socket/socket_bw_ping.py drone --base-host 192.168.0.10 --ping-target 192.168.0.10 --gps-command "python3 ./gpsGetter_single.py"
```

### Execução como serviço (`systemd` ou tmux)

- Base: rodar em um host com energia/CPU sobrando (ex.: laptop ou estação base). Configure `Restart=on-failure`.
- Drone: rodar no Raspberry Pi Zero. Use `--disable-iperf` caso não queira sobrecarregar o dispositivo.
- Garanta que o serviço de GPS da Base (servidor `nc`) esteja em execução antes de ligar o controlador para evitar timeouts.

---

## Estrutura de saída

- CSV padrão: `runs/socket_bw_ping/measurements.csv` (pode apontar para `runs/socket_bw_ping/<data>/` para sessões diferentes).
- Cada linha contém: `timestamp, base_lat, base_lon, drone_lat, drone_lon, dist_m, ping_ms, bw_mbps, trigger, request_id, status, message`.

---

## Checklist rápido

1. **Base**: confirme serviço de GPS (netcat) ativo e `iperf3 -s` rodando.
2. **Drone**: garanta que `gpsGetter_single.py` funciona standalone (`python3 gpsGetter_single.py`).
3. Rode Base e Drone (ordem não importa, mas a Base deve estar ouvindo quando o Drone conectar).
4. Verifique os logs: `HELLO`, `HEARTBEAT`, `RUN_TEST`, `RESULT`.
5. Analise o CSV gerado.

Com este guia, você tem todos os parâmetros documentados e consegue rodar cada papel da maneira mais simples para o seu fluxo (wrapper, módulos dedicados ou `uv`).
