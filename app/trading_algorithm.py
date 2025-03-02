import pandas as pd
from loguru import logger
from indicators import  Strategy




def fetch_and_process_data(data, close_time, augmentation=0):
    if isinstance(data, str):
        df = pd.read_csv(data)
    elif isinstance(data, pd.DataFrame):
        df = data.copy()
    else:
        raise ValueError("`data` must be a file path (str) or a pandas DataFrame.")

    if 'close_time' not in df.columns:
        raise KeyError("Missing 'close_time' column in the dataset.")

    df['close_time'] = pd.to_datetime(df['close_time'])
    close_time = pd.to_datetime(close_time)

    df_past = df[df['close_time'] <= close_time].sort_values(by='close_time', ascending=False).head(200)
    df_future = df[df['close_time'] > close_time].sort_values(by='close_time', ascending=True).head(augmentation)

    df_final = pd.concat([df_past, df_future]).sort_values(by='close_time', ascending=True).reset_index(drop=True)

    # Ensure the DataFrame is not empty
    if df_final.empty:
        logger.warning(f"No data found for close_time: {close_time}")
        return pd.DataFrame()  # Return an empty DataFrame

    return df_final

def backtest_multi_timeframe(df_1h, df_15m, augmentation_15m=40):
    """
    Backtest using multi-timeframe: 1-hour (HTF) and 15-minute (LTF).
    """
    # Initialize 1H Strategy and generate signals
    strategy_1h = Strategy(df_1h, '1h')
    df_1h = strategy_1h.generate_signals()
    trades = []

    # Iterate over 1H signals
    for index, row in df_1h.iterrows():
        if row['Signal'] == 1:  # Bullish trend identified on 1H
            logger.info(f"Bullish trend identified on 1H at {row['close_time']}")
            close_time = row['close_time']

            # Process 15M Timeframe (LTF)
            for aug_15m in range(augmentation_15m):
                df_15m_filtered = fetch_and_process_data(df_15m, close_time, aug_15m)
                if df_15m_filtered.empty:
                    logger.warning(f"No data in df_15m_filtered for augmentation {aug_15m}")
                    continue  # Skip this iteration

                strategy_15m = Strategy(df_15m_filtered, '15m')
                df_15m_filtered = strategy_15m.generate_signals()

                if not df_15m_filtered.empty and df_15m_filtered['Signal'].iloc[-1] == 1:  # Buy signal confirmed on 15M
                    close_time_15m = df_15m_filtered['close_time'].iloc[-1]
                    close_price_15m = df_15m_filtered['close'].iloc[-1]
                    logger.success(f"Buy signal confirmed on 15M at {close_time_15m}, Price: {close_price_15m}")
                    
                    trades.append({'time': close_time_15m, "price": close_price_15m})
                    break  # Stop at the first confirmed trade on 15M

    return trades


# Example usage
df_1h = pd.read_csv('spot_month_klines_data/BTCUSDT_1h_3-3-2024.csv')
df_15m = pd.read_csv('spot_month_klines_data/BTCUSDT_15m_3-3-2024.csv')

results = backtest_multi_timeframe(df_1h, df_15m)
logger.info(f"Total Buy Opportunities: {len(results)}")
logger.info(results)