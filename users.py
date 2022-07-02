# Set up UserAndScore class

class UserAndScore:
    def __init__(self,
                 mentionName: str,
                 username: str,
                 currentPrediction,
                 predictionTimestamp,
                 numCorrectPredictions: int,
                 previousPredictionCorrect: int,
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
