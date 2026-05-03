import os
import smtplib
from email.message import EmailMessage
import requests
from openai import OpenAI

def get_weather(city, api_key):
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {"q": city, "appid": api_key, "units": "metric"}
    response = requests.get(url, params=params).json()
    
    return {
        "city": response["name"],
        "temperature": response["main"]["temp"],
        "description": response["weather"][0]["description"],
    }

def get_groq_advice(weather, groq_key):
    # Connecting to Groq just like your other project!
    client = OpenAI(
        api_key=groq_key,
        base_url="https://api.groq.com/openai/v1"
    )
    
    prompt = f"The weather in {weather['city']} today is {weather['temperature']}°C with {weather['description']}. Act as a smart, highly efficient weather agent. Give me a sharp, accurate recommendation on what to wear and how to prepare for the day ahead. Keep it to two concise sentences."
    
    # Using your preferred Llama model
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

def send_email(sender_email, sender_password, weather, advice):
    subject = "🌤️ Your Daily Weather & Style Guide"
    
    body = f"""Hello Abdullah,

Here is your daily update:
Temperature: {weather['temperature']}°C
Condition: {weather['description'].title()}

🧠 Smart Agent Advice (Powered by Groq):
{advice}
"""

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = sender_email
    msg.set_content(body)

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)

def main():
    email = os.environ["EMAIL_ADDRESS"]
    password = os.environ["EMAIL_PASSWORD"]
    weather_key = os.environ["WEATHER_API_KEY"]
    groq_key = os.environ["GROQ_API_KEY"]
    
    weather_data = get_weather("Islamabad", weather_key)
    
    # Let Groq write the email advice
    daily_advice = get_groq_advice(weather_data, groq_key)
    
    send_email(email, password, weather_data, daily_advice)

if __name__ == "__main__":
    main()
