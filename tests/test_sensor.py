"""Tests for Willy Wind Forecast sensor platform."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from homeassistant.helpers.entity_component import async_update_entity
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import load_fixture

from custom_components.willywindforecast import DOMAIN

VALID_CONFIG = {
    DOMAIN: {
        "api_key": "test_api_key",
        "forecast_days": 2,
        "poll_period_hours": 3,
    }
}


def _mock_requests_get(search_json, forecast_json):
    responses = []
    for data in [search_json, forecast_json]:
        resp = MagicMock()
        resp.json.return_value = data
        resp.raise_for_status.return_value = None
        responses.append(resp)
    return MagicMock(side_effect=responses)


async def _setup_integration(hass):
    """Set up the integration with mocked API calls and return True/False."""
    hass.states.async_set("zone.home", "zoning", {
        "latitude": -31.918,
        "longitude": 116.079,
    })

    search_data = json.loads(load_fixture("search_response.json", DOMAIN))
    forecast_data = json.loads(load_fixture("forecast_response.json", DOMAIN))

    with patch(
        "custom_components.willywindforecast.requests.get",
        _mock_requests_get(search_data, forecast_data),
    ):
        result = await async_setup_component(hass, DOMAIN, VALID_CONFIG)
        await hass.async_block_till_done()

    for day in range(VALID_CONFIG[DOMAIN]["forecast_days"]):
        for metric in ("speed_max", "speed_min", "dominant_direction", "dominant_direction_text"):
            await async_update_entity(
                hass, f"sensor.willy_wind_forecast_{metric}_{day}"
            )
    await hass.async_block_till_done()

    return result


class TestSensorPlatform:
    """Tests for sensor entity creation and state."""

    async def test_sensors_created(self, hass):
        assert await _setup_integration(hass)

        for day in range(2):
            for metric in ("speed_max", "speed_min", "dominant_direction", "dominant_direction_text"):
                entity_id = f"sensor.willy_wind_forecast_{metric}_{day}"
                state = hass.states.get(entity_id)
                assert state is not None, f"Entity {entity_id} not found"

    async def test_day_0_speed_max(self, hass):
        await _setup_integration(hass)
        state = hass.states.get("sensor.willy_wind_forecast_speed_max_0")
        assert state.state == "30.0"

    async def test_day_0_speed_min(self, hass):
        await _setup_integration(hass)
        state = hass.states.get("sensor.willy_wind_forecast_speed_min_0")
        assert state.state == "10.0"

    async def test_day_0_dominant_direction(self, hass):
        await _setup_integration(hass)
        state = hass.states.get("sensor.willy_wind_forecast_dominant_direction_0")
        assert state.state == "90.0"

    async def test_day_0_dominant_direction_text(self, hass):
        await _setup_integration(hass)
        state = hass.states.get("sensor.willy_wind_forecast_dominant_direction_text_0")
        assert state.state == "E"

    async def test_day_1_values(self, hass):
        await _setup_integration(hass)
        assert hass.states.get("sensor.willy_wind_forecast_speed_max_1").state == "25.0"
        assert hass.states.get("sensor.willy_wind_forecast_speed_min_1").state == "15.0"
        assert hass.states.get("sensor.willy_wind_forecast_dominant_direction_1").state == "180.0"
        assert hass.states.get("sensor.willy_wind_forecast_dominant_direction_text_1").state == "S"

    async def test_speed_units(self, hass):
        await _setup_integration(hass)
        state = hass.states.get("sensor.willy_wind_forecast_speed_max_0")
        assert state.attributes.get("unit_of_measurement") == "km/h"

    async def test_direction_units(self, hass):
        await _setup_integration(hass)
        state = hass.states.get("sensor.willy_wind_forecast_dominant_direction_0")
        assert state.attributes.get("unit_of_measurement") == "°"

    async def test_direction_text_no_unit(self, hass):
        await _setup_integration(hass)
        state = hass.states.get("sensor.willy_wind_forecast_dominant_direction_text_0")
        assert state.attributes.get("unit_of_measurement") is None

    async def test_no_discovery_no_entities(self, hass):
        from custom_components.willywindforecast.sensor import setup_platform

        add_entities = MagicMock()
        await hass.async_add_executor_job(
            setup_platform, hass, {}, add_entities, None
        )
        add_entities.assert_not_called()
