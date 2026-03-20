import os

import mlflow
import pandas as pd
from mlflow.models.signature import infer_signature

from notebooks.serving.starter_model import StarterModel


def get_df_and_signature():
    """Return a sample dataframe and its MLflow signature."""
    df = pd.DataFrame({"value": [1, 2, 3]})
    signature = infer_signature(df, df)
    return df, signature


mlflow.set_registry_uri("databricks-uc")

df, signature = get_df_and_signature()

with mlflow.start_run() as run:
    model_info = mlflow.pyfunc.log_model(
        python_model=StarterModel(),
        code_path=["./starter_model.py"],
        artifact_path="model",
        input_example=df,
        pip_requirements="./requirements.txt",
        signature=signature,
    )

# Model name can be overridden via the MODEL_NAME environment variable
name = os.getenv("MODEL_NAME", "app.default.dummy-serving-endpoint")

new_model = mlflow.register_model(model_info.model_uri, name)

