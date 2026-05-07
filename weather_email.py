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
    
    prompt = f"""
    You are a friendly morning weather assistant for {weather['city']}, Pakistan.
    Write ONLY these 3 sections. Be concise (2-3 sentences each max).

    1. Weather Summary based on {weather['temperature']}C, {weather['description']}, {weather['humidity']}% humidity.
    2. What to Wear based on {weather['rain_probability']}% rain chance.
    3. Daily Motivation — one powerful, uplifting sentence.

    CRITICAL INSTRUCTION: Separate each section using exactly three pound signs (###). No section titles. Just the text.
    
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

def build_html_email(weather, namaz, advice, sender_email):
    today_full = datetime.now().strftime("%A, %B %d · %Y")
    today_short = datetime.now().strftime("%d %b %Y")
    
    sections = [s.strip() for s in advice.split('###')]
    summary  = sections[0] if len(sections) > 0 else "Enjoy the weather today!"
    outfit   = sections[1] if len(sections) > 1 else "Dress comfortably."
    motivation = sections[2] if len(sections) > 2 else "Have a great day!"

    desc = weather['description'].lower()
    if 'rain'              in desc: weather_icon = "🌧️"; icon_bg = "#0f2a3f"
    elif 'thunder'         in desc: weather_icon = "⛈️"; icon_bg = "#1a1a0f"
    elif 'cloud'           in desc: weather_icon = "☁️"; icon_bg = "#1a1a2e"
    elif 'clear'           in desc: weather_icon = "☀️"; icon_bg = "#2a1f00"
    elif 'snow'            in desc: weather_icon = "❄️"; icon_bg = "#0f1f2a"
    elif 'haze' in desc or 'fog' in desc: weather_icon = "🌫️"; icon_bg = "#1a1a1a"
    else:                            weather_icon = "🌤️"; icon_bg = "#1a2a1a"

    mailto_link = f"mailto:{sender_email}?subject=Re%3A%20Your%20Daily%20Weather%20%26%20Schedule%20App"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,600;0,700;1,400;1,600&family=Outfit:wght@300;400;500;600&display=swap');

*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

body {{
  background: #06060a;
  font-family: 'Outfit', -apple-system, sans-serif;
  -webkit-font-smoothing: antialiased;
  padding: 32px 12px 64px;
}}

.wrap {{ max-width: 600px; margin: 0 auto; }}

/* ── TOP BAR ── */
.topbar {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 18px;
  padding: 0 4px;
}}
.topbar-brand {{
  font-family: 'Cormorant Garamond', serif;
  font-size: 13px;
  font-weight: 600;
  color: #c8963c;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}}
.topbar-date {{
  font-size: 11px;
  color: #2a2a3a;
  letter-spacing: 0.08em;
  font-weight: 400;
}}

/* ── MAIN CARD ── */
.card {{
  background: #0c0c12;
  border-radius: 24px;
  border: 1px solid rgba(200,150,60,0.12);
  overflow: hidden;
  box-shadow:
    0 0 0 1px rgba(255,255,255,0.03),
    0 32px 64px rgba(0,0,0,0.7),
    0 0 80px rgba(200,150,60,0.04);
}}

/* ── HERO ── */
.hero {{
  position: relative;
  padding: 0;
  overflow: hidden;
  min-height: 280px;
  background: linear-gradient(160deg, #0e0e1a 0%, #12100a 50%, #0a0a0e 100%);
}}
.hero-noise {{
  position: absolute;
  inset: 0;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)' opacity='0.04'/%3E%3C/svg%3E");
  opacity: 0.6;
  pointer-events: none;
}}
.hero-glow-top {{
  position: absolute;
  top: -80px; left: 50%;
  transform: translateX(-50%);
  width: 400px; height: 300px;
  background: radial-gradient(ellipse, rgba(200,150,60,0.12) 0%, transparent 70%);
  pointer-events: none;
}}
.hero-glow-side {{
  position: absolute;
  bottom: -40px; right: -60px;
  width: 200px; height: 200px;
  background: radial-gradient(circle, rgba(200,150,60,0.06) 0%, transparent 70%);
  pointer-events: none;
}}
.hero-content {{
  position: relative;
  z-index: 2;
  padding: 40px 36px 36px;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
}}
.hero-left {{ flex: 1; }}
.hero-eyebrow {{
  display: inline-flex;
  align-items: center;
  gap: 7px;
  background: rgba(200,150,60,0.08);
  border: 1px solid rgba(200,150,60,0.18);
  border-radius: 99px;
  padding: 5px 13px;
  margin-bottom: 18px;
}}
.eyebrow-dot {{
  width: 5px; height: 5px;
  border-radius: 50%;
  background: #c8963c;
  box-shadow: 0 0 6px rgba(200,150,60,0.6);
}}
.eyebrow-text {{
  font-size: 10px;
  font-weight: 500;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: #c8963c;
}}
.hero-city {{
  font-family: 'Cormorant Garamond', serif;
  font-size: 52px;
  font-weight: 700;
  color: #f5f0e8;
  line-height: 0.95;
  letter-spacing: -1px;
}}
.hero-country {{
  font-size: 12px;
  color: #3a3020;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  margin-top: 10px;
  font-weight: 500;
}}
.hero-right {{
  text-align: right;
  padding-top: 8px;
}}
.temp-big {{
  font-family: 'Cormorant Garamond', serif;
  font-size: 88px;
  font-weight: 600;
  color: #ffffff;
  line-height: 1;
  letter-spacing: -4px;
}}
.temp-deg {{
  font-size: 40px;
  color: #c8963c;
  vertical-align: super;
  letter-spacing: 0;
}}
.weather-icon-hero {{
  font-size: 28px;
  display: block;
  margin-bottom: 4px;
  text-align: right;
}}
.temp-desc {{
  font-size: 14px;
  color: #6a5a3a;
  margin-top: 4px;
  font-weight: 300;
  letter-spacing: 0.04em;
}}
.temp-feels {{
  font-size: 12px;
  color: #3a3020;
  margin-top: 3px;
}}

/* ── GOLD DIVIDER ── */
.gold-rule {{
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(200,150,60,0.4) 30%, rgba(200,150,60,0.4) 70%, transparent);
  margin: 0 36px;
}}

/* ── STATS BAR ── */
.stats-bar {{
  display: flex;
  margin: 0;
  border-bottom: 1px solid rgba(255,255,255,0.04);
}}
.stat {{
  flex: 1;
  text-align: center;
  padding: 18px 8px;
  border-right: 1px solid rgba(255,255,255,0.04);
  position: relative;
}}
.stat:last-child {{ border-right: none; }}
.stat-icon {{ font-size: 18px; display: block; margin-bottom: 6px; }}
.stat-val {{
  font-family: 'Cormorant Garamond', serif;
  font-size: 22px;
  font-weight: 600;
  color: #e8dcc8;
  letter-spacing: -0.5px;
}}
.stat-lbl {{
  font-size: 9.5px;
  text-transform: uppercase;
  letter-spacing: 0.14em;
  color: #2a2518;
  margin-top: 3px;
  font-weight: 500;
}}

/* ── CONTENT SECTIONS ── */
.sections {{ padding: 8px 0; }}

.sec {{
  padding: 24px 36px;
  border-bottom: 1px solid rgba(255,255,255,0.03);
  display: flex;
  gap: 20px;
  align-items: flex-start;
}}
.sec:last-child {{ border-bottom: none; }}

.sec-left {{
  flex-shrink: 0;
  width: 36px;
  text-align: center;
  padding-top: 2px;
}}
.sec-num {{
  font-family: 'Cormorant Garamond', serif;
  font-size: 11px;
  font-weight: 600;
  color: #c8963c;
  letter-spacing: 0.1em;
  display: block;
  margin-top: 6px;
}}
.sec-icon {{ font-size: 22px; display: block; }}

.sec-right {{ flex: 1; }}
.sec-label {{
  font-size: 9.5px;
  text-transform: uppercase;
  letter-spacing: 0.18em;
  color: #3a3020;
  font-weight: 600;
  margin-bottom: 8px;
  display: block;
}}
.sec-body {{
  font-size: 15px;
  line-height: 1.75;
  color: #b8a888;
  font-weight: 300;
}}

/* ── NAMAZ GRID ── */
.namaz-grid {{
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 8px;
  margin-top: 2px;
}}
.namaz-cell {{
  background: rgba(200,150,60,0.04);
  border: 1px solid rgba(200,150,60,0.1);
  border-radius: 12px;
  padding: 12px 10px;
  text-align: center;
}}
.namaz-emoji {{ font-size: 16px; display: block; margin-bottom: 5px; }}
.namaz-name {{
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: #4a3a20;
  font-weight: 600;
  display: block;
  margin-bottom: 4px;
}}
.namaz-time {{
  font-family: 'Cormorant Garamond', serif;
  font-size: 15px;
  font-weight: 600;
  color: #c8963c;
  letter-spacing: -0.2px;
}}

/* ── MOTIVATION ── */
.motivation-wrap {{
  margin: 4px 36px 28px;
  background: linear-gradient(135deg, rgba(200,150,60,0.06), rgba(200,150,60,0.02));
  border: 1px solid rgba(200,150,60,0.15);
  border-radius: 18px;
  padding: 28px 30px;
  text-align: center;
  position: relative;
  overflow: hidden;
}}
.motivation-wrap::before {{
  content: '\u201C';
  position: absolute;
  top: -10px; left: 16px;
  font-family: 'Cormorant Garamond', serif;
  font-size: 80px;
  color: rgba(200,150,60,0.08);
  line-height: 1;
  pointer-events: none;
}}
.motivation-text {{
  font-family: 'Cormorant Garamond', serif;
  font-size: 20px;
  font-weight: 400;
  font-style: italic;
  color: #c8963c;
  line-height: 1.55;
  position: relative;
  z-index: 1;
}}

/* ── REPLY BUTTON ── */
.reply-wrap {{
  padding: 4px 36px 28px;
  text-align: center;
}}
.reply-btn {{
  display: inline-block;
  background: linear-gradient(135deg, #c8963c, #e8b84a);
  color: #0a0806 !important;
  text-decoration: none !important;
  font-family: 'Outfit', sans-serif;
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.06em;
  padding: 14px 36px;
  border-radius: 99px;
  box-shadow: 0 8px 32px rgba(200,150,60,0.25), 0 2px 8px rgba(200,150,60,0.15);
}}
.reply-hint {{
  font-size: 11px;
  color: #2a2518;
  margin-top: 10px;
  letter-spacing: 0.04em;
  font-weight: 400;
}}

/* ── FOOTER ── */
.footer {{
  padding: 18px 36px 22px;
  border-top: 1px solid rgba(255,255,255,0.04);
  display: flex;
  align-items: center;
  justify-content: space-between;
}}
.footer-left {{
  font-size: 10.5px;
  color: #1e1810;
  letter-spacing: 0.08em;
  font-family: 'Courier New', monospace;
}}
.footer-right {{
  font-family: 'Cormorant Garamond', serif;
  font-size: 13px;
  font-weight: 600;
  color: #3a3020;
  letter-spacing: 0.06em;
}}
.footer-right span {{ color: #c8963c; }}

/* ── BOTTOM ── */
.bottom {{
  text-align: center;
  margin-top: 20px;
  font-size: 10px;
  color: #18140c;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  font-weight: 500;
}}
</style>
</head>
<body>
<div class="wrap">

  <div class="topbar">
    <span class="topbar-brand">Daily Briefing</span>
    <span class="topbar-date">{today_short}</span>
  </div>

  <div class="card">

    <!-- HERO -->
    <div class="hero">
      <div class="hero-noise"></div>
      <div class="hero-glow-top"></div>
      <div class="hero-glow-side"></div>
      <div class="hero-content">
        <div class="hero-left">
          <div class="hero-eyebrow">
            <div class="eyebrow-dot"></div>
            <span class="eyebrow-text">{today_full}</span>
          </div>
          <div class="hero-city">{weather['city']}</div>
          <div class="hero-country">Islamic Republic of Pakistan</div>
        </div>
        <div class="hero-right">
          <span class="weather-icon-hero">{weather_icon}</span>
          <div class="temp-big">{weather['temperature']}<span class="temp-deg">°</span></div>
          <div class="temp-desc">{weather['description']}</div>
          <div class="temp-feels">Feels like {weather['feels_like']}°C</div>
        </div>
      </div>
    </div>

    <!-- GOLD RULE -->
    <div class="gold-rule"></div>

    <!-- STATS -->
    <div class="stats-bar">
      <div class="stat">
        <span class="stat-icon">💧</span>
        <div class="stat-val">{weather['humidity']}%</div>
        <div class="stat-lbl">Humidity</div>
      </div>
      <div class="stat">
        <span class="stat-icon">🌂</span>
        <div class="stat-val">{weather['rain_probability']}%</div>
        <div class="stat-lbl">Rain</div>
      </div>
      <div class="stat">
        <span class="stat-icon">💨</span>
        <div class="stat-val">{weather['wind_speed']} m/s</div>
        <div class="stat-lbl">Wind</div>
      </div>
    </div>

    <!-- SECTIONS -->
    <div class="sections">

      <div class="sec">
        <div class="sec-left">
          <span class="sec-icon">🌤️</span>
          <span class="sec-num">01</span>
        </div>
        <div class="sec-right">
          <span class="sec-label">Weather Summary</span>
          <div class="sec-body">{summary}</div>
        </div>
      </div>

      <div class="sec">
        <div class="sec-left">
          <span class="sec-icon">👕</span>
          <span class="sec-num">02</span>
        </div>
        <div class="sec-right">
          <span class="sec-label">What to Wear &amp; Prep</span>
          <div class="sec-body">{outfit}</div>
        </div>
      </div>

      <div class="sec">
        <div class="sec-left">
          <span class="sec-icon">🕌</span>
          <span class="sec-num">03</span>
        </div>
        <div class="sec-right">
          <span class="sec-label">Prayer &amp; Sun Schedule</span>
          <div class="namaz-grid">
            <div class="namaz-cell">
              <span class="namaz-emoji">🌅</span>
              <span class="namaz-name">Fajr</span>
              <span class="namaz-time">{namaz['Fajr']}</span>
            </div>
            <div class="namaz-cell">
              <span class="namaz-emoji">☀️</span>
              <span class="namaz-name">Sunrise</span>
              <span class="namaz-time">{namaz['Sunrise']}</span>
            </div>
            <div class="namaz-cell">
              <span class="namaz-emoji">🌞</span>
              <span class="namaz-name">Dhuhr</span>
              <span class="namaz-time">{namaz['Dhuhr']}</span>
            </div>
            <div class="namaz-cell">
              <span class="namaz-emoji">🌇</span>
              <span class="namaz-name">Asr</span>
              <span class="namaz-time">{namaz['Asr']}</span>
            </div>
            <div class="namaz-cell">
              <span class="namaz-emoji">🌆</span>
              <span class="namaz-name">Maghrib</span>
              <span class="namaz-time">{namaz['Maghrib']}</span>
            </div>
            <div class="namaz-cell">
              <span class="namaz-emoji">🌙</span>
              <span class="namaz-name">Isha</span>
              <span class="namaz-time">{namaz['Isha']}</span>
            </div>
          </div>
        </div>
      </div>

    </div>

    <!-- MOTIVATION -->
    <div class="motivation-wrap">
      <div class="motivation-text">{motivation}</div>
    </div>

    <!-- REPLY BUTTON -->
    <div class="reply-wrap">
      <a href="{mailto_link}" class="reply-btn">💬 &nbsp; Ask a Question</a>
      <div class="reply-hint">Have a question about today's weather? Just hit reply — AI answers instantly.</div>
    </div>

    <!-- FOOTER -->
    <div class="footer">
      <div class="footer-left">auto-delivered · islamabad · pkT</div>
      <div class="footer-right">by <span>Abdullah Adnan</span></div>
    </div>

  </div>

  <div class="bottom">Powered by Groq &amp; OpenWeather · Built by Abdullah</div>

</div>
</body>
</html>"""
    return html

def send_email(sender_email, sender_password, recipient_email, weather, namaz, advice):
    subject = "🌤️ Your Daily Weather & Schedule — Islamabad"
    
    html_content = build_html_email(weather, namaz, advice, sender_email)
    
    msg = MIMEMultipart('alternative')
    msg["Subject"] = subject
    msg["From"]    = sender_email
    msg["To"]      = recipient_email
    
    msg.attach(MIMEText(html_content, 'html', 'utf-8'))

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)

def main():
    email       = os.environ["EMAIL_ADDRESS"]
    password    = os.environ["EMAIL_PASSWORD"]
    weather_key = os.environ["WEATHER_API_KEY"]
    groq_key    = os.environ["GROQ_API_KEY"]
    recipient   = os.environ.get("EMAIL_RECIPIENT", "adspk243@gmail.com")
    
    city = "Islamabad"
    
    weather_data = get_weather(city, weather_key)
    namaz_data   = get_namaz_times(city)
    daily_advice = get_groq_advice(weather_data, namaz_data, groq_key)
    
    send_email(email, password, recipient, weather_data, namaz_data, daily_advice)

if __name__ == "__main__":
    main()
