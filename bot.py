# bot.py
import json
import os
import random
# import discord
import pickle
import string
import re
import requests
import time

from discord.ext import commands, tasks
from dotenv import load_dotenv
# from datetime import datetime

# URL to invite bot
# https://discord.com/api/oauth2/authorize?client_id=917479797242875936&permissions=274878114880&scope=bot

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
# GUILD = os.getenv('DISCORD_GUILD')

# client = discord.Client()
# define bot command decorator
bot = commands.Bot(command_prefix='!')


# Set up UserAndScore class
class UserAndScore:
    def __init__(self, mentionName, username, currentPrediction):
        self.mentionName = mentionName
        self.username = username
        self.currentPrediction = currentPrediction
        # self.numCorrectPredictions = numCorrectPredictions
        # self.leaderboardPosition = leaderboardPosition


# Global Lists
currentUsersClassList = []
currentPredictions = []

# Global Dictionaries
currentFixture = {}
nextFixture = {}

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

channel_id = 917754145367289929

current_fixture_id = None

# regex definitions
scorePattern = re.compile('^[0-9]{1,2}-[0-9]{1,2}$')
scorePatternHigh = re.compile('^[0-9]{1,5}-[0-9]{1,5}$')

# try:
#     with open('currentPredictionsClassList.list', 'rb') as currentPredictionsClassList_file:
#         currentUsersClassList = pickle.load(currentPredictionsClassList_file)
# except:
#     currentUsersClassList = []

try:
    # with open("file.json", 'r') as f:
    #     currentUsersClassList = json.loads(f)
    currentUsersClassList = json.loads("file.json")
except:
    currentUsersClassList = []

try:
    # with open('currentPredictions.list', 'rb') as currentPredictions_file:
    #     currentPredictions = pickle.load(currentPredictions_file)

    currentPredictions = json.loads("currentPredictions.json")
except:
    currentPredictions = []


# Option 2 Lists
# currentScorePredictions = []
# currentUserPredictions = []


# Check fixture info every hour
@tasks.loop(minutes=30)
async def check_fixtures():
    #    if datetime.now().hour == 14:
    # API call to get team fixtures for 2021 Season
    url_fixtures = "https://api-football-v1.p.rapidapi.com/v3/fixtures"

    querystring_fixtures = {"season": "2021", "team": "48"}

    headers_fixtures = {
        'x-rapidapi-host': "api-football-v1.p.rapidapi.com",
        'x-rapidapi-key': "44ffe7d755msh9b3e1938f982d4bp104096jsn7da8ebb4fde8"
    }

    api_response = requests.request("GET", url_fixtures, headers=headers_fixtures, params=querystring_fixtures)
    data = api_response.text
    fixtures_dict_json = json.loads(data)

    # with open('fixtures_dict_json.json', 'wb') as fixtures_dict_json_file:
    #     pickle.dump(fixtures_dict_json, fixtures_dict_json_file)

    with open('fixtures_dict_json.json', 'w') as f:
        json.dump(fixtures_dict_json, f)

    # API call to get team info for 2021 Season
    url_leagues = "https://api-football-v1.p.rapidapi.com/v3/leagues"

    querystring_leagues = {
        "season": "2021",
        "team": "48"
    }

    headers_leagues = {
        'x-rapidapi-host': "api-football-v1.p.rapidapi.com",
        'x-rapidapi-key': "44ffe7d755msh9b3e1938f982d4bp104096jsn7da8ebb4fde8"
    }

    api_response = requests.request("GET", url_leagues, headers=headers_leagues, params=querystring_leagues)
    data = api_response.text
    leagues_dict_json = json.loads(data)

    # with open('leagues_dict_json.json', 'wb') as leagues_dict_json_file:
    #     pickle.dump(leagues_dict_json, leagues_dict_json_file)

    with open('leagues_dict_json.json', 'w') as f:
        json.dump(leagues_dict_json, f)




# looping every minute for testing purposes
@tasks.loop(minutes=1)
async def check_next_fixture():
    global matchInProgress
    with open("fixtures_dict_json.json", "r") as read_file:
        all_fixtures = json.load(read_file)

        # Test - pulls first fixture's timestamp
        # first_fixture = all_fixtures['response'][0]['fixture']['timestamp']

        # creates list with full "response" dictionary from api
        all_fixtures_list = all_fixtures['response']

        # for each item in response dictionary list, find timestamp
        current_time = int(time.time())

        # set shortest_time_diff to arbitrarily high value
        global shortest_time_diff
        shortest_time_diff = current_time
        global currentFixture
        global current_fixture_id

        if current_fixture_id is not None:
            for each in all_fixtures['response']:
                if each['fixture']['id'] == current_fixture_id:
                    if each['fixture']['status']['short'] == 'FT' \
                            or each == 'AET' \
                            or each == 'PEN' \
                            or each == 'PST' \
                            or each == 'CANC' \
                            or each == 'ABD' \
                            or each == 'AWD' \
                            or each == 'WO':
                        await give_results()
                        current_fixture_id = None
                        currentFixture = {}
                        break

        for each in all_fixtures['response']:
            # get fixture timestamp
            fixture_time = (each['fixture']['timestamp'])
            # get fixture status
            fixture_status = (each['fixture']['status']['short'])

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
                    or fixture_status == 'INT':
                matchInProgress = True
                # get fixture id
                current_fixture_id = (each['fixture']['id'])
                currentFixture = each
                break

            # else check if fixture status is not started
            elif fixture_status == 'NS':
                # if not matchInProgress:

                # is time to fixture less than the current shortest time to fixture?
                if time_difference < shortest_time_diff:
                    # yes, set as new shortest time and set as nextFixture
                    shortest_time_diff = time_difference
                    global nextFixture
                    nextFixture = each

                else:
                    # no, continue to next fixture
                    continue

            # TBD, SUSP, INT
            else:
                # check if previous iteration had a match in progress
                if matchInProgress:
                    await give_results()
                    matchInProgress = False
                continue



@bot.event
async def give_results():
    # Channel ID is static as not sure how to pull Channel ID in code
    if bot_ready:
        channel = bot.get_channel(channel_id)

        with open("fixtures_dict_json.json", "r") as read_file:
            all_fixtures = json.load(read_file)

            for each in all_fixtures['response']:
                if current_fixture_id == (each['fixture']['id']):
                    home_team = each['teams']['home']['name']
                    away_team = each['teams']['away']['name']
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

            # Create an initially empty list for the correct predictions
            correct_prediction_list = []
            # For each object in class, check if their currentPrediction matches the fixture score result
            # then add to correct_prediction_list if it does
            for each in currentUsersClassList:
                if each.currentPrediction == fixture_result_score:
                    correct_prediction_user_mention = each.mentionName
                    correct_prediction_list.append(correct_prediction_user_mention)
            # Check if list is empty (no correct guesses) and print a response accordingly
            # --- unsure whether this is the correct pythonic way to check empty list
            # if correct_prediction_list is None:
            if not correct_prediction_list:
                response = f'The match finished {fixture_result_full}\n' \
                           f'\n' \
                           f'Unfortunately no one guessed the score correctly!'
            # else there must be at least one correct prediction, so congratulate user(s) with an @Mention tag
            else:
                correct_predictions = '\n'.join(correct_prediction_list)
                response = f'The match finished {fixture_result_full}\n' \
                           f'\n' \
                           f'Well done:\n' \
                           f'{correct_predictions}'
            # now clear all user Objects' current predictions in the list
            for each in currentUsersClassList:
                each.currentPrediction = None
            await channel.send(response)
            await next_fixture()


@bot.event
async def next_fixture():
    # Channel ID is static as not sure how to pull Channel ID in code
    if bot_ready:
        channel = bot.get_channel(channel_id)
        # Grab details for next match

        next_home_team = nextFixture['teams']['home']['name']
        next_away_team = nextFixture['teams']['away']['name']

        if next_home_team == 'West Ham':
            is_home = True
        else:
            is_home = False

        if is_home:
            response = f'The next fixture is **West Ham vs {next_away_team}**\nGet your predictions in now using _!p_\n'
        else:
            response = f'The next fixture is **{next_home_team} vs West Ham**\nGet your predictions in now using _!p_\n'

        await channel.send(response)




# When the bot joins a server
@bot.event
async def on_ready():
    global bot_ready
    print(f'{bot.user.name} has connected to Discord!')
    channel = bot.get_channel(channel_id)
    results = f'{bot.user.name} has connected to Discord!'
    bot_ready = True
    await channel.send(results)
    await next_fixture()


# # Api-Football Statistics based on team id
# @bot.command(name='massive', help='Who is absolutely massive?')
# async def massive(ctx):
#     url = "https://api-football-v1.p.rapidapi.com/v3/teams/statistics"
#
#     querystring = {"league": "39", "season": "2021", "team": "48"}
#
#     headers = {
#         'x-rapidapi-host': "api-football-v1.p.rapidapi.com",
#         'x-rapidapi-key': "44ffe7d755msh9b3e1938f982d4bp104096jsn7da8ebb4fde8"
#     }
#
#     api_response = requests.request("GET", url, headers=headers, params=querystring)
#     data = api_response.text
#     response_dict_json = json.loads(data)
#     team_name = str(response_dict_json['response']['team']['name'])
#
#     response = team_name + ' are absolutely massive'
#
#     await ctx.send(response)


@bot.command(name='p', help='Submit your score prediction! e.g. 2-1')
async def user_prediction(ctx, score):
    # get current time
    current_time = int(time.time())
    # get next fixtures time
    fixture_time = nextFixture['fixture']['timestamp']
    # check if the fixture has started
    if fixture_time - current_time <= 0 or matchInProgress:
        response = "Sorry, you're too late!\nThe match has already started!"
    else:
        score.translate({ord(c): None for c in string.whitespace})

        if scorePatternHigh.match(score):
            if scorePattern.match(score):
                # find user that sent command
                author_mention_name = format(ctx.message.author.mention)
                author_text_name = format(ctx.message.author)

                # for each UserAndScore object in List
                for UserAndScoreObj in currentUsersClassList:
                    # if User already exists in list
                    if UserAndScoreObj.mentionName == author_mention_name:
                        # update that user's current prediction
                        UserAndScore.currentPrediction = score
                        UserAndScore.mentionName = author_mention_name

                        x = currentUsersClassList.index(UserAndScoreObj)

                        currentUsersClassList[x] = UserAndScore
                        existing_user = UserAndScore(author_mention_name, author_text_name, score)
                        score_and_name = existing_user.currentPrediction + ' - ' + existing_user.username

                        currentPredictions[x] = score_and_name

                        # write currentPredictionsClassList to a file
                        # with open('currentPredictionsClassList.list', 'wb') as currentPredictionsClassList_file:
                        #     pickle.dump(currentUsersClassList, currentPredictionsClassList_file)

                        # write currentPredictions to a file
                        # with open('currentPredictions.list', 'wb') as currentPredictions_file:
                        #     pickle.dump(currentPredictions, currentPredictions_file)

                        break
                else:
                    # add new user & score to list
                    # new_user is an object of UserAndScore class with name and currentPrediction inside
                    # (more attributes to be added & set to 0/null)
                    new_user = UserAndScore(author_mention_name, author_text_name, score)
                    currentUsersClassList.append(new_user)

                    # write currentPredictionsClassList to a file
                    # with open('currentPredictionsClassList.list', 'wb') as currentPredictionsClassList_file:
                    #     pickle.dump(currentUsersClassList, currentPredictionsClassList_file)

                    # with open("file.json", "w") as f:
                    # json.dumps(currentUsersClassList, indent=2)
                    # json.dump(currentUsersClassList, f, indent=2)

                    score_and_name = new_user.currentPrediction + ' - ' + new_user.username
                    currentPredictions.append(score_and_name)

                    # write currentPredictions to a file
                    with open('currentPredictions.list', 'wb') as currentPredictions_file:
                        pickle.dump(currentPredictions, currentPredictions_file)

                    # currentPredictions = json.dumps("currentPredictions.json")

                response = random.choice(correct_score_format) + author_mention_name + '!'

            else:
                response = "Maybe try being a little more realistic!"
        else:
            response = "Please structure your prediction correctly e.g. 1-0 "
    await ctx.send(response)


# At the moment, this function will clear the User Objects, so all current predictions and any scoreboard rating

@bot.command(name='clear-predictions', help='Clear the users and predictions in memory')
async def clear_predictions(ctx):
    currentUsersClassList.clear()
    currentPredictions.clear()

    await ctx.send('Memory has been cleared')

    with open('currentPredictionsClassList.list', 'wb') as currentPredictionsClassList_file:
        pickle.dump(currentUsersClassList, currentPredictionsClassList_file)

    with open('currentPredictions.list', 'wb') as currentPredictions_file:
        pickle.dump(currentPredictions, currentPredictions_file)

    # currentPredictions = json.dumps("currentPredictions.json")

    await ctx.send('Files have been cleared')


@bot.command(name='predictions', help='Show all upcoming or current match predictions!')
async def current_predictions(ctx):
    # Test Values
    # predictions = [
    #     '1-0 - RealCat',
    #     '1-1 - Hammers4life',
    #     '1-0 - Gonzo',
    #     '2-2 - Geo',
    # ]
    # # put all values in list into "response" string separated by a new line "\n"
    # response = 'Here are all the predictions vs Chelsea\n\n' + '\n'.join(predictions)

    home_team = nextFixture['teams']['home']['name']
    away_team = nextFixture['teams']['away']['name']

    if matchInProgress:
        home_team = currentFixture['teams']['home']['name']
        away_team = currentFixture['teams']['away']['name']

    # Is the match at Home or Away
    if home_team == 'West Ham':
        is_home = True
    else:
        is_home = False

    # Combine attributes of each object in UserAndScore class into one string and add to new list
    if not currentPredictions:
        if is_home:
            response = f'No score predictions for West Ham vs {away_team}, why not be the first!'
        else:
            response = f'No score predictions for {home_team} vs West Ham, why not be the first!'
    else:
        if is_home:
            response = f'Here are all the score predictions for West Ham vs {away_team}\n\n'\
                       + '\n'.join(currentPredictions)
        else:
            response = f'Here are all the score predictions for {home_team} vs West Ham\n\n'\
                       + '\n'.join(currentPredictions)
    await ctx.send(response)


@bot.command(name='leaderboard', help='Shows top score predictors!')
async def leaderboard(ctx):
    response = 'A leaderboard is coming soon!'
    await ctx.send(response)


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
#     #     'x-rapidapi-key': "44ffe7d755msh9b3e1938f982d4bp104096jsn7da8ebb4fde8"
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
#     response = 'West Ham are in the following leagues: ' + all_league_names
#
#     #Number of leagues
#     #number_of_leagues = str(response_dict_json['results'])
#     #response = 'West Ham are in ' + number_of_leagues + ' league/s'
#
#     await ctx.send(response)


# on error, write to err.log
@bot.event
async def on_error(event, *args, **kwargs):
    with open('err.log', 'a') as f:
        if event == 'on_message':
            f.write(f'Unhandled message: {args[0]}\n')
        else:
            raise


check_fixtures.start()
check_next_fixture.start()

bot.run(TOKEN)

exit()
