"""
OpenIntent SDK - Federation decorators (RFC-0022 & RFC-0023).

Provides @Federation for server configuration, federation_visibility for
@Agent, federation_policy for @Coordinator, and lifecycle hooks for
federated work.
"""

import logging
from typing import Any, Callable, Optional

from .models import (
    AgentVisibility,
    TrustPolicy,
)
from .security import ServerIdentity

logger = logging.getLogger("openintent.federation.decorators")


def on_federation_received(func: Any) -> Any:
    func._openintent_handler = "federation_received"
    return func


def on_federation_callback(func: Any) -> Any:
    func._openintent_handler = "federation_callback"
    return func


def on_budget_warning(func: Any) -> Any:
    func._openintent_handler = "budget_warning"
    return func


def Federation(  # noqa: N802
    server: Any = None,
    identity: Optional[str] = None,
    key_path: Optional[str] = None,
    visibility_default: str = "public",
    trust_policy: str = "allowlist",
    peers: Optional[list[str]] = None,
    server_url: Optional[str] = None,
) -> Callable[[type], type]:
    def decorator(cls: type) -> type:
        original_init = cls.__init__ if hasattr(cls, "__init__") else None  # type: ignore[misc]

        def new_init(self: Any, *args: Any, **kwargs: Any) -> None:
            if original_init and original_init is not object.__init__:
                original_init(self, *args, **kwargs)

            _server_url = server_url or ""
            if server and hasattr(server, "config"):
                _server_url = f"http://{server.config.host}:{server.config.port}"

            if key_path:
                self._federation_identity = ServerIdentity.from_key_file(
                    _server_url, key_path
                )
            else:
                self._federation_identity = ServerIdentity.generate(_server_url)

            if identity:
                self._federation_identity.did = identity

            self._federation_trust_policy = TrustPolicy(trust_policy)
            self._federation_visibility_default = AgentVisibility(visibility_default)
            self._federation_peers = peers or []
            self._federation_server_url = _server_url

            if server and hasattr(server, "app"):
                from ..server.federation import configure_federation

                configure_federation(
                    server_url=_server_url,
                    server_did=self._federation_identity.did,
                    trust_policy=self._federation_trust_policy,
                    visibility_default=self._federation_visibility_default,
                    peers=self._federation_peers,
                    identity=self._federation_identity,
                )

            logger.info(
                f"Federation configured: did={self._federation_identity.did}, "
                f"trust_policy={trust_policy}, peers={len(self._federation_peers)}"
            )

        cls.__init__ = new_init  # type: ignore[assignment,misc]

        cls._federation_configured = True  # type: ignore[attr-defined]
        cls._federation_trust_policy_name = trust_policy  # type: ignore[attr-defined]
        cls._federation_visibility_default_name = visibility_default  # type: ignore[attr-defined]
        cls._federation_peer_list = peers or []  # type: ignore[attr-defined]

        return cls

    return decorator
