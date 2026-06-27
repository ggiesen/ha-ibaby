# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Config flow for the ibaby integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from pyibaby import Camera, IBabyCloud
from pyibaby.cloud import CloudError

from .const import (
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
    """Sign in to the iBaby cloud, then add a discovered camera (one entry each)."""

    def __init__(self) -> None:
        self._email: str = ""
        self._password: str = ""
        self._cameras: list[Camera] = []

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Collect cloud credentials and enumerate the account's cameras."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._email = user_input[CONF_EMAIL]
            self._password = user_input[CONF_PASSWORD]
            try:
                cameras = await self.hass.async_add_executor_job(self._login)
            except CloudError:
                errors["base"] = "invalid_auth"
            except Exception:  # noqa: BLE001 - any network/parse failure -> generic
                _LOGGER.exception("unexpected error signing in to iBaby")
                errors["base"] = "cannot_connect"
            else:
                self._cameras = [c for c in cameras if c.is_pppp]
                if not self._cameras:
                    return self.async_abort(reason="no_cameras")
                return await self.async_step_pick()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_EMAIL): str, vol.Required(CONF_PASSWORD): str}
            ),
            errors=errors,
        )

    def _login(self) -> list[Camera]:
        return IBabyCloud().login(self._email, self._password)

    async def async_step_pick(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Pick one of the not-yet-configured cameras to add."""
        configured = {entry.unique_id for entry in self._async_current_entries()}
        available = [c for c in self._cameras if c.camid not in configured]
        if not available:
            return self.async_abort(reason="already_configured")

        if user_input is not None:
            cam = next(c for c in available if c.camid == user_input[CONF_CAMID])
            await self.async_set_unique_id(cam.camid)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=cam.camname or cam.camid,
                data={
                    CONF_EMAIL: self._email,
                    CONF_PASSWORD: self._password,
                    CONF_CAMID: cam.camid,
                    CONF_CAMNAME: cam.camname,
                    CONF_CAMTYPE: cam.camtype,
                    CONF_P2P_UID: cam.p2p_uid,
                    CONF_P2P_PROVIDER: cam.p2p_provider,
                    CONF_P2P_PASSWORD: cam.p2p_password,
                },
            )

        choices = {c.camid: f"{c.camname or c.camid} ({c.camtype or 'iBaby'})" for c in available}
        return self.async_show_form(
            step_id="pick",
            data_schema=vol.Schema({vol.Required(CONF_CAMID): vol.In(choices)}),
        )
