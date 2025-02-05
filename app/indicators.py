import talib
import pandas as pd
from loguru import logger

class Strategy:
    def __init__(self, data, rsi_length=14, sma_short=50, sma_long=200, atr_length=14, support_resistance_window=10):
        self.data = data  # DataFrame containing historical price data
        self.rsi_length = rsi_length  # RSI period
        self.sma_short = sma_short  # Short-term SMA
        self.sma_long = sma_long  # Long-term SMA
        self.atr_length = atr_length  # ATR period
        self.window = support_resistance_window  # Support/Resistance window

    def calculate_indicators(self):
        # RSI Calculation
        self.data['RSI'] = talib.RSI(self.data['close_price'], timeperiod=self.rsi_length)
        
        # SMA Calculation
        self.data['SMA_Short'] = talib.SMA(self.data['close_price'], timeperiod=self.sma_short)
        self.data['SMA_Long'] = talib.SMA(self.data['close_price'], timeperiod=self.sma_long)
        
        # ATR Calculation for volatility-based stop loss/take profit
        self.data['ATR'] = talib.ATR(self.data['high_price'], self.data['low_price'], self.data['close_price'], timeperiod=self.atr_length)
        
        # Support/Resistance Calculation using rolling min/max
        self.data['Support'] = self.data['low_price'].rolling(window=self.window).min()
        self.data['Resistance'] = self.data['high_price'].rolling(window=self.window).max()
        
        return self.data

    def preprocess_data(self):
        # Drop NaN values after adding indicators
        self.data.dropna(inplace=True)
        return self.data

    def get_decision(self):
        self.calculate_indicators()
        self.preprocess_data()
        
        # Buy signal: RSI < 40, price above support, and short SMA above long SMA (uptrend confirmation)
        self.data.loc[
            (self.data['RSI'] <= 40) & 
            (self.data['close_price'] > self.data['Support']) & 
            (self.data['SMA_Short'] > self.data['SMA_Long']),
            'Signal'
        ] = 1  # Buy


        return self.data
