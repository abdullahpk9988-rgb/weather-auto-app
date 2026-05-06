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
      .header {{ background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%); padding: 40px 36px 32px; text-align: center; position: relative; }}
      .header::after {{ content: ''; position: absolute; bottom: -1px; left: 0; right: 0; height: 40px; background: #1a1a2e; clip-path: ellipse(55% 100% at 50% 100%); }}
      .date-badge {{ display: inline-block; background: rgba(255,255,255,0.12); border: 1px solid rgba(255,255,255,0.2); border-radius: 20px; padding: 6px 16px; font-size: 12px; letter-spacing: 1.5px; text-transform: uppercase; margin-bottom: 20px; color: #a8c4e8; }}
      .city-name {{ font-family: 'Playfair Display', serif; font-size: 36px; font-weight: 700; color: #ffffff; margin-bottom: 6px; letter-spacing: -0.5px; }}
      .country {{ font-size: 13px; color: #7eadd4; letter-spacing: 2px; text-transform: uppercase; }}
      .temp-hero {{ text-align: center; padding: 40px 36px 20px; }}
      .weather-icon {{ font-size: 64px; line-height: 1; margin-bottom: 12px; display: block; }}
      .temp-display {{ font-family: 'Playfair Display', serif; font-size: 80px; font-weight: 700; color: #ffffff; line-height: 1; letter-spacing: -3px; }}
      .temp-unit {{ font-size: 36px; color: #7eadd4; vertical-align: super; }}
      .weather-desc {{ font-size: 18px; color: #a8c4e8; margin-top: 8px; font-weight: 300; letter-spacing: 0.5px; }}
      .feels-like {{ font-size: 13px; color: #6a8aaa; margin-top: 6px; }}
      .stats-row {{ display: flex; margin: 24px 36px; background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08); border-radius: 16px; overflow: hidden; }}
      .stat {{ flex: 1; text-align: center; padding: 16px 8px; border-right: 1px solid rgba(255,255,255,0.06); }}
      .stat:last-child {{ border-right: none; }}
      .stat-icon {{ font-size: 20px; display: block; margin-bottom: 6px; }}
      .stat-value {{ font-size: 18px; font-weight: 500; color: #ffffff; }}
      .stat-label {{ font-size: 11px; color: #5a7a9a; text-transform: uppercase; letter-spacing: 1px; margin-top: 2px; }}
      .section {{ margin: 0 36px 24px; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.07); border-radius: 16px; padding: 24px; }}
      .section-header {{ display: flex; align-items: center; gap: 10px; margin-bottom: 14px; }}
      .section-icon {{ font-size: 20px; }}
      .section-title {{ font-size: 11px; text-transform: uppercase; letter-spacing: 2px; color: #5a7a9a; font-weight: 500; }}
      .section-body {{ font-size: 15px; line-height: 1.7; color: #c8d8e8; font-weight: 300; }}
      .namaz-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 4px; }}
      .namaz-item {{ background: rgba(255,255,255,0.04); border-radius: 10px; padding: 12px 14px; display: flex; justify-content: space-between; align-items: center; }}
      .namaz-name {{ font-size: 13px; color: #7eadd4; font-weight: 500; }}
      .namaz-time {{ font-size: 13px; color: #ffffff; font-weight: 400; }}
      .motivation {{ margin: 0 36px 24px; background: linear-gradient(135deg, rgba(30,60,114,0.5), rgba(42,82,152,0.3)); border: 1px solid rgba(126,173,212,0.2); border-radius: 16px; padding: 24px; text-align: center; }}
      .motivation-text {{ font-family: 'Playfair Display', serif; font-size: 17px; color: #a8c4e8; line-height: 1.6; font-style: italic; }}
      .footer {{ text-align: center; padding: 20px 36px 32px; border-top: 1px solid rgba(255,255,255,0.05); }}
      .footer-text {{ font-size: 12px; color: #3a5a7a; letter-spacing: 0.5px; }}
      .footer-brand {{ font-size: 13px; color: #5a7a9a; margin-top: 6px; font-weight: 500; }}
    </style>
    </head>
    <body>
    <div class="wrapper">
      <div class="header">
        <div class="date-badge">{today}</div>
        <div class="city-name">{weather['city']}</div>
        <div class="country">{COUNTRY} &nbsp;|&nbsp; Daily Briefing</div>
      </div>
      <div class="temp-hero">
        <span class="weather-icon">{weather_icon}</span>
        <div><span class="temp-display">{weather['temperature']}<span class="temp-unit">°C</span></span></div>
        <div class="weather-desc">{weather['description']}</div>
        <div class="feels-like">Feels like {weather['feels_like']}°C</div>
      </div>
      <div class="stats-row">
        <div class="stat"><span class="stat-icon">💧</span><div class="stat-value">{weather['humidity']}%</div><div class="stat-label">Humidity</div></div>
        <div class="stat"><span class="stat-icon">🌂</span><div class="stat-value">{weather['rain_probability']}%</div><div class="stat-label">Rain</div></div>
        <div class="stat"><span class="stat-icon">💨</span><div class="stat-value">{weather['wind_speed']} m/s</div><div class="stat-label">Wind</div></div>
      </div>
      <div class="section">
        <div class="section-header"><span class="section-icon">🌤️</span><span class="section-title">Weather Summary</span></div>
        <div class="section-body">{summary}</div>
      </div>
      <div class="section">
        <div class="section-header"><span class="section-icon">👕</span><span class="section-title">What to Wear & Prep</span></div>
        <div class="section-body">{outfit}</div>
      </div>
      <div class="section">
        <div class="section-header"><span class="section-icon">🕌</span><span class="section-title">Prayer & Sun Schedule</span></div>
        <div class="namaz-grid">
          <div class="namaz-item"><span class="namaz-name">🌅 Fajr</span><span class="namaz-time">{namaz.get('Fajr', 'N/A')}</span></div>
          <div class="namaz-item"><span class="namaz-name">☀️ Sunrise</span><span class="namaz-time">{namaz.get('Sunrise', 'N/A')}</span></div>
          <div class="namaz-item"><span class="namaz-name">🌞 Dhuhr</span><span class="namaz-time">{namaz.get('Dhuhr', 'N/A')}</span></div>
          <div class="namaz-item"><span class="namaz-name">🌇 Asr</span><span class="namaz-time">{namaz.get('Asr', 'N/A')}</span></div>
          <div class="namaz-item"><span class="namaz-name">🌆 Maghrib</span><span class="namaz-time">{namaz.get('Maghrib', 'N/A')}</span></div>
          <div class="namaz-item"><span class="namaz-name">🌙 Isha</span><span class="namaz-time">{namaz.get('Isha', 'N/A')}</span></div>
        </div>
      </div>
      <div class="motivation">
        <div class="motivation-text">"{motivation}"</div>
      </div>
      <div class="footer">
        <div class="footer-text">Delivered fresh every morning ☕</div>
        <div class="footer-brand">✨ Made &amp; Designed by Abdullah</div>
      </div>
    </div>
    </body>
    </html>
    """

def send_email(sender_email: str, sender_password: str, recipient_email: str, html_content: str) -> None:
    """Connects to Gmail SMTP and dispatches the HTML email."""
    logger.info(f"Sending daily briefing to {recipient_email}...")
    
    msg = MIMEMultipart('alternative')
    msg["Subject"] = "📱 Your Daily Weather & Schedule App"
    msg["From"] = sender_email
    msg["To"] = recipient_email
    msg.attach(MIMEText(html_content, 'html', 'utf-8'))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
        logger.info("✅ Email successfully delivered!")
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        sys.exit(1)

# ==========================================
# MAIN EXECUTION PIPELINE
# ==========================================

def validate_environment() -> None:
    """Ensures all required environment variables exist before running."""
    required_keys = ["EMAIL_ADDRESS", "EMAIL_PASSWORD", "WEATHER_API_KEY", "GROQ_API_KEY"]
    missing = [key for key in required_keys if key not in os.environ]
    if missing:
        logger.error(f"Missing environment variables: {', '.join(missing)}")
        sys.exit(1)

def main():
    logger.info("Starting Daily Weather App Pipeline...")
    validate_environment()

    # Load Credentials
    email = os.environ["EMAIL_ADDRESS"]
    password = os.environ["EMAIL_PASSWORD"]
    weather_key = os.environ["WEATHER_API_KEY"]
    groq_key = os.environ["GROQ_API_KEY"]
    recipient = os.environ.get("EMAIL_RECIPIENT", "adspk243@gmail.com")
    
    # 1. Fetch Data
    weather_data = get_weather(CITY, weather_key)
    namaz_data = get_namaz_times(CITY, COUNTRY)
    
    # 2. Process AI Text
    summary, outfit, motivation = get_groq_advice(weather_data, groq_key)
    
    # 3. Build & Send
    html_payload = build_html_email(weather_data, namaz_data, summary, outfit, motivation)
    send_email(email, password, recipient, html_payload)

if __name__ == "__main__":
    main()
