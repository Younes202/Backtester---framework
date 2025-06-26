from indicators import FuturesStrategyScalping
from risk_management import RiskManagement


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
    # Load and prepare
    df = pd.read_csv(csv_path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values('timestamp').reset_index(drop=True)

    # Convert target timestamp
    target_dt = pd.to_datetime(target_timestamp)

    # Fetch rows before or at the target
    df_before = df[df['timestamp'] <= target_dt].tail(n_points)

    # Fetch next rows strictly after the target
    df_after = df[df['timestamp'] > target_dt].head(augmentation_next)

    # Combine and return
    df_result = pd.concat([df_before, df_after]).reset_index(drop=True)
    return df_result


def backtest_futures_strategy_scalping(df, tp=0.5, sl=0.3):
    """
    Backtest the FuturesStrategyScalping strategy on the provided DataFrame.

    Args:
        df (pd.DataFrame): DataFrame containing historical data with a 'timestamp' column.
        tp (float): Take profit value (not used in this function, placeholder for future use).
        sl (float): Stop loss value (not used in this function, placeholder for future use).
    Returns:
        List[dict]: List of signal dictionaries with timestamp, signal, and close price.
    """
    signals = []
    for i in range(20, len(df)):
        # Fetch the most recent data from the CSV file
        df_recent = fetch_recent_data_from_csv(
            csv_path='futures-klines/btcusdt_3m_2024-06-22_2025-06-22.csv',
            target_timestamp=df['timestamp'].iloc[i],
            n_points=40,
            augmentation_next=0
        )
        logger.info(f"Fetched {len(df_recent)} rows for backtesting at timestamp {df['timestamp'].iloc[i]}")

        # Apply the FuturesStrategyScalping strategy
        strategy = FuturesStrategyScalping(df_recent)
        df_signals = strategy.generate_signals()

        # Use the last signal from the generated signals
        last_signal = df_signals['Signal'].iloc[-1] if not df_signals.empty else 0

        if last_signal != 0:
            logger.info(f"Signal generated at {df['timestamp'].iloc[i]}: {last_signal}")
            signals.append({
                'timestamp': df['timestamp'].iloc[i],
                'signal': last_signal,
                'close': df['close'].iloc[i]
            })
            priceorder = df['close'].iloc[i]
            currentprice = df['close'].iloc[i]
            atr = df['atr'].iloc[i] if 'atr' in df.columns else 0.0  # Ensure ATR is available
            target_profit = tp
            stoploss = sl
            dollar_investment = 1000  # Example investment amount
            while True:
                # Risk management logic can be added here
                risk_management = RiskManagement(priceorder, currentprice, target_profit, stoploss, dollar_investment, atr, fees=0.1)
                risk_management.set_stop_loss(sl)
                risk_management.set_take_profit(tp)
                # For now, we just log the stop loss and take profit values
                logger.info(f"Stop Loss set to {sl}, Take Profit set to {tp}")
                break


        else:
            logger.info(f"No signal generated at {df['timestamp'].iloc[i]}")

    return signals


signals = backtest_futures_strategy_scalping(df_3min)
print(signals)
