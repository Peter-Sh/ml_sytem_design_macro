import click
from etna.datasets.tsdataset import TSDataset
from etna.metrics import MAE, MSE, SMAPE, MAPE
from etna.models import CatBoostPerSegmentModel, LinearPerSegmentModel, NaiveModel
from etna.pipeline import Pipeline
import joblib
import pandas as pd
import logging
import os

from etna.transforms import LogTransform, LagTransform


# @click.command()
# # @click.argument("src_model_file_path", type=click.Path())
# @click.argument("src_model_name", type=str, default="CatBoostPerSegmentModel")  # TBD: discuss with the team
# @click.argument("src_data_file_path", type=click.Path(), default="../../data/interim/stockdata.csv.gz")
# @click.argument("src_data_timeframe", type=str, default="H")
# @click.argument("column_for_timestamp", type=str, default="ts")
# @click.argument("column_for_target", type=str, default="adj_close")
# @click.argument("forecast_horizon", type=int, default=1)
# @click.argument("backtest_n_folds", type=int, default=24)
# @click.argument("out_predictions_file_path", type=click.Path(), default="../../data/predicted/predictions.csv.gz")
def launch_model_backtesting(
    # src_model_file_path: str,
    src_model_name: str,        # Hard-coded (TBD) ETNA model name
    src_data_file_path: str,
    src_data_timeframe: str,    # Frequency of data record. Ex: "MS" for months, "H" for 1h
    column_for_timestamp: str,
    column_for_target: str,
    forecast_horizon: int,      # Set the horizon for predictions
    backtest_n_folds: int,
    out_predictions_file_path: str,
):
    """
    Loads trained model, loads data, do predictions for the data, and exports them to the specified file.
    """
    logger = logging.getLogger(__name__)

    # TBD: check exceptions

    # Load the trained model from file
    # src_model_abs_file_path = os.path.abspath(src_model_file_path)
    # logger.info(f"Reading trained model from file {src_model_abs_file_path}")
    # model = joblib.load(src_model_abs_file_path)  # TBD: file not found, file corrupted

    # Create model by the specified name (TBD: discuss)
    if src_model_name == "NaiveModel":
        model = NaiveModel(lag=1)
    elif src_model_name == "LinearPerSegmentModel":
        model = LinearPerSegmentModel()
    elif src_model_name == "CatBoostPerSegmentModel":
        model = CatBoostPerSegmentModel(iterations=100, random_state=42)
    else:
        raise NotImplementedError(f"The model {src_model_name} is not yet supported.")

    # Read the data
    src_data_abs_file_path = os.path.abspath(src_data_file_path)
    logger.info(f"Reading data from file {src_data_abs_file_path}")
    # TBD: handle if file not found
    df_src = pd.read_csv(src_data_abs_file_path, index_col=column_for_timestamp, parse_dates=[column_for_timestamp])
    logger.info(f".. loaded data shape: {df_src.shape}")

    # Resample the data to fill missing candles, and forward-fill the gaps (including nans if any)
    df_src = df_src.resample(rule=src_data_timeframe).ffill()
    # Replace remaining nans to previous good values (rarely occurred)
    df_src = df_src.ffill()

    # Prepare columns "timestamp", "segment", "target" that are required by ETNA
    df_src["timestamp"] = df_src.index      # For now - just create copy of index. TBD: try to rename the index
    df_src["segment"] = "dummy_segment"     # Segments are required by ETNA
    df_src["target"] = df_src[column_for_target]    # TBD: check if "target" exists.

    # TBD:
    df_src = df_src[["timestamp", "segment", "target"]]

    # TBD: optimize memory (do not copy the columns)
    # Convert pandas dataframe to ETNA Dataset format.
    df_ts_format = TSDataset.to_dataset(df_src)
    tsd_dataset = TSDataset(df_ts_format, freq=src_data_timeframe)

    # A list of transforms
    transforms = [
        # This ffill transformer gives an error like "NaNs in y_true" -> replaced with manual resample.
        # TimeSeriesImputerTransform(in_column="target", strategy=ImputerMode.forward_fill)
        LogTransform(in_column="target"),
        LagTransform(in_column="target", lags=[1, 2, 3, 4, 5])
    ]

    # Do forecast (use "backtest" method for now) TBD: try to use "predict", "forecast" methods of pipeline
    pipeline = Pipeline(model=model, transforms=transforms, horizon=forecast_horizon)
    metrics_df, forecast_df, fold_info_df = pipeline.backtest(
        ts=tsd_dataset,
        metrics=[MAE(), MSE(), SMAPE(), MAPE()],
        n_folds=backtest_n_folds, )

    # Prepare output dataframe (take the last column)
    out_df = pd.DataFrame(index=forecast_df.index, data=forecast_df.iloc[:, -1].rename("prediction"))

    # Write the forecast to output file with possible compression (according to file extension)
    out_predictions_ans_file_path = os.path.abspath(out_predictions_file_path)
    out_df.to_csv(out_predictions_ans_file_path, compression="infer")
    logger.info(f"Saved dataframe with forecast to file : {out_predictions_ans_file_path}")


if __name__ == "__main__":
    # Setup logging
    log_fmt = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    logging.basicConfig(level=logging.INFO, format=log_fmt)

    # Main function call
    launch_model_backtesting()
