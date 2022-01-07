# bot.py
import json
import os
import random
import string
import re
import requests
import time
import datetime

from github import Github
from discord.ext import commands, tasks
from dotenv import load_dotenv
from datetime import date

# URL to invite bot
# https://discord.com/api/oauth2/authorize?client_id=917479797242875936&permissions=274878114880&scope=bot

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
# GUILD = os.getenv('DISCORD_GUILD')
RAPIDAPIKEY = os.getenv('RAPIDAPI_KEY')
GITHUBTOKEN = os.getenv('GITHUB_TOKEN')

# client = discord.Client()
# define bot command decorator
bot = commands.Bot(command_prefix='!')


# Set up UserAndScore class
class UserAndScore:
    def __init__(self,
                 mentionName: str,
                 username: str,
                 currentPrediction,
                 numCorrectPredictions: int,
                 previousPredictionCorrect: bool,
                 predictionStreak: int,
                 longestPredictionStreak: int):
        self.mentionName = mentionName
        self.username = username
        self.currentPrediction = currentPrediction
        self.numCorrectPredictions = numCorrectPredictions
        self.previousPredictionCorrect = previousPredictionCorrect
        self.predictionStreak = predictionStreak
        self.longestPredictionStreak = longestPredictionStreak


# Global Lists
currentUsersClassList = []

# Global Dictionaries
currentFixture = {}
nextFixture = {}
discord_channels = {}

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

# channel_id pulled from admin using !channel then stored in a dict & external json file on Github for any restarts

# Test Server Channel ID
# channel_id = 917754145367289929

# Hammers Chat Channel ID
# channel_id = 818488786190991360


# regex definitions
scorePattern = re.compile('^[0-9]{1,2}-[0-9]{1,2}$')
scorePatternHigh = re.compile('^[0-9]{1,5}-[0-9]{1,5}$')


@bot.command(name='channel', help='Admin Only - Assign the channel that this bot will operate in')
@commands.has_permissions(administrator=True)
async def which_channel(ctx):
    guild_id = ctx.guild.id
    channel_id = ctx.channel.id
    discord_channels[guild_id] = channel_id
    await write_channel_backup()


async def write_channel_backup():
    # perform local write (NO READ) for testing purposes
    with open('channel_backup.json', 'w') as outfile:
        json.dump(discord_channels, outfile, indent=2)

    # convert "data" to a json_string and send this to 'hc-bot-memory' repo on GitHub for backup
    json_string = json.dumps(discord_channels)
    github = Github(GITHUBTOKEN)
    repository = github.get_user().get_repo('hc-bot-memory')
    filename = 'channel_backup.json'
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
        repository.update_file(filename, "Updated channel_backup file", json_string, contents.sha)
    else:
        repository.create_file(filename, "Created channel_backup file", json_string)


async def read_channel_backup():
    try:
        # download file from Github repo 'hc-bot-memory' and decode to json_string
        github = Github(GITHUBTOKEN)
        repository = github.get_user().get_repo('hc-bot-memory')
        filename = 'channel_backup.json'
        file = repository.get_contents(filename)
        json_string = file.decoded_content.decode()

        global discord_channels
        # convert json_string to "discord_channels"
        discord_channels = json.loads(json_string)

    # If the read fails in any way, send hardcoded warning message to Test Server and TAG ME
    except:
        test_server_id = bot.get_channel(917754145367289929)
        response = "This bot has failed to read the channel backup from Github <@110010452045467648> "
        await test_server_id.send(response)


# Check fixture info every hour
@tasks.loop(minutes=30)
async def check_fixtures():
    # Only perform this check after 8am and stop at midnight - can be removed if necessary
    # This will save API calls as few changes to West Ham fixture will occur between these times
    timenow = datetime.datetime.now()
    if timenow.hour >= 9:
        # find today's date
        today = date.today()
        # set the month to an int e.g. 02
        today_month = int(today.strftime("%m"))
        # set the year to an int e.g. 2021
        today_year = int(today.strftime("%Y"))

        # if the month is less than 6, set the current_season to the current year, -1 e.g in 02/2022 the season is 2021
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

        with open('fixtures_dict_json.json', 'w') as f:
            json.dump(fixtures_dict_json, f)

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


@tasks.loop(minutes=10)
async def check_save():
    global predictions_updated
    if bot_ready:
        if predictions_updated:
            await save_to_file()
            predictions_updated = False


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
    if bot_ready:
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
                    # increment correct predictions tally for "each" when correct
                    each.numCorrectPredictions += 1
                    # increase prediction streak by 1 and set previousPredictionCorrect to True
                    each.predictionStreak += 1
                    each.previousPredictionCorrect = True
                # else if wrong, set streak to 0 and previousPredictionCorrect to False
                else:
                    each.predictionStreak = 0
                    each.previousPredictionCorrect = False

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

            for each in discord_channels:
                this_channel = bot.get_channel(discord_channels[each])
                await this_channel.send(response)
            await next_fixture()


@bot.event
async def next_fixture():
    if bot_ready:
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
        for each in discord_channels:
            this_channel = bot.get_channel(discord_channels[each])
            await this_channel.send(response)


# When the bot joins a server
@bot.event
async def on_ready():
    global bot_ready
    global currentUsersClassList
    print(f'{bot.user.name} has connected to Discord!')
    results = f'{bot.user.name} has connected to Discord!'
    await read_channel_backup()
    bot_ready = True
    try:
        await read_from_file()
    except:
        currentUsersClassList = []
    for each in discord_channels:
        this_channel = bot.get_channel(discord_channels[each])
        await this_channel.send(results)
    await next_fixture()


@bot.command(name='p', help='Submit (or update) your score prediction! e.g. !p 2-1')
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

                score_added = False
                # Check if user already has a predictions - if yes, update it
                # for each UserAndScore object in List
                for each in currentUsersClassList:
                    # if User already exists in list
                    if each.mentionName == author_mention_name:
                        # update that user's current prediction
                        each.currentPrediction = score

                        # write currentPredictionsClassList to a file
                        # with open('currentPredictionsClassList.list', 'wb') as currentPredictionsClassList_file:
                        #     pickle.dump(currentUsersClassList, currentPredictionsClassList_file)

                        # await save_to_file()

                        # if this value is None, then prediction was reset from previous fixture
                        # and no previous prediction for this fixture has occurred
                        # to be used for Score Streak in Future Feature
                        if each.currentPrediction is None:
                            predictions_updated = True
                            response = random.choice(correct_score_format) + author_mention_name + '!'
                        else:
                            predictions_updated = True
                            response = '_Prediction updated_\n' + random.choice(correct_score_format) \
                                       + author_mention_name + '!'
                        score_added = True
                if not score_added:
                    # add new user & score to list
                    # new_user is an object of UserAndScore class with name and currentPrediction inside
                    # (more attributes to be added & set to 0/null)
                    new_user = UserAndScore(author_mention_name, author_text_name, score, 0, False, 0, 0)
                    currentUsersClassList.append(new_user)
                    predictions_updated = True

                    # await save_to_file()
                    # write currentPredictionsClassList to a file
                    # with open('currentPredictionsClassList.list', 'wb') as currentPredictionsClassList_file:
                    #     pickle.dump(currentUsersClassList, currentPredictionsClassList_file)

                    # with open("file.json", "w") as f:
                    # json.dumps(currentUsersClassList, indent=2)
                    # json.dump(currentUsersClassList, f, indent=2)

                    response = random.choice(correct_score_format) + author_mention_name + '!'
            else:
                response = "Maybe try being a little more realistic!"
        else:
            response = "Please structure your prediction correctly e.g. 1-0 "
    # ignore this error - not possible to return a blank response due to use of boolean "score_added"
    await ctx.send(response)


@bot.command(name='correct-scores', help='Check your total number of correct guesses!')
async def score_streak(ctx):
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


@bot.command(name='score-streak', help='Check your current number of correct guesses in a row!')
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



@bot.command(name='force-backup', help='Admin Only - Force a file backup of the users')
@commands.has_permissions(administrator=True)
async def force_backup(ctx):
    await save_to_file()
    await ctx.send('Users backed up to file')


async def save_to_file():
    # create "data" and save all objects in currentUsersClassList in a nested dict
    data = {'Users': []}
    for each in currentUsersClassList:
        data['Users'].append({
            'mentionName': each.mentionName,
            'username': each.username,
            'currentPrediction': each.currentPrediction,
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
    if filename in all_files:
        contents = repository.get_contents(filename)
        repository.update_file(filename, "Updated predictions file", json_string, contents.sha)
    else:
        repository.create_file(filename, "Created predictions file", json_string)


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
                                    each['numCorrectPredictions'],
                                    each['previousPredictionCorrect'],
                                    each['predictionStreak'],
                                    each['longestPredictionStreak'])
            currentUsersClassList.append(new_user)
    # if fail due to empty file, clear currentUsersClassList to an empty list
    except json.decoder.JSONDecodeError:
        currentUsersClassList.clear()


# At the moment, this function will clear the User Objects, so all current predictions and any scoreboard rating

@bot.command(name='clear-users',
             help='Admin Only - Clear ALL the users, predictions and their history in memory - use with caution')
@commands.has_permissions(administrator=True)
async def clear_users(ctx):
    currentUsersClassList.clear()

    await ctx.send('Memory has been cleared')

    await save_to_file()

    await ctx.send('Files have been cleared')

@bot.command(name='admintest', help='Admin Only - Tells you if you have admin rights')
@commands.has_permissions(administrator=True)
async def admintest(ctx):
    await ctx.send('You have admin rights')


@bot.command(name='predictions', help='Show all upcoming or current match predictions!')
async def current_predictions(ctx):
    # Create temporary currentPredictions list from Objects rather than globally
    current_predictions_list = []
    for each in currentUsersClassList:
        score_and_name = each.currentPrediction + ' - ' + each.username
        current_predictions_list.append(score_and_name)

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
    if not current_predictions_list:
        if is_home:
            response = f'No score predictions for **West Ham vs {away_team}**, why not be the first!'
        else:
            response = f'No score predictions for **{home_team} vs West Ham**, why not be the first!'
    else:
        if is_home:
            response = f'Here are all the score predictions for **West Ham vs {away_team}**\n\n' \
                       + '\n'.join(current_predictions_list)
        else:
            response = f'Here are all the score predictions for **{home_team} vs West Ham**\n\n' \
                       + '\n'.join(current_predictions_list)
    await ctx.send(response)


@bot.command(name='leaderboard', help='Shows top score predictors!')
async def leaderboard(ctx):
    unsorted_leaderboard_dict = {}
    for each in currentUsersClassList:
        correct_predictions = each.numCorrectPredictions
        username = each.username
        unsorted_leaderboard_dict[username] = correct_predictions

    leaderboard_dict = {}
    sorted_key = sorted(unsorted_leaderboard_dict, key=unsorted_leaderboard_dict.get, reverse=True)
    for x in sorted_key:
        leaderboard_dict[x] = unsorted_leaderboard_dict[x]

    # Format response into a table
    response = ("\n\n**Top Predictions Leaderboard**" +
                "\n\n```Correct Scores |  Username"
                "\n---------------+------------------------"
                "\n" + "\n".join("\t  {}\t\t|  {}".format(v, k) for k, v in leaderboard_dict.items()) + "```")

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
check_save.start()

bot.run(TOKEN)

exit()
