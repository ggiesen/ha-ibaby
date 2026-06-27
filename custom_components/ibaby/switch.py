# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Projector / privacy switches.

The camera reports no state for these, and the projector self-disables after
~15 minutes, so the switches are optimistic (assumed state).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from pyibaby import LANCamera

from .coordinator import IbabyConfigEntry, IbabyCoordinator
from .entity import IbabyEntity


@dataclass(frozen=True, kw_only=True)
class IbabySwitchDescription(SwitchEntityDescription):
    """Describes a switch and the camera calls that drive it."""

    turn_on: Callable[[LANCamera], None]
    turn_off: Callable[[LANCamera], None]


SWITCHES: tuple[IbabySwitchDescription, ...] = (
    IbabySwitchDescription(
        key="moonlight",
        translation_key="moonlight",
        turn_on=lambda lan: lan.moonlight(True),
        turn_off=lambda lan: lan.moonlight(False),
    ),
    IbabySwitchDescription(
        key="music_light",
        translation_key="music_light",
        turn_on=lambda lan: lan.music_light(True),
        turn_off=lambda lan: lan.music_light(False),
    ),
    IbabySwitchDescription(
        key="privacy",
        translation_key="privacy",
        turn_on=lambda lan: lan.privacy_mode(True),
        turn_off=lambda lan: lan.privacy_mode(False),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IbabyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the projector / privacy switches."""
    coordinator = entry.runtime_data
    async_add_entities(IbabySwitch(coordinator, description) for description in SWITCHES)


class IbabySwitch(IbabyEntity, SwitchEntity):
    """An optimistic on/off control with no device read-back."""

    _attr_assumed_state = True
    entity_description: IbabySwitchDescription

    def __init__(self, coordinator: IbabyCoordinator, description: IbabySwitchDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description
        self._attr_is_on = False

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_command(self.entity_description.turn_on)
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_command(self.entity_description.turn_off)
        self._attr_is_on = False
        self.async_write_ha_state()
