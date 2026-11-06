from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_HOUSE, CONF_STREET, DOMAIN
from .coordinator import DtekCoordinator


class DtekEntity(CoordinatorEntity[DtekCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: DtekCoordinator, key: str) -> None:
        super().__init__(coordinator)
        eid = coordinator.entry.entry_id
        self._attr_unique_id = f"{eid}_{key}"
        d = coordinator.entry.data
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, eid)},
            name=f"ДТЕК: {d[CONF_STREET]}, {d[CONF_HOUSE]}",
            manufacturer="ДТЕК Дніпровські електромережі",
        )
