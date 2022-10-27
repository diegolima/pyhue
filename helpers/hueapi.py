# pylint: disable=all
from dataclasses import dataclass
import json
import urllib3

@dataclass
class HueApiResponse:
    status: int
    data: dict

class HueApiRequest:
    def __init__(
        self,
        bridge_address: str,
        urllib3_http_pool: urllib3.PoolManager,
        bridge_username: str = None,
        api_version: str = 2
    ) -> None:
        self.address = bridge_address
        self.username = bridge_username
        self.api_version = api_version

        self.__http_pool = urllib3_http_pool

    def send(
        self,
        method: str,
        endpoint: str,
        body: str = None,
        headers: dict = {},
        api_version: int = None
    ) -> HueApiResponse:
        if not api_version:
            api_version = self.api_version

        api_response = HueApiResponse(
            status = None, 
            data = None
        )

        if self.address:
            if api_version == 2:
                url = f'https://{self.address}/clip/v2/{endpoint}'
            elif api_version == 1:
                url = f'https://{self.address}/api/{endpoint}'
            else:
                raise RuntimeError(f'Unknown API version: {api_version}')

            if self.username:
                headers['hue-application-key'] = self.username

            print(f'Sending {method} to {url}')
            api_response = self.__http_pool.request(
                url = url,
                method=method,
                body=body,
                headers=headers
            )
            if api_response.status == 200:
                api_response = HueApiResponse(
                    status = api_response.status,
                    data = json.loads(api_response.data.decode('utf-8'))
                )
            else:
                raise RuntimeError(f'Error {api_response.status} in request: {api_response.data.decode()}')
        else:
            raise RuntimeError('Bridge address not set. Did you initialize first?')
        
        return api_response