
import pandas_ta as ta

class Strategy:
    def __init__(self, data, rsi_length=14, sma_short_length=50, sma_long_length=200, atr_length=14, support_resistance_window=10):
        self.data = data  # DataFrame containing historical price data
        self.rsi_length = rsi_length  # RSI period
        self.sma_short_length = sma_short_length  # Short-term SMA
        self.sma_long_length = sma_long_length  # Long-term SMA
        self.atr_length = atr_length  # ATR period
        self.window = support_resistance_window  # Support/Resistance window

    def calculate_indicators(self):


        self.data['RSI'] = ta.rsi(self.data['close_price'], length=self.rsi_length)
        self.data['ATR'] = ta.atr(self.data['high_price'], self.data['low_price'], self.data['close_price'], length=self.atr_length)
        self.data['SMA_Short'] = ta.sma(self.data['close_price'], length=self.sma_short_length)
        self.data['SMA_Long'] = ta.sma(self.data['close_price'], length=self.sma_long_length)
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
        # # 30 %
        self.data.loc[
            (self.data['RSI'].between(40, 45)) & 
            (self.data['close_price'] > self.data['Support']) & 
            (self.data['SMA_Short'] > self.data['SMA_Long']),
            ['Signal', 'type']
        ] = [1, 'SIGNAL_0_4']  # Assign Buy signal and type


        self.data.loc[
            (self.data['RSI'].between(35, 39)) & 
            (self.data['close_price'] > self.data['Support']) & 
            (self.data['SMA_Short'] > self.data['SMA_Long']),
            ['Signal', 'type']
        ] = [1, 'SIGNAL_0_5']  # Assign Buy signal and type

        # 40 %
        self.data.loc[
            (self.data['RSI'].between(30, 34)) & 
            (self.data['close_price'] > self.data['Support']) & 
            (self.data['SMA_Short'] > self.data['SMA_Long']),
            ['Signal', 'type']
        ] = [1, 'SIGNAL_1']  # Assign Buy signal and type


        self.data.loc[
            (self.data['RSI'].between(25, 29)) & 
            (self.data['close_price'] > self.data['Support']) & 
            (self.data['SMA_Short'] > self.data['SMA_Long']),
            ['Signal', 'type']
        ] = [1, 'SIGNAL_1_5']  # Assign Buy signal and type

        # 50 %
        self.data.loc[      
            (self.data['RSI'].between(20, 24)) & 
            (self.data['close_price'] > self.data['Support']) & 
            (self.data['SMA_Short'] > self.data['SMA_Long']),
            ['Signal', 'type']
        ] = [1, 'SIGNAL_2']  # Assign Buy signal and type

        self.data.loc[
            (self.data['RSI'].between(15, 19)) & 
            (self.data['close_price'] > self.data['Support']) & 
            (self.data['SMA_Short'] > self.data['SMA_Long']),
            ['Signal', 'type']
        ] = [1, 'SIGNAL_2_5']  # Assign Buy signal and type


        self.data.loc[
            (self.data['RSI'].between(10, 14)) & 
            (self.data['close_price'] > self.data['Support']) & 
            (self.data['SMA_Short'] > self.data['SMA_Long']),
            ['Signal', 'type']
        ] = [1, 'SIGNAL_3']  # Assign Buy signal and type


        return self.data
