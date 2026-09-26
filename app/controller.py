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

        Registration is idempotent. Existing service metadata is refreshed
        on every successful registration so deployed versions, endpoints,
        capabilities, and observation resources remain current.

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
                "Controller registration verified: %s on node %s",
                self.service_id,
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

            self._request(
                "GET",
                f"/api/v1/nodes/{self.node_id}",
            )

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
        Register the generic edge-time service declaration.

        The declaration describes controller-visible management-plane
        capabilities and read-only observation resources.

        The controller does not interpret these resources as edge-time
        specific. They are ordinary service declarations.
        """

        registration = {
            "service_id": self.service_id,
            "name": self.service_name,
            "version": self.service_version,

            "endpoint": {
                "scheme": "http",
                "port": 8095,
                "path": "/health",
            },

            "capabilities": {
                "status": True,
                "observe": True,
                "diagnostics": True,
                "configuration": False,
                "actions": False,
                "time": True,
                "authority": True,
                "evidence": False,
            },

            "observation_resources": [
                {
                    "id": "health",
                    "method": "GET",
                    "path": "/health",
                    "enabled": True,
                    "description": (
                        "Service health and role identity"
                    ),
                },
                {
                    "id": "status",
                    "method": "GET",
                    "path": "/status",
                    "enabled": True,
                    "description": (
                        "Current edge-time operational state"
                    ),
                },
                {
                    "id": "time",
                    "method": "GET",
                    "path": "/time",
                    "enabled": True,
                    "description": (
                        "Selected time and provenance state"
                    ),
                },
                {
                    "id": "sources",
                    "method": "GET",
                    "path": "/time/sources",
                    "enabled": True,
                    "description": (
                        "Individual time-source observations"
                    ),
                },
                {
                    "id": "attestation",
                    "method": "GET",
                    "path": "/time/attestation",
                    "enabled": True,
                    "description": (
                        "Local time attestation information"
                    ),
                },
                {
                    "id": "authority",
                    "method": "GET",
                    "path": "/authority",
                    "enabled": True,
                    "description": (
                        "Authority identity and state"
                    ),
                },
                {
                    "id": "authority_time",
                    "method": "GET",
                    "path": "/authority/time",
                    "enabled": True,
                    "description": (
                        "Authoritative platform time"
                    ),
                },
                {
                    "id": "consistency",
                    "method": "GET",
                    "path": "/time/consistency",
                    "enabled": True,
                    "description": (
                        "Local time consistency measurement "
                        "against the configured authority"
                    ),
                },
            ],
        }

        self._request(
            "POST",
            f"/api/v1/nodes/{self.node_id}/services",
            registration,
        )

        logger.info(
            "Registered service declaration: "
            "%s version=%s",
            self.service_id,
            self.service_version,
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
                (response or {})
                .get(
                    "configuration",
                    {},
                )
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