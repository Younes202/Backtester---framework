from indicators import FuturesStrategyScalping
from risk_management import RiskManagementFutures


from loguru import logger
import pandas as pd


# Load file 3m timframe for btc/usdt contract  
df_3min = pd.read_csv('futures-klines/btcusdt_3m_2024-06-22_2025-06-22.csv')
df_1min = pd.read_csv('futures-klines/btcusdt_1_2024-06-22_2025-06-22.csv')


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
    df = pd.read_csv(csv_path)
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


def backtest_futures_strategy_scalping(tp=0.5, sl=0.3):
    """
    Backtest the FuturesStrategyScalping strategy on the provided DataFrame.

    Args:
        tp (float): Take profit value (not used in this function, placeholder for future use).
        sl (float): Stop loss value (not used in this function, placeholder for future use).
    Returns:
        List[dict]: List of signal dictionaries with timestamp, signal, and close price.
    """
    signals = []
    time_considered = '2024-06-22 23:42:00'
    df_path = 'futures-klines/btcusdt_3m_2024-06-22_2025-06-22.csv'
    df_path_1m = 'futures-klines/btcusdt_1_2024-06-22_2025-06-22.csv'

    while True:
        # Fetch the most recent data from the CSV file
        df_recent = fetch_recent_data_from_csv(
            csv_path=df_path,
            target_timestamp=time_considered,
            n_points=40,
            augmentation_next=0
        )

        if df_recent.empty:
            logger.warning("No data fetched for the given timestamp.")
            break

        logger.info(f"Fetched {len(df_recent)} rows for backtesting at timestamp {time_considered}")

        # Apply the FuturesStrategyScalping strategy
        strategy = FuturesStrategyScalping(df_recent)
        df_signals = strategy.generate_signals()

        # Use the last signal from the generated signals
        last_signal = df_signals['Signal'].iloc[-1] if not df_signals.empty else 0
        print("Last Signal is : ", last_signal)
        if last_signal != 0:
            logger.info(f"Signal generated at {df_signals['timestamp'].iloc[-1]}: {last_signal}")
            signals.append({
                'timestamp entry': df_signals['timestamp'].iloc[-1],
                'signal': last_signal,
                'price entry': df_signals['close'].iloc[-1]
            })
            priceorder = df_signals['close'].iloc[-1]
            target_profit = tp
            stoploss = sl
            position_type = last_signal

            # Start from the next timestamp after entry
            entry_time = df_signals['timestamp'].iloc[-1]
            i = 1
            exit_found = False

            while not exit_found:
                # Fetch the next i-th row after entry_time
                df_1min = fetch_recent_data_from_csv(
                    csv_path=df_path_1m,
                    target_timestamp=entry_time,
                    n_points=30,
                    augmentation_next=i
                )
                if df_1min.empty or len(df_1min) <= 30:
                    logger.warning("No more data to check for exit.")
                    break

                # Only consider the new row for exit logic
                df_new = df_1min.iloc[-1:]
                strategy = FuturesStrategyScalping(df_1min)
                df_signals = strategy.generate_signals()
                atr = df_signals['ATR'].iloc[-1]
                currentprice = df_new['close'].iloc[-1]

                risk_management = RiskManagementFutures(
                    priceorder, currentprice, stoploss, target_profit, atr, position_type,
                    leverage=1, initial_margin=1000, fees=0.0002
                )
                exit_status = risk_management.should_exit()
                if exit_status:
                    pnl = risk_management.calculate_pnl(risk_management.current_price)

                    logger.info(f"Exit condition met at {df_new['timestamp'].iloc[-1]}")
                    if exit_status == "LOSS":
                        print(f"🔴 STOP LOSS EXIT | Loss: ${abs(pnl):.2f}")
                    elif exit_status == "PROFIT":
                        print(f"🟢 TAKE PROFIT EXIT | Profit: ${pnl:.2f}")
                    else:
                        print(f"💥 LIQUIDATION | Loss: ${abs(pnl):.2f}")

                    time_considered = df_new['timestamp'].iloc[-1] + pd.Timedelta(minutes=3)
                    signals.append({
                        'timestamp exit': df_new['timestamp'].iloc[-1],
                        'exit price': currentprice,
                        'exit_status': exit_status,
                        'profit_or_loss': risk_management.profit_or_loss
                    })
                    exit_found = True
                else:
                    logger.debug(f"Exit condition doesn't meet at [({priceorder},{currentprice}), {df_new['timestamp'].iloc[-1]}]")
                    i += 1

        else:
            # Move to the next 3m candle
            time_considered = df_recent['timestamp'].iloc[-1] + pd.Timedelta(minutes=3)
            logger.info(f"No signal generated at {df_recent['timestamp'].iloc[-1]}")

    return signals

signals = backtest_futures_strategy_scalping(tp=0.5, sl=0.3)
print(signals)