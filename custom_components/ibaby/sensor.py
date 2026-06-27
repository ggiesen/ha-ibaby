# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Environment sensors (temperature / humidity / eCO2 / TVOC / wifi)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    EntityCategory,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from pyibaby.sensors import SensorReading

from .coordinator import IbabyConfigEntry, IbabyCoordinator
from .entity import IbabyEntity


@dataclass(frozen=True, kw_only=True)
class IbabySensorDescription(SensorEntityDescription):
    """Describes an iBaby sensor and how to read it from a SensorReading."""

    value_fn: Callable[[SensorReading], float | int | None]


SENSORS: tuple[IbabySensorDescription, ...] = (
    IbabySensorDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda r: r.temperature_c,
    ),
    IbabySensorDescription(
        key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda r: r.humidity_pct,
    ),
    IbabySensorDescription(
        key="co2",
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda r: r.co2_ppm,
    ),
    # Raw TVOC index (not a ppb concentration), so no device class.
    IbabySensorDescription(
        key="voc",
        translation_key="voc",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda r: r.voc,
    ),
    IbabySensorDescription(
        key="wifi",
        translation_key="wifi",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda r: r.wifi,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IbabyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the environment sensors for every camera."""
    async_add_entities(
        IbabySensor(coordinator, description)
        for coordinator in entry.runtime_data
        for description in SENSORS
    )


class IbabySensor(IbabyEntity, SensorEntity):
    """A single environment reading from the camera."""

    entity_description: IbabySensorDescription

    def __init__(self, coordinator: IbabyCoordinator, description: IbabySensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float | int | None:
        data = self.coordinator.data
        if data is None or data.sensors is None:
            return None
        return self.entity_description.value_fn(data.sensors)
