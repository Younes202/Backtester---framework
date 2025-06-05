import pandas as pd
from loguru import logger
from indicators import  Strategy
from risk_management import RiskManagement
import talib

    
def fetch_and_process_data(data, close_time, timeframe=None, augmentation=0):
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

    return data


### ----------------------- 2. LOAD FILES & APPLY STRATEGY -----------------------------

# Load CSVs
df_1d = pd.read_csv("spot_klines_data/BTCUSDT_1d_2024-2025.csv")
df_1h = pd.read_csv("spot_klines_data/BTCUSDT_1h_2024-2025.csv")
df_15m = pd.read_csv("spot_klines_data/BTCUSDT_15m_2024-2025.csv")

print("1D Spot Close time  ")
print(df_1d["close_time"].head(1))
print(df_1d["close_time"].iloc[-1])

print("1H Spot Close time  ")
print(df_1h["close_time"].head(1))
print(df_1h["close_time"].iloc[-1])

print("Spot Close time  ")
print(df_15m["close_time"].head(1))
print(df_15m["close_time"].iloc[-1])


"""# Generate daily signals (D1)
strategy_1d = Strategy(df_1d, '1d')
df_1d = strategy_1d.generate_signals()
logger.debug(f"Daily DataFrame Signal column: {df_1d['Signal']}")"""

# Print the las1t signal


"""
print(df_1d.head())
print(df_1h.head())
print(df_15m.head())"""

"""results = backtest_multi_timeframe(df_1d, df_1h, df_15m, df_1mm)
logger.info(f"Total Buy Opportunities: {len(results)}")
logger.info(results)"""
# after buy detected start searching buys and start searching a sell via risk managmnet i build before after get the righ data point to exit start from it search for buy and continue like that .
#

"""
                           i = 0
                            while True:
                                df_1m_filtered = fetch_and_process_data(df_1m, close_time, augmentation=i)
                                current_price = df_1m_filtered['close']
                                latest_atr = df_1m_filtered['atr']
                                close_time_1m = df_1m_filtered['close_time']
                                i = i + 1
                                risk_manager = RiskManagement(priceorder=close_price, currentprice=current_price, target_profit=1, stoploss=0.5, dollar_investment=600, atr=latest_atr, fees=0.1)

                                if risk_manager.should_exit():
                                    print("✅ Exit condition met on 1m data.")
                                    if risk_manager.profit_or_loss is not None:
                                        if risk_manager.profit_or_loss > 0:
                                            print("📈 Gain Confirmed.")
                                            trades.append({"buy price": close_price, "sell price": current_price, "profit_or_loss": "profit"})

                                        else:
                                            print("📉 Loss Confirmed.")
                                            trades.append({"buy price": close_price, "sell price": current_price, "profit_or_loss": "loss"})

                                        logger.success(f"Sell signal confirmed at {close_time_1m}, Price: {current_price}")
                                        logger.info(f"Trade executed: Buy at {trades[-1]['buy price']}, Sell at {trades[-1]['sell price']}")
                                        logger.info(f"Trade details: {trades[-1]}")
                                        break  # Exit the risk management loop once an exit is found
                                else:
                                    print("⏳ Hold the position in 1m risk management.")
""" 