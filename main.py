import yfinance as yf
import pandas as pd
import gymnasium as gym
import gym_anytrading
from stable_baselines3 import PPO
from gym_anytrading.envs import StocksEnv

# 1. 準備數據
def get_data():
    # 抓取 0050 數據 (近 5 年)
    df = yf.Ticker("0050.TW").history(period="5y")
    df.reset_index(inplace=True)
    # gym-anytrading 需要 Date 作為索引
    df['Date'] = pd.to_datetime(df['Date'])
    df.set_index('Date', inplace=True)
    df.dropna(inplace=True)
    return df

# 2. 建立自定義環境 (加入技術指標可優化，此處示範基礎版)
def train_and_predict():
    df = get_data()
    
    # 切分訓練集 (前 80%) 與 測試集 (後 20%)
    split_idx = int(len(df) * 0.8)
    
    # 建立訓練環境 (window_size=10 代表 AI 看過去 10 天來做決定)
    env = gym.make('stocks-v0', df=df, frame_bound=(10, split_idx), window_size=10)
    
    print("🚀 開始訓練 RL 模型 (PPO)...")
    model = PPO("MlpPolicy", env, verbose=1)
    model.learn(total_timesteps=20000) # 訓練步數，越高越準但也越久
    print("✅ 訓練完成")

    # 3. 進行預測 (回測後 20% 數據)
    test_env = gym.make('stocks-v0', df=df, frame_bound=(split_idx, len(df)), window_size=10)
    observation, info = test_env.reset()
    
    buy_signals = []
    
    while True:
        # AI 決定動作 (action: 1=Buy, 0=Sell)
        action, _states = model.predict(observation)
        observation, reward, terminated, truncated, info = test_env.step(action)
        
        # 紀錄買入點
        if action == 1: 
            current_idx = test_env.unwrapped._current_tick
            current_date = df.index[current_idx]
            buy_signals.append(current_date.strftime('%Y-%m-%d'))

        if terminated or truncated:
            break
            
    print("\n💡 AI 建議買進日期 (最近 5 次):")
    for date in buy_signals[-5:]:
        print(f"💰 {date} 建議買進")

    print(f"\n📊 最終模擬獲利: {info['total_profit']:.2f} (初始 1.0)")

if __name__ == "__main__":
    train_and_predict()
