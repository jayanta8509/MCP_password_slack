from mcp.server.fastmcp import FastMCP
import smtplib
import random
import string
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from config import supabase
from config import (
    SMTP_SERVICE,
    SMTP_PORT,
    SMTP_USER,
    SMTP_PASSWORD,
    SMTP_SENDER,
)

mcp = FastMCP("Forget_Password")

# temp pass util
def generate_temp_password(employee_id: str) -> str:
    random_part = ''.join(
        random.choices(string.ascii_uppercase + string.digits, k=5)
    )
    return f"{employee_id}_{random_part}"

# email sender util
def send_password_reset_email(to_email: str, temp_password: str):
    """
    Sends password reset email with new password
    """
    with open("email_template.html", "r", encoding="utf-8") as file:
        html_template = file.read()

    html_content = html_template.replace(
        "{{TEMP_PASSWORD}}", temp_password
    )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Password Reset Successful"
    msg["From"] = SMTP_SENDER
    msg["To"] = to_email

    msg.attach(MIMEText(html_content, "html"))

    server = smtplib.SMTP(SMTP_SERVICE, SMTP_PORT)
    server.starttls()
    server.login(SMTP_USER, SMTP_PASSWORD)
    server.sendmail(SMTP_SENDER, to_email, msg.as_string())
    server.quit()

# functions 

@mcp.tool()
def verify_employee_id(employee_id: str):
    """
    Checks if employee exists in Database
    """
    response = (
        supabase
        .table("demo")
        .select("*")
        .eq("Employee_ID", employee_id)
        .execute()
    )

    if not response.data:
        return {
            "verified": False,
            "message": f" Employee with ID {employee_id} does not exist."
        }

    return {
        "verified": True,
        "employee": response.data[0]
    }

@mcp.tool()
def fetch_security_question(employee_id: str):
    """
    Fetch security question for given employee
    """
    response = (
        supabase
        .table("demo")
        .select("Security_Question")
        .eq("Employee_ID", employee_id)
        .execute()
    )

    if not response.data:
        return {
            "success": False,
            "message": "Employee not found."
        }

    return {
        "success": True,
        "security_question": response.data[0]["Security_Question"]
    }

@mcp.tool()
def verify_security_answer_and_reset(
    employee_id: str,
    user_answer: str
):
    """
    Matches security answer.
    If verified:
    - Generate new password
    - Update password
    - Send email with password
    """

    response = (
        supabase
        .table("demo")
        .select("Security_Ans, email_id")
        .eq("Employee_ID", employee_id)
        .execute()
    )

    if not response.data:
        return {
            "verified": False,
            "message": "Employee not found."
        }

    correct_answer = response.data[0]["Security_Ans"]
    email_id = response.data[0]["email_id"]

    if correct_answer.strip().lower() != user_answer.strip().lower():
        return {
            "verified": False,
            "message": " Wrong answer! Identity not verified."
        }

    new_password = generate_temp_password(employee_id)

    supabase.table("demo").update(
        {"password": new_password}
    ).eq(
        "Employee_ID", employee_id
    ).execute()

    # Send email
    send_password_reset_email(
        to_email=email_id,
        temp_password=new_password
    )

    return {
        "verified": True,
        "message": " Identity Verified! Password reset successfully."
        # "ticket_id": "TKT-001"
    }

if __name__ == "__main__":
    mcp.run(transport="stdio")
