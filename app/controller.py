import json
import logging
import os
import platform
import socket
import urllib.error
import urllib.request


logger = logging.getLogger(__name__)


class ControllerClient:
    """
    Generic edge-controller integration for edge-time.

    Controller integration is management-plane functionality only.
    edge-time remains fully operational when the controller is unavailable.

    The controller registration is intentionally refreshed rather than
    treated as immutable. This allows service version, endpoint, and other
    registration metadata to change when a new service build is deployed.
    """

    def __init__(self):
        self.base_url = os.environ.get(
            "EDGE_CONTROLLER_URL",
            "",
        ).rstrip("/")

        self.timeout = int(
            os.environ.get(
                "EDGE_CONTROLLER_TIMEOUT",
                "5",
            )
        )

        self.node_id = (
            os.environ.get("EDGE_NODE_ID")
            or socket.gethostname()
        )

        self.service_id = os.environ.get(
            "EDGE_SERVICE_ID",
            "edge-time",
        )

        self.service_name = os.environ.get(
            "EDGE_SERVICE_NAME",
            "edge-time",
        )

        self.service_version = os.environ.get(
            "EDGE_SERVICE_VERSION",
            "${SER_VER}",
        )

        self.service_scheme = os.environ.get(
            "EDGE_SERVICE_SCHEME",
            "http",
        )

        self.service_port = int(
            os.environ.get(
                "EDGE_SERVICE_PORT",
                "8095",
            )
        )

        self.service_health_path = os.environ.get(
            "EDGE_SERVICE_HEALTH_PATH",
            "/health",
        )

    def _request(
        self,
        method: str,
        path: str,
        payload=None,
    ):
        if not self.base_url:
            return None

        data = (
            json.dumps(payload).encode("utf-8")
            if payload is not None
            else None
        )

        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=data,
            method=method,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )

        with urllib.request.urlopen(
            request,
            timeout=self.timeout,
        ) as response:
            raw = response.read()

            if not raw:
                return None

            return json.loads(
                raw.decode("utf-8")
            )

    def register(self) -> bool:
        """
        Ensure the node and service are registered with the controller.

        Registration is safe to call repeatedly.

        Existing resources are updated with the current service metadata
        rather than being treated as immutable. This is important for
        service version changes between deployments.

        Returns False if the controller is unavailable.
        """

        if not self.base_url:
            logger.info(
                "EDGE_CONTROLLER_URL is not configured; "
                "controller integration disabled"
            )

            return False

        try:
            self._register_node()
            self._register_service()

            logger.info(
                "Controller registration verified: "
                "%s version=%s on node %s",
                self.service_id,
                self.service_version,
                self.node_id,
            )

            return True

        except Exception as exc:
            logger.warning(
                "Controller registration failed: %s",
                exc,
            )

            return False

    def _register_node(self):
        try:
            response = self._request(
                "GET",
                f"/api/v1/nodes/{self.node_id}",
            )

            if response:
                return

        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise

        self._request(
            "POST",
            "/api/v1/nodes",
            {
                "node_id": self.node_id,
                "hostname": socket.gethostname(),
                "platform": (
                    f"{platform.system().lower()}"
                    f"-{platform.machine()}"
                ),
            },
        )

        logger.info(
            "Registered node: %s",
            self.node_id,
        )

    def _register_service(self):
        """
        Register or refresh the service registration.

        Do not skip registration when the service already exists. The
        controller uses the POST operation as an idempotent upsert and
        updates version, endpoint, and service metadata for existing
        registrations.
        """

        payload = {
            "service_id": self.service_id,
            "name": self.service_name,
            "version": self.service_version,
            "endpoint": {
                "scheme": self.service_scheme,
                "port": self.service_port,
                "path": self.service_health_path,
            },
        }

        self._request(
            "POST",
            f"/api/v1/nodes/{self.node_id}/services",
            payload,
        )

        logger.info(
            "Registered/refreshed service: "
            "%s version=%s endpoint=%s://%s:%s%s",
            self.service_id,
            self.service_version,
            self.service_scheme,
            socket.gethostname(),
            self.service_port,
            self.service_health_path,
        )

    def get_configuration(self) -> dict:
        """
        Retrieve generic service configuration from the controller.

        Configuration is optional. Failure must not stop edge-time.
        """

        if not self.base_url:
            return {}

        try:
            response = self._request(
                "GET",
                (
                    f"/api/v1/nodes/{self.node_id}"
                    f"/services/{self.service_id}"
                    "/configuration"
                ),
            )

            return (
                response or {}
            ).get(
                "configuration",
                {},
            )

        except Exception as exc:
            logger.warning(
                "Controller configuration unavailable: %s",
                exc,
            )

            return {}

    def update_status(
        self,
        status: str,
        data: dict,
    ) -> bool:
        """
        Publish generic service status to the controller.
        """

        if not self.base_url:
            return False

        try:
            self._request(
                "PUT",
                (
                    f"/api/v1/nodes/{self.node_id}"
                    f"/services/{self.service_id}/status"
                ),
                {
                    "status": status,
                    "data": data,
                },
            )

            return True

        except Exception as exc:
            logger.warning(
                "Controller status update failed: %s",
                exc,
            )

            return False