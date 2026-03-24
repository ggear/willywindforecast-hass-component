# Willy Wind Forecast

A Home Assistant custom component that provides wind forecast sensor data from the [WillyWeather](https://www.willyweather.com.au/) API which patches a gap in the Australian BOM data feed.

## Installation

Copy this folder to `<config_dir>/custom_components/willywindforecast/`.

## Configuration

Add the following to your `configuration.yaml`:

```yaml
willywindforecast:
  api_key: "YOUR_WILLYWEATHER_API_KEY"
  forecast_days: 7       # optional, default 7
  poll_period_hours: 3   # optional, default 3
```

## Sensors

For each forecast day (indexed from 0), the following sensors are created:

- `willy_wind_forecast_speed_max_{day}` — Maximum wind speed (km/h)
- `willy_wind_forecast_speed_min_{day}` — Minimum wind speed (km/h)
- `willy_wind_forecast_dominant_direction_{day}` — Dominant wind direction (degrees)
- `willy_wind_forecast_dominant_direction_text_{day}` — Dominant wind direction (compass text)

Dominant direction is calculated as a speed-weighted circular mean of the hourly wind direction entries for each day.
