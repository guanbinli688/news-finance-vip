from .validation import validate_prediction

def accepted_predictions(raw):
    return [result.prediction for item in raw for result in [validate_prediction(item)] if result.accepted]
