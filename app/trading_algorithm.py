from indicators import Strategy
from risk_management import RiskManagementFutures


from loguru import logger
import pandas as pd


# Load file 3m timframe for btc/usdt contract  



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

def backtest_futures_strategy(tp=0.5, sl=0.3, leverage=0, intial_margin=1000):
    """
    Backtest the Strategy strategy on the provided DataFrame.

    Args:
        tp (float): Take profit value (not used in this function, placeholder for future use).
        sl (float): Stop loss value (not used in this function, placeholder for future use).
    Returns:
        List[dict]: List of signal dictionaries with timestamp, signal, and close price.
    """
    signals = []
    seen_entries = set()  # To track unique entry timestamps
    seen_exits = set()    # To track unique exit timestamps

    time_considered_15 = '2024-07-03 03:15:00'
    time_considered_1h = None 
    df_path_1m = 'futures-klines/btcusdt_1_2024-06-22_2025-06-22.csv'
    df_path_1h = 'futures-klines/btcusdt_60_2024-06-22_2025-06-22.csv'
    df_path_15m = 'futures-klines/btcusdt_15_2024-06-22_2025-06-22.csv'

    while True:
        # Fetch the most recent data from the CSV file for 15min  
        df_recent = fetch_recent_data_from_csv(
            csv_path=df_path_15m,
            target_timestamp=time_considered_15,
            n_points=100,  # Increased to ensure enough data for indicators like ADX
            augmentation_next=0
        )

        if df_recent.empty:
            logger.warning("No data 15min fetched for the given timestamp.")
            break
        logger.info(f"Fetched {len(df_recent)} rows for backtesting at timestamp {time_considered_15}")
        # Apply the Strategy strategy
        strategy = Strategy(df_recent, '15m')
        df_signals = strategy.generate_signals()

        # Use the last signal from the generated signals
        last_signal = df_signals['Signal'].iloc[-1] if not df_signals.empty else 0
        print("\n Last Signal is : ", last_signal)
        if last_signal != 0:
            entry_timestamp = pd.Timestamp(df_signals['timestamp'].iloc[-1])
            if entry_timestamp not in seen_entries:
                logger.info(f"15m Signal generated at {entry_timestamp}: {last_signal}")
                signals.append({
                    'timestamp entry': entry_timestamp,
                    'signal': last_signal,
                    'price entry': df_signals['close'].iloc[-1]
                })
                seen_entries.add(entry_timestamp)
            singal_type_15m = last_signal
            time_considered_1h = entry_timestamp.floor('h')

            # --- Only fetch and process 1h if 15m signal is nonzero ---
            df_recent_1h = fetch_recent_data_from_csv(
                csv_path=df_path_1h,
                target_timestamp=time_considered_1h,
                n_points=100,
                augmentation_next=0
            )
            if df_recent_1h.empty:
                logger.warning("No data 1h fetched for the given timestamp.")
                break   
            logger.info(f"Fetched {len(df_recent_1h)} rows for backtesting at timestamp {time_considered_1h}")
            strategy = Strategy(df_recent_1h, '1h')
            df_signals_1h = strategy.generate_signals()
            if df_signals_1h.empty:
                logger.warning("No signals generated for 1h timeframe.")
                break
            last_signal_1h = df_signals_1h['Signal'].iloc[-1] if not df_signals_1h.empty else 0

            # Only proceed if 1h signal matches 15m, otherwise skip to next 15m candle
            if singal_type_15m == last_signal_1h:
                confirmation_timestamp = pd.Timestamp(df_signals_1h['timestamp'].iloc[-1])
                # Only add confirmation if not already present
                if confirmation_timestamp not in seen_entries:
                    logger.info(f"1h Signal generated at {confirmation_timestamp}: {last_signal_1h}")
                    signals.append({
                        'timestamp confirmation': confirmation_timestamp,
                        'signal confirmation ': last_signal_1h,
                        'price confirmation': df_signals_1h['close'].iloc[-1]
                    })
                    seen_entries.add(confirmation_timestamp)
                priceorder = df_signals['close'].iloc[-1]
                target_profit = tp
                stoploss = sl
                position_type = last_signal
                entry_time = entry_timestamp
                i = 1
                while True:
                    df_1min = fetch_recent_data_from_csv(
                        csv_path=df_path_1m,
                        target_timestamp=entry_time,
                        n_points=50,
                        augmentation_next=i
                    )
                    if df_1min.empty or len(df_1min) <= 50:
                        logger.warning("No more data to check for exit.")
                        break

                    df_new = df_1min.iloc[-1:]
                    strategy = Strategy(df_1min, "1m")
                    df_signals = strategy.generate_signals()
                    atr = df_signals['atr'].iloc[-1]
                    currentprice = df_new['close'].iloc[-1]
                    exit_timestamp = pd.Timestamp(df_new['timestamp'].iloc[-1])

                    risk_management = RiskManagementFutures(
                        priceorder, currentprice, stoploss, target_profit, atr, position_type,
                        leverage=leverage, initial_margin=intial_margin, fees=0.0002
                    )
                    exit_status = risk_management.should_exit()
                    if exit_status:
                        if exit_timestamp not in seen_exits:
                            pnl = risk_management.calculate_pnl(risk_management.current_price)
                            logger.info(f"Exit condition met at {exit_timestamp}")
                            if exit_status == "LOSS":
                                print(f"🔴 STOP LOSS EXIT | Loss: ${abs(pnl):.2f}")
                            elif exit_status == "PROFIT":
                                print(f"🟢 TAKE PROFIT EXIT | Profit: ${pnl:.2f}")
                            else:
                                print(f"💥 LIQUIDATION | Loss: ${abs(pnl):.2f}")
                            signals.append({
                                'timestamp exit': exit_timestamp,
                                'exit price': currentprice,
                                'exit_status': exit_status,
                                'profit_or_loss': pnl
                            })
                            seen_exits.add(exit_timestamp)
                        break
                    else:
                        logger.debug(f"Exit condition doesn't meet at  [({priceorder},{currentprice}), {exit_timestamp}]")
                        i += 1
                        print("Available signals are : ", signals)

            # Move to the next 15m candle after processing, regardless of match/mismatch
            else:
                logger.info(f"Signal mismatch between 1h and 15m at {df_signals['timestamp'].iloc[-1]}")

            time_considered_15 = df_recent['timestamp'].iloc[-1] + pd.Timedelta(minutes=180)

        else:
            # Move to the next  candle
            time_considered_15 = df_recent['timestamp'].iloc[-1] + pd.Timedelta(minutes=15)
            logger.info(f"No 15m signal generated at {df_recent['timestamp'].iloc[-1]}")

    return signals  

signals = backtest_futures_strategy_scalping(tp=0.01, sl=2, leverage=1, intial_margin=100000)
print(signals)

