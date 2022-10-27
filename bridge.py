# pylint: disable=all
from pathlib import Path
from time import sleep
from typing import List, Tuple
from .helpers.hueapi import HueApiRequest, HueApiResponse
from .huedevice import HueDevice as Device
from .huelight import HueLight as Light
from .hueswitch import HueSwitch as Switch
from .huebridge import HueBridge
import fcntl
import ipaddress
import json
import os
import socket
import struct
import urllib3

class Bridge:
    def __init__(
            self,
            autoinit = True,
            app_name = 'pyhue',
            app_instance = '0',
            discover_subnet = None,
            bridge_address = None
        ) -> None:

        home = str(Path('~').expanduser())
        config_dir = f'{home}/.pyhue'
        config_file = f'{config_dir}/client'
        try:
            os.mkdir(config_dir)
        except FileExistsError:
            pass

        self.__local_subnet = discover_subnet

        urllib3.disable_warnings(category=urllib3.exceptions.InsecureRequestWarning)
        self.__http_pool = urllib3.PoolManager(retries = False, cert_reqs='CERT_NONE')
        self.__bridge_id_string = 'hue personal wireless lighting'

        self.devices = []

        if autoinit:
            if bridge_address:
                self.address = bridge_address
            else:
                self.address = self.discover()

            self.__hue_api_request = HueApiRequest(
                bridge_address = self.address,
                urllib3_http_pool = self.__http_pool
            )

            self.config = self.__load_config(
                config_file = config_file,
                bridge_address = self.address
            )
            
            if not self.config:
                app_name = f'{app_name}#{app_instance}'
                username, clientkey = self.get_credentials(app_name)
                self.config = self.__create_config(
                    config_file = config_file,
                    bridge_address = self.address,
                    app_name = app_name,
                    username = username,
                    clientkey = clientkey
                )

            self.__hue_api_request.username = self.config['username']
            
            self.refresh_devices()

    def __create_config(self, 
            config_file: str,
            bridge_address: str,
            app_name: str,
            username: str,
            clientkey: str
        ) -> dict:

        conf = {}
        if os.path.isfile(config_file):
            with open(config_file, 'r') as cf:
                conf = json.loads(cf.read())

        with open(config_file, 'w') as cf:
            conf[bridge_address] = {}
            conf[bridge_address]['app_name'] = app_name
            conf[bridge_address]['username'] = username
            conf[bridge_address]['clientkey'] = clientkey
            cf.write(json.dumps(conf))
        return conf[bridge_address]

    def __load_config(self, config_file: str, bridge_address: str) -> dict:
        conf = {}
        if os.path.isfile(config_file):
            with open(config_file, 'r') as cf:
                contents = json.loads(cf.read())

            if contents.get(bridge_address):
                conf = contents[bridge_address]
                print(f'Loaded config: {conf}')
        return conf

    def __get_own_ip(self) -> str:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 53))
        return s.getsockname()[0]

    def __get_nic_with_ip(self, ip: str) -> str:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        for nic in socket.if_nameindex():
            try:
                packed_iface = struct.pack('256s', nic[1].encode('utf_8'))
                packed_addr = fcntl.ioctl(sock.fileno(), 0x8915, packed_iface)[20:24]
                nic_addr = socket.inet_ntoa(packed_addr)
                if nic_addr == ip:
                    return nic[1]
            except IOError:
                pass

    def __get_nic_netmask(self, nic: str) -> str:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        packed_netmask = fcntl.ioctl(sock.fileno(), 0x891b, struct.pack('256s', nic.encode('utf-8')))[20:24]
        nic_netmask = socket.inet_ntoa(packed_netmask)
        return nic_netmask

    def __get_hosts(self, subnet):
        subnet = ipaddress.ip_network(subnet, strict=False)
        return subnet.hosts()

    def discover(self) -> str:
        if not self.__local_subnet:
            my_addr = self.__get_own_ip()
            my_nic = self.__get_nic_with_ip(my_addr)
            my_netmask = self.__get_nic_netmask(my_nic)
            self.__local_subnet = f'{my_addr}/{my_netmask}'

        for host in self.__get_hosts(self.__local_subnet):
            try:
                url = f'https://{host}'
                api_response = self.__http_pool.request('GET', url)
                if api_response.status == 200 or api_response.status == 403:
                    if self.__bridge_id_string in api_response.data.decode('utf-8').lower():
                        return host.exploded
            except urllib3.exceptions.MaxRetryError:
                pass
            except urllib3.exceptions.NewConnectionError:
                pass
            except urllib3.exceptions.SSLError:
                pass

    def get_credentials(self, app_name) -> Tuple[str, str]:
        body = f'{{"devicetype":"{app_name}", "generateclientkey":true}}'
        clientkey = None
        error_type = 101
        while error_type == 101:
            api_response = self.__hue_api_request.send(method = 'POST', endpoint='', body=body, api_version='1')
            if api_response.data[0].get('error'):
                error_type = api_response.data[0]['error']['type']
                if error_type == 101:
                    print('Press the link button on the bridge')
                    sleep(1)
                else:
                    raise RuntimeError(f"Error {error_type} retrieving token: {api_response.data[0]['error']['description']}")
            else:
                error_type = None
                username = api_response.data[0]['success']['username']
                clientkey = api_response.data[0]['success']['clientkey']
        return username, clientkey

    def refresh_devices(self) -> None:
        api_response = self.__hue_api_request.send(method='GET', endpoint='/resource/device')
        devices = []
        for device in api_response.data.get('data'):
            rtypes = []
            for service in device.get('services'):
                rtypes.append(service['rtype'])
            if 'light' in rtypes:
                d = Light(
                    id = device.get('id'),
                    id_v1 = device.get('id_v1'),
                    type = device.get('type'),
                    send = self.__hue_api_request.send
                )
            elif 'button' in rtypes:
                d = Switch(
                    id = device.get('id'),
                    id_v1 = device.get('id_v1'),
                    type = device.get('type'),
                    send = self.__hue_api_request.send
                )
            elif 'bridge' in rtypes:
                d = HueBridge(
                    id = device.get('id'),
                    id_v1 = device.get('id_v1'),
                    type = device.get('type'),
                    send = self.__hue_api_request.send
                )
            else:
                d = Device(
                    id = device.get('id'),
                    id_v1 = device.get('id_v1'),
                    type = device.get('type'),
                    send = self.__hue_api_request.send
                )
            for entry in device.get('metadata'):
                for key in device['metadata'].keys():
                    d.add_metadata(key, device['metadata'][key])
            for entry in device.get('product_data'):
                for key in device['product_data'].keys():
                    d.add_product_data(key, device['product_data'][key])
            for service in device.get('services'):
                d.add_service(service['rid'], service['rtype'])
            d.refresh_state()
            devices.append(d)
        self.devices = devices

    def list(self, device_type: str, names: bool = True) -> List[Device]:
        if names:
            devices = [device.metadata.get('name') for device in self.devices if device.friendly_type == device_type]
        else:
            devices = [device for device in self.devices if device.friendly_type == device_type]
        return devices

    def find_devices_by_name(self, device_name: str, device_type: str = None, case_sensitive = False, regex = False) -> List[Device]:
        devices = []
        for device in self.devices:
            if regex:
                raise NotImplementedError
            else:
                if device.metadata and (
                    (case_sensitive and device.metadata.get('name') == device_name) or
                    (not case_sensitive and device.metadata.get('name').lower() == device_name.lower())
                ):
                    if not device_type or device.friendly_type == device_type:
                        devices.append(device)
        return devices
