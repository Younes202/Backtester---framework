


# Example parameters for TradingSystem
"""trading_params = {
"month":"2024-01",
"rsi_length": 8,                # Faster RSI for quick momentum detection
"bollinger_length": 10,         # Shorter Bollinger Bands length to capture faster market movements
"bollinger_std_dev": 1.5,       # Tighter Bollinger Bands (standard deviation) for quicker breakouts
"atr_length": 7,                # Shorter ATR length to measure short-term volatility
'volume_length': 10,             # Shorter volume length to track immediate changes in trading activity
"target_profit": 0.4,
"stoploss": 30,
"fees": 0.1,
"initial_investment": 125
}

# Create a TradingSystem instance for the current month
trading_system = TradingSystem(**trading_params)

# Fetch data and run the trading cycle
trading_system.fetch_data_from_db()  # Ensure data is fetched
trading_system.run_trading_cycle()
# Get metrics for the current month
dm = trading_system.calculate_metrics()
trading_system.print_metrics()
"""