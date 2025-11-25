#!/usr/bin/env python3
"""Shared utilities for socket-based latency/bandwidth orchestration."""
from __future__ import annotations

import argparse
import json
import logging
import math
import re
import socket
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

PING_REGEX = re.compile(r"(\d+\.\d+)/(\d+\.\d+)/(\d+\.\d+)/(\d+\.\d+) ms")
JSONType = Dict[str, Any]


# -----------------------------------------------------------------------------
# Generic helpers
# -----------------------------------------------------------------------------

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def json_dumps(message: JSONType) -> bytes:
    return (json.dumps(message, separators=(",", ":")) + "\n").encode("utf-8")


def parse_json_line(line: bytes) -> JSONType:
    if not line:
        raise ValueError("empty line")
    return json.loads(line.decode("utf-8"))


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return distance in meters between two lat/lon pairs."""
    r = 6371000  # meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


def run_command(command, *, timeout: float, text: bool = True, shell: bool = False) -> subprocess.CompletedProcess:
    logging.debug("Executing command: %s", command)
    return subprocess.run(
        command,
        capture_output=True,
        timeout=timeout,
        text=text,
        check=False,
        shell=shell,
        executable="/bin/bash" if shell else None,
    )


def get_base_gps(base_ip: str, port: int, timeout: float) -> Tuple[float, float]:
    decoder = json.JSONDecoder()
    start_time = time.monotonic()
    buffer = ""

    try:
        with socket.create_connection((base_ip, port), timeout=timeout) as conn:
            conn.settimeout(timeout)
            while True:
                elapsed = time.monotonic() - start_time
                remaining = timeout - elapsed
                if remaining <= 0:
                    raise TimeoutError
                conn.settimeout(remaining)
                chunk = conn.recv(4096)
                if not chunk:
                    break
                buffer += chunk.decode("utf-8", errors="ignore")

                first_brace = buffer.find("{")
                if first_brace == -1:
                    continue
                try:
                    data, _ = decoder.raw_decode(buffer[first_brace:])
                    return float(data["latitude"]), float(data["longitude"])
                except json.JSONDecodeError:
                    continue
    except TimeoutError as exc:
        raise RuntimeError("Timeout ao ler dados de GPS da Base.") from exc
    except OSError as exc:
        raise RuntimeError(f"Falha ao conectar na Base em {base_ip}:{port}.") from exc

    raise RuntimeError("Nenhum JSON válido recebido da Base.")




def run_gps_command(command: str, timeout: float) -> Tuple[float, float]:
    try:
        result = run_command(command, timeout=timeout, shell=True)
    except FileNotFoundError as exc:
        raise RuntimeError("Shell padrão não disponível para executar comando de GPS.") from exc

    if result.returncode != 0:
        raise RuntimeError(
            f"Comando de GPS falhou (code={result.returncode}): {result.stderr.strip() or result.stdout.strip()}"
        )

    output = result.stdout.strip().splitlines()
    json_line = next((line for line in reversed(output) if line.strip().startswith("{")), None)
    if not json_line:
        raise RuntimeError("Nenhum JSON encontrado na saída do comando de GPS do drone.")
    data = json.loads(json_line)
    return float(data["latitude"]), float(data["longitude"])


def start_iperf_server() -> subprocess.Popen:
    """Inicia o servidor iperf3 em background."""
    command = ["iperf3", "-s"]
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("Comando 'iperf3' não encontrado.") from exc

    time.sleep(1)  # Aguarda um momento para garantir que o servidor iniciou
    if process.poll() is not None:
        raise RuntimeError("Falha ao iniciar o servidor iperf3.")
    return process

def run_ping_test(target_ip: str, duration: int) -> float:
    try:
        result = run_command(["ping", "-w", str(duration), target_ip], timeout=duration + 5)
    except FileNotFoundError as exc:
        raise RuntimeError("Comando 'ping' não encontrado.") from exc

    if result.returncode != 0:
        raise RuntimeError(result.stdout.strip() or result.stderr.strip() or "Ping falhou")

    match = PING_REGEX.search(result.stdout)
    if not match:
        raise RuntimeError("Não foi possível extrair a média do ping.")
    return float(match.group(2))


def run_iperf_test(
    target_ip: str,
    duration: int,
    *,
    udp: bool = False,
    reverse: bool = False,
    bandwidth: Optional[str] = None,
) -> float:
    command = ["iperf3", "-c", target_ip, "-t", str(duration), "-J"]
    if udp:
        command.append("-u")
        if bandwidth:
            command.extend(["-b", bandwidth])
    if reverse:
        command.append("-R")
    try:
        result = run_command(command, timeout=duration + 10)
    except FileNotFoundError as exc:
        raise RuntimeError("Comando 'iperf3' não encontrado.") from exc

    if result.returncode != 0:
        raise RuntimeError(result.stdout.strip() or result.stderr.strip() or "iperf3 falhou")

    try:
        data = json.loads(result.stdout)
        bits_per_second = data["end"]["sum_sent"]["bits_per_second"]
    except (KeyError, json.JSONDecodeError) as exc:
        raise RuntimeError("Falha ao decodificar saída do iperf3.") from exc
    return bits_per_second / 1_000_000


# -----------------------------------------------------------------------------
# Configuration dataclasses
# -----------------------------------------------------------------------------


@dataclass
class BaseConfig:
    listen_host: str
    listen_port: int
    base_ip: str
    netcat_port: int
    netcat_timeout: float
    csv_path: Path
    sample_distance_m: float
    sample_interval_s: float
    enable_ping: bool
    enable_iperf: bool
    ping_duration: int
    iperf_duration: int
    iperf_udp: bool
    iperf_reverse: bool
    iperf_bandwidth: Optional[str]
    heartbeat_timeout: float


@dataclass
class DroneConfig:
    control_host: str
    control_port: int
    control_retry_start: float
    control_retry_max: float
    heartbeat_interval: float
    gps_command: str
    gps_timeout: float
    ping_target: str
    ping_duration: int
    iperf_target: str
    iperf_duration: int
    iperf_udp: bool
    iperf_reverse: bool
    iperf_bandwidth: Optional[str]
    enable_ping: bool
    enable_iperf: bool


# -----------------------------------------------------------------------------
# Argument helpers
# -----------------------------------------------------------------------------


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(message)s",
    )


def add_base_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--listen-host", default="0.0.0.0", help="Host de escuta do socket")
    parser.add_argument("--listen-port", type=int, default=5555, help="Porta de escuta")
    parser.add_argument("--base-ip", required=True, help="IP da Base para Netcat e referência")
    parser.add_argument("--nc-port", type=int, default=8080, help="Porta usada pelo Netcat local")
    parser.add_argument("--nc-timeout", type=float, default=5.0, help="Timeout (s) do Netcat")
    parser.add_argument(
        "--csv-path",
        default="runs/socket_bw_ping/measurements.csv",
        help="Arquivo CSV de saída",
    )
    parser.add_argument("--sample-distance-m", type=float, default=10.0, help="Mínimo em metros")
    parser.add_argument("--sample-interval-s", type=float, default=120.0, help="Intervalo máximo em segundos")
    parser.add_argument("--ping-duration", type=int, default=10, help="Duração do ping (s)")
    parser.add_argument("--iperf-duration", type=int, default=5, help="Duração do iperf3 (s)")
    parser.add_argument("--iperf-udp", action="store_true", help="Executar iperf3 em UDP")
    parser.add_argument("--iperf-reverse", action="store_true", help="Executar iperf3 no modo reverse")
    parser.add_argument("--iperf-bandwidth", help="Largura de banda alvo iperf (ex.: 10M)")
    parser.add_argument("--disable-ping", action="store_true", help="Não executar ping")
    parser.add_argument("--disable-iperf", action="store_true", help="Não executar iperf")
    parser.add_argument(
        "--heartbeat-timeout", type=float, default=30.0, help="Timeout máximo sem heartbeat"
    )


def add_drone_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--base-host", required=True, help="Host do controlador")
    parser.add_argument("--base-port", type=int, default=5555, help="Porta do controlador")
    parser.add_argument(
        "--control-retry-start", type=float, default=5.0, help="Retry inicial ao reconectar"
    )
    parser.add_argument("--control-retry-max", type=float, default=60.0, help="Retry máximo")
    parser.add_argument("--heartbeat-interval", type=float, default=10.0, help="Intervalo heartbeat")
    parser.add_argument(
        "--gps-command",
        required=True,
        help="Comando shell que retorna JSON com latitude/longitude",
    )
    parser.add_argument("--gps-timeout", type=float, default=30.0, help="Timeout do comando de GPS")
    parser.add_argument("--ping-target", required=True, help="IP destino para ping")
    parser.add_argument("--ping-duration", type=int, default=10, help="Duração do ping (s)")
    parser.add_argument("--iperf-target", required=True, help="IP destino para iperf3")
    parser.add_argument("--iperf-duration", type=int, default=5, help="Duração do iperf3 (s)")
    parser.add_argument("--iperf-udp", action="store_true", help="Rodar iperf3 em UDP")
    parser.add_argument("--iperf-reverse", action="store_true", help="Rodar iperf3 reverse")
    parser.add_argument("--iperf-bandwidth", help="Largura de banda alvo iperf (ex.: 10M)")
    parser.add_argument("--disable-ping", action="store_true", help="Desabilita ping")
    parser.add_argument("--disable-iperf", action="store_true", help="Desabilita iperf")
