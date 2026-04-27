import logging
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

def calculate_bollinger_bands(df: pd.DataFrame, period: int = 20, std_dev: float = 2) -> pd.DataFrame:
    """计算布林线"""
    sma = df['close'].rolling(window=period).mean()
    std = df['close'].rolling(window=period).std()
    upper_band = sma + std_dev * std
    lower_band = sma - std_dev * std
    
    df['BB_Upper'] = upper_band
    df['BB_Middle'] = sma
    df['BB_Lower'] = lower_band
    return df

def calculate_volume_divergence(df: pd.DataFrame, lookback: int = 20) -> pd.DataFrame:
    """计算成交量背离"""
    max_price = df['close'].rolling(window=lookback).max()
    min_price = df['close'].rolling(window=lookback).min()
    max_volume = df['volume'].rolling(window=lookback).max()
    
    volume_divergence = pd.Series(0.0, index=df.index)
    for i in range(lookback, len(df)):
        if df['close'].iloc[i] == max_price.iloc[i] and df['volume'].iloc[i] < max_volume.iloc[i] * 0.5:
            volume_divergence.iloc[i] = -0.5
        elif df['close'].iloc[i] == min_price.iloc[i] and df['volume'].iloc[i] > max_volume.iloc[i] * 0.8:
            volume_divergence.iloc[i] = 0.5
    
    df['Volume_Divergence'] = volume_divergence
    return df

def calculate_chan_patterns(df: pd.DataFrame, lookback: int = 5) -> pd.DataFrame:
    """缠中说禅高低点识别"""
    high_points = pd.Series(False, index=df.index)
    low_points = pd.Series(False, index=df.index)
    
    for i in range(lookback, len(df) - lookback):
        if df['high'].iloc[i] == df['high'].iloc[i-lookback:i+lookback+1].max():
            high_points.iloc[i] = True
        if df['low'].iloc[i] == df['low'].iloc[i-lookback:i+lookback+1].min():
            low_points.iloc[i] = True
    
    df['Chan_High'] = high_points
    df['Chan_Low'] = low_points
    return df

def calculate_obv(df: pd.DataFrame) -> pd.DataFrame:
    """计算OBV (On-Balance Volume)"""
    obv = pd.Series(0.0, index=df.index)
    for i in range(1, len(df)):
        if df['close'].iloc[i] > df['close'].iloc[i-1]:
            obv.iloc[i] = obv.iloc[i-1] + df['volume'].iloc[i]
        elif df['close'].iloc[i] < df['close'].iloc[i-1]:
            obv.iloc[i] = obv.iloc[i-1] - df['volume'].iloc[i]
        else:
            obv.iloc[i] = obv.iloc[i-1]
    
    df['OBV'] = obv
    return df

def calculate_momentum(df: pd.DataFrame, period: int = 12) -> pd.DataFrame:
    """计算动量指标 (ROC - Rate of Change)"""
    df['Momentum'] = df['close'].pct_change(periods=period) * 100
    return df

def apply_all_advanced_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """应用所有高级指标"""
    df = calculate_bollinger_bands(df)
    df = calculate_volume_divergence(df)
    df = calculate_chan_patterns(df)
    df = calculate_obv(df)
    df = calculate_momentum(df)
    logger.info("✅ 已应用所有高级技术指标")
    return df
