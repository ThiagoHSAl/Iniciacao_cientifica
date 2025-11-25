#!/usr/bin/env python3
"""Base controller role for socket_bw_ping."""
from __future__ import annotations

import argparse
import asyncio
import csv
import logging
import time
import uuid
from pathlib import Path
from typing import Optional, Tuple

from common import (
	BaseConfig,
	JSONType,
	add_base_arguments,
	configure_logging,
	get_base_gps,
	start_iperf_server,
	haversine,
	json_dumps,
	parse_json_line,
	utc_now,
)


class BaseController:
	"""Coordinates measurements and stores results on the Base station."""

	def __init__(self, config: BaseConfig) -> None:
		self.config = config
		self.server: Optional[asyncio.AbstractServer] = None
		self.reader: Optional[asyncio.StreamReader] = None
		self.writer: Optional[asyncio.StreamWriter] = None
		self.scheduler_task: Optional[asyncio.Task] = None
		self.pending_request: Optional[str] = None
		self.pending_reason: Optional[str] = None
		self.last_measurement_point: Optional[Tuple[float, float]] = None
		self.last_measurement_time: float = 0.0
		self.last_heartbeat_point: Optional[Tuple[float, float]] = None
		self.last_heartbeat_time: float = 0.0
		self.csv_file = None
		self.csv_writer: Optional[csv.DictWriter] = None
		self.base_point: Optional[Tuple[float, float]] = None

	async def start(self) -> None:
		logging.info(
			"Iniciando Base Controller em %s:%s", self.config.listen_host, self.config.listen_port
		)
		self._prepare_csv()

		if self.config.enable_iperf:
			start_iperf_server()

		try:
			self.base_point = get_base_gps(
				self.config.base_ip, self.config.netcat_port, self.config.netcat_timeout
			)
			logging.info("Base GPS inicial: Lat=%.6f Lon=%.6f", *self.base_point)
		except Exception as exc:
			logging.warning("Falha ao obter GPS inicial da base: %s", exc)

		self.server = await asyncio.start_server(
			self._handle_client, self.config.listen_host, self.config.listen_port
		)
		self.scheduler_task = asyncio.create_task(self._scheduler_loop())
		async with self.server:
			await self.server.serve_forever()

	def _prepare_csv(self) -> None:
		self.config.csv_path.parent.mkdir(parents=True, exist_ok=True)
		file_exists = self.config.csv_path.exists()
		self.csv_file = self.config.csv_path.open("a", newline="")
		fieldnames = [
			"timestamp",
			"base_lat",
			"base_lon",
			"drone_lat",
			"drone_lon",
			"dist_m",
			"ping_ms",
			"bw_mbps",
			"trigger",
			"request_id",
			"status",
			"message",
		]
		self.csv_writer = csv.DictWriter(self.csv_file, fieldnames=fieldnames)
		if not file_exists:
			self.csv_writer.writeheader()
			self.csv_file.flush()

	async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
		peer = writer.get_extra_info("peername")
		logging.info("Drone conectado: %s", peer)
		if self.writer:
			logging.warning("Já existe um drone conectado. Substituindo conexão anterior.")
		self.reader, self.writer = reader, writer
		try:
			while not reader.at_eof():
				line = await reader.readline()
				if not line:
					break
				try:
					message = parse_json_line(line)
				except ValueError as exc:
					logging.error("Falha ao decodificar mensagem: %s", exc)
					continue
				await self._process_message(message)
		except asyncio.CancelledError:
			raise
		except Exception as exc:
			logging.error("Conexão com drone encerrada por erro: %s", exc)
		finally:
			logging.info("Drone desconectado")
			if writer:
				writer.close()
				await writer.wait_closed()
			self.reader = self.writer = None
			self.pending_request = None

	async def _process_message(self, message: JSONType) -> None:
		msg_type = message.get("type")
		if msg_type == "HELLO":
			logging.info("Handshake recebido: %s", message)
		elif msg_type == "HEARTBEAT":
			lat = message.get("drone_lat")
			lon = message.get("drone_lon")
			if lat is not None and lon is not None:
				self.last_heartbeat_point = (float(lat), float(lon))
				self.last_heartbeat_time = time.monotonic()
		elif msg_type == "RESULT":
			await self._handle_result(message)
		elif msg_type == "ERROR":
			logging.error("Drone reportou erro: %s", message.get("message"))
			if message.get("request_id") == self.pending_request:
				self.pending_request = None
		elif msg_type == "PONG":
			self.last_heartbeat_time = time.monotonic()
		else:
			logging.debug("Mensagem desconhecida: %s", message)

	async def _handle_result(self, message: JSONType) -> None:
		request_id = message.get("request_id")
		if self.pending_request and request_id != self.pending_request:
			logging.warning("Resultado fora de ordem: %s", request_id)
		status = message.get("status", "OK")
		drone_lat = message.get("drone_lat")
		drone_lon = message.get("drone_lon")
		ping_ms = message.get("ping_ms")
		bw_mbps = message.get("bandwidth_mbps")
		msg_text = message.get("message")
		trigger = self.pending_reason or message.get("trigger", "manual")

		if drone_lat is not None and drone_lon is not None:
			self.last_measurement_point = (float(drone_lat), float(drone_lon))
			self.last_measurement_time = time.monotonic()

		try:
			base_lat, base_lon = get_base_gps(
				self.config.base_ip, self.config.netcat_port, self.config.netcat_timeout
			)
			self.base_point = (base_lat, base_lon)
		except Exception as exc:
			logging.warning("Falha ao atualizar GPS da base: %s", exc)
			if self.base_point:
				base_lat, base_lon = self.base_point
			else:
				base_lat = base_lon = float("nan")
		dist_m = float("nan")
		if self.base_point and drone_lat is not None and drone_lon is not None:
			dist_m = haversine(base_lat, base_lon, float(drone_lat), float(drone_lon))

		if self.csv_writer:
			self.csv_writer.writerow(
				{
					"timestamp": message.get("timestamp_utc", utc_now()),
					"base_lat": base_lat,
					"base_lon": base_lon,
					"drone_lat": drone_lat,
					"drone_lon": drone_lon,
					"dist_m": dist_m,
					"ping_ms": ping_ms,
					"bw_mbps": bw_mbps,
					"trigger": trigger,
					"request_id": request_id,
					"status": status,
					"message": msg_text,
				}
			)
			if self.csv_file:
				self.csv_file.flush()

		logging.info(
			"Resultado registrado | dist=%.2fm ping=%s ms bw=%s Mbps status=%s",
			dist_m,
			ping_ms if ping_ms is not None else "-",
			bw_mbps if bw_mbps is not None else "-",
			status,
		)
		self.pending_request = None
		self.pending_reason = None

	async def _scheduler_loop(self) -> None:
		while True:
			await asyncio.sleep(1)
			if not self.writer:
				continue
			if self.pending_request:
				if self.last_heartbeat_time and (
					time.monotonic() - self.last_heartbeat_time > self.config.heartbeat_timeout
				):
					logging.warning("Sem heartbeat recente; cancelando requisição pendente.")
					self.pending_request = None
				continue
			reason = self._should_trigger()
			if reason:
				await self._send_run_test(reason)

	def _should_trigger(self) -> Optional[str]:
		now = time.monotonic()
		if self.last_measurement_time == 0:
			return "initial"
		if (
			self.config.sample_interval_s > 0
			and now - self.last_measurement_time >= self.config.sample_interval_s
		):
			return "interval"
		if (
			self.config.sample_distance_m > 0
			and self.last_measurement_point
			and self.last_heartbeat_point
		):
			dist = haversine(
				self.last_measurement_point[0],
				self.last_measurement_point[1],
				self.last_heartbeat_point[0],
				self.last_heartbeat_point[1],
			)
			if dist >= self.config.sample_distance_m:
				return "distance"
		return None

	async def _send_run_test(self, reason: str) -> None:
		if not self.writer:
			return
		request_id = str(uuid.uuid4())
		message = {
			"type": "RUN_TEST",
			"request_id": request_id,
			"timestamp_utc": utc_now(),
			"payload": {
				"enable_ping": self.config.enable_ping,
				"enable_iperf": self.config.enable_iperf,
				"ping_duration": self.config.ping_duration,
				"iperf_duration": self.config.iperf_duration,
				"iperf_udp": self.config.iperf_udp,
				"iperf_reverse": self.config.iperf_reverse,
				"iperf_bandwidth": self.config.iperf_bandwidth,
			},
		}
		logging.info("Solicitando RUN_TEST (motivo=%s)", reason)
		self.writer.write(json_dumps(message))
		await self.writer.drain()
		self.pending_request = request_id
		self.pending_reason = reason


def config_from_args(args: argparse.Namespace) -> BaseConfig:
	return BaseConfig(
		listen_host=args.listen_host,
		listen_port=args.listen_port,
		base_ip=args.base_ip,
		netcat_port=args.nc_port,
		netcat_timeout=args.nc_timeout,
		csv_path=Path(args.csv_path),
		sample_distance_m=args.sample_distance_m,
		sample_interval_s=args.sample_interval_s,
		enable_ping=not args.disable_ping,
		enable_iperf=not args.disable_iperf,
		ping_duration=args.ping_duration,
		iperf_duration=args.iperf_duration,
		iperf_udp=args.iperf_udp,
		iperf_reverse=args.iperf_reverse,
		iperf_bandwidth=args.iperf_bandwidth,
		heartbeat_timeout=args.heartbeat_timeout,
	)


def build_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(description="Controller da Base para socket_bw_ping")
	parser.add_argument("--log-level", default="INFO", help="Nível de log (default: INFO)")
	add_base_arguments(parser)
	return parser


def main(argv: Optional[list[str]] = None) -> None:
	parser = build_parser()
	args = parser.parse_args(argv)
	configure_logging(args.log_level)
	config = config_from_args(args)
	controller = BaseController(config)
	asyncio.run(controller.start())


if __name__ == "__main__":
	main()
