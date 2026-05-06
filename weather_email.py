import os
import smtplib
from email.message import EmailMessage
import requests
from openai import OpenAI
from datetime import datetime

SIGNATURE = "\n\n---\n✨ Made & Designed by Abdullah\n"

def get_weather(city, api_key):
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {"q": city, "appid": api_key, "units": "metric"}
    current = requests.get(url, params=params).json()
    
    forecast_url = "https://api.openweathermap.org/data/2.5/forecast"
    forecast = requests.get(forecast_url, params=params).json()
    
    rain_prob = int(forecast['list'][0]['pop'] * 100)
    
    return {
        "city": current["name"],
        "temperature": current["main"]["temp"],
        "description": current["weather"][0]["description"],
        "humidity": current["main"]["humidity"],
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
    client = OpenAI(
        api_key=groq_key,
        base_url="https://api.groq.com/openai/v1"
    )
    
    prompt = f"""
    You are a friendly, highly intelligent morning weather assistant. Write a daily briefing for the user based on this data for {weather['city']}. 
    Make it highly visual, engaging, and user-friendly by using emojis. It should feel like reading a premium weather app.
    
    DATA:
    Current Temp: {weather['temperature']}°C
    Condition: {weather['description']}
    Humidity: {weather['humidity']}%
    Rain Probability: {weather['rain_probability']}%
    
    Namaz & Sun Schedule:
    Sunrise: {namaz['Sunrise']}
    Fajr: {namaz['Fajr']}
    Dhuhr: {namaz['Dhuhr']}
    Asr: {namaz['Asr']}
    Sunset: {namaz['Sunset']}
    Maghrib: {namaz['Maghrib']}
    Isha: {namaz['Isha']}
    
    Format the email clearly with these sections:
    1. 🌤️ Weather Summary: An engaging summary of how the morning, afternoon, and night will feel.
    2. 👕 What to Wear & Prep: Specific advice considering the temperature, humidity, and rain probability.
    3. 🕌 Daily Schedule: A clean bulleted list of the Namaz times and Sunrise/Sunset. Keep the times exactly as provided.
    4. 💡 Daily Motivation: A short, positive closing thought.
    """
    
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

def send_email(sender_email, sender_password, recipient_email, advice):
    subject = "📱 Your Daily Weather & Schedule App"
    
    # Add signature to weather email
    full_content = advice + SIGNATURE
    
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = recipient_email
    msg.set_content(full_content)

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
    
    send_email(email, password, recipient, daily_advice)

if __name__ == "__main__":
    main()
