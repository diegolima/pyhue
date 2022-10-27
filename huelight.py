# pylint: disable=all
from .huedevice import HueDevice

class HueLight(HueDevice):
    def __init__(self, id: str, id_v1: str, type: str, send) -> None:
        super().__init__(id, id_v1, type, send)
        self.friendly_type = 'light'
        self.rtype = 'light'

    def __set_on_off(self, on = False):
        body = f'{{"on":{{"on":{str(on).lower()}}}}}'

        if not self.is_on():
            self.send()

    def is_on(self) -> bool:
        for endpoint in self.endpoints:
            return self.endpoints[endpoint]['data'][0]['on']['on']

    def turn_on(self) -> bool:
        return self.__set_on_off(on=True)    

