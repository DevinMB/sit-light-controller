import requests
import os
import json
from dotenv import load_dotenv


class HueController:
    
    def __init__(self, bridge_ip, user_token):
        load_dotenv()  # Ensure environment variables are loaded
        self.bridge_ip = bridge_ip
        self.user_token = user_token
        # Parse environment variables after ensuring they're loaded
        try:
            self.off_config = json.loads(os.getenv('LIGHT_OFF_CONFIG'))
            self.on_config = json.loads(os.getenv('LIGHT_ON_CONFIG'))
        except json.JSONDecodeError:
            print("Error decoding JSON from environment variables")
            self.off_config = {}
            self.on_config = {}

    def make_api_call_to_group(self, group_id, data):
        url = f'http://{self.bridge_ip}/api/{self.user_token}/groups/{group_id}/action'
        response = requests.put(url, json=data)
        return response.json()
    
    def make_api_call_to_light(self, light_id, data):
        url = f'http://{self.bridge_ip}/api/{self.user_token}/lights/{light_id}/state'
        response = requests.put(url, json=data)
        return response.json()

    def turn_on_light(self, light_id):
        print(os.getenv('LIGHT_ON_CONFIG'))
        data = self.on_config
        return self.make_api_call_to_light(light_id, data)

    def turn_off_light(self, light_id):
        print(os.getenv('LIGHT_OFF_CONFIG'))
        data = self.off_config
        return self.make_api_call_to_light(light_id, data)

