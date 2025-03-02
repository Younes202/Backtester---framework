
from ta.trend import EMAIndicator, MACD
from ta.momentum import RSIIndicator
from ta.volume import VolumeWeightedAveragePrice
class Strategy:
    def __init__(self, data, timeframe_type):
        self.data = data
        self.timeframe_type = timeframe_type

    def calculate_indicators(self):
        """
        Calculate indicators based on the timeframe.
        """
        # Common indicators for all timeframes
        self.data['EMA50'] = EMAIndicator(close=self.data['close'], window=50).ema_indicator()
        self.data['RSI'] = RSIIndicator(close=self.data['close'], window=14).rsi()
        macd = MACD(close=self.data['close'], window_slow=12, window_fast=6, window_sign=5)
        self.data['MACD'] = macd.macd()
        self.data['MACD_Signal'] = macd.macd_signal()

        # HTF-specific indicators (1-hour)
        if self.timeframe_type == '1h':
            self.data['EMA200'] = EMAIndicator(close=self.data['close'], window=200).ema_indicator()
            self.data['VWAP'] = VolumeWeightedAveragePrice(
                high=self.data['high'],
                low=self.data['low'],
                close=self.data['close'],
                volume=self.data['volume'],
                window=20
            ).volume_weighted_average_price()

        return self.data

    def generate_signals(self):
        """
        Generate buy signals based on the HTF and LTF conditions.
        """
        self.calculate_indicators()
        self.data['Signal'] = 0  # Default signal value

        # HTF (1-hour timeframe)
        if self.timeframe_type == '1h':
            # Bullish trend: EMA50 > EMA200, RSI > 50, and price above VWAP
            self.data.loc[
                (self.data['EMA50'] > self.data['EMA200']) &  # EMA50 > EMA200 (Bullish Trend)
                (self.data['RSI'] > 50) &  # RSI > 50 (Bullish Momentum)
                (self.data['close'] > self.data['VWAP']),  # Price above VWAP (Strong Buying Pressure)
                'Signal'
            ] = 1  # Bullish trend signal

        # LTF (15-minute timeframe)
        elif self.timeframe_type == '15m':
            # Buy signal: Pullback to EMA50, RSI > 50, and MACD bullish crossover
            self.data.loc[
                (self.data['close'] > self.data['EMA50']) &  # Price above EMA50 (Pullback)
                (self.data['RSI'] > 50) &  # RSI > 50 (Bullish Momentum)
                (self.data['MACD'] > self.data['MACD_Signal']),  # MACD bullish crossover
                'Signal'
            ] = 1  # Buy signal

        return self.data