from ta.trend import EMAIndicator, MACD
from ta.momentum import RSIIndicator
from ta.volume import VolumeWeightedAveragePrice
import pandas as pd

class Strategy:
    def __init__(self, data, timeframe_type):
        self.data = data
        self.timeframe_type = timeframe_type

    def calculate_indicators(self):
        """
        Calculate indicators based on the timeframe.
        """
        self.data['EMA50'] = EMAIndicator(close=self.data['close'], window=50).ema_indicator()
        self.data['EMA200'] = EMAIndicator(close=self.data['close'], window=200).ema_indicator()
        self.data['RSI'] = RSIIndicator(close=self.data['close'], window=14).rsi()
        macd = MACD(close=self.data['close'], window_slow=12, window_fast=6, window_sign=5)
        self.data['MACD'] = macd.macd()
        self.data['MACD_Signal'] = macd.macd_signal()

        if self.timeframe_type in ['1h', '15m']:
            self.data['VWAP'] = VolumeWeightedAveragePrice(
                high=self.data['high'],
                low=self.data['low'],
                close=self.data['close'],
                volume=self.data['volume'],
                window=20
            ).volume_weighted_average_price()
        
        return self.data
    
    def detect_fvg(self):
        """
        Detect Fair Value Gaps (FVG)
        """
        self.data['FVG'] = ((self.data['low'].shift(1) > self.data['high'].shift(-1)) |
                             (self.data['high'].shift(1) < self.data['low'].shift(-1)))
        return self.data

    def detect_cisd(self):
        """
        Detect Change in Structure (CISD)
        """
        self.data['Higher_High'] = self.data['high'] > self.data['high'].shift(1)
        self.data['Higher_Low'] = self.data['low'] > self.data['low'].shift(1)
        self.data['Bullish_Structure'] = self.data['Higher_High'] & self.data['Higher_Low']
        
        self.data['Lower_High'] = self.data['high'] < self.data['high'].shift(1)
        self.data['Lower_Low'] = self.data['low'] < self.data['low'].shift(1)
        self.data['Bearish_Structure'] = self.data['Lower_High'] & self.data['Lower_Low']
        
        return self.data
    
    def generate_signals(self):
        """
        Generate buy signals based on the multi-timeframe analysis.
        """
        self.calculate_indicators()
        self.detect_fvg()
        self.detect_cisd()
        self.data['Signal'] = 0  # Default to no signal

        # Daily (1D) Trend Bias - Defines Market Direction
        if self.timeframe_type == '1d':
            self.data['Signal'] = ((self.data['EMA50'] > self.data['EMA200']) & (self.data['RSI'] > 50)).astype(int)

        # 1-Hour Confirmation (H1) - Ensures D1 Trend is Valid & Checks for Inefficiencies
        elif self.timeframe_type == '1h':
            self.data.loc[
                (self.data['EMA50'] > self.data['EMA200']) &  # Trend confirmation
                (self.data['RSI'] > 50) &
                (self.data['close'] > self.data['VWAP']) &
                (~self.data['FVG']),  # No Fair Value Gap, confirming efficiency
                'Signal'
            ] = 1  # Bullish Confirmation

        # 15-Minute Entry (M30/M15) - Final Entry Trigger
        elif self.timeframe_type == '15m':
            self.data.loc[
                (self.data['close'] > self.data['EMA50']) &  # Price above EMA50 (Pullback Entry)
                (self.data['RSI'] > 50) &  # RSI confirming momentum
                (self.data['MACD'] > self.data['MACD_Signal']) &  # MACD Bullish Crossover
                (self.data['Bullish_Structure']),  # Structure Aligning with Uptrend
                'Signal'
            ] = 1  # Buy signal

        return self.data
