# pylint: disable=all
from typing import List

class HueDevice:
    def __init__(
        self,
        id: str,
        id_v1: str,
        type: str,
        send
    ) -> None:
        self.id = id
        self.id_v1 = id_v1
        self.type = type
        self.product_data = {}
        self.metadata = {}
        self.identify = None
        self.services = {}
        self.friendly_type = 'generic_device'
        self.send = send
        self.rtype = None

    def add_metadata(self, key: str, value: str):
        self.metadata[key] = value

    def add_product_data(self, key: str, value: str):
        self.product_data[key] = value
    
    def add_service(self, rid: str, type: str):
        self.services[rid] = type

    def get_services(self):
        services = []
        for service in self.services:
            services.append(self.services[service])
        return services

    def get_endpoints(self, rtype: str = None, api_version: str = 2) -> List[str]:
        if not rtype:
            rtype = self.rtype

        endpoints = []
        for service in self.services:
            if self.services[service] == rtype:
                if api_version == 2:
                    endpoints.append(f'/resource/{rtype}/{service}')
                else:
                    raise NotImplementedError
        return endpoints

    def get_endpoint_details(self, endpoint: str) -> dict:
        return self.send(
                        method = 'GET',
                        endpoint = endpoint
                    ).data

    def get_properties(self):
        properties = self.__dict__.copy()
        if properties.get('send'):
            del properties['send']
        return properties

    def refresh_state(self):
        endpoint_list = self.get_endpoints(self.rtype)
        endpoints = {}
        for endpoint in endpoint_list:
            endpoints[endpoint] = self.get_endpoint_details(endpoint)

        self.endpoints = endpoints
