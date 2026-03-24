"""Tests for Willy Wind Forecast integration setup."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import load_fixture

from custom_components.willywindforecast import (
    DOMAIN,
    _compute_dominant_direction,
    _process_forecast,
)

VALID_CONFIG = {
    DOMAIN: {
        "api_key": "test_api_key",
        "forecast_days": 2,
        "poll_period_hours": 3,
    }
}


def _mock_requests_get(search_json, forecast_json):
    """Return a side_effect function that returns search then forecast responses."""
    responses = []
    for data in [search_json, forecast_json]:
        resp = MagicMock()
        resp.json.return_value = data
        resp.raise_for_status.return_value = None
        responses.append(resp)
    return MagicMock(side_effect=responses)


class TestComputeDominantDirection:
    """Tests for the speed-weighted circular mean direction algorithm."""

    def test_empty_entries(self):
        deg, text = _compute_dominant_direction([])
        assert deg == 0.0
        assert text == "N"

    def test_uniform_east(self):
        entries = [
            {"speed": 10, "direction": 90},
            {"speed": 10, "direction": 90},
            {"speed": 10, "direction": 90},
        ]
        deg, text = _compute_dominant_direction(entries)
        assert deg == 90.0
        assert text == "E"

    def test_uniform_south(self):
        entries = [
            {"speed": 20, "direction": 180},
            {"speed": 20, "direction": 180},
        ]
        deg, text = _compute_dominant_direction(entries)
        assert deg == 180.0
        assert text == "S"

    def test_uniform_north(self):
        entries = [{"speed": 10, "direction": 0}]
        deg, text = _compute_dominant_direction(entries)
        assert deg == 0.0
        assert text == "N"

    def test_uniform_west(self):
        entries = [{"speed": 10, "direction": 270}]
        deg, text = _compute_dominant_direction(entries)
        assert deg == 270.0
        assert text == "W"

    def test_speed_weighted_toward_stronger_wind(self):
        entries = [
            {"speed": 100, "direction": 90},
            {"speed": 1, "direction": 270},
        ]
        deg, text = _compute_dominant_direction(entries)
        assert 85 < deg < 95
        assert text == "E"

    def test_northwest(self):
        entries = [{"speed": 10, "direction": 315}]
        deg, text = _compute_dominant_direction(entries)
        assert deg == 315.0
        assert text == "NW"

    def test_wrapping_around_north(self):
        entries = [
            {"speed": 10, "direction": 350},
            {"speed": 10, "direction": 10},
        ]
        deg, text = _compute_dominant_direction(entries)
        assert deg < 11 or deg > 349
        assert text == "N"


class TestProcessForecast:
    """Tests for processing raw API forecast data into per-day summaries."""

    def test_from_fixture(self):
        data = json.loads(load_fixture("forecast_response.json", DOMAIN))
        result = _process_forecast(data)
        assert len(result) == 2

        assert result[0]["speed_max"] == 30.0
        assert result[0]["speed_min"] == 10.0
        assert result[0]["dominant_direction"] == 90.0
        assert result[0]["dominant_direction_text"] == "E"

        assert result[1]["speed_max"] == 25.0
        assert result[1]["speed_min"] == 15.0
        assert result[1]["dominant_direction"] == 180.0
        assert result[1]["dominant_direction_text"] == "S"

    def test_empty_entries_day(self):
        data = {
            "forecasts": {
                "wind": {
                    "days": [{"dateTime": "2026-03-24 00:00:00", "entries": []}]
                }
            }
        }
        result = _process_forecast(data)
        assert len(result) == 1
        assert result[0]["speed_max"] is None
        assert result[0]["dominant_direction"] is None

    def test_empty_response(self):
        assert _process_forecast({}) == []

    def test_single_entry_day(self):
        data = {
            "forecasts": {
                "wind": {
                    "days": [
                        {
                            "dateTime": "2026-03-24 00:00:00",
                            "entries": [
                                {"dateTime": "2026-03-24 12:00:00", "speed": 42.0, "direction": 225, "directionText": "SW"}
                            ],
                        }
                    ]
                }
            }
        }
        result = _process_forecast(data)
        assert result[0]["speed_max"] == 42.0
        assert result[0]["speed_min"] == 42.0
        assert result[0]["dominant_direction"] == 225.0
        assert result[0]["dominant_direction_text"] == "SW"


class TestSetup:
    """Tests for integration setup via async_setup_component."""

    async def test_successful_setup(self, hass):
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

        assert result is True
        assert DOMAIN in hass.data
        assert hass.data[DOMAIN]["location_id"] == 15895
        assert hass.data[DOMAIN]["forecast_days"] == 2
        assert len(hass.data[DOMAIN]["forecast"]) == 2

    async def test_setup_fails_on_search_error(self, hass):
        hass.states.async_set("zone.home", "zoning", {
            "latitude": -31.918,
            "longitude": 116.079,
        })

        with patch(
            "custom_components.willywindforecast.requests.get",
            side_effect=Exception("API error"),
        ):
            result = await async_setup_component(hass, DOMAIN, VALID_CONFIG)

        assert result is False

    async def test_setup_fails_on_forecast_error(self, hass):
        hass.states.async_set("zone.home", "zoning", {
            "latitude": -31.918,
            "longitude": 116.079,
        })

        search_data = json.loads(load_fixture("search_response.json", DOMAIN))
        search_resp = MagicMock()
        search_resp.json.return_value = search_data
        search_resp.raise_for_status.return_value = None

        forecast_resp = MagicMock()
        forecast_resp.raise_for_status.side_effect = Exception("API error")

        with patch(
            "custom_components.willywindforecast.requests.get",
            side_effect=[search_resp, forecast_resp],
        ):
            result = await async_setup_component(hass, DOMAIN, VALID_CONFIG)

        assert result is False

    async def test_poll_updates_forecast_data(self, hass):
        hass.states.async_set("zone.home", "zoning", {
            "latitude": -31.918,
            "longitude": 116.079,
        })

        search_data = json.loads(load_fixture("search_response.json", DOMAIN))
        forecast_data = json.loads(load_fixture("forecast_response.json", DOMAIN))

        with patch(
            "custom_components.willywindforecast.requests.get",
            _mock_requests_get(search_data, forecast_data),
        ) as mock_get, patch(
            "custom_components.willywindforecast.track_time_interval"
        ) as mock_track:
            result = await async_setup_component(hass, DOMAIN, VALID_CONFIG)
            await hass.async_block_till_done()

        assert result is True

        update_fn = mock_track.call_args[0][1]

        updated_forecast = {
            "forecasts": {
                "wind": {
                    "days": [
                        {
                            "dateTime": "2026-03-25 00:00:00",
                            "entries": [
                                {"dateTime": "2026-03-25 00:00:00", "speed": 50.0, "direction": 0, "directionText": "N"},
                            ],
                        },
                        {
                            "dateTime": "2026-03-26 00:00:00",
                            "entries": [
                                {"dateTime": "2026-03-26 00:00:00", "speed": 5.0, "direction": 270, "directionText": "W"},
                            ],
                        },
                    ]
                }
            }
        }
        updated_resp = MagicMock()
        updated_resp.json.return_value = updated_forecast
        updated_resp.raise_for_status.return_value = None

        with patch(
            "custom_components.willywindforecast.requests.get",
            return_value=updated_resp,
        ):
            update_fn()

        assert hass.data[DOMAIN]["forecast"][0]["speed_max"] == 50.0
        assert hass.data[DOMAIN]["forecast"][1]["dominant_direction_text"] == "W"

    async def test_poll_error_preserves_existing_data(self, hass):
        hass.states.async_set("zone.home", "zoning", {
            "latitude": -31.918,
            "longitude": 116.079,
        })

        search_data = json.loads(load_fixture("search_response.json", DOMAIN))
        forecast_data = json.loads(load_fixture("forecast_response.json", DOMAIN))

        with patch(
            "custom_components.willywindforecast.requests.get",
            _mock_requests_get(search_data, forecast_data),
        ), patch(
            "custom_components.willywindforecast.track_time_interval"
        ) as mock_track:
            await async_setup_component(hass, DOMAIN, VALID_CONFIG)
            await hass.async_block_till_done()

        original_forecast = hass.data[DOMAIN]["forecast"].copy()
        update_fn = mock_track.call_args[0][1]

        with patch(
            "custom_components.willywindforecast.requests.get",
            side_effect=Exception("network error"),
        ):
            update_fn()

        assert hass.data[DOMAIN]["forecast"] == original_forecast
