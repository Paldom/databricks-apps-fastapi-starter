import mlflow
from mlflow.models import set_model
import pandas as pd


class StarterModel(mlflow.pyfunc.PythonModel):
    def __init__(self):
        # The starter model has no state to initialize.
        pass

    def predict(self, context, model_input: pd.DataFrame) -> pd.DataFrame:
        df = model_input
        return df


model = StarterModel()
set_model(model)

