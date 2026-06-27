# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Pan/tilt buttons.

pyibaby's PTZ is discrete command dispatch (no continuous-move/stop surface is
exposed), so each press issues a single move in one direction.
"""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from pyibaby import protocol as P

from .coordinator import IbabyConfigEntry, IbabyCoordinator
from .entity import IbabyEntity


@dataclass(frozen=True, kw_only=True)
class IbabyButtonDescription(ButtonEntityDescription):
    """Describes a PTZ button and its pyibaby direction code."""

    direction: int


BUTTONS: tuple[IbabyButtonDescription, ...] = (
    IbabyButtonDescription(
        key="ptz_up", translation_key="ptz_up", icon="mdi:arrow-up-bold", direction=P.PTZ_UP
    ),
    IbabyButtonDescription(
        key="ptz_down", translation_key="ptz_down", icon="mdi:arrow-down-bold", direction=P.PTZ_DOWN
    ),
    IbabyButtonDescription(
        key="ptz_left", translation_key="ptz_left", icon="mdi:arrow-left-bold", direction=P.PTZ_LEFT
    ),
    IbabyButtonDescription(
        key="ptz_right",
        translation_key="ptz_right",
        icon="mdi:arrow-right-bold",
        direction=P.PTZ_RIGHT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IbabyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the PTZ buttons for every camera."""
    async_add_entities(
        IbabyButton(coordinator, description)
        for coordinator in entry.runtime_data
        for description in BUTTONS
    )


class IbabyButton(IbabyEntity, ButtonEntity):
    """A single discrete pan/tilt move."""

    entity_description: IbabyButtonDescription

    def __init__(self, coordinator: IbabyCoordinator, description: IbabyButtonDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    async def async_press(self) -> None:
        direction = self.entity_description.direction
        await self.coordinator.async_command(lambda lan: lan.ptz(direction))
