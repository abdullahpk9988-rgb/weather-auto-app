#!/usr/bin/env python3
"""
Daily Weather Email Script

This script fetches current weather data from OpenWeatherMap
and emails a formatted weather report using Gmail SMTP.

Required environment variables:
- EMAIL_ADDRESS      (your Gmail address, e.g., you@gmail.com)
- EMAIL_PASSWORD     (your Gmail App Password, not regular password)
- WEATHER_API_KEY    (your OpenWeatherMap API key)

Optional environment variables:
- WEATHER_CITY       (default: Islamabad)
- EMAIL_RECIPIENT    (default: EMAIL_ADDRESS)

Automation:
- Windows Task Scheduler:
  1. Open Task Scheduler -> Create Basic Task.
  2. Choose Daily trigger and set your time.
  3. Action: Start a program.
  4. Program/script: path to python.exe
  5. Add arguments: path\\to\\weather_email.py
  6. Ensure env vars are available to the task user.

- Linux/Mac cron:
  1. Run: crontab -e
  2. Add (example: every day at 7:00 AM):
     0 7 * * * /usr/bin/python3 /path/to/weather_email.py
  3. Ensure environment variables are available to cron.
"""

import os
import smtplib
from email.message import EmailMessage
from pathlib import Path

import requests


def load_env_file(env_path: Path | None = None) -> None:
    """
    Load KEY=VALUE pairs from a local .env file into environment variables.
    Existing environment variables are not overwritten.
    """
    if env_path is None:
        env_path = Path(__file__).resolve().parent / ".env"

    if not env_path.exists():
        return

    try:
        with env_path.open("r", encoding="utf-8") as file:
            for raw_line in file:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except OSError as exc:
        raise RuntimeError(f"Could not read {env_path}: {exc}") from exc


def get_weather(city: str, api_key: str) -> dict:
    """
    Fetch current weather data for a given city from OpenWeatherMap.
    """
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {"q": city, "appid": api_key, "units": "metric"}

    try:
        response = requests.get(url, params=params, timeout=15)
    except requests.exceptions.RequestException as exc:
        raise RuntimeError(f"Network error while calling weather API: {exc}") from exc

    if response.status_code != 200:
        try:
            error_data = response.json()
            api_message = error_data.get("message", "Unknown API error")
        except ValueError:
            api_message = response.text or "Unknown API error"
        raise RuntimeError(f"Weather API error ({response.status_code}): {api_message}")

    try:
        data = response.json()
        return {
            "city": data["name"],
            "temperature": data["main"]["temp"],
            "description": data["weather"][0]["description"],
            "humidity": data["main"]["humidity"],
            "wind_speed": data["wind"]["speed"],
        }
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("Unexpected weather data format received from API.") from exc


def build_human_weather_advice(weather: dict) -> str:
    """
    Build a natural, practical advice message from today's weather.
    """
    temp = weather["temperature"]
    humidity = weather["humidity"]
    wind = weather["wind_speed"]
    description = weather["description"].lower()

    advice = []

    if temp >= 40:
        advice.append(
            "It's extremely hot today, so wear light clothes and drink plenty of water."
        )
    elif temp >= 30:
        advice.append(
            "It's quite warm today, so breathable clothes and water will keep you comfortable."
        )
    elif temp >= 20:
        advice.append(
            "The weather is pleasant today, so normal comfortable clothing should be fine."
        )
    elif temp >= 10:
        advice.append("It's a bit cool today, so a light jacket is a good idea.")
    else:
        advice.append("It's cold today, so wear warm clothes before going out.")

    if any(word in description for word in ["rain", "drizzle", "shower", "thunderstorm"]):
        advice.append("Take an umbrella or raincoat in case showers start.")
    elif "snow" in description:
        advice.append("Wear warm layers and careful footwear because of snowy conditions.")
    elif any(word in description for word in ["mist", "fog", "haze", "smoke"]):
        advice.append("Visibility may be reduced, so travel carefully.")
    elif "clear" in description:
        advice.append("Skies are clear, so it's a nice day for outdoor plans.")

    if wind >= 10:
        advice.append("Winds are strong, so keep a secure outer layer if you're outside.")

    if humidity >= 80:
        advice.append("Humidity is high, so it may feel warmer than the temperature shows.")
    elif humidity <= 25:
        advice.append("The air is dry today, so staying hydrated will help.")

    return " ".join(advice)


def send_email(
    sender_email: str,
    sender_password: str,
    recipient_email: str,
    weather: dict,
) -> None:
    """
    Send a weather report email using Gmail SMTP.
    """
    subject = "Today's Weather Report"
    daily_advice = build_human_weather_advice(weather)

    body = f"""Hello,

Here is today's weather report:

City: {weather['city']}
Temperature: {weather['temperature']} C
Weather: {weather['description'].title()}
Humidity: {weather['humidity']}%
Wind Speed: {weather['wind_speed']} m/s

Today's Advice:
{daily_advice}

This email was sent by Abdullah Adnan.

Have a great day!
"""

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = recipient_email
    msg.set_content(body)

    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
    except smtplib.SMTPException as exc:
        raise RuntimeError(f"SMTP error while sending email: {exc}") from exc
    except OSError as exc:
        raise RuntimeError(f"Network/system error while sending email: {exc}") from exc


def main() -> None:
    """
    Main workflow:
    1. Read credentials/config from environment variables.
    2. Fetch weather data.
    3. Send weather report email.
    """
    load_env_file()

    email_address = os.getenv("EMAIL_ADDRESS")
    email_password = os.getenv("EMAIL_PASSWORD")
    weather_api_key = os.getenv("WEATHER_API_KEY")
    city = os.getenv("WEATHER_CITY", "Islamabad")
    recipient_email = os.getenv("EMAIL_RECIPIENT", email_address)

    missing_vars = []
    if not email_address:
        missing_vars.append("EMAIL_ADDRESS")
    if not email_password:
        missing_vars.append("EMAIL_PASSWORD")
    if not weather_api_key:
        missing_vars.append("WEATHER_API_KEY")

    if missing_vars:
        raise RuntimeError(
            f"Missing required environment variable(s): {', '.join(missing_vars)}"
        )

    try:
        weather = get_weather(city=city, api_key=weather_api_key)
        send_email(
            sender_email=email_address,
            sender_password=email_password,
            recipient_email=recipient_email,
            weather=weather,
        )
        print("Weather email sent successfully.")
    except RuntimeError as exc:
        print(f"Error: {exc}")


if __name__ == "__main__":
    main()
