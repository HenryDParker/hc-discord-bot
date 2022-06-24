import requests
import os
import json
from dotenv import load_dotenv

load_dotenv()
RAPIDAPIKEY = os.getenv('RAPIDAPI_KEY')
url_fixtures = "https://api-football-v1.p.rapidapi.com/v3/fixtures"

# Creates the API request based on parameters passed in

def base_request(team_id, current_season, *args, **kwargs):
    next_fixture = kwargs.get('next_fixture', False)
    fixture_id = kwargs.get('fixture_id', None)

    headers_dict = {'x-rapidapi-host': "api-football-v1.p.rapidapi.com", 'x-rapidapi-key': RAPIDAPIKEY}
    # Query with required parameters & constant optional timezone param
    querystring_dict = {"season": current_season, "team": team_id, "timezone": "Europe/London"}

    # Add optional parameters if passed
    if next_fixture:
        next_fixture = 1
        querystring_dict["next"] = next_fixture

    if fixture_id:
        querystring_dict["id"] = fixture_id

    try:
        api_response = requests.request("GET", url_fixtures, headers=headers_dict, params=querystring_dict)
        data = api_response.text

    except requests.exceptions.HTTPError as err:
        raise SystemExit(err)

    return json.loads(data)
