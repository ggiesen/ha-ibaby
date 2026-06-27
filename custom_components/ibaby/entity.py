# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Base entity for the ibaby integration."""

from __future__ import annotations

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import IbabyCoordinator


class IbabyEntity(CoordinatorEntity[IbabyCoordinator]):
    """Common base: shared device, name handling, and a per-camera unique id."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: IbabyCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = f"{coordinator.camera.camid}_{key}"
