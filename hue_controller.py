import requests
import os
import json
from dotenv import load_dotenv


class HueController:
    
    def __init__(self, bridge_ip, user_token):
        load_dotenv()  # Ensure environment variables are loaded
        self.bridge_ip = bridge_ip
        self.user_token = user_token
        self.control_type = os.getenv('GROUP_OR_LIGHT')
        self.light_id = os.getenv('LIGHT_ID')
        self.group_id = os.getenv('GROUP_ID')
        # Parse environment variables after ensuring they're loaded
        try:
            self.off_config = json.loads(os.getenv('OFF_CONFIG'))
            self.on_config = json.loads(os.getenv('ON_CONFIG'))
        except json.JSONDecodeError:
            print("Error decoding JSON from environment variables")
            self.off_config = {}
            self.on_config = {}

    def make_api_call_to_group(self, data):
        url = f'http://{self.bridge_ip}/api/{self.user_token}/groups/{self.group_id}/action'
        response = requests.put(url, json=data)
        return response.json()
    
    def make_api_call_to_light(self, data):
        url = f'http://{self.bridge_ip}/api/{self.user_token}/lights/{self.light_id}/state'
        response = requests.put(url, json=data)
        return response.json()

    def turn_on_light(self):
        data = self.on_config
        if(self.control_type == 'LIGHT'):
            return self.make_api_call_to_light(data)
        if(self.control_type == 'GROUP'):
            return self.make_api_call_to_group(data)


    def turn_off_light(self):
        data = self.off_config
        if(self.control_type == 'LIGHT'):
            return self.make_api_call_to_light(data)
        if(self.control_type == 'GROUP'):
            return self.make_api_call_to_group(data)


