# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Config flow for the ibaby integration.

One sign-in adds the whole account: every PPPP camera on it becomes a device
under a single config entry.
"""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from pyibaby import Camera, IBabyCloud
from pyibaby.cloud import CloudError

from .const import (
    CONF_CAMERAS,
    CONF_CAMID,
    CONF_CAMNAME,
    CONF_CAMTYPE,
    CONF_EMAIL,
    CONF_P2P_PASSWORD,
    CONF_P2P_PROVIDER,
    CONF_P2P_UID,
    CONF_PASSWORD,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class IbabyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Sign in once and add every camera on the account."""

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Collect cloud credentials and add all of the account's cameras."""
        errors: dict[str, str] = {}
        if user_input is not None:
            email = user_input[CONF_EMAIL]
            password = user_input[CONF_PASSWORD]
            try:
                cameras = await self.hass.async_add_executor_job(self._login, email, password)
            except CloudError:
                errors["base"] = "invalid_auth"
            except Exception:  # noqa: BLE001 - any network/parse failure -> generic
                _LOGGER.exception("unexpected error signing in to iBaby")
                errors["base"] = "cannot_connect"
            else:
                pppp = [c for c in cameras if c.is_pppp]
                if not pppp:
                    return self.async_abort(reason="no_cameras")
                await self.async_set_unique_id(email.lower())
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=email,
                    data={
                        CONF_EMAIL: email,
                        CONF_PASSWORD: password,
                        CONF_CAMERAS: [self._camera_data(c) for c in pppp],
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_EMAIL): str, vol.Required(CONF_PASSWORD): str}
            ),
            errors=errors,
        )

    def _login(self, email: str, password: str) -> list[Camera]:
        return IBabyCloud().login(email, password)

    @staticmethod
    def _camera_data(cam: Camera) -> dict[str, Any]:
        return {
            CONF_CAMID: cam.camid,
            CONF_CAMNAME: cam.camname,
            CONF_CAMTYPE: cam.camtype,
            CONF_P2P_UID: cam.p2p_uid,
            CONF_P2P_PROVIDER: cam.p2p_provider,
            CONF_P2P_PASSWORD: cam.p2p_password,
        }
