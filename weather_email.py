import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import requests
from openai import OpenAI
from datetime import datetime

def get_weather(city, api_key):
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {"q": city, "appid": api_key, "units": "metric"}
    current = requests.get(url, params=params).json()
    
    forecast_url = "https://api.openweathermap.org/data/2.5/forecast"
    forecast = requests.get(forecast_url, params=params).json()
    
    rain_prob = int(forecast['list'][0]['pop'] * 100)
    
    return {
        "city": current["name"],
        "temperature": round(current["main"]["temp"]),
        "feels_like": round(current["main"]["feels_like"]),
        "description": current["weather"][0]["description"].title(),
        "humidity": current["main"]["humidity"],
        "wind_speed": round(current["wind"]["speed"]),
        "rain_probability": rain_prob
    }

def get_namaz_times(city):
    url = f"http://api.aladhan.com/v1/timingsByCity?city={city}&country=Pakistan&method=1"
    response = requests.get(url).json()
    timings = response['data']['timings']
    
    for key, value in timings.items():
        clean_time = value.split(" ")[0]
        try:
            time_obj = datetime.strptime(clean_time, "%H:%M")
            timings[key] = time_obj.strftime("%I:%M %p").lstrip("0")
        except Exception:
            pass
            
    return timings

def get_groq_advice(weather, namaz, groq_key):
    client = OpenAI(api_key=groq_key, base_url="https://api.groq.com/openai/v1")
    
    # FIX: Updated prompt to force the AI to use a strict '###' divider
    prompt = f"""
    You are a friendly morning weather assistant for {weather['city']}, Pakistan.
    Write ONLY these 3 sections. Be concise (2-3 sentences each max).

    1. Weather Summary based on {weather['temperature']}C, {weather['description']}, {weather['humidity']}% humidity.
    2. What to Wear based on {weather['rain_probability']}% rain chance.
    3. Daily Motivation

    CRITICAL INSTRUCTION: You must separate each section using exactly three pound signs (###). Do NOT include section titles or headers. Just the text.
    
    Example format:
    Today is sunny and warm...
    ###
    Wear a light t-shirt...
    ###
    Go out there and crush it!
    """
    
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

def build_html_email(weather, namaz, advice):
    today = datetime.now().strftime("%A, %B %d %Y")
    
    # FIX: Parse advice sections safely using the ### delimiter so newlines don't break it
    sections = [s.strip() for s in advice.split('###')]
    summary = sections[0] if len(sections) > 0 else "Enjoy the weather today!"
    outfit = sections[1] if len(sections) > 1 else "Dress comfortably."
    motivation = sections[2] if len(sections) > 2 else "Have a great day!"

    # Weather icon based on description
    desc = weather['description'].lower()
    if 'rain' in desc: weather_icon = "🌧️"
    elif 'cloud' in desc: weather_icon = "☁️"
    elif 'clear' in desc: weather_icon = "☀️"
    elif 'snow' in desc: weather_icon = "❄️"
    elif 'storm' in desc: weather_icon = "⛈️"
    elif 'haze' in desc or 'fog' in desc: weather_icon = "🌫️"
    else: weather_icon = "🌤️"

    html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
  @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700&family=DM+Sans:wght@300;400;500&display=swap');
  
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  
  body {{
    background: #0f0f1a;
    font-family: 'DM Sans', sans-serif;
    color: #e8e8f0;
    padding: 20px;
  }}
  
  .wrapper {{
    max-width: 600px;
    margin: 0 auto;
    background: linear-gradient(145deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
    border-radius: 24px;
    overflow: hidden;
    border: 1px solid rgba(255,255,255,0.08);
  }}

  /* HEADER */
  .header {{
    background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
    padding: 40px 36px 32px;
    text-align: center;
    position: relative;
  }}
  .header::after {{
    content: '';
    position: absolute;
    bottom: -1px; left: 0; right: 0;
    height: 40px;
    background: #1a1a2e;
    clip-path: ellipse(55% 100% at 50% 100%);
  }}
  .date-badge {{
    display: inline-block;
    background: rgba(255,255,255,0.12);
    border: 1px solid rgba(255,255,255,0.2);
    border-radius: 20px;
    padding: 6px 16px;
    font-size: 12px;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    margin-bottom: 20px;
    color: #a8c4e8;
  }}
  .city-name {{
    font-family: 'Playfair Display', serif;
    font-size: 36px;
    font-weight: 700;
    color: #ffffff;
    margin-bottom: 6px;
    letter-spacing: -0.5px;
  }}
  .country {{
    font-size: 13px;
    color: #7eadd4;
    letter-spacing: 2px;
    text-transform: uppercase;
  }}

  /* TEMP HERO */
  .temp-hero {{
    text-align: center;
    padding: 40px 36px 20px;
  }}
  .weather-icon {{
    font-size: 64px;
    line-height: 1;
    margin-bottom: 12px;
    display: block;
  }}
  .temp-display {{
    font-family: 'Playfair Display', serif;
    font-size: 80px;
    font-weight: 700;
    color: #ffffff;
    line-height: 1;
    letter-spacing: -3px;
  }}
  .temp-unit {{
    font-size: 36px;
    color: #7eadd4;
    vertical-align: super;
  }}
  .weather-desc {{
    font-size: 18px;
    color: #a8c4e8;
    margin-top: 8px;
    font-weight: 300;
    letter-spacing: 0.5px;
  }}
  .feels-like {{
    font-size: 13px;
    color: #6a8aaa;
    margin-top: 6px;
  }}

  /* STATS ROW */
  .stats-row {{
    display: flex;
    margin: 24px 36px;
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 16px;
    overflow: hidden;
  }}
  .stat {{
    flex: 1;
    text-align: center;
    padding: 16px 8px;
    border-right: 1px solid rgba(255,255,255,0.06);
  }}
  .stat:last-child {{ border-right: none; }}
  .stat-icon {{ font-size: 20px; display: block; margin-bottom: 6px; }}
  .stat-value {{ font-size: 18px; font-weight: 500; color: #ffffff; }}
  .stat-label {{ font-size: 11px; color: #5a7a9a; text-transform: uppercase; letter-spacing: 1px; margin-top: 2px; }}

  /* SECTIONS */
  .section {{
    margin: 0 36px 24px;
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 16px;
    padding: 24px;
  }}
  .section-header {{
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 14px;
  }}
  .section-icon {{ font-size: 20px; }}
  .section-title {{
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 2px;
    color: #5a7a9a;
    font-weight: 500;
  }}
  .section-body {{
    font-size: 15px;
    line-height: 1.7;
    color: #c8d8e8;
    font-weight: 300;
  }}

  /* NAMAZ GRID */
  .namaz-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
    margin-top: 4px;
  }}
  .namaz-item {{
    background: rgba(255,255,255,0.04);
    border-radius: 10px;
    padding: 12px 14px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }}
  .namaz-name {{
    font-size: 13px;
    color: #7eadd4;
    font-weight: 500;
  }}
  .namaz-time {{
    font-size: 13px;
    color: #ffffff;
    font-weight: 400;
  }}

  /* MOTIVATION */
  .motivation {{
    margin: 0 36px 24px;
    background: linear-gradient(135deg, rgba(30,60,114,0.5), rgba(42,82,152,0.3));
    border: 1px solid rgba(126,173,212,0.2);
    border-radius: 16px;
    padding: 24px;
    text-align: center;
  }}
  .motivation-text {{
    font-family: 'Playfair Display', serif;
    font-size: 17px;
    color: #a8c4e8;
    line-height: 1.6;
    font-style: italic;
  }}

  /* FOOTER */
  .footer {{
    text-align: center;
    padding: 20px 36px 32px;
    border-top: 1px solid rgba(255,255,255,0.05);
  }}
  .footer-text {{
    font-size: 12px;
    color: #3a5a7a;
    letter-spacing: 0.5px;
  }}
  .footer-brand {{
    font-size: 13px;
    color: #5a7a9a;
    margin-top: 6px;
    font-weight: 500;
  }}
</style>
</head>
<body>
<div class="wrapper">

  <!-- HEADER -->
  <div class="header">
    <div class="date-badge">{today}</div>
    <div class="city-name">{weather['city']}</div>
    <div class="country">Pakistan &nbsp;|&nbsp; Daily Briefing</div>
  </div>

  <!-- TEMP HERO -->
  <div class="temp-hero">
    <span class="weather-icon">{weather_icon}</span>
    <div>
      <span class="temp-display">{weather['temperature']}<span class="temp-unit">°C</span></span>
    </div>
    <div class="weather-desc">{weather['description']}</div>
    <div class="feels-like">Feels like {weather['feels_like']}°C</div>
  </div>

  <!-- STATS ROW -->
  <div class="stats-row">
    <div class="stat">
      <span class="stat-icon">💧</span>
      <div class="stat-value">{weather['humidity']}%</div>
      <div class="stat-label">Humidity</div>
    </div>
    <div class="stat">
      <span class="stat-icon">🌂</span>
      <div class="stat-value">{weather['rain_probability']}%</div>
      <div class="stat-label">Rain</div>
    </div>
    <div class="stat">
      <span class="stat-icon">💨</span>
      <div class="stat-value">{weather['wind_speed']} m/s</div>
      <div class="stat-label">Wind</div>
    </div>
  </div>

  <!-- WEATHER SUMMARY -->
  <div class="section">
    <div class="section-header">
      <span class="section-icon">🌤️</span>
      <span class="section-title">Weather Summary</span>
    </div>
    <div class="section-body">{summary}</div>
  </div>

  <!-- WHAT TO WEAR -->
  <div class="section">
    <div class="section-header">
      <span class="section-icon">👕</span>
      <span class="section-title">What to Wear & Prep</span>
    </div>
    <div class="section-body">{outfit}</div>
  </div>

  <!-- NAMAZ TIMES -->
  <div class="section">
    <div class="section-header">
      <span class="section-icon">🕌</span>
      <span class="section-title">Prayer & Sun Schedule</span>
    </div>
    <div class="namaz-grid">
      <div class="namaz-item"><span class="namaz-name">🌅 Fajr</span><span class="namaz-time">{namaz['Fajr']}</span></div>
      <div class="namaz-item"><span class="namaz-name">☀️ Sunrise</span><span class="namaz-time">{namaz['Sunrise']}</span></div>
      <div class="namaz-item"><span class="namaz-name">🌞 Dhuhr</span><span class="namaz-time">{namaz['Dhuhr']}</span></div>
      <div class="namaz-item"><span class="namaz-name">🌇 Asr</span><span class="namaz-time">{namaz['Asr']}</span></div>
      <div class="namaz-item"><span class="namaz-name">🌆 Maghrib</span><span class="namaz-time">{namaz['Maghrib']}</span></div>
      <div class="namaz-item"><span class="namaz-name">🌙 Isha</span><span class="namaz-time">{namaz['Isha']}</span></div>
    </div>
  </div>

  <!-- MOTIVATION -->
  <div class="motivation">
    <div class="motivation-text">"{motivation}"</div>
  </div>

  <!-- FOOTER -->
  <div class="footer">
    <div class="footer-text">Delivered fresh every morning ☕</div>
    <div class="footer-brand">✨ Made &amp; Designed by Abdullah</div>
  </div>

</div>
</body>
</html>
"""
    return html

def send_email(sender_email, sender_password, recipient_email, weather, namaz, advice):
    subject = "📱 Your Daily Weather & Schedule App"
    
    html_content = build_html_email(weather, namaz, advice)
    
    msg = MIMEMultipart('alternative')
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = recipient_email
    
    # Attach HTML version
    msg.attach(MIMEText(html_content, 'html', 'utf-8'))

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)

def main():
    email = os.environ["EMAIL_ADDRESS"]
    password = os.environ["EMAIL_PASSWORD"]
    weather_key = os.environ["WEATHER_API_KEY"]
    groq_key = os.environ["GROQ_API_KEY"]
    recipient = os.environ.get("EMAIL_RECIPIENT", "adspk243@gmail.com")
    
    city = "Islamabad"
    
    weather_data = get_weather(city, weather_key)
    namaz_data = get_namaz_times(city)
    daily_advice = get_groq_advice(weather_data, namaz_data, groq_key)
    
    send_email(email, password, recipient, weather_data, namaz_data, daily_advice)

if __name__ == "__main__":
    main()
