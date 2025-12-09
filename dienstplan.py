import csv
import datetime
import os

from dotenv import load_dotenv

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

load_dotenv()

# TODO: google batch requests
# https://developers.google.com/calendar/v3/guides/batch

# TODO: Improve get_events_from_csv (split into smaller functions)

# TODO: Add CloudVision API and LLM API to programmatically parse shift schedule

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/calendar"]
CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS_FILE")
CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID")
CSV_PATH = os.getenv("CSV_FILE_PATH")

if not CREDENTIALS or not CALENDAR_ID or not CSV_PATH:
    print("Missing required environment variables")
    exit(1)

BEREITSCHAFTSARTEN = ("KFP", "MFP", "Dispo")


def credentials() -> Credentials:
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS, SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    return creds


def get_events_from_csv(file_path) -> list[dict]:
    event_list = []
    try:
        with open(file_path, mode="r", newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file, delimiter=",", quotechar='"')
            try:
                for row in reader:
                    event = {
                        "colorId": "10",
                        "start": {"timeZone": "Europe/Berlin"},
                        "end": {"timeZone": "Europe/Berlin"},
                        "summary": row["Dienst"],
                    }

                    # Parse Date
                    date_obj = datetime.datetime.strptime(
                        row["Datum"], "%Y-%m-%d"
                    ).date()
                    date = date_obj.strftime("%Y-%m-%d")

                    if row["Zeiten"]:
                        # Split row["Zeiten"] into start and end time
                        start_time = row["Zeiten"].split("-")[0].strip()
                        end_time = row["Zeiten"].split("-")[1].strip()

                        # Create datetime obj for comparison
                        start_time_obj = datetime.datetime.strptime(
                            start_time, "%H:%M"
                        ).time()
                        end_time_obj = datetime.datetime.strptime(
                            end_time, "%H:%M"
                        ).time()

                        # Create event start and end times
                        event["start"]["dateTime"] = (
                            f"{date}T{start_time_obj.strftime('%H:%M:%S')}"
                        )
                        if start_time_obj < end_time_obj:
                            # Date remains the same
                            event["end"]["dateTime"] = (
                                f"{date}T{end_time_obj.strftime('%H:%M:%S')}"
                            )
                        else:
                            # Date changes
                            end_date_obj = date_obj + datetime.timedelta(days=1)
                            event["end"]["dateTime"] = end_date_obj.strftime("%Y-%m-%d")
                            event["end"]["dateTime"] += (
                                f"T{end_time_obj.strftime('%H:%M:%S')}"
                            )

                    if not row["Zeiten"]:
                        if row["Dienst"] not in BEREITSCHAFTSARTEN:
                            # Create all-day event
                            event["start"]["date"] = date
                            event["end"]["date"] = (
                                date_obj + datetime.timedelta(days=1)
                            ).strftime("%Y-%m-%d")
                        elif row["Dienst"] in BEREITSCHAFTSARTEN:
                            # Create event for on-call duty
                            event["start"]["dateTime"] = f"{date}T08:00:00"
                            event["end"]["dateTime"] = f"{date}T20:00:00"

                    event_list.append(event)
                return event_list
            except TypeError as e:
                print(f"Error processing row in CSV file: {e}")
    except FileNotFoundError:
        print(f"CSV file not found: {file_path}")
    except Exception as e:
        print(f"Error reading CSV file: {e}")


def events_to_cal(list_of_events, credentials):
    if credentials is None:
        print("No valid credentials found.")
        return
    try:
        service = build("calendar", "v3", credentials=credentials)

        event = None
        added_days = 0
        for event in list_of_events:
            service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
            added_days += 1
        print(f"Added {added_days} days to calendar.")
    except HttpError as e:
        print(f"Error creating event {event}: {e}")


if __name__ == "__main__":
    creds = credentials()
    events = get_events_from_csv(CSV_PATH)
    if events:
        events_to_cal(events, creds)
    else:
        print("No valid events found in CSV file.")
