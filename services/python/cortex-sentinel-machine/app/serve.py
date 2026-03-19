from __future__ import annotations

from time import sleep

from app.collector import CompositeCollector
from app.config import RuntimeSettings
from app.observability import SecureObservabilityServer
from app.runtime import SentinelRuntime
from app.service import SentinelMachineService
from app.transport import SentinelGrpcServer


def main() -> None:
    settings = RuntimeSettings()
    settings.state_dir.mkdir(parents=True, exist_ok=True)
    settings.queue_path.parent.mkdir(parents=True, exist_ok=True)
    service = SentinelMachineService(settings, CompositeCollector(settings))
    runtime = SentinelRuntime(service)
    grpc_server = SentinelGrpcServer(service, settings)
    obs_server = SecureObservabilityServer(service, settings.observability_token)

    host, port = settings.observability_bind.split(":")
    grpc_server.start(settings.grpc_bind)
    obs_server.start(host, int(port))
    runtime.register_command_subscription()
    try:
        while True:
            service.process_once()
            sleep(2.0)
    except KeyboardInterrupt:
        pass
    finally:
        obs_server.stop()
        grpc_server.stop(0)
        service.close()


if __name__ == "__main__":
    main()
