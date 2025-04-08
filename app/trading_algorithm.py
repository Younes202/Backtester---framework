import pandas as pd
from loguru import logger
from indicators import  Strategy
from risk_management import RiskManagement



    
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


def backtest_multi_timeframe(df_1d, df_1h, df_15m, augmentation_1h=24, augmentation_15m=4):
    """
    Multi-timeframe backtest using Daily (D1) for bias, 1-Hour (H1) for confirmation,
    and 15-Minute (M15) for precise entry.
    """
    # Initialize and generate signals for Daily Bias (D1)
    strategy_1d = Strategy(df_1d, '1d')
    df_1d = strategy_1d.generate_signals()
    logger.debug(f" dataFrame of day is like that : {df_1d["Signal"]}")
    trades = []
    
    # Loop over daily signals first
    for index_d, row_d in df_1d.iterrows():
        if row_d['Signal'] == 1:  # Bullish bias on daily timeframe
            logger.info(f"Bullish trend confirmed on D1 at {row_d['close_time']}")
            close_time_d1 = row_d['close_time']
            
            # Process 1H Timeframe Confirmation
            for aug_1h in range(augmentation_1h):
                df_1h_filtered = fetch_and_process_data(df_1h, close_time_d1, aug_1h)
                if df_1h_filtered.empty:
                    continue
                
                strategy_1h = Strategy(df_1h_filtered, '1h')
                df_1h_filtered = strategy_1h.generate_signals()
                logger.debug(f" dataFrame of day is like that : {df_1h_filtered}")

                for index_h, row_h in df_1h_filtered.iterrows():
                    if row_h['Signal'] == 1:  # Bullish confirmation on 1H
                        logger.info(f"Bullish trend confirmed on H1 at {row_h['close_time']}")
                        close_time_h1 = row_h['close_time']
                        
                        # Process 15M Timeframe Entry
                        for aug_15m in range(augmentation_15m):
                            df_15m_filtered = fetch_and_process_data(df_15m, close_time_h1, aug_15m)
                            if df_15m_filtered.empty:
                                continue
                            
                            strategy_15m = Strategy(df_15m_filtered, '15m')
                            df_15m_filtered = strategy_15m.generate_signals()
                            logger.debug(f" dataFrame of day is like that : {df_15m_filtered}")

                            if df_15m_filtered['Signal'].iloc[-1] == 1:  # Buy confirmed on 15M
                                close_time_15m = df_15m_filtered['close_time'].iloc[-1]
                                close_price_15m = df_15m_filtered['close'].iloc[-1]
                                logger.debug(f" dataFrame of day is like that : {df_15m_filtered.shape}")
                                logger.success(f"Buy signal confirmed on 15M at {close_time_15m}, Price: {close_price_15m}")
                                trades.append({'time': close_time_15m, "price": close_price_15m})

                                break  # Stop at the first valid trade entry
    return trades
 

# Example usage
df_1d = pd.read_csv('spot_klines_data/BTCUSDT_1d_2024-2025.csv')
df_1h = pd.read_csv('spot_klines_data/BTCUSDT_1h_2024-2025.csv')
df_15m = pd.read_csv('spot_klines_data/BTCUSDT_15m_2024-2025.csv')
df_1mm = pd.read_csv('spot_klines_data/BTCUSDT_1m_2024-2025.csv')
print(df_1d.head())
print(df_1h.head())
print(df_15m.head())

results = backtest_multi_timeframe(df_1d, df_1h, df_15m)
logger.info(f"Total Buy Opportunities: {len(results)}")
logger.info(results)

# after buy detected start searching buys and start searching a sell via risk managmnet i build before after get the righ data point to exit start from it search for buy and continue like that .

