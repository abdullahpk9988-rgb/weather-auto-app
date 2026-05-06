import os
import sys
import smtplib
import logging
import requests
from typing import Dict, Any, Tuple
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from openai import OpenAI

# ==========================================
# CONFIGURATION & LOGGING SETUP
# ==========================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

# Constants
CITY = "Islamabad"
COUNTRY = "Pakistan"
OPENWEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"
OPENWEATHER_FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"
ALADHAN_URL = "http://api.aladhan.com/v1/timingsByCity"

# ==========================================
# DATA FETCHING SERVICES
# ==========================================

def get_weather(city: str, api_key: str) -> Dict[str, Any]:
    """Fetches current weather and rain probability from OpenWeatherMap."""
    logger.info(f"Fetching weather data for {city}...")
    params = {"q": city, "appid": api_key, "units": "metric"}
    
    try:
        current_resp = requests.get(OPENWEATHER_URL, params=params)
        current_resp.raise_for_status()
        current = current_resp.json()
        
        forecast_resp = requests.get(OPENWEATHER_FORECAST_URL, params=params)
        forecast_resp.raise_for_status()
        forecast = forecast_resp.json()
        
        rain_prob = int(forecast['list'][0].get('pop', 0) * 100)
        
        return {
            "city": current["name"],
            "temperature": round(current["main"]["temp"]),
            "feels_like": round(current["main"]["feels_like"]),
            "description": current["weather"][0]["description"].title(),
            "humidity": current["main"]["humidity"],
            "wind_speed": round(current["wind"]["speed"]),
            "rain_probability": rain_prob
        }
    except requests.RequestException as e:
        logger.error(f"Failed to fetch weather data: {e}")
        sys.exit(1)

def get_namaz_times(city: str, country: str) -> Dict[str, str]:
    """Fetches and formats daily prayer and sun schedules."""
    logger.info(f"Fetching prayer times for {city}, {country}...")
    params = {"city": city, "country": country, "method": 1}
    
    try:
        response = requests.get(ALADHAN_URL, params=params)
        response.raise_for_status()
        timings = response.json()['data']['timings']
        
        formatted_timings = {}
        for key, value in timings.items():
            clean_time = value.split(" ")[0]
            try:
                time_obj = datetime.strptime(clean_time, "%H:%M")
                # Convert to 12-hour format (e.g., "05:30 AM" -> "5:30 AM")
                formatted_timings[key] = time_obj.strftime("%I:%M %p").lstrip("0")
            except ValueError:
                formatted_timings[key] = clean_time
                
        return formatted_timings
    except requests.RequestException as e:
        logger.error(f"Failed to fetch Namaz times: {e}")
        sys.exit(1)

def get_groq_advice(weather: Dict[str, Any], groq_key: str) -> Tuple[str, str, str]:
    """Generates AI advice using Groq based on current weather."""
    logger.info("Generating AI daily briefing via Groq...")
    client = OpenAI(api_key=groq_key, base_url="https://api.groq.com/openai/v1")
    
    prompt = f"""
    You are a friendly morning weather assistant for {weather['city']}, Pakistan.
    Write ONLY these 3 sections, nothing else. Be concise (2-3 sentences each max).

    WEATHER SUMMARY:
    Write an engaging summary of how today will feel based on {weather['temperature']}C, {weather['description']}, {weather['humidity']}% humidity.

    WHAT TO WEAR:
    Give specific outfit and prep advice based on the weather and {weather['rain_probability']}% rain chance.

    DAILY MOTIVATION:
    One short uplifting sentence to start the day.

    Do NOT use markdown, headers, or bullet points. Just plain paragraph text for each section separated by a new line.
    """
    
    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}]
        )
        advice = response.choices[0].message.content
        
        # Safely parse the AI output
        lines = [l.strip() for l in advice.strip().split('\n') if l.strip()]
        summary = lines[0] if len(lines) > 0 else "Enjoy your day!"
        outfit = lines[1] if len(lines) > 1 else "Dress comfortably."
        motivation = lines[-1] if len(lines) > 2 else "Have a great day ahead!"
        
        return summary, outfit, motivation
    except Exception as e:
        logger.error(f"Failed to generate Groq advice: {e}")
        return "Enjoy your day!", "Dress comfortably.", "Have a great day ahead!"

# ==========================================
# EMAIL CONSTRUCTION & DELIVERY
# ==========================================

def get_weather_icon(description: str) -> str:
    """Returns the appropriate emoji based on the weather description."""
    desc = description.lower()
    if 'rain' in desc: return "🌧️"
    if 'cloud' in desc: return "☁️"
    if 'clear' in desc: return "☀️"
    if 'snow' in desc: return "❄️"
    if 'storm' in desc: return "⛈️"
    if 'haze' in desc or 'fog' in desc: return "🌫️"
    return "🌤️"

def build_html_email(weather: Dict[str, Any], namaz: Dict[str, str], summary: str, outfit: str, motivation: str) -> str:
    """Constructs the final HTML string for the email."""
    logger.info("Building HTML email template...")
    today = datetime.now().strftime("%A, %B %d %Y")
    weather_icon = get_weather_icon(weather['description'])

    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700&family=DM+Sans:wght@300;400;500&display=swap');
      * {{ margin: 0; padding: 0; box-sizing: border-box; }}
      body {{ background: #0f0f1a; font-family: 'DM Sans', sans-serif; color: #e8e8f0; padding: 20px; }}
      .wrapper {{ max-width: 600px; margin: 0 auto; background: linear-gradient(145deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%); border-radius: 24px; overflow: hidden; border: 1px solid rgba(255,255,255,0.08); }}
      .header {{ background: linear-gradient(135deg, #1
