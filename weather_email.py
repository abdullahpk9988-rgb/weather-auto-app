import os
import smtplib
from email.message import EmailMessage
import requests
from openai import OpenAI
from datetime import datetime

def get_weather(city, api_key):
    # Get current weather, sunrise, sunset
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {"q": city, "appid": api_key, "units": "metric"}
    current = requests.get(url, params=params).json()
    
    # Get forecast for rain probability
    forecast_url = "https://api.openweathermap.org/data/2.5/forecast"
    forecast = requests.get(forecast_url, params=params).json()
    
    # Extract data
    rain_prob = int(forecast['list'][0]['pop'] * 100) # Convert to percentage
    sunrise = datetime.fromtimestamp(current['sys']['sunrise']).strftime('%I:%M %p')
    sunset = datetime.fromtimestamp(current['sys']['sunset']).strftime('%I:%M %p')
    
    return {
        "city": current["name"],
        "temperature": current["main"]["temp"],
        "description": current["weather"][0]["description"],
        "rain_probability": rain_prob,
        "sunrise": sunrise,
        "sunset": sunset
    }

def get_namaz_times(city):
    # Free API for Namaz times
    url = f"http://api.aladhan.com/v1/timingsByCity?city={city}&country=Pakistan&method=1"
    response = requests.get(url).json()
    return response['data']['timings']

def get_groq_advice(weather, namaz, groq_key):
    client = OpenAI(
        api_key=groq_key,
        base_url="https://api.groq.com/openai/v1"
    )
    
    # The Mega-Prompt
    prompt = f"""
    You are a highly intelligent and helpful morning assistant. Write a daily briefing for the user based on this data for {weather['city']}.
    
    Current Temp: {weather['temperature']}°C
    Condition: {weather['description']}
    Rain Probability: {weather['rain_probability']}%
    Sunrise: {weather['sunrise']}
    Sunset: {weather['sunset']}
    
    Namaz Times Today:
    Fajr: {namaz['Fajr']}
    Dhuhr: {namaz['Dhuhr']}
    Asr: {namaz['Asr']}
    Maghrib: {namaz['Maghrib']}
    Isha: {namaz['Isha']}
    
    Please format the email clearly with these sections:
    1. A quick summary of the day's weather (predict how the morning, afternoon, and night will feel).
    2. Specific clothing and preparation advice for the day (e.g., if rain probability is high, mention an umbrella).
    3. A clean, easy-to-read schedule of the Namaz times alongside the Sunrise/Sunset times.
    4. A short, motivating closing thought.
    """
    
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

def send_email(sender_email, sender_password, recipient_email, advice):
    subject = "🌅 Your Ultimate Daily Briefing & Schedule"
    
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender_email
    # Fixed: Now sending directly to your target email
    msg["To"] = recipient_email 
    msg.set_content(advice)

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)

def main():
    email = os.environ["EMAIL_ADDRESS"]
    password = os.environ["EMAIL_PASSWORD"]
    weather_key = os.environ["WEATHER_API_KEY"]
    groq_key = os.environ["GROQ_API_KEY"]
    # Pulling the recipient from your workflow file
    recipient = os.environ.get("EMAIL_RECIPIENT", "adspk243@gmail.com")
    
    city = "Islamabad"
    
    weather_data = get_weather(city, weather_key)
    namaz_data = get_namaz_times(city)
    
    daily_advice = get_groq_advice(weather_data, namaz_data, groq_key)
    
    send_email(email, password, recipient, daily_advice)

if __name__ == "__main__":
    main()
