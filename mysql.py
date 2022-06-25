import pymysql
import os
from dotenv import load_dotenv

load_dotenv()

PASSWORD = os.getenv('AWS_DB_PASS')
ENDPOINT = os.getenv('AWS_DB_ENDPOINT')

PORT = 3306
USER = "admin"
REGION = "eu-west-2"
DBNAME = "scorepredictor"

db = pymysql.connect(host=ENDPOINT, port=PORT, user=USER, passwd=PASSWORD, db=DBNAME)
cursor = db.cursor()

print(f'database read')
