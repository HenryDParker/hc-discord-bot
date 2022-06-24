import pymysql

ENDPOINT = "db-scorepredictor.cesiamq9hubf.eu-west-2.rds.amazonaws.com"
PORT = 3306
USER = "admin"
PASSWORD = "QJ4NCV&pnj6j"
REGION = "eu-west-2"
DBNAME = "scorepredictor"

db = pymysql.connect(host=ENDPOINT, port=PORT, user=USER, passwd=PASSWORD, db=DBNAME)
cursor = db.cursor()

print(f'database read')