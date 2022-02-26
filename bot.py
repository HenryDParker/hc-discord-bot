# bot.py
import json
import os
import random
import string
import re
import discord
import requests
import time

from github import Github
from discord.ext import commands, tasks
from dotenv import load_dotenv
from datetime import datetime, date
from dateutil import tz

# URL to invite TEST bot
# https://discord.com/api/oauth2/authorize?client_id=946767991670997052&permissions=274878114880&scope=bot

# URL to invite LIVE bot
# https://discord.com/api/oauth2/authorize?client_id=917479797242875936&permissions=274878114880&scope=bot

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
# GUILD = os.getenv('DISCORD_GUILD')
RAPIDAPIKEY = os.getenv('RAPIDAPI_KEY')
GITHUBTOKEN = os.getenv('GITHUB_TOKEN')
channel_id = int(os.getenv('CHANNEL_ID'))

# client = discord.Client()
# define bot command decorator
command_prefix = '>'
bot = commands.Bot(command_prefix=command_prefix)

# Remove default help command
bot.remove_command("help")


# Set up UserAndScore class
class UserAndScore:
    def __init__(self,
                 mentionName: str,
                 username: str,
                 currentPrediction,
                 predictionTimestamp,
                 numCorrectPredictions: int,
                 previousPredictionCorrect: bool,
                 predictionStreak: int,
                 longestPredictionStreak: int):
        self.mentionName = mentionName
        self.username = username
        self.currentPrediction = currentPrediction
        self.predictionTimestamp = predictionTimestamp
        self.numCorrectPredictions = numCorrectPredictions
        self.previousPredictionCorrect = previousPredictionCorrect
        self.predictionStreak = predictionStreak
        self.longestPredictionStreak = longestPredictionStreak


# Global Lists
currentUsersClassList = []

# Global Dictionaries
currentFixture = {}
nextFixture = {}
#discord_channels = {}

# list of responses to a correct score format
correct_score_format = [
    'Good luck, ',
    'Wish you the best, ',
    'Best of luck, ',
    'Fingers crossed, ',
]

# Global variables
matchInProgress = False
bot_ready = False
predictions_updated = False
current_fixture_id = None
reminder24hr_sent = False
reminder1hr_sent = False
is_fixture_today = False

west_ham_logo = "https://media.api-sports.io/football/teams/48.png"
predictor_bot_logo = "https://i.imgur.com/9runQEU.png"

# Setting up timezones
utc_tz = tz.gettz('UTC')
uk_tz = tz.gettz('Europe/London')

# channel_id pulled from admin using {command_prefix}channel
# then stored in a dict & external json file on Github for any restarts

# Static Channel ID so
# Test Server Channel ID
# channel_id = 917754145367289929

# Hammers Chat Channel ID
# channel_id = 929200954023215194


# regex definitions
scorePattern = re.compile('^[0-9]{1,2}-[0-9]{1,2}$')
scorePatternHigh = re.compile('^[0-9]{1,5}-[0-9]{1,5}$')


# Reminder status storage and backup
# ----------------------------------------------------------------------------------------------------------------------
async def write_reminder_status():
    # perform local write (NO READ) for testing purposes
    global reminder24hr_sent
    global reminder1hr_sent
    reminders_status_dict = {
        "reminder24hr": reminder24hr_sent,
        "reminder1hr": reminder1hr_sent
    }


    with open('reminder_status.json', 'w') as outfile:
        json.dump(reminders_status_dict, outfile, indent=2)

    # convert "data" to a json_string and send this to 'hc-bot-memory' repo on GitHub for backup
    json_string = json.dumps(reminders_status_dict)
    github = Github(GITHUBTOKEN)
    repository = github.get_user().get_repo('hc-bot-memory')
    filename = 'reminder_status.json'
    contents = repository.get_contents("")
    all_files = []

    # check all values in contents
    while contents:
        # take first value as file_content
        file_content = contents.pop(0)
        # if file_content is a directory (shouldn't ever be)
        if file_content.type == "dir":
            contents.extend(repository.get_contents(file_content.path))
        # else must be a file
        else:
            file = file_content
            # remove extra text to create clean file name for comparison
            all_files.append(str(file).replace('ContentFile(path="', '').replace('")', ''))

    # check if filename matches in all_files list - if yes then update, if no then create
    if filename in all_files:
        contents = repository.get_contents(filename)
        repository.update_file(filename, "Updated reminder_status file", json_string, contents.sha)
    else:
        repository.create_file(filename, "Created reminder_status file", json_string)
    print(f'Reminder status write complete')


async def read_reminder_status():
    global reminder24hr_sent
    global reminder1hr_sent
    try:
        # download file from Github repo 'hc-bot-memory' and decode to json_string
        github = Github(GITHUBTOKEN)
        repository = github.get_user().get_repo('hc-bot-memory')
        filename = 'reminder_status.json'
        file = repository.get_contents(filename)
        json_string = file.decoded_content.decode()

        # convert json_file to "reminders_status"
        reminders_status_dict = json.loads(json_string)
        reminder24hr_sent = reminders_status_dict['reminder24hr']
        reminder1hr_sent = reminders_status_dict['reminder1hr']
        print(f'Channel backup read complete')

    # If the read fails in any way, set reminders to False as a backup
    # This is not catastrophic, will only send a Reminder again in case of a bot restart
    except:
        reminder24hr_sent = False
        reminder1hr_sent = False
        print(f'reminder status read FAILED\nReminder set to FALSE')


# ----------------------------------------------------------------------------------------------------------------------


# Timed tasks
# ----------------------------------------------------------------------------------------------------------------------
# Check fixture info every quarter-hour
@tasks.loop(minutes=15)
async def check_fixtures():
    # Only perform this check after 8am and stop at midnight - can be removed if necessary
    # This will save API calls as few changes to West Ham fixture will occur between these times
    timenow = datetime.now()
    #global match_today
    if timenow.hour <= 2 or timenow.hour >= 7:
        # find today's date
        today = date.today()
        # set the month to an int e.g. 02
        today_month = int(today.strftime("%m"))
        # set the year to an int e.g. 2021
        today_year = int(today.strftime("%Y"))

        # if the month is less than 6, set the current_season to the current year, -1
        # e.g in 03/2022 the season is 2021
        if today_month < 6:
            current_season = today_year - 1
        else:
            current_season = today_year

        # API call to get team fixtures for current Season
        url_fixtures = "https://api-football-v1.p.rapidapi.com/v3/fixtures"

        querystring_fixtures = {"season": current_season, "team": "48"}

        headers_fixtures = {
            'x-rapidapi-host': "api-football-v1.p.rapidapi.com",
            'x-rapidapi-key': RAPIDAPIKEY
        }

        api_response = requests.request("GET", url_fixtures, headers=headers_fixtures, params=querystring_fixtures)
        data = api_response.text
        fixtures_dict_json = json.loads(data)

        try:
            with open('fixtures_dict_json.json', 'w') as f:
                json.dump(fixtures_dict_json, f)
            print(f'API Fixture check complete')
        except:
            print(f'API Fixture check FAILED')
    # else:
    #     match_today = False

        # # API call to get team info for 2021 Season
        # url_leagues = "https://api-football-v1.p.rapidapi.com/v3/leagues"
        #
        # querystring_leagues = {
        #     "season": current_season,
        #     "team": "48"
        # }
        #
        # headers_leagues = {
        #     'x-rapidapi-host': "api-football-v1.p.rapidapi.com",
        #     'x-rapidapi-key': RAPIDAPIKEY
        # }
        #
        # api_response = requests.request("GET", url_leagues, headers=headers_leagues, params=querystring_leagues)
        # data = api_response.text
        # leagues_dict_json = json.loads(data)
        #
        # # with open('leagues_dict_json.json', 'wb') as leagues_dict_json_file:
        # #     pickle.dump(leagues_dict_json, leagues_dict_json_file)
        #
        # with open('leagues_dict_json.json', 'w') as f:
        #     json.dump(leagues_dict_json, f)

# looping every 10 minutes
@tasks.loop(minutes=10)
async def check_save():
    global predictions_updated
    if bot_ready:
        if predictions_updated:
            await save_to_file()
            predictions_updated = False


# looping every minute
@tasks.loop(minutes=1)
async def check_next_fixture():
    # This was causing excessive logging - would be useful if logs were stored locally
    #print(f'Check next fixture')
    global matchInProgress
    with open("fixtures_dict_json.json", "r") as read_file:
        all_fixtures = json.load(read_file)

        # for each item in response dictionary list, find timestamp
        current_time = int(time.time())
        current_date = datetime.utcnow().date()


        #next_kickoff_iso_utc = nextFixture['fixture']['date']
        #next_kickoff_utc = datetime.strptime(next_kickoff_iso_utc, '%Y-%m-%dT%H:%M:%S%z')



        # set shortest_time_diff to arbitrarily high value
        shortest_time_diff = current_time
        global currentFixture
        global current_fixture_id

        try:
            if current_fixture_id is not None:
                for each in all_fixtures['response']:
                    if each['fixture']['id'] == current_fixture_id:
                        fixture_status = (each['fixture']['status']['short'])

                        # check if the current fixture id has a Full Time status
                        if fixture_status == 'FT' or fixture_status == 'AET' or fixture_status == 'PEN':
                            print(f'Current fixture has a Full Time status')
                            await give_results()
                            current_fixture_id = None
                            currentFixture = {}
                            break

                        elif fixture_status == 'AWD' or fixture_status == 'WO':
                            # Match awarded technical loss or walkover - result is null and score streaks are maintained
                            print(f'Current fixture - {fixture_status}')

                            await null_result(fixture_status)
                            current_fixture_id = None
                            currentFixture = {}
                            break

                        elif fixture_status == 'ABD' or fixture_status == 'PST':
                            # Match abandoned - result is null and  score streaks are maintained
                            print(f'Current fixture - {fixture_status}')

                            await null_result(fixture_status)
                            current_fixture_id = None
                            currentFixture = {}
                            break


        except KeyError:
            await save_error_to_file(all_fixtures)
            print(f'Cannot find fixture info - current_fixture_id - all_fixtures dict')

        try:
            global is_fixture_today
            for each in all_fixtures['response']:
                # get fixture timestamp
                fixture_time = (each['fixture']['timestamp'])
                # get fixture status
                fixture_status = (each['fixture']['status']['short'])
                fixture_date = (each['fixture']['date'])
                fixture_date = datetime.strptime(fixture_date, '%Y-%m-%dT%H:%M:%S%z')
                fixture_date = fixture_date.date()

                is_fixture_today = await fixture_today(current_date, fixture_date)


                time_difference = fixture_time - current_time

                # check if difference is negative (fixture is before now) - if yes, skip to next for loop iteration
                # if time_difference <= 0:
                # check if fixture status is Full Time (or other finished) - if yes, skip to next for loop iteration
                if fixture_status == 'FT' \
                        or fixture_status == 'AET' \
                        or fixture_status == 'PEN' \
                        or fixture_status == 'PST' \
                        or fixture_status == 'CANC' \
                        or fixture_status == 'ABD' \
                        or fixture_status == 'AWD' \
                        or fixture_status == 'WO':
                    # check if previous iteration had a match in progress
                    continue

                # else check if fixture status is in progress
                elif fixture_status == '1H' \
                        or fixture_status == 'HT' \
                        or fixture_status == '2H' \
                        or fixture_status == 'ET' \
                        or fixture_status == 'P' \
                        or fixture_status == 'BT' \
                        or fixture_status == 'LIVE' \
                        or fixture_status == 'INT'\
                        or fixture_status == 'SUSP':
                    matchInProgress = True
                    # get fixture id
                    current_fixture_id = (each['fixture']['id'])
                    currentFixture = each
                    print(f'Match in progress is set to currentFixture')
                    continue

                # else check if fixture status is not started
                elif fixture_status == 'NS':
                    # if not matchInProgress:

                    # is time to fixture less than the current shortest time to fixture?
                    if time_difference < shortest_time_diff:
                        # yes, set as new shortest time and set as nextFixture
                        shortest_time_diff = time_difference
                        global nextFixture
                        nextFixture = each
                        #print(f'Upcoming fixture set to nextFixture')

                    else:
                        # no, continue to next fixture
                        continue

                # # TBD, SUSP, INT
                # else:
                #     # check if previous iteration had a match in progress
                #     if matchInProgress:
                #         await give_results()
                #         matchInProgress = False
                #         print(f'Match in progress is TBD, SUSP or INT')
                #     continue

            next_fixture_status = nextFixture['fixture']['status']['short']

            if next_fixture_status == "CANC" or next_fixture_status == "PST":
                await postponed_fixture(next_fixture_status)


        except KeyError:
            await save_error_to_file(all_fixtures)
            print(f'Cannot find fixture info - all_fixtures dict')



# 24hrs reminder
@tasks.loop(minutes=1)
async def reminder():
    if bot_ready:

        global reminder24hr_sent
        global reminder1hr_sent

        timenow_iso_utc = datetime.now(tz=utc_tz).isoformat(timespec='seconds')
        next_kickoff_iso_utc = nextFixture['fixture']['date']

        timenow_utc = datetime.strptime(timenow_iso_utc, '%Y-%m-%dT%H:%M:%S%z')
        next_kickoff_utc = datetime.strptime(next_kickoff_iso_utc, '%Y-%m-%dT%H:%M:%S%z')

        # Check difference in times
        year_diff = next_kickoff_utc.year - timenow_utc.year
        month_diff = next_kickoff_utc.month - timenow_utc.month
        day_diff = next_kickoff_utc.day - timenow_utc.day

        hour_diff = next_kickoff_utc.hour - timenow_utc.hour
        minute_diff = next_kickoff_utc.minute - timenow_utc.minute

        # datetime is naive, so set timezone
        next_kickoff_utc = next_kickoff_utc.replace(tzinfo=utc_tz)
        timenow_utc = timenow_utc.replace(tzinfo=utc_tz)

        next_kickoff_uk = next_kickoff_utc.astimezone(uk_tz)

        # Convert back to strings to allow for leading 0s
        next_kickoff_hour = next_kickoff_uk.strftime("%H")
        next_kickoff_minute = next_kickoff_uk.strftime("%M")

        next_home_team = nextFixture['teams']['home']['name']
        next_away_team = nextFixture['teams']['away']['name']
        competition = nextFixture['league']['name']
        competition_round = nextFixture['league']['round']
        competition_icon_url = nextFixture['league']['logo']

        if next_home_team == 'West Ham':
            is_home = True
            opposition_logo = nextFixture['teams']['away']['logo']
        else:
            is_home = False
            opposition_logo = nextFixture['teams']['home']['logo']

        predictions_prompt = f'Get your predictions in now using *{command_prefix}p*'

        this_channel = bot.get_channel(channel_id)

        if year_diff == 0 and month_diff == 0 and day_diff == 1\
                and hour_diff == 0 and minute_diff <= 0 and not reminder24hr_sent:
            if is_home:
                response = f'**West Ham vs {next_away_team}** starts in less than 24 hours ' \
                           f'at {next_kickoff_hour}:{next_kickoff_minute} UK Time'
            else:
                response = f'**{next_home_team} vs West Ham** starts in less than 24 hours ' \
                           f'at {next_kickoff_hour}:{next_kickoff_minute} UK Time'

            em = discord.Embed(title="**Match Reminder**",
                               description=f'{response}\n{predictions_prompt}',
                               colour=discord.Colour.from_rgb(129, 19, 49))
            em.set_thumbnail(url=opposition_logo)
            em.set_footer(text=f'{competition} ({competition_round})', icon_url=competition_icon_url)
            await this_channel.send(embed=em)
            print(f'Fixture 24hr reminder sent')
            reminder24hr_sent = True
            await write_reminder_status()


        elif year_diff == 0 and month_diff == 0 and day_diff == 0\
                and hour_diff == 1 and minute_diff <= 0 and not reminder1hr_sent:
            if is_home:
                response = f'**West Ham vs {next_away_team}** starts in less than 1 hour ' \
                           f'at {next_kickoff_hour}:{next_kickoff_minute} UK Time'
            else:
                response = f'**{next_home_team} vs West Ham** starts in less than 1 hour ' \
                           f'at {next_kickoff_hour}:{next_kickoff_minute} UK Time'

            em = discord.Embed(title="**Match Reminder**",
                               description=f'{response}\n{predictions_prompt}',
                               colour=discord.Colour.from_rgb(129, 19, 49))
            em.set_thumbnail(url=opposition_logo)
            em.set_footer(text=f'{competition} ({competition_round})', icon_url=competition_icon_url)
            await this_channel.send(embed=em)
            print(f'Fixture 1hr reminder sent')
            reminder1hr_sent = True
            await write_reminder_status()



# ----------------------------------------------------------------------------------------------------------------------


@bot.event
async def give_results():
    if bot_ready:
        with open("fixtures_dict_json.json", "r") as read_file:
            all_fixtures = json.load(read_file)

            for each in all_fixtures['response']:
                # for each fixture, check if is the current fixture by id
                if current_fixture_id == (each['fixture']['id']):
                    home_team = each['teams']['home']['name']
                    away_team = each['teams']['away']['name']
                    competition = each['league']['name']
                    competition_round = each['league']['round']
                    competition_icon_url = each['league']['logo']
                    if (each['fixture']['status']['short']) == 'FT':
                        home_score = (each['score']['fulltime']['home'])
                        away_score = (each['score']['fulltime']['away'])
                        # Full fixture result with team names
                        fixture_result_full = f'{home_team} {str(home_score)} - {str(away_score)} {away_team}'
                        # Short fixture result for prediction comparison
                        fixture_result_score = f'{str(home_score)}-{str(away_score)}'
                    elif (each['fixture']['status']['short']) == 'AET':
                        home_score = (each['score']['extratime']['home'])
                        away_score = (each['score']['extratime']['away'])
                        # Full fixture result with team names
                        fixture_result_full = f'{home_team} {str(home_score)} - {str(away_score)} {away_team}'
                        # Short fixture result for prediction comparison
                        fixture_result_score = f'{str(home_score)}-{str(away_score)}'
                    elif (each['fixture']['status']['short']) == 'PEN':
                        home_score = (each['score']['extratime']['home'])
                        away_score = (each['score']['extratime']['away'])
                        home_score_pens = (each['score']['penalty']['home'])
                        away_score_pens = (each['score']['penalty']['away'])
                        # Full fixture result with team names (and penalties)
                        fixture_result_full = f'{home_team} {str(home_score)} ({str(home_score_pens)})' \
                                              f' - {str(away_score)} ({str(away_score_pens)}) {away_team}'
                        # Short fixture result for prediction comparison  (NOT including penalties at the moment)
                        fixture_result_score = f'{str(home_score)}-{str(away_score)}'

            global matchInProgress
            matchInProgress = False

            # Create an initially empty list for the correct predictions
            correct_prediction_list = []
            # For each object in class, check if their currentPrediction matches the fixture score result
            # then add to correct_prediction_list if it does
            for each in currentUsersClassList:
                if each.currentPrediction == fixture_result_score:
                    correct_prediction_user_mention = each.mentionName
                    correct_prediction_list.append(correct_prediction_user_mention)
                    # increment correct predictions tally for "each" when correct
                    each.numCorrectPredictions += 1
                    # increase prediction streak by 1, increase longest streak if new streak is larger
                    # and set previousPredictionCorrect to True
                    each.predictionStreak += 1
                    if each.predictionStreak < each.longestPredictionStreak:
                        each.longestPredictionStreak = each.predictionStreak
                    each.previousPredictionCorrect = True
                # else if wrong, set streak to 0 and previousPredictionCorrect to False
                else:
                    each.predictionStreak = 0
                    each.previousPredictionCorrect = False

            # Check if list is empty (no correct guesses) and print a response accordingly
            # --- unsure whether this is the correct pythonic way to check empty list

            response = f'The match finished **{fixture_result_full}**'

            em = discord.Embed(title="**Match Result**",
                               description=f'{response}',
                               colour=discord.Colour.from_rgb(129, 19, 49))

            # if correct_prediction_list is None:
            if not correct_prediction_list:
                correct_guesses = f'Unfortunately no one guessed the score correctly!'
                em.add_field(name=correct_guesses, value='Better luck next time!')
            # else there must be at least one correct prediction, so congratulate user(s) with an @Mention tag
            else:
                correct_predictions = '\n'.join(correct_prediction_list)
                correct_guesses = f'Well done:'
                em.add_field(name=correct_guesses, value=f'{correct_predictions}')

            em.set_thumbnail(url=west_ham_logo)
            em.set_footer(text=f'{competition} ({competition_round})', icon_url=competition_icon_url)


            #for each in discord_channels:
            this_channel = bot.get_channel(channel_id)
            await this_channel.send(embed=em)

            #await this_channel.send(response)
            print(f'Prediction results sent')

            # now clear all user Objects' current predictions in the list
            for each in currentUsersClassList:
                each.currentPrediction = None
            # write class to file
            await save_to_file()

            # Send leaderboard after results given
            await leaderboard()
            await next_fixture()


@bot.event
async def null_result(null_fixture_status):
    global matchInProgress
    # match no longer in progress
    matchInProgress = False

    # clear current predictions as predictions are nullified
    for each in currentUsersClassList:
        each.currentPrediction = None
    # write class to file
    await save_to_file()

    if null_fixture_status == 'ABD':
        response = f'The match was abandoned'
    elif null_fixture_status == 'AWD':
        response = f'The match was a technical loss'
    elif null_fixture_status == 'WO':
        response = f'The match was a walkover'
    else:
        response = f'The match finished for unknown reasons'

    em = discord.Embed(title="**Match Result**",
                       description=f'{response}',
                       colour=discord.Colour.from_rgb(129, 19, 49))

    title = f'To maintain fairness'
    subtitle = f'Predictions have been nullified and score streaks are maintained'
    em.add_field(name=title, value=subtitle)

    await next_fixture()

@bot.event
async def postponed_fixture(postponed_fixture_status):

    for each in currentUsersClassList:
        each.currentPrediction = None
    # write class to file
    await save_to_file()

    if postponed_fixture_status == 'PST':
        response = f'The upcoming match has been postponed'
    elif postponed_fixture_status == 'CANC':
        response = f'The upcoming match has been cancelled'
    else:
        response = f'The upcoming match will not go ahead for unknown reasons'

    em = discord.Embed(title="**Match Info**",
                       description=f'{response}',
                       colour=discord.Colour.from_rgb(129, 19, 49))

    title = f'To maintain fairness'
    subtitle = f'Predictions have been nullified and score streaks are maintained'
    em.add_field(name=title, value=subtitle)

    await next_fixture()


@bot.event
async def next_fixture():
    if bot_ready:
        this_channel = bot.get_channel(channel_id)

        # Reset reminder bools
        global reminder24hr_sent
        global reminder1hr_sent
        reminder24hr_sent = False
        reminder1hr_sent = False

        await write_reminder_status()

        # Grab details for next match
        next_home_team = nextFixture['teams']['home']['name']
        next_away_team = nextFixture['teams']['away']['name']
        competition = nextFixture['league']['name']
        competition_round = nextFixture['league']['round']
        competition_icon_url = nextFixture['league']['logo']

        predictions_prompt = f'Get your predictions in now using *{command_prefix}p*'

        if matchInProgress:
            current_home_team = currentFixture['teams']['home']['name']
            current_away_team = currentFixture['teams']['away']['name']
            current_competition = currentFixture['league']['name']
            current_competition_round = currentFixture['league']['round']
            current_competition_icon_url = currentFixture['league']['logo']

            if current_home_team == 'West Ham':
                current_is_home = True
                current_away_team_icon = currentFixture['teams']['away']['logo']

                response = f'**West Ham vs {current_away_team}**'

                em_current = discord.Embed(title="**There is a match in progress!**",
                                           description=f'{response}',
                                           colour=discord.Colour.from_rgb(129, 19, 49))
                em_current.set_thumbnail(url=current_away_team_icon)
            else:
                current_is_home = False
                current_home_team_icon = currentFixture['teams']['home']['logo']

                response = f'**{current_home_team} vs West Ham**'

                em_current = discord.Embed(title="**There is a match in progress!**",
                                           description=f'{response}',
                                           colour=discord.Colour.from_rgb(129, 19, 49))
                em_current.set_thumbnail(url=current_home_team_icon)

            em_current.set_footer(text=f'{current_competition} ({current_competition_round})',
                                  icon_url=current_competition_icon_url)
            await this_channel.send(embed=em_current)
            predictions_prompt = "Get your predictions in once the current match is over!"

        else:
            if next_home_team == 'West Ham':
                is_home = True
                away_team_icon = nextFixture['teams']['away']['logo']

                response = f'The next fixture is **West Ham vs {next_away_team}**'

                em = discord.Embed(title="**Next Fixture**",
                                   description=f'{response}\n{predictions_prompt}',
                                   colour=discord.Colour.from_rgb(129, 19, 49))
                em.set_thumbnail(url=away_team_icon)
            else:
                is_home = False
                home_team_icon = nextFixture['teams']['home']['logo']

                response = f'The next fixture is **{next_home_team} vs West Ham**'

                em = discord.Embed(title="**Next Fixture**",
                                   description=f'{response}\n{predictions_prompt}',
                                   colour=discord.Colour.from_rgb(129, 19, 49))
                em.set_thumbnail(url=home_team_icon)

            em.set_footer(text=f'{competition} ({competition_round})', icon_url=competition_icon_url)
            await this_channel.send(embed=em)
        print(f'Next fixture information sent')


@bot.event
async def fixture_today(current_date, fixture_date):
    if current_date == fixture_date:
        return True
    else:
        return False


# @bot.event
# async def write_match_in_progress():
#     if matchInProgress:
#         if not match_written_to_file:
#             # save to file
#             match_written_to_file = True



# When the bot joins a server
@bot.event
async def on_ready():
    global bot_ready
    global currentUsersClassList
    print(f'{bot.user.name} has connected to Discord!')
    # Commented out the message in discord to avoid spam as Heroku restarts applications once a day
    # results = f'{bot.user.name} has connected to Discord!'
    await read_reminder_status()
    bot_ready = True
    try:
        await read_from_file()
    except:
        currentUsersClassList = []
        print(f'currentUsersClass has been set to empty as file read failed')
    #for each in discord_channels:
    this_channel = bot.get_channel(channel_id)
    # Commented out the message in discord to avoid spam as Heroku restarts applications once a day
    # await this_channel.send(results)
    await set_status()
    # Commented out the next_fixture in discord to avoid spam as Heroku restarts applications once a day
    # await next_fixture()


# Set bot status
async def set_status():
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching,
                                                        name=f"West Ham | {command_prefix}help"))
    print(f'Bot status set')


# Bot help section
# ----------------------------------------------------------------------------------------------------------------------
@bot.group(invoke_without_command=True)
async def help(ctx):
    em = discord.Embed(title="Help", description=f"Use {command_prefix}help *command* for extended information",
                       colour=discord.Colour.from_rgb(129, 19, 49))
    em.add_field(name="Commands",
                 value=f"**{command_prefix}predict** (**{command_prefix}p**)"
                       f" - Add or update your score prediction\n"
                       f"**{command_prefix}next-fixture** (**{command_prefix}nf**)"
                       f" - Show the next fixture information\n"
                       f"**{command_prefix}predictions** (**{command_prefix}cpr**)"
                       f" - Show the predictions for the upcoming fixture\n"
                       f"**{command_prefix}leaderboard** (**{command_prefix}lb**)"
                       f" - Show the current leaderboard of predictors\n"
                       f"**{command_prefix}correct-scores** (**{command_prefix}cs**)"
                       f" - Your total number of correct scores\n"
                       f"**{command_prefix}score-streak** (**{command_prefix}ss**)"
                       f" - Your current number of correct scores in a row\n")
    em.set_thumbnail(url=predictor_bot_logo)
    await ctx.send(embed=em)


@help.command(name="p")
async def help_p(ctx):
    em = discord.Embed(title="p", description="Add or update you score prediction for the next match",
                       colour=discord.Colour.from_rgb(129, 19, 49))
    em.add_field(name="*Syntax*", value=f"{command_prefix}p *homescore*-*awayscore*")
    em.set_thumbnail(url=predictor_bot_logo)
    await ctx.send(embed=em)

@help.command(name="predict")
async def help_predict(ctx):
    em = discord.Embed(title="predict",
                       description=f"An alias of {command_prefix}p "
                                   f"- Add or update you score prediction for the next match",
                       colour=discord.Colour.from_rgb(129, 19, 49))
    em.add_field(name="*Syntax*", value=f"{command_prefix}predict *homescore*-*awayscore*")
    em.set_thumbnail(url=predictor_bot_logo)
    await ctx.send(embed=em)


@help.command(name="predictions")
async def help_predictions(ctx):
    em = discord.Embed(title="predictions", description="Show all the submitted predictions for the upcoming fixture",
                       colour=discord.Colour.from_rgb(129, 19, 49))
    em.add_field(name="*Aliases*", value=f"{command_prefix}current-predictions or {command_prefix}cp")
    em.set_thumbnail(url=predictor_bot_logo)
    await ctx.send(embed=em)


@help.command(name="current-predictions")
async def help_predictions(ctx):
    em = discord.Embed(title="predictions", description="Show all the submitted predictions for the upcoming fixture",
                       colour=discord.Colour.from_rgb(129, 19, 49))
    em.add_field(name="*Aliases*", value=f"{command_prefix}predictions or {command_prefix}cpr")
    em.set_thumbnail(url=predictor_bot_logo)
    await ctx.send(embed=em)


@help.command(name="leaderboard")
async def help_leaderboard(ctx):
    em = discord.Embed(title="leaderboard", description="Show the current leaderboard of the top score predictors",
                       colour=discord.Colour.from_rgb(129, 19, 49))
    em.add_field(name="*Aliases*", value=f"{command_prefix}lb")
    em.set_thumbnail(url=predictor_bot_logo)
    await ctx.send(embed=em)


@help.command(name="correct-scores")
async def help_correct_scores(ctx):
    em = discord.Embed(title="correct-scores", description="Show your total number of correct score predictions",
                       colour=discord.Colour.from_rgb(129, 19, 49))
    em.add_field(name="*Aliases*", value=f"{command_prefix}cs")
    em.set_thumbnail(url=predictor_bot_logo)
    await ctx.send(embed=em)


@help.command(name="score-streak")
async def help_score_streak(ctx):
    em = discord.Embed(title="score-streak", description="Show your current number of correct score predictions"
                                                         " in a row",
                       colour=discord.Colour.from_rgb(129, 19, 49))
    em.add_field(name="*Aliases*", value=f"{command_prefix}ss")
    em.set_thumbnail(url=predictor_bot_logo)
    await ctx.send(embed=em)


@help.command(name="next-fixture")
async def help_next_fixture(ctx):
    em = discord.Embed(title="next-fixture", description="Show the next fixture information",
                       colour=discord.Colour.from_rgb(129, 19, 49))
    em.add_field(name="*Aliases*", value=f"{command_prefix}nf")
    em.set_thumbnail(url=predictor_bot_logo)
    await ctx.send(embed=em)


# ----------------------------------------------------------------------------------------------------------------------


# User commands
# ----------------------------------------------------------------------------------------------------------------------
@bot.command(name='p', help=f'Submit (or update) your score prediction! e.g. {command_prefix}p 2-1',
             aliases=["predict"])
async def user_prediction(ctx, score):
    global predictions_updated
    # get current time
    current_time = int(time.time())
    # get next fixtures time
    fixture_time = nextFixture['fixture']['timestamp']
    # check if the fixture has started
    if fixture_time - current_time <= 0 or matchInProgress:
        response = "Sorry, you're too late!\nThe match has already started!"
    else:
        # remove whitespace from prediction
        score.translate({ord(c): None for c in string.whitespace})
        # match score to defined regex patterns
        if scorePatternHigh.match(score):
            if scorePattern.match(score):
                # find user that sent command
                author_mention_name = format(ctx.message.author.mention)
                author_text_name = format(ctx.message.author)

                home_team = nextFixture['teams']['home']['name']
                away_team = nextFixture['teams']['away']['name']

                score_added = False
                # Check if user already has a predictions - if yes, update it
                # for each UserAndScore object in List
                for each in currentUsersClassList:
                    # if User already exists in list
                    if each.mentionName == author_mention_name:
                        # # update that user's current prediction
                        # each.currentPrediction = score
                        each.username = author_text_name
                        each.predictionTimestamp = current_time

                        # if this value is None, then prediction was reset from previous fixture
                        # and no previous prediction for this fixture has occurred
                        # to be used for Score Streak in Future Feature
                        if each.currentPrediction is None:
                            predictions_updated = True
                            response = f"You have predicted {home_team} {score} {away_team}\n"\
                                       + random.choice(correct_score_format) + author_mention_name + '!'
                        else:
                            predictions_updated = True
                            response = '_Prediction updated_\n'\
                                       f"You have predicted {home_team} {score} {away_team}\n"\
                                       + random.choice(correct_score_format) + author_mention_name + '!'
                        # update that user's current prediction
                        each.currentPrediction = score
                        score_added = True
                if not score_added:
                    # add new user & score to list
                    # new_user is an object of UserAndScore class with name and currentPrediction inside
                    # (more attributes to be added & set to 0/null)
                    new_user = UserAndScore(author_mention_name, author_text_name, score, current_time, 0, False, 0, 0)
                    currentUsersClassList.append(new_user)
                    predictions_updated = True

                    # await save_to_file()
                    # write currentPredictionsClassList to a file
                    # with open('currentPredictionsClassList.list', 'wb') as currentPredictionsClassList_file:
                    #     pickle.dump(currentUsersClassList, currentPredictionsClassList_file)

                    # with open("file.json", "w") as f:
                    # json.dumps(currentUsersClassList, indent=2)
                    # json.dump(currentUsersClassList, f, indent=2)

                    response = f"You have predicted {home_team} {score} {away_team}\n"\
                               + random.choice(correct_score_format) + author_mention_name + '!'

                    print(f'A user has made a prediction - {author_text_name} {score}')

                # else:
                #     response = "You shouldn't see this"
            else:
                response = "Maybe try being a little more realistic!"
        else:
            response = f"Please structure your prediction correctly e.g. *{command_prefix}p 1-0*"


    await ctx.send(response)


@bot.command(name='correct-scores', help='Check your total number of correct guesses!', aliases=["cs"])
async def correct_scores(ctx):
    author_mention_name = format(ctx.message.author.mention)
    response = "It looks like you haven't made any predictions yet!"
    for each in currentUsersClassList:
        if each.mentionName == author_mention_name:
            if each.previousPredictionCorrect:
                response = f'You have correctly predicted {each.numCorrectPredictions} result(s)' \
                           f' and your previous guess was correct. Good luck on your prediction streak, ' \
                           f'it is currently {each.predictionStreak} in a row.'
            else:
                response = f'You have correctly predicted {each.numCorrectPredictions} result(s).'
            break
    await ctx.send(response)
    print(f'A user ({ctx.message.author}) requested their correct_scores')


@bot.command(name='score-streak', help='Check your current number of correct guesses in a row!', aliases=["ss"])
async def score_streak(ctx):
    author_mention_name = format(ctx.message.author.mention)
    response = "It looks like you haven't made any predictions yet!"
    for each in currentUsersClassList:
        if each.mentionName == author_mention_name:
            if each.predictionStreak == 0:
                response = f"Your streak is {each.predictionStreak}. " \
                           f"It looks like you got the previous result wrong or you didn't make a guess!"
            elif each.predictionStreak == 1:
                response = f"Your streak is {each.predictionStreak}. " \
                           f"Congratulations on the previous correct result, good luck on the next one!"
            else:
                response = f'Your current streak is {each.predictionStreak} correct predictions in a row!'
            break
    await ctx.send(response)
    print(f'A user ({ctx.message.author}) requested their score_streak')


@bot.command(name='predictions', help='Show all upcoming or current match predictions!',
             aliases=["cpr", "current-predictions"])
async def current_predictions(ctx):
    # Create temporary currentPredictions list from Objects rather than globally
    current_predictions_list = []
    for each in currentUsersClassList:
        if each.currentPrediction is None:
            continue
        score_and_name = each.currentPrediction + ' - ' + each.username
        current_predictions_list.append(score_and_name)

    home_team = nextFixture['teams']['home']['name']
    away_team = nextFixture['teams']['away']['name']
    competition = nextFixture['league']['name']
    competition_round = nextFixture['league']['round']
    competition_icon_url = nextFixture['league']['logo']

    if matchInProgress:
        home_team = currentFixture['teams']['home']['name']
        away_team = currentFixture['teams']['away']['name']
        competition = currentFixture['league']['name']
        competition_round = currentFixture['league']['round']
        competition_icon_url = currentFixture['league']['logo']

    # Is the match at Home or Away
    if home_team == 'West Ham':
        is_home = True
        opposition_logo = nextFixture['teams']['away']['logo']
    else:
        is_home = False
        opposition_logo = nextFixture['teams']['home']['logo']

    if matchInProgress:
        if home_team == 'West Ham':
            is_home = True
            opposition_logo = currentFixture['teams']['away']['logo']
        else:
            is_home = False
            opposition_logo = currentFixture['teams']['home']['logo']

    # Combine attributes of each object in UserAndScore class into one string and add to new list
    # if not current_predictions_list:
    #     if is_home:
    #         response = f'No score predictions for **West Ham vs {away_team}**, why not be the first!'
    #     else:
    #         response = f'No score predictions for **{home_team} vs West Ham**, why not be the first!'
    # else:
    #     if is_home:
    #         response = f'Here are all the score predictions for **West Ham vs {away_team}**\n\n' \
    #                    + '\n'.join(current_predictions_list)
    #     else:
    #         response = f'Here are all the score predictions for **{home_team} vs West Ham**\n\n' \
    #                    + '\n'.join(current_predictions_list)
    # await ctx.send(response)

    embed = discord.Embed(title="Current Predictions", colour=discord.Colour.from_rgb(129, 19, 49))

    if not current_predictions_list:
        if is_home:
            response = f'No score predictions for *West Ham vs {away_team}*\n' \
                       f'in the {competition} ({competition_round})'
        else:
            response = f'No score predictions for *{home_team} vs West Ham*\n' \
                       f'in the {competition} ({competition_round})'

        sub_header = f'Why not be the first to make a guess!'
        embed.add_field(name=response, value=sub_header)

    else:

        predictions_string = '\n'.join(current_predictions_list)

        if is_home:
            response = f'Score predictions for *West Ham vs {away_team}*\n' \
                       f'in the {competition} ({competition_round})'
        else:
            response = f'Score predictions for *{home_team} vs West Ham*\n' \
                       f'in the {competition} ({competition_round})'

        embed.add_field(name=response, value=predictions_string)

    embed.set_thumbnail(url=opposition_logo)
    embed.set_footer(text=f'{competition} ({competition_round})', icon_url=competition_icon_url)

    await ctx.send(embed=embed)
    print(f'A user ({ctx.message.author}) requested upcoming match predictions')


@bot.command(name='leaderboard', help='Shows top score predictors!', aliases=["lb"])
async def command_leaderboard(ctx):
    await leaderboard()
    print(f'A user ({ctx.message.author}) requested the predictions leaderboard')


@bot.command(name='next-fixture', help='Show the next fixture information', aliases=["nf"])
async def command_next_fixture(ctx):
    await next_fixture()
    print(f'A user ({ctx.message.author}) requested the next fixture information')


# ----------------------------------------------------------------------------------------------------------------------


# Admin Tools
# ----------------------------------------------------------------------------------------------------------------------
@bot.command(name='admintest', help='Admin Only - Tells you if you have admin rights')
@commands.has_permissions(administrator=True)
async def admintest(ctx):
    await ctx.send('You have admin rights')
    print(f'admintest run in {ctx.guild.name} ({ctx.guild.id}) by {ctx.message.author}')


# At the moment, this function will clear the User Objects, so all current predictions and any scoreboard rating
@bot.command(name='clear-users',
             help='Admin Only - Clear ALL the users, predictions and their history in memory - use with caution')
@commands.has_permissions(administrator=True)
async def clear_users(ctx):
    currentUsersClassList.clear()
    await ctx.send('Memory has been cleared')

    await save_to_file()
    await ctx.send('Files have been cleared')

    print(f'Clear_Users run in {ctx.guild.name} ({ctx.guild.id}) by {ctx.message.author}')


@bot.command(name='force-backup', help='Admin Only - Force a file backup of the users')
@commands.has_permissions(administrator=True)
async def force_backup(ctx):
    await save_to_file()
    await ctx.send('Users backed up to file')

    print(f'Force backup run in {ctx.guild.name} ({ctx.guild.id}) by {ctx.message.author}')


# Writing and reading Users to Github as storage
# ----------------------------------------------------------------------------------------------------------------------
async def save_to_file():
    # create "data" and save all objects in currentUsersClassList in a nested dict
    data = {'Users': []}
    for each in currentUsersClassList:
        data['Users'].append({
            'mentionName': each.mentionName,
            'username': each.username,
            'currentPrediction': each.currentPrediction,
            'predictionTimestamp': each.predictionTimestamp,
            'numCorrectPredictions': each.numCorrectPredictions,
            'previousPredictionCorrect': each.previousPredictionCorrect,
            'predictionStreak': each.predictionStreak,
            'longestPredictionStreak': each.longestPredictionStreak
        })

    # perform local write (NO READ) for testing purposes
    with open('users.json', 'w') as outfile:
        json.dump(data, outfile, indent=2)

    # convert "data" to a json_string and send this to 'hc-bot-memory' repo on GitHub for backup
    json_string = json.dumps(data)
    github = Github(GITHUBTOKEN)
    repository = github.get_user().get_repo('hc-bot-memory')
    filename = 'users.json'
    contents = repository.get_contents("")
    all_files = []

    # check all values in contents
    while contents:
        # take first value as file_content
        file_content = contents.pop(0)
        # if file_content is a directory (shouldn't ever be)
        if file_content.type == "dir":
            contents.extend(repository.get_contents(file_content.path))
        # else must be a file
        else:
            file = file_content
            # remove extra text to create clean file name for comparison
            all_files.append(str(file).replace('ContentFile(path="', '').replace('")', ''))

    # check if filename matches in all_files list - if yes then update, if no then create
    try:
        if filename in all_files:
            contents = repository.get_contents(filename)
            repository.update_file(filename, "Updated predictions file", json_string, contents.sha)
        else:
            repository.create_file(filename, "Created predictions file", json_string)
        print(f'Users save to file successful')
    except:
        print(f'Users save to file FAILED')


async def read_from_file():
    try:
        # download file from Github repo 'hc-bot-memory' and decode to json_string
        github = Github(GITHUBTOKEN)
        repository = github.get_user().get_repo('hc-bot-memory')
        filename = 'users.json'
        file = repository.get_contents(filename)
        json_string = file.decoded_content.decode()
        # convert json_string to "data", nested dict
        data = json.loads(json_string)
        # set "data" to currentUsersClassList
        for each in data['Users']:
            new_user = UserAndScore(each['mentionName'],
                                    each['username'],
                                    each['currentPrediction'],
                                    each['predictionTimestamp'],
                                    each['numCorrectPredictions'],
                                    each['previousPredictionCorrect'],
                                    each['predictionStreak'],
                                    each['longestPredictionStreak'])
            currentUsersClassList.append(new_user)
        print(f'Users save to file successful')
    # if fail due to empty file, clear currentUsersClassList to an empty list
    except json.decoder.JSONDecodeError:
        currentUsersClassList.clear()
        print(f'Users save to file FAILED - or empty file')


async def save_error_to_file(error_string):
    data = error_string

    json_string = json.dumps(data)
    github = Github(GITHUBTOKEN)
    repository = github.get_user().get_repo('hc-bot-memory')
    filename = 'all_fixtures.json'
    contents = repository.get_contents("")
    all_files = []

    # check all values in contents
    while contents:
        # take first value as file_content
        file_content = contents.pop(0)
        # if file_content is a directory (shouldn't ever be)
        if file_content.type == "dir":
            contents.extend(repository.get_contents(file_content.path))
        # else must be a file
        else:
            file = file_content
            # remove extra text to create clean file name for comparison
            all_files.append(str(file).replace('ContentFile(path="', '').replace('")', ''))

    # check if filename matches in all_files list - if yes then update, if no then create
    try:
        if filename in all_files:
            contents = repository.get_contents(filename)
            repository.update_file(filename, "Updated all_fixtures error file", json_string, contents.sha)
        else:
            repository.create_file(filename, "Created all_fixtures error file", json_string)
        print(f'all_fixtures error save to file successful')
    except:
        print(f'all_fixtures error save to file FAILED')


# ----------------------------------------------------------------------------------------------------------------------

    # To sort out double digit correct predictions
    # maybe add a white space to single digit values to match spacing of double digit values?

@bot.event
async def leaderboard():
    unsorted_leaderboard_dict = {}
    leaderboardUsersClassList = currentUsersClassList

    # Sort leaderboardUsersClassList by timestamp, so first prediction is at the top of the printout
    leaderboardUsersClassList.sort(key=lambda x: x.predictionTimestamp)
    print(f'leaderboardUsersClassList sorted')

    for each in leaderboardUsersClassList:
        correct_predictions = each.numCorrectPredictions
        username = each.username
        unsorted_leaderboard_dict[username] = correct_predictions

    leaderboard_dict = {}
    sorted_key = sorted(unsorted_leaderboard_dict, key=unsorted_leaderboard_dict.get, reverse=True)
    for x in sorted_key:
        leaderboard_dict[x] = unsorted_leaderboard_dict[x]

    leaderboard_dict = {k:v for k, v in leaderboard_dict.items() if v != 0}


    # Format response into a table using Embed & monospaced code block
    if leaderboard_dict:
        title = "Correct Predictions"
        leaderboard_string = ("```" + "\n".join("  {}  |  {}".format(v, k) for k, v in leaderboard_dict.items()) + "```")
    else:
        title = f"No one has got a prediction right yet"
        leaderboard_string = f"See if you can be the first!"


    embed = discord.Embed(title="Top Predictors Leaderboard", colour=discord.Colour.from_rgb(129, 19, 49))
    embed.add_field(name=title, value=leaderboard_string)
    embed.set_thumbnail(url=predictor_bot_logo)
    this_channel = bot.get_channel(channel_id)
    await this_channel.send(embed=embed)

# #Api-Football - Leagues by team ID & season
# @bot.command(name='leagues', help='Which competitions are West Ham in?')
# async def leagues(ctx):
#     # url = "https://api-football-v1.p.rapidapi.com/v3/leagues"
#     #
#     # querystring = {
#     #     "season": "2021",
#     #     "team": "48"
#     # }
#     #
#     # headers = {
#     #     'x-rapidapi-host': "api-football-v1.p.rapidapi.com",
#     #     'x-rapidapi-key': RAPIDAPIKEY
#     # }
#     #
#     # api_response = requests.request("GET", url, headers=headers, params=querystring)
#     # data = api_response.text
#     # fixtures_dict_json = json.loads(data)
#
#
#     try:
#         with open('leagues_dict_json.json') as leagues_dict_json_file:
#             leagues_dict_json = json.load(leagues_dict_json_file)
#         # with open('leagues_dict_json.json', 'rb') as leagues_dict_json_file:
#         #     leagues_dict_json = pickle.load(leagues_dict_json_file)
#     except:
#         leagues_dict_json = []
#
#
#     full_leagues_list = []
#     for i in leagues_dict_json['response']:
#         full_leagues_list.append(i)
#
#     short_leagues_list = []
#     for i in full_leagues_list:
#         league_name = '\n' + (str(i['league']['name']))
#         short_leagues_list.append(league_name)
#
#         #all_league_names = all_league_names + league_name
#     all_league_names = ''.join(short_leagues_list)
#     response = 'West Ham are in the following competitions: ' + all_league_names
#
#     #Number of leagues
#     #number_of_leagues = str(response_dict_json['results'])
#     #response = 'West Ham are in ' + number_of_leagues + ' league/s'
#
#     await ctx.send(response)

# Bot Error testing
# ----------------------------------------------------------------------------------------------------------------------
# on error, write to err.log
@bot.event
async def on_error(event, *args, **kwargs):
    with open('err.log', 'a') as f:
        if event == 'on_message':
            f.write(f'Unhandled message: {args[0]}\n')
        else:
            raise


# ----------------------------------------------------------------------------------------------------------------------


check_fixtures.start()
check_next_fixture.start()
check_save.start()
reminder.start()

bot.run(TOKEN)

exit()
