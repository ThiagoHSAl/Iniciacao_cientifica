# socket_bw_ping: Plano de Implementação e Boas Práticas

## 1. Objetivo Geral

Consolidar os testes de latência (ping) e largura de banda (iperf3) em um único serviço contínuo. A Base atua como **controlador** e armazena os resultados; o drone (Raspberry Pi Zero) atua como **executor**, recebendo comandos via socket persistente, executando os testes somente quando necessário e retornando os dados para a Base registrar em CSV.

## 2. Metas Funcionais

1. Abrir uma sessão única entre Base e Drone usando TCP puro (biblioteca padrão `socket`).
2. Executar os testes automaticamente a cada \~10 metros (ou intervalo configurável).
3. Registrar cada amostra em CSV com timestamp, coordenadas, distância, ping médio e throughput.
4. Manter o consumo de CPU/RAM no drone o mais baixo possível.
5. Oferecer resiliência básica: reconexão, heartbeats e mensagens de erro claras.

## 3. Arquitetura em Alto Nível

```
+-------------+                                +------------------+
|   Base      |<==== TCP socket persistente ===|    Drone (Pi0)   |
| Controller  |                                |   Executor       |
+-------------+                                +------------------+
       |                                                |
       |--- get_base_gps (nc local) ------------------->|
       |<--- telemetria + testes -----------------------|
       |--- CSV logging --------------------------------|
```

### Papéis
- **Base**
  - Mantém `socketserver`/`asyncio` TCP ouvindo em porta fixa.
  - Decide quando solicitar nova amostra (por distância ou tempo).
  - Consolida registros em CSV e apresenta logs ao operador.
- **Drone**
  - Cliente TCP que reconecta automaticamente.
  - Ao receber comando `RUN_TEST`, coleta GPS local, executa ping/iperf e devolve resultado JSON.
  - Envia heartbeats periódicos e estado de saúde (ex.: temperatura, uso de CPU opcional).

## 4. Protocolo de Mensagens (JSON Lines)

Todas as mensagens são objetos JSON codificados em UTF-8 e terminados com `\n` para facilitar parsing via `readline()`.

### 4.1 Estrutura Base → Drone
| Campo          | Tipo     | Descrição                                           |
| -------------- | -------- | --------------------------------------------------- |
| `type`         | string   | `RUN_TEST`, `PING`, `STOP`, `CONFIG_UPDATE`.        |
| `request_id`   | string   | UUID v4 para correlacionar comandos/respostas.      |
| `payload`      | objeto   | Config específica (ex.: thresholds dinâmicos).      |

### 4.2 Estrutura Drone → Base
| Campo              | Tipo     | Descrição                                                  |
| ------------------ | -------- | ---------------------------------------------------------- |
| `type`             | string   | `HELLO`, `HEARTBEAT`, `RESULT`, `ERROR`.                    |
| `request_id`       | string   | Eco do comando (quando aplicável).                          |
| `timestamp_utc`    | string   | ISO 8601.                                                   |
| `drone_lat`/`lon`  | float    | Coordenadas mais recentes.                                 |
| `ping_ms`          | float?   | Média do ping; `null` se teste desativado ou falhou.       |
| `bandwidth_mbps`   | float?   | Saída do iperf3; `null` se desativado/falhou.              |
| `distance_m`       | float    | Distância calculada no drone (opcional) ou pelo servidor.  |
| `status`           | string   | `OK`, `TIMEOUT`, `NO_GPS`, etc.                             |
| `message`          | string   | Texto curto para troubleshooting.                          |

## 5. Fluxo na Base

1. **Bootstrap**
   - Carrega `.env`/args (`--listen-port`, `--base-ip`, thresholds, caminho CSV).
   - Inicia servidor TCP e aguarda conexão.
2. **Gestão de Clientes**
   - Ao receber `HELLO`, registra capacidades (suporta iperf? ping?).
   - Mantém último ponto e horário para cálculo de gatilhos.
3. **Gatilhos**
   - Distância: se `haversine(curr, last_logged) >= sample_distance_m`.
   - Tempo (fallback): `now - last_logged_time >= sample_interval_s`.
4. **Execução**
   - Envia `RUN_TEST` com `request_id` e configurações (por ex. `ping_duration`, `iperf_time`).
   - Aguarda `RESULT` com timeout; se expira, reenvia ou marca erro.
5. **Persistência**
   - Usa `csv.DictWriter` com cabeçalho fixo: `timestamp,base_lat,base_lon,drone_lat,drone_lon,dist_m,ping_ms,bw_mbps,trigger,notes`.
   - Faz `flush()` após cada `writerow` para evitar perda em caso de queda.
6. **Monitoramento**
   - Imprime logs humanos (`logging.INFO`).
   - Opcional: expõe API REST pequena (FastAPI) para visualizar dados em tempo real.

## 6. Fluxo no Drone (Raspberry Pi Zero)

1. **Processo Único**
   - Usa `asyncio` ou loop básico com `select` (menos overhead que múltiplos processos).
2. **Conexão**
   - `socket.create_connection((base_host, base_port))` com retry exponencial (5s, 10s, 30s, 60s, ...).
   - Envia `HELLO` com versão, hostname, capacidades (`{"ping": true, "iperf": true}`).
3. **Heartbeats**
   - A cada 10 s, envia `HEARTBEAT` com última leitura de GPS para Base estimar distância mesmo sem testes.
4. **Execução de Testes**
   - Ao receber `RUN_TEST`:
     1. Obtém GPS (chamando função local equivalente a `get_drone_gps`).
     2. Executa `ping -w X` se habilitado.
     3. Executa `iperf3 -c <base_ip> -J -t Y` (ou `-u`/`-b` menor para aliviar CPU).
     4. Retorna `RESULT` com métricas, `status` e logs relevantes.
   - Em caso de falha, preenche `status=ERROR` e `message` com exceção simplificada; campos numéricos viram `null`.
5. **Uso de Recursos**
   - Tudo em Python puro (sem pandas/numpy).
   - Limitar threads; se usar `asyncio.create_subprocess_exec`, aguardar término antes de rodar próxima etapa.
   - Preaquecer `iperf3` em modo servidor (`iperf3 -s`) **na Base** para evitar chamar processos pesados na Pi.

## 7. Estrutura de Código

O código agora está modularizado:

```text
src/testes_socket/
├── common.py           # Funções compartilhadas, dataclasses e helpers de CLI
├── base.py             # BaseController + CLI dedicada (somente papel Base)
├── drone.py            # DroneExecutor + CLI dedicada (somente papel Drone)
└── socket_bw_ping.py   # Wrapper fino com os subcomandos "base" e "drone"
```

# Execução direta (útil para systemd/uv run)
python src/testes_socket/base.py --base-ip 192.168.0.10 --csv out.csv
python src/testes_socket/drone.py --base-host 192.168.0.10 --ping-target 192.168.0.10 --gps-command "python3 ./gpsGetter_single.py"
```

## 8. Estratégia de Amostragem

- **Distância mínima (`sample_distance_m`)**: default 10 m. Use o `haversine` com lat/lon recebidos pelo heartbeat.
- **Intervalo máximo (`sample_interval_s`)**: garante leitura periódica mesmo parado (ex.: 120 s).
- **Cooldown pós-teste**: aguarde pelo menos 15 s antes de aceitar novo `RUN_TEST` para evitar sobrecarga.

## 9. CSV e Versionamento de Dados

- Local do arquivo: `./socket_bw_ping/<data>/measurements_<timestamp>.csv`.
- Cabeçalho recomendado:
  - `timestamp,base_lat,base_lon,drone_lat,drone_lon,dist_m,ping_ms,bw_mbps,trigger,request_id,status,message`
- Para cada sessão, criar diretório com timestamp (`2025-11-14T10-30Z`) contendo CSV + `config.json` indicando parâmetros usados.

## 10. Boas Práticas para a Raspberry Pi Zero

1. **Limitar processos externos**: evite rodar múltiplos `ssh`; prefira importar `gpsGetter_single.py` como módulo e expor `get_location()`.
2. **Uso de swap**: não habilitar swap se não necessário; monitore com `top`/`htop`.
3. **Log em memória**: utilize `logging.handlers.MemoryHandler` com flush eventual para não desgastar o SD.
4. **iperf3 otimizado**: use `-t 5`, `-b 10M` (UDP) ou `-R` (reverse) conforme necessidade para reduzir carga.
5. **Watchdog**: opcionalmente configure `systemd` para reiniciar o serviço se travar (`Restart=on-failure`).

## 11. Passo a Passo de Implementação

1. **Refatorar funções de utilidade**
   - Mover `get_base_gps`, `get_drone_gps`, `haversine`, `run_ping_test`, `run_iperf_test` para um módulo comum.
2. **Criar CLI com subcomandos Base/Drone**.
3. **Implementar protocolo TCP**
   - `asyncio.start_server` para Base; `asyncio.open_connection` para Drone.
   - Reutilizar `json.dumps` + `writer.write((msg + "\n").encode())`.
4. **Agendador na Base**
   - Task dedicada monitora heartbeats e dispara `RUN_TEST`.
5. **Executor no Drone**
   - Task para heartbeats, outra que lê comandos e processa sequencialmente.
6. **CSV Logger**
   - Inicializa no startup com `newline=''` para evitar linhas em branco.
7. **Validação**
   - Simular ambos papéis na mesma máquina (diferentes terminais) antes de levar ao hardware.
8. **Deploy**
   - Criar serviços `systemd`: `socket_bw_ping_base.service` e `socket_bw_ping_drone.service` com ambiente configurado.

## 12. Testes Recomendados

1. **Teste local**: rodar Base e Drone em localhost (usar `--base-host 127.0.0.1`). Mockar GPS retornando posições artificiais.
2. **Teste sem iperf**: executar apenas ping para validar protocolo.
3. **Teste de reconexão**: desligar Wi-Fi do drone e verificar se ele reconecta e reenvia `HELLO`.
4. **Carga controlada**: medir CPU/RAM na Pi Zero durante execução; ajustar intervalos conforme necessidade.

## 13. Troubleshooting

| Sintoma                        | Possível Causa                        | Ação sugerida                          |
| ------------------------------ | ------------------------------------- | -------------------------------------- |
| Sem resposta ao `RUN_TEST`     | Drone travado no iperf/ping           | Aplicar timeout + matar subprocess.    |
| CSV vazio mesmo com testes     | Base não recebeu `RESULT`             | Verificar parsing de `\n` e request_id |
| Reconexões frequentes          | Wi-Fi fraco                           | Bufferizar comandos perdidos, reduzir timeout |
| Pi reiniciando                 | Consumo alto de CPU/energia           | Reduzir frequência ou tempo do iperf.  |
