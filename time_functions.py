from datetime import datetime, date
import pytz


def local_time_now():
    # Set up timezone
    timezone = pytz.timezone('Europe/London')
    # Get time now and format to same as API date format
    timenow_datetime_string = datetime.now(timezone).strftime("%Y-%m-%dT%H:%M:%S%z")
    timenow_datetime = convert_time(timenow_datetime_string)
    return timenow_datetime


# Function to convert a time string from into a datetime object
def convert_time(time_string):
    time_datetime = datetime.strptime(time_string, "%Y-%m-%dT%H:%M:%S%z")
    return time_datetime


def days_delta(datetime1, datetime2):
    delta = datetime1 - datetime2
    return delta.days

def hours_delta(datetime1, datetime2):
    delta = datetime1 - datetime2
    return delta.hours
