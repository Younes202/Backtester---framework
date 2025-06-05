from ta.trend import EMAIndicator, MACD
from ta.momentum import RSIIndicator
from ta.volume import VolumeWeightedAveragePrice
import pandas as pd
import talib
from ta.trend import EMAIndicator, MACD
from ta.momentum import RSIIndicator
from ta.volume import VolumeWeightedAveragePrice
import talib

### ----------------------- 1. STRATEGY CLASS -----------------------------

class Strategy:
    def __init__(self, data, timeframe_type):
        self.data = data.copy()
        self.timeframe_type = timeframe_type
        self.data['timestamp'] = pd.to_datetime(self.data['open_time'])

    def calculate_indicators(self):
        self.data['EMA50'] = EMAIndicator(close=self.data['close'], window=50).ema_indicator()
        self.data['EMA200'] = EMAIndicator(close=self.data['close'], window=200).ema_indicator()
        self.data['RSI'] = RSIIndicator(close=self.data['close'], window=14).rsi()
        macd = MACD(close=self.data['close'], window_slow=12, window_fast=6, window_sign=5)
        self.data['MACD'] = macd.macd()
        self.data['MACD_Signal'] = macd.macd_signal()

        if all(col in self.data.columns for col in ['high', 'low', 'close', 'volume']):
            self.data['VWAP'] = VolumeWeightedAveragePrice(
                high=self.data['high'], low=self.data['low'],
                close=self.data['close'], volume=self.data['volume'], window=20
            ).volume_weighted_average_price()
        return self.data

    def detect_fvg(self):
        self.data['FVG'] = (
            (self.data['low'].shift(1) > self.data['high'].shift(-1)) |
            (self.data['high'].shift(1) < self.data['low'].shift(-1))
        )
        return self.data

    def detect_cisd(self):
        self.data['Higher_High'] = self.data['high'] > self.data['high'].shift(1)
        self.data['Higher_Low'] = self.data['low'] > self.data['low'].shift(1)
        self.data['Bullish_Structure'] = self.data['Higher_High'] & self.data['Higher_Low']
        self.data['Lower_High'] = self.data['high'] < self.data['high'].shift(1)
        self.data['Lower_Low'] = self.data['low'] < self.data['low'].shift(1)
        self.data['Bearish_Structure'] = self.data['Lower_High'] & self.data['Lower_Low']
        self.data['atr'] = talib.ATR(self.data['high'], self.data['low'], self.data['close'], timeperiod=14)
        return self.data

    def generate_signals(self):
        self.calculate_indicators()
        self.detect_fvg()
        self.detect_cisd()
        self.data['Signal'] = 0

        if self.timeframe_type == '1d':
            self.data['Bias'] = (
                (self.data['EMA50'] > self.data['EMA200']) &
                (self.data['RSI'] > 50) &
                (self.data['close'] > self.data['VWAP'])
            ).astype(int)

        elif self.timeframe_type == '1h':
            self.data['Confirm'] = (
                (~self.data['FVG']) & self.data['Bullish_Structure']
            ).astype(int)

        elif self.timeframe_type == '15m':
            self.data['Entry'] = (
                (self.data['close'] > self.data['EMA50']) &
                (self.data['RSI'] > 50) &
                (self.data['MACD'] > self.data['MACD_Signal']) &
                (self.data['Bullish_Structure'])
            ).astype(int)

        self.data.dropna(inplace=True)
        return self.data


