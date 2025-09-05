from loguru import logger  # Ensure correct import
import pandas as pd
from app.indicators import Strategy
from app.risk_management import RiskManagementFutures
import ta

# Prepare Data

df_path_15m = 'futures-klines/BTCUSDT_15m_1-9-2025.csv'
df_path_1m = 'futures-klines/BTCUSDT_1m_1-9-2025.csv'
df_path_1h = 'futures-klines/BTCUSDT_1h_1-9-2025.csv'
df_path_4h = 'futures-klines/BTCUSDT_4h_1-9-2025.csv'


"""
data_1h = pd.read_csv(df_path_1h)
data_15m = pd.read_csv(df_path_15m)
data_4h = pd.read_csv(df_path_4h)
df_1m = pd.read_csv(df_path_1m)
data_30m = pd.read_csv(df_path_30m)
data_strategy = Strategy(data_15m=data_15m, data_1h=data_1h, data_4h=data_4h)
data = data_strategy.generate_signals()
data_buys = data[data["Signal"] == 1]
data_sells = data[data["Signal"] == -1]
data_buys.to_csv("strategy_buy.csv", index=False)
data_sells.to_csv("strategy_sell.csv", index=False)
"""


def wrangle_signals(file_path, output_path):
    # Load CSV
    df = pd.read_csv(file_path, parse_dates=["timestamp"])
    
    if df.empty:
        print(f"{file_path} is empty.")
        return pd.DataFrame()
    
    # Extract date (ignore time)
    df["date"] = df["timestamp"].dt.date
    
    # Keep only the first signal of each day
    df_first = df.groupby("date").first().reset_index(drop=True)
    
    # Save back to CSV
    df_first.to_csv(output_path, index=False)
    
    print(f"Saved wrangled signals to {output_path}")
    return df_first


"""# Wrangle buys and sells
buys = wrangle_signals("strategy_buy.csv", "strategy_buy_one_per_day.csv")
sells = wrangle_signals("strategy_sell.csv", "strategy_sell_one_per_day.csv")
"""


# this function fetches the most recent data from a CSV file based on a target timestamp
def fetch_recent_data_from_csv(
    csv_path,
    target_timestamp,
    n_points=40,
    augmentation_next=0
):  
    """
    Fetches n_points rows before or at the target_timestamp, and if augmentation_next > 0,
    adds that many rows strictly after the target_timestamp.
    """
    try:
        df = pd.read_csv(csv_path)
    except pd.errors.EmptyDataError:
        logger.error(f"CSV file '{csv_path}' is empty or missing columns.")
        return pd.DataFrame()
    except FileNotFoundError:
        logger.error(f"CSV file '{csv_path}' not found.")
        return pd.DataFrame()
    if df.empty:
        logger.error(f"CSV file '{csv_path}' contains no data.")
        return pd.DataFrame()
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values('timestamp').reset_index(drop=True)

    # Convert target timestamp
    target_dt = pd.to_datetime(target_timestamp)

    # Find the index of the first row with timestamp >= target_dt
    idx = df[df['timestamp'] >= target_dt].index
    if len(idx) == 0:
        # If target timestamp is after all data, just return last n_points
        df_before = df.tail(n_points)
        df_after = pd.DataFrame()
    else:
        idx = idx[0]
        # Get n_points rows before or at the target timestamp
        start_idx = max(0, idx - n_points)
        df_before = df.iloc[start_idx:idx]
        # Optionally include the row at target_dt if it matches exactly
        if df.iloc[idx]['timestamp'] == target_dt:
            df_before = pd.concat([df_before, df.iloc[[idx]]])
            idx += 1  # Move index forward for after-data

        # Get augmentation_next rows after the target timestamp
        df_after = df.iloc[idx:idx + augmentation_next]

    # Combine and return
    df_result = pd.concat([df_before, df_after]).reset_index(drop=True)
    return df_result

def backtest_futures_strategy_amir_(
    tp=0.5,
    sl=0.3,
    leverage=10,
    initial_margin=1000,
    output_csv="backtest_results.csv"
):
    signals = []
    time_considered = pd.to_datetime("2025-02-20 00:00:00")

    while True:
        logger.debug(f"Backtesting at 4h timestamp: {time_considered}")
        if time_considered > pd.to_datetime("2025-09-01 00:00:00"):
            logger.info("Reached end of backtesting period")
            break

        df_1h = fetch_recent_data_from_csv(
            csv_path=df_path_1h,
            target_timestamp=time_considered,
            n_points=1000,
            augmentation_next=0
        )
        df_15m = fetch_recent_data_from_csv(
            csv_path=df_path_15m,
            target_timestamp=time_considered,
            n_points=1000,
            augmentation_next=0
        )
        df_4h = fetch_recent_data_from_csv(
            csv_path=df_path_4h,
            target_timestamp=time_considered,
            n_points=1000,
            augmentation_next=0
        )

        if df_15m.empty:
            logger.warning(f"No 15m data fetched for timestamp {time_considered}. Skipping...")
            break
        if df_1h.empty:
            logger.warning(f"No 1h data fetched for timestamp {time_considered}. Skipping...")
            break
        if df_4h.empty:
            logger.warning(f"No 4h data fetched for timestamp {time_considered}. Skipping...")
            break

        strategy = Strategy(data_15m=df_15m, data_1h=df_1h, data_4h=df_4h)
        strategy_data = strategy.generate_signals()
        last_signal = strategy_data["Signal"].iloc[-1]

        if last_signal != 0:
            logger.info(f"{'buy' if last_signal == 1 else 'sell'} Signal detected at {time_considered} with price {strategy_data['close'].iloc[-1]}") 
            last_timestamp = strategy_data["timestamp"].iloc[-1]
            last_price = strategy_data["close"].iloc[-1]
            signals.append({
                "entry_time": last_timestamp,
                "signal": 1 if last_signal == 1 else -1,
                "entry_price": last_price,
                "exit_price": None,
                "exit_time": None,
                "exit_status": None,
                "profit_or_loss": None
            })
            # Filter strictly after the signal timestamp
            i = 1
            while True:
                df_1min = fetch_recent_data_from_csv(
                    csv_path=df_path_1m,
                    target_timestamp=last_timestamp,
                    n_points=50,
                    augmentation_next=i
                )
                if df_1min.empty or len(df_1min) <= 50:
                    logger.warning("No more data to check for exit.")
                    break


                # Calculate ATR using ta library (last 14 periods)
                atr = ta.volatility.AverageTrueRange(
                    high=df_1min['high'],
                    low=df_1min['low'],
                    close=df_1min['close'],
                    window=14
                ).average_true_range().iloc[-1]
                currentprice = df_1min['close'].iloc[-1]
                exit_timestamp = pd.Timestamp(df_1min['timestamp'].iloc[-1])
                risk_management = RiskManagementFutures(
                    last_price, currentprice, sl, tp, atr, last_signal,
                    leverage=leverage, initial_margin=initial_margin, fees=0.0002
                )
                exit_status = risk_management.should_exit()
                if exit_status:
                        pnl = risk_management.calculate_pnl(risk_management.current_price)
                        logger.info(f"Exit condition met at {exit_timestamp}")
                        if exit_status == "LOSS":
                            print(f"🔴 STOP LOSS EXIT | Loss: ${abs(pnl):.2f}")
                        elif exit_status == "PROFIT":
                            print(f"🟢 TAKE PROFIT EXIT | Profit: ${pnl:.2f}")
                        else:
                            print(f"💥 LIQUIDATION | Loss: ${abs(pnl):.2f}")
                        signals[-1].update({
                            'exit_time': exit_timestamp,
                            'exit_price': currentprice,
                            'exit_status': exit_status,
                            'profit_or_loss': pnl
                        })
                        time_considered = exit_timestamp + pd.Timedelta(hours=12)
                        break
                i += 1

        else:
            logger.debug(f"No signal at {time_considered}")
            time_considered += pd.Timedelta(hours=4)


    return signals

signals = backtest_futures_strategy_amir_(
    tp=0.03,
    sl=2,
    leverage=1,
    initial_margin=100000,
    output_csv="backtest_results.csv"
)
print(signals)
