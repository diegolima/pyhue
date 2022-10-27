# pylint: disable=all
from .huedevice import HueDevice

class HueBridge(HueDevice):
    def __init__(self, id: str, id_v1: str, type: str, send) -> None:
        super().__init__(id, id_v1, type, send)
        self.friendly_type = 'bridge'