from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, EmailStr
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

app = FastAPI()

# Replace with your actual Gmail credentials
GMAIL_USER = os.getenv("GMAIL_USER", "muhammadabubakarcbs@gmail.com")
GMAIL_PASSWORD = os.getenv("GMAIL_PASSWORD", "zfzz rhbj dpey nopv")

class EmailSchema(BaseModel):
    email: EmailStr
    subject: str
    message: str

def send_email(to_email: str, subject: str, message: str):
    try:
        msg = MIMEMultipart()
        msg['From'] = GMAIL_USER
        msg['To'] = to_email
        msg['Subject'] = subject

        msg.attach(MIMEText(message, 'plain'))

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(GMAIL_USER, GMAIL_PASSWORD)
        text = msg.as_string()
        server.sendmail(GMAIL_USER, to_email, text)
        server.quit()

        return "Email sent successfully"
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail="Failed to send email")

@app.post("/send-email/")
async def send_custom_email(email_details: EmailSchema):
    result = send_email(
        email_details.email, email_details.subject, email_details.message
    )
    return {"message": result}
