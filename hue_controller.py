"""
Home Assistant backend for sit-light-controller.

Drop-in replacement for the original hue_controller.py. The Philips Hue bridge that
used to live at 192.168.1.46 is gone and Home Assistant now owns the bulbs, so this
keeps the exact same class name and method signatures and translates each Hue bridge
call into an equivalent Home Assistant service call. sit_light_controller.py is
unchanged.

Config, from the environment:
    HA_BASE_URL    e.g. http://192.168.1.5:8123
    HA_TOKEN       long-lived access token
    HA_ENTITY_ID   e.g. light.basement_track_left
    ON_CONFIG      unchanged, still Hue-shaped: {"on": true, "xy": [x,y], "bri": 254}
    OFF_CONFIG     unchanged, Hue-shaped
    GROUP_OR_LIGHT unchanged; only LIGHT is meaningful against Home Assistant

Translation:
    Hue  PUT /lights/<id>/state  {"on": true,  "xy": [x,y], "bri": n}
    HA   POST /api/services/light/turn_on   {"entity_id": E, "xy_color": [x,y],
                                             "brightness": n}
    Hue  PUT /lights/<id>/state  {"on": false}
    HA   POST /api/services/light/turn_off  {"entity_id": E}
"""

import json
import os

import requests
from dotenv import load_dotenv


class HueController:
    """Same surface as the original Hue bridge client; Home Assistant underneath."""

    def __init__(self, bridge_ip=None, user_token=None):
        load_dotenv()

        # bridge_ip / user_token are accepted so the caller does not change, but the
        # Hue bridge no longer exists and they are deliberately unused.
        self.base_url = (os.getenv("HA_BASE_URL") or "").rstrip("/")
        self.token = os.getenv("HA_TOKEN")
        self.entity_id = os.getenv("HA_ENTITY_ID")

        self.control_type = os.getenv("GROUP_OR_LIGHT")
        self.light_id = os.getenv("LIGHT_ID")
        self.group_id = os.getenv("GROUP_ID")

        missing = [n for n, v in (("HA_BASE_URL", self.base_url),
                                  ("HA_TOKEN", self.token),
                                  ("HA_ENTITY_ID", self.entity_id)) if not v]
        if missing:
            raise RuntimeError(
                "Home Assistant config missing: " + ", ".join(missing)
            )

        self.timeout = float(os.getenv("HA_TIMEOUT", "10"))

        try:
            self.off_config = json.loads(os.getenv("OFF_CONFIG") or "{}")
            self.on_config = json.loads(os.getenv("ON_CONFIG") or "{}")
        except json.JSONDecodeError:
            print("Error decoding JSON from environment variables")
            self.off_config = {}
            self.on_config = {}

        print(f"HueController -> Home Assistant {self.base_url} entity {self.entity_id}")

    # -- plumbing ---------------------------------------------------------------

    @property
    def _headers(self):
        return {"Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"}

    def _call_service(self, domain, service, payload):
        url = f"{self.base_url}/api/services/{domain}/{service}"
        try:
            r = requests.post(url, headers=self._headers, json=payload,
                              timeout=self.timeout)
            r.raise_for_status()
            return r.json() if r.content else {}
        except requests.RequestException as e:
            # Never raise: the caller runs inside the Kafka consume loop and an
            # unreachable light must not kill the consumer.
            print(f"Home Assistant call {domain}.{service} failed: {e}")
            return {"error": str(e)}

    @staticmethod
    def _hue_to_ha(data, entity_id):
        """Translate a Hue light-state dict into (service, payload)."""
        if data.get("on") is False:
            return "turn_off", {"entity_id": entity_id}

        payload = {"entity_id": entity_id}
        if "xy" in data:
            xy = data["xy"]
            if isinstance(xy, (list, tuple)) and len(xy) == 2:
                payload["xy_color"] = [float(xy[0]), float(xy[1])]
        if "bri" in data:
            # Hue bri and HA brightness share the same 0-255 scale.
            payload["brightness"] = max(0, min(255, int(data["bri"])))
        if "ct" in data:
            payload["color_temp"] = int(data["ct"])
        if "transitiontime" in data:
            # Hue counts tenths of a second; HA uses seconds.
            payload["transition"] = int(data["transitiontime"]) / 10.0
        return "turn_on", payload

    # -- original interface -----------------------------------------------------

    def make_api_call_to_light(self, data):
        service, payload = self._hue_to_ha(data, self.entity_id)
        return self._call_service("light", service, payload)

    def make_api_call_to_group(self, data, group_id=None):
        """
        Hue groups and Hue scenes have no automatic Home Assistant equivalent — the
        old group ids (1, 89) and scene id q5pVqBrNrB8yFlFO existed only on the
        bridge. Logged and skipped rather than guessed at, so the 100-sit celebration
        degrades to just the single light instead of failing the consumer.

        To restore it, map the group to an HA scene or light group and call
        scene.turn_on / light.turn_on with that entity_id here.
        """
        target = group_id if group_id is not None else self.group_id
        print(f"[skipped] Hue group call to group {target} with {data} — "
              f"no Home Assistant mapping configured")
        return {"skipped": True, "group": target}

    def turn_on_light(self):
        if self.control_type == "LIGHT":
            self.set_previous_light_config()
            return self.make_api_call_to_light(self.on_config)
        if self.control_type == "GROUP":
            return self.make_api_call_to_group(self.on_config)
        print(f"Unknown GROUP_OR_LIGHT value: {self.control_type!r}")
        return {}

    def turn_off_light(self):
        if self.control_type == "LIGHT":
            return self.make_api_call_to_light(self.off_config)
        if self.control_type == "GROUP":
            return self.make_api_call_to_group(self.off_config)
        print(f"Unknown GROUP_OR_LIGHT value: {self.control_type!r}")
        return {}

    def set_previous_light_config(self):
        """
        Snapshot the light's current state into off_config, so 'off' restores whatever
        the light was before the sit rather than forcing a fixed colour. Same intent as
        the original, reading Home Assistant's state object instead of the bridge's.
        """
        url = f"{self.base_url}/api/states/{self.entity_id}"
        try:
            r = requests.get(url, headers=self._headers, timeout=self.timeout)
            r.raise_for_status()
            state = r.json()
        except (requests.RequestException, ValueError) as e:
            print(f"Could not read previous state of {self.entity_id}: {e} — "
                  f"keeping existing off_config")
            return

        attrs = state.get("attributes") or {}
        previous = {"on": state.get("state") == "on"}

        bri = attrs.get("brightness")
        if bri is not None:
            previous["bri"] = int(bri)

        xy = attrs.get("xy_color")
        if xy and len(xy) == 2:
            previous["xy"] = [float(xy[0]), float(xy[1])]

        self.off_config = previous
