# bot.py
import json
import os
import random
import discord
import pickle
import string
import re
import requests
import time

from discord.ext import commands, tasks
from dotenv import load_dotenv
from datetime import datetime


# URL to invite bot - https://discord.com/api/oauth2/authorize?client_id=917479797242875936&permissions=274878114880&scope=bot

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
# GUILD = os.getenv('DISCORD_GUILD')

# client = discord.Client()
# define bot command decorator
bot = commands.Bot(command_prefix='!')

# Set up UserAndScore class
class UserAndScore:
    def __init__(self, name, currentPrediction):
        self.name = name
        self.currentPrediction = currentPrediction
        #self.numCorrectPredictions = numCorrectPredictions
        #self.leaderboardPosition = leaderboardPosition

# Global Lists
currentUsersClassList = []
currentPredictions = []

# Global Dictionaries
nextFixture = {}

# list of responses to a correct score format
correct_score_format = [
    'Good luck, ',
    'Wish you the best, ',
    'Best of luck, ',
    'Fingers crossed, ',
]

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

@tasks.loop(minutes=60)
async def check_fixtures():
    if datetime.now().hour == 1:
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

@tasks.loop(minutes=60)
async def check_next_fixtures():
    with open("fixtures_dict_json.json", "r") as read_file:
        all_fixtures = json.load(read_file)

        # Test - pulls first fixture's timestamp
        first_fixture = all_fixtures['response'][0]['fixture']['timestamp']

        # creates list with full "response" dictionary from api
        all_fixtures_list = all_fixtures['response']

        # for each item in response dictionary list, find timestamp
        current_time = int(time.time())
        for each in all_fixtures['response']:
            fixture_time = (each['fixture']['timestamp'])
            time_difference = fixture_time - current_time
            # check is difference is negative - if yes, skip to next for loop iteration
            if time_difference <= 0:
                continue

            # otherwise store the fixture & break out of for loop
            else:
                global nextFixture
                nextFixture = each
                break

# When the bot joins a server
@bot.event
async def on_ready():
    print(f'{bot.user.name} has connected to Discord!')

# Sends a DM when a person joins the server
# @bot.event
# async def on_member_join(member):
#     await member.create_dm()
#     await member.dm_channel.send(
#         f'Hi {member.name}, welcome to my Discord server!'
#     )

# Api-Football Statistics based on team id
@bot.command(name='massive', help='Who is absolutely massive?')
async def massive(ctx):
    url = "https://api-football-v1.p.rapidapi.com/v3/teams/statistics"

    querystring = {"league": "39", "season": "2021", "team": "48"}

    headers = {
        'x-rapidapi-host': "api-football-v1.p.rapidapi.com",
        'x-rapidapi-key': "44ffe7d755msh9b3e1938f982d4bp104096jsn7da8ebb4fde8"
    }

    api_response = requests.request("GET", url, headers=headers, params=querystring)
    data = api_response.text
    response_dict_json = json.loads(data)
    team_name = str(response_dict_json['response']['team']['name'])

    response = team_name + ' are absolutely massive'

    await ctx.send(response)



#Api-Football - Leagues by team ID & season
@bot.command(name='leagues', help='Which competitions are West Ham in?')
async def leagues(ctx):
    # url = "https://api-football-v1.p.rapidapi.com/v3/leagues"
    #
    # querystring = {
    #     "season": "2021",
    #     "team": "48"
    # }
    #
    # headers = {
    #     'x-rapidapi-host': "api-football-v1.p.rapidapi.com",
    #     'x-rapidapi-key': "44ffe7d755msh9b3e1938f982d4bp104096jsn7da8ebb4fde8"
    # }
    #
    # api_response = requests.request("GET", url, headers=headers, params=querystring)
    # data = api_response.text
    # fixtures_dict_json = json.loads(data)


    try:
        with open('leagues_dict_json.json') as leagues_dict_json_file:
            leagues_dict_json = json.load(leagues_dict_json_file)
        # with open('leagues_dict_json.json', 'rb') as leagues_dict_json_file:
        #     leagues_dict_json = pickle.load(leagues_dict_json_file)
    except:
        leagues_dict_json = []


    full_leagues_list = []
    for i in leagues_dict_json['response']:
        full_leagues_list.append(i)

    short_leagues_list = []
    for i in full_leagues_list:
        league_name = '\n' + (str(i['league']['name']))
        short_leagues_list.append(league_name)

        #all_league_names = all_league_names + league_name
    all_league_names = ''.join(short_leagues_list)
    response = 'West Ham are in the following leagues: ' + all_league_names

    #Number of leagues
    #number_of_leagues = str(response_dict_json['results'])
    #response = 'West Ham are in ' + number_of_leagues + ' league/s'

    await ctx.send(response)




@bot.command(name='p', help='Submit your score prediction!')
async def user_prediction(ctx, score):
    score.translate({ord(c): None for c in string.whitespace})

    if scorePatternHigh.match(score):
        if scorePattern.match(score):
            # find user that sent command
            messageAuthor = format(ctx.message.author.mention)

            # for each UserAndScore object in List
            for UserAndScoreObj in currentUsersClassList:
                # if User already exists in list
                if UserAndScoreObj.name == messageAuthor:
                    # update that user's current prediction
                    UserAndScore.currentPrediction = score
                    UserAndScore.name = messageAuthor

                    x = currentUsersClassList.index(UserAndScoreObj)

                    currentUsersClassList[x] = UserAndScore
                    existingUser = UserAndScore(messageAuthor, score)
                    scoreAndName = existingUser.currentPrediction + ' - ' + existingUser.name

                    currentPredictions[x] = scoreAndName

                    # write currentPredictionsClassList to a file
                    # with open('currentPredictionsClassList.list', 'wb') as currentPredictionsClassList_file:
                    #     pickle.dump(currentUsersClassList, currentPredictionsClassList_file)

                    # write currentPredictions to a file
                    # with open('currentPredictions.list', 'wb') as currentPredictions_file:
                    #     pickle.dump(currentPredictions, currentPredictions_file)

                    break
            else:
                #add new user & score to list
                # newUser is an object of UserAndScore class with name and currentPrediction inside (more attributes to be added & set to 0/null)
                newUser = UserAndScore(messageAuthor, score)
                currentUsersClassList.append(newUser)


                # write currentPredictionsClassList to a file
                # with open('currentPredictionsClassList.list', 'wb') as currentPredictionsClassList_file:
                #     pickle.dump(currentUsersClassList, currentPredictionsClassList_file)

                #with open("file.json", "w") as f:
                #json.dumps(currentUsersClassList, indent=2)
                    #json.dump(currentUsersClassList, f, indent=2)

                scoreAndName = newUser.currentPrediction + ' - ' + newUser.name
                currentPredictions.append(scoreAndName)

                # write currentPredictions to a file
                with open('currentPredictions.list', 'wb') as currentPredictions_file:
                    pickle.dump(currentPredictions, currentPredictions_file)

                # currentPredictions = json.dumps("currentPredictions.json")

            response = random.choice(correct_score_format) + messageAuthor + '!'

        else:
            response = "Maybe try being a little more realistic!"
    else:
        response = "Please structure your prediction correctly e.g. 1-0 "
    await ctx.send(response)

@bot.command(name='clear-predictions')
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



@bot.command(name='predictions', help='Shows all upcoming or current match predictions!')
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

    # Is the match at Home or Away
    if home_team == 'West Ham':
        is_home = True
    else:
        is_home = False

    # Combine attributes of each object in UserAndScore class into one string and add to new list
    if not currentPredictions:
        response = 'No score predictions yet, why not be the first!'
    else:
        if is_home:
            response = 'Here are all the score predictions vs ' + away_team + '\n\n' + '\n'.join(currentPredictions)
        else:
            response = 'Here are all the score predictions vs ' + home_team + '\n\n' + '\n'.join(currentPredictions)
    await ctx.send(response)


@bot.command(name='leaderboard', help='Shows top score predictors!')
async def leaderboard(ctx):
    response = 'A leaderboard is coming soon!'
    await ctx.send(response)


# on error, write to err.log
@bot.event
async def on_error(event, *args, **kwargs):
    with open('err.log', 'a') as f:
        if event == 'on_message':
            f.write(f'Unhandled message: {args[0]}\n')
        else:
            raise

check_fixtures.start()
check_next_fixtures.start()

bot.run(TOKEN)

exit()
