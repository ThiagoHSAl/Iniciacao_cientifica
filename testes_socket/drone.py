#!/usr/bin/env python3
"""Drone executor role for socket_bw_ping."""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
from typing import Optional, Tuple

from common import (
	DroneConfig,
	JSONType,
	add_drone_arguments,
	configure_logging,
	json_dumps,
	parse_json_line,
	run_gps_command,
	run_iperf_test,
	run_ping_test,
	utc_now,
)


class DroneExecutor:
	"""Executes measurements on the drone device and reports back to the Base."""

	def __init__(self, config: DroneConfig) -> None:
		self.config = config
		self.reader: Optional[asyncio.StreamReader] = None
		self.writer: Optional[asyncio.StreamWriter] = None
		self.heartbeat_task: Optional[asyncio.Task] = None
		self.backoff = config.control_retry_start
		self.last_gps: Optional[Tuple[float, float]] = None
		self._gps_lock = asyncio.Lock()

	async def start(self) -> None:
		while True:
			try:
				logging.info(
					"Conectando ao controlador em %s:%s",
					self.config.control_host,
					self.config.control_port,
				)
				self.reader, self.writer = await asyncio.open_connection(
					self.config.control_host, self.config.control_port
				)
				await self._on_connect()
				self.backoff = self.config.control_retry_start
			except (ConnectionError, OSError) as exc:
				logging.error("Conexão falhou: %s", exc)
				await asyncio.sleep(self.backoff)
				self.backoff = min(self.backoff * 2, self.config.control_retry_max)
			finally:
				if self.writer:
					self.writer.close()
					try:
						await self.writer.wait_closed()
					except Exception:
						pass
				self.reader = self.writer = None
				if self.heartbeat_task:
					self.heartbeat_task.cancel()
					with contextlib.suppress(asyncio.CancelledError):
						await self.heartbeat_task

	async def _on_connect(self) -> None:
		await self._send(
			{
				"type": "HELLO",
				"timestamp_utc": utc_now(),
				"capabilities": {
					"ping": self.config.enable_ping,
					"iperf": self.config.enable_iperf,
				},
			}
		)
		self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())
		await self._receive_loop()

	async def _heartbeat_loop(self) -> None:
		while True:
			await asyncio.sleep(self.config.heartbeat_interval)
			drone_lat, drone_lon = await self._refresh_gps("HEARTBEAT")
			payload: JSONType = {
				"type": "HEARTBEAT",
				"timestamp_utc": utc_now(),
				"drone_lat": float(drone_lat),
				"drone_lon": float(drone_lon),
			}
			await self._send(payload)

	async def _receive_loop(self) -> None:
		assert self.reader is not None
		while not self.reader.at_eof():
			line = await self.reader.readline()
			if not line:
				break
			try:
				message = parse_json_line(line)
			except ValueError as exc:
				logging.error("Mensagem inválida do controlador: %s", exc)
				continue
			await self._handle_command(message)

	async def _handle_command(self, message: JSONType) -> None:
		msg_type = message.get("type")
		if msg_type == "RUN_TEST":
			await self._handle_run_test(message)
		elif msg_type == "PING":
			await self._send({"type": "PONG", "timestamp_utc": utc_now()})
		elif msg_type == "STOP":
			logging.info("Comando STOP recebido; encerrando.")
			raise SystemExit(0)
		else:
			logging.debug("Comando não reconhecido: %s", message)

	async def _handle_run_test(self, message: JSONType) -> None:
		payload = message.get("payload", {})
		request_id = message.get("request_id")
		enable_ping = payload.get("enable_ping", self.config.enable_ping)
		enable_iperf = payload.get("enable_iperf", self.config.enable_iperf)
		ping_duration = payload.get("ping_duration", self.config.ping_duration)
		iperf_duration = payload.get("iperf_duration", self.config.iperf_duration)
		iperf_udp = payload.get("iperf_udp", self.config.iperf_udp)
		iperf_reverse = payload.get("iperf_reverse", self.config.iperf_reverse)
		iperf_bandwidth = payload.get("iperf_bandwidth", self.config.iperf_bandwidth)

		response: JSONType = {
			"type": "RESULT",
			"timestamp_utc": utc_now(),
			"request_id": request_id,
		}
		try:
			drone_lat, drone_lon = await self._refresh_gps("RUN_TEST")
			response["drone_lat"] = float(drone_lat)
			response["drone_lon"] = float(drone_lon)

			if enable_ping:
				response["ping_ms"] = await asyncio.get_event_loop().run_in_executor(
					None,
					lambda: run_ping_test(self.config.ping_target, ping_duration),
				)
			else:
				response["ping_ms"] = None

			if enable_iperf:
				response["bandwidth_mbps"] = await asyncio.get_event_loop().run_in_executor(
					None,
					lambda: run_iperf_test(
						self.config.iperf_target,
						iperf_duration,
						udp=iperf_udp,
						reverse=iperf_reverse,
						bandwidth=iperf_bandwidth,
					),
				)
			else:
				response["bandwidth_mbps"] = None

			response["status"] = "OK"
			response["message"] = ""
		except Exception as exc:
			logging.error("Falha durante RUN_TEST: %s", exc)
			response["status"] = "ERROR"
			response["message"] = str(exc)
		await self._send(response)

	def _safe_get_gps(self) -> Optional[Tuple[float, float]]:
		try:
			return run_gps_command(self.config.gps_command, self.config.gps_timeout)
		except Exception as exc:
			logging.error("Erro ao obter GPS: %s", exc)
			return None

	async def _send(self, message: JSONType) -> None:
		if not self.writer:
			return
		self.writer.write(json_dumps(message))
		await self.writer.drain()

	async def _refresh_gps(self, context: str) -> Tuple[float, float]:
		gps = await self._read_gps_locked()
		if gps:
			self.last_gps = gps
		else:
			logging.warning("GPS indisponível durante %s; enviando coordenadas (0,0)", context)
			self.last_gps = (0.0, 0.0)
		return self.last_gps

	async def _read_gps_locked(self) -> Optional[Tuple[float, float]]:
		async with self._gps_lock:
			return await asyncio.get_event_loop().run_in_executor(None, self._safe_get_gps)


def config_from_args(args: argparse.Namespace) -> DroneConfig:
	return DroneConfig(
		control_host=args.base_host,
		control_port=args.base_port,
		control_retry_start=args.control_retry_start,
		control_retry_max=args.control_retry_max,
		heartbeat_interval=args.heartbeat_interval,
		gps_command=args.gps_command,
		gps_timeout=args.gps_timeout,
		ping_target=args.ping_target,
		ping_duration=args.ping_duration,
		iperf_target=args.iperf_target,
		iperf_duration=args.iperf_duration,
		iperf_udp=args.iperf_udp,
		iperf_reverse=args.iperf_reverse,
		iperf_bandwidth=args.iperf_bandwidth,
		enable_ping=not args.disable_ping,
		enable_iperf=not args.disable_iperf,
	)


def build_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(description="Executor do drone para socket_bw_ping")
	parser.add_argument("--log-level", default="INFO", help="Nível de log (default: INFO)")
	add_drone_arguments(parser)
	return parser


def main(argv: Optional[list[str]] = None) -> None:
	parser = build_parser()
	args = parser.parse_args(argv)
	configure_logging(args.log_level)
	config = config_from_args(args)
	executor = DroneExecutor(config)
	asyncio.run(executor.start())


if __name__ == "__main__":
	main()
