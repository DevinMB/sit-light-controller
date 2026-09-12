# sit-light-controller
Controls device lights based on events.

Consumes sit events from Kafka and drives a light. As of v3.0.0 the backend is
**Home Assistant**, not a Philips Hue bridge.

## Configuration

| Variable | Purpose |
|---|---|
| `BROKER` | Kafka bootstrap server, e.g. `192.168.1.250:9092` |
| `HA_BASE_URL` | Home Assistant base URL, e.g. `http://192.168.1.5:8123` |
| `HA_TOKEN` | Home Assistant long-lived access token |
| `HA_ENTITY_ID` | Target light entity, e.g. `light.basement_track_left` |
| `GROUP_OR_LIGHT` | `LIGHT` (only meaningful value against Home Assistant) |
| `ON_CONFIG` | Hue-shaped state applied on sit-down, e.g. `{"on": true, "xy": [0.2725, 0.1096], "bri": 254}` |
| `OFF_CONFIG` | Hue-shaped fallback for sit-up; normally overwritten by the light's previous state |
| `HA_TIMEOUT` | optional, seconds, default `10` |

`ON_CONFIG` / `OFF_CONFIG` stay in Hue's shape and are translated at the boundary:

```
Hue  PUT /lights/<id>/state {"on": true, "xy": [x,y], "bri": n}
HA   POST /api/services/light/turn_on  {"entity_id": E, "xy_color": [x,y], "brightness": n}

Hue  PUT /lights/<id>/state {"on": false}
HA   POST /api/services/light/turn_off {"entity_id": E}
```

## Migration from v2.x

`BRIDGE_IP`, `USER_TOKEN` and `LIGHT_ID` are no longer used; set `HA_BASE_URL`,
`HA_TOKEN` and `HA_ENTITY_ID` instead. Behaviour is otherwise unchanged: sit-down
applies `ON_CONFIG`, sit-up restores the light's previous state.

The 100-sit celebration previously fired Hue group ids and a Hue scene, which existed
only on the bridge. `make_api_call_to_group()` is now a logged no-op; map the groups to
a Home Assistant scene and call `scene.turn_on` to restore it.
