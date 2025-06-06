# -*- coding: utf-8 -*-
"""Untitled0.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/12YlNMA5KDISq7uhnnYl8cxTqbre---Ur
"""

import streamlit as st
import pandas as pd
import numpy as np
import joblib
import os
import xgboost as xgb # モデル推論時に必要

# --- 定数定義 (モデル訓練時と同じものを使用) ---
MEDALS_PER_GAME_COST = 3
REPLAY_PROBABILITY = 1 / 7.3  # マイジャグラーVの一般的なリプレイ確率
PAYOUT_BIG_GROSS = 252      # BIGボーナス1回あたりの総獲得枚数
PAYOUT_REG_GROSS = 96       # REGボーナス1回あたりの総獲得枚数

def preprocess_inputs_for_10feature_model(input_data_dict):
    """
    ユーザー入力の辞書（8つの基本情報＋小役カウント）から、
    モデル予測に必要な10個の特徴量を計算する関数。
    """
    df = pd.DataFrame([input_data_dict])

    # 必須キーの存在と型チェック
    required_keys_type = {
        'num_games_simulated': int,
        'sashimai': int,
        'solo_bb_count': int,
        'cherry_bb_count': int,
        'solo_rb_count': int,
        'cherry_rb_count': int,
        'grape_count': int,
        'cherry_count': int
    }
    for key, expected_type in required_keys_type.items():
        if key not in df.columns or pd.isna(df[key].iloc[0]):
            st.error(f"入力エラー: '{key}' の値が設定されていません。")
            return None
        try:
            df[key] = df[key].astype(expected_type)
        except ValueError:
            st.error(f"入力エラー: '{key}' の値が不正です。適切な数値を入力してください。")
            return None
        if key == 'num_games_simulated' and df[key].iloc[0] <= 0:
            st.error(f"入力エラー: 'num_games_simulated' は正の整数である必要があります。")
            return None

    # --- 10個の基本特徴量の計算 ---
    df['num_games'] = df['num_games_simulated']

    # estimated_total_medals_in と calculated_total_medals_out の計算
    df['estimated_total_medals_in'] = df['num_games'] * (1 - REPLAY_PROBABILITY) * MEDALS_PER_GAME_COST
    df['estimated_total_medals_in'] = np.where(df['num_games'] > 0, df['estimated_total_medals_in'], 0).clip(min=0)
    df['calculated_total_medals_out'] = df['sashimai'] + df['estimated_total_medals_in']

    # 各種レートの計算
    total_bb_count = df['solo_bb_count'] + df['cherry_bb_count']
    df['bb_rate'] = np.where(df['num_games'] > 0, total_bb_count / df['num_games'], 0)
    total_rb_count = df['solo_rb_count'] + df['cherry_rb_count']
    df['rb_rate'] = np.where(df['num_games'] > 0, total_rb_count / df['num_games'], 0)

    df['machine_percentage_rpm'] = np.where(
        df['estimated_total_medals_in'] > 0,
        df['calculated_total_medals_out'] / df['estimated_total_medals_in'], 1.0
    )
    df['grape_rate'] = np.where(df['num_games'] > 0, df['grape_count'] / df['num_games'], 0)
    df['cherry_rate'] = np.where(df['num_games'] > 0, df['cherry_count'] / df['num_games'], 0) # 総チェリー回数を使用
    df['solo_bb_rate'] = np.where(df['num_games'] > 0, df['solo_bb_count'] / df['num_games'], 0)
    df['solo_rb_rate'] = np.where(df['num_games'] > 0, df['solo_rb_count'] / df['num_games'], 0)
    df['cherry_bb_rate'] = np.where(df['num_games'] > 0, df['cherry_bb_count'] / df['num_games'], 0)
    df['cherry_rb_rate'] = np.where(df['num_games'] > 0, df['cherry_rb_count'] / df['num_games'], 0)

    # モデルが使用する特徴量のリスト (訓練時と完全に一致させる)
    feature_columns = [
        'num_games', 'bb_rate', 'rb_rate', 'machine_percentage_rpm',
        'grape_rate', 'cherry_rate',
        'solo_bb_rate', 'solo_rb_rate', 'cherry_bb_rate', 'cherry_rb_rate'
    ]

    # NaN/inf処理
    for col in feature_columns:
        if col in df.columns:
             df[col] = df[col].replace([np.inf, -np.inf], np.nan).fillna(0)
        else:
            st.error(f"エラー: 特徴量 '{col}' が生成されていません。入力キーや計算過程を確認してください。")
            return None

    X_transformed = df[feature_columns]
    return X_transformed

# モデルの読み込みをキャッシュする
@st.cache_resource # Streamlit 1.19.0 以降では _resource, それ以前は _singleton や _rerun
def load_model(model_path):
    if not os.path.exists(model_path):
        st.error(f"モデルファイル '{model_path}' が見つかりません。パスを確認してください。")
        return None
    try:
        model = joblib.load(model_path)
        st.success(f"モデル '{model_path}' を正常に読み込みました。")
        return model
    except Exception as e:
        st.error(f"モデルの読み込み中にエラーが発生しました: {e}")
        return None

# --- Streamlit アプリのUI部分 ---
st.set_page_config(page_title="設定判別アプリ (詳細入力版)", layout="wide")
st.title("マイジャグラーV 設定判別アプリ (詳細入力・2値分類)")
st.markdown("入力されたデータから、設定が「低中設定(1-3)」か「高中設定(4-6)」かを予測します。")

# ★★★ 学習済みモデルのファイルパスを指定 ★★★
MODEL_FILE_PATH = 'juggler_binary_classifier_grape_tuned.joblib' # 10特徴量で訓練・チューニングしたモデル

trained_model = load_model(MODEL_FILE_PATH)

# サイドバーでユーザー入力を受け付ける
st.sidebar.header("遊技データを入力してください")
num_games_input = st.sidebar.number_input("総ゲーム数", min_value=1, value=3000, step=100, key="num_games_detailed")
sashimai_input = st.sidebar.number_input("差枚 (例: +1000, -500)", value=0, step=50, key="sashimai_detailed")
solo_bb_count_input = st.sidebar.number_input("単独BIG回数", min_value=0, value=8, step=1, key="solo_bb_detailed")
cherry_bb_count_input = st.sidebar.number_input("チェリー重複BIG回数", min_value=0, value=2, step=1, key="cherry_bb_detailed")
solo_rb_count_input = st.sidebar.number_input("単独REG回数", min_value=0, value=7, step=1, key="solo_rb_detailed")
cherry_rb_count_input = st.sidebar.number_input("チェリー重複REG回数", min_value=0, value=3, step=1, key="cherry_rb_detailed")
grape_count_input = st.sidebar.number_input("ブドウ回数", min_value=0, value=500, step=10, key="grape_detailed")
cherry_count_input = st.sidebar.number_input("総チェリー回数 (ボーナス重複含む)", min_value=0, value=80, step=5, key="cherry_total_detailed")


# 予測ボタン
if st.sidebar.button("設定グループを判別する (詳細入力)", type="primary", key="predict_button_detailed"):
    if trained_model is not None:
        # preprocess関数が期待するキー名に合わせる
        user_inputs_dict = {
            'num_games_simulated': num_games_input,
            'sashimai': sashimai_input,
            'solo_bb_count': solo_bb_count_input,
            'cherry_bb_count': cherry_bb_count_input,
            'solo_rb_count': solo_rb_count_input,
            'cherry_rb_count': cherry_rb_count_input,
            'grape_count': grape_count_input,
            'cherry_count': cherry_count_input
        }

        st.markdown("---")
        st.subheader("入力データ (詳細):")
        # 表示用に整形
        display_inputs = {
            "総ゲーム数": user_inputs_dict['num_games_simulated'],
            "差枚": user_inputs_dict['sashimai'],
            "単独BIG": user_inputs_dict['solo_bb_count'],
            "チェリー重複BIG": user_inputs_dict['cherry_bb_count'],
            "単独REG": user_inputs_dict['solo_rb_count'],
            "チェリー重複REG": user_inputs_dict['cherry_rb_count'],
            "ブドウ回数": user_inputs_dict['grape_count'],
            "総チェリー回数": user_inputs_dict['cherry_count'],
        }
        st.json(display_inputs)

        # 特徴量へ変換
        features_for_prediction = preprocess_inputs_for_10feature_model(user_inputs_dict)

        if features_for_prediction is not None:
            st.subheader("計算された特徴量 (モデル入力用):")
            st.dataframe(features_for_prediction)

            try:
                # 予測の実行
                prediction_label_encoded = trained_model.predict(features_for_prediction)[0]
                predicted_probabilities = trained_model.predict_proba(features_for_prediction)[0]

                class_names = ['設定1-3グループ (低中設定)', '設定4-6グループ (高中設定)']
                predicted_class_name = class_names[prediction_label_encoded]

                st.subheader("📈 予測結果")
                st.markdown(f"**判別されたグループ:** <span style='font-size:1.5em; color:blue;'>{predicted_class_name}</span>", unsafe_allow_html=True)

                col1, col2 = st.columns(2)
                with col1:
                    st.metric(label=f"'{class_names[0]}' である確率", value=f"{predicted_probabilities[0]:.2%}")
                with col2:
                    st.metric(label=f"'{class_names[1]}' である確率", value=f"{predicted_probabilities[1]:.2%}")

                # 確率に基づいた簡易的なコメント
                if predicted_probabilities[1] > 0.80: # 高中設定である確率が80%超
                    st.success("高中設定グループの可能性が非常に高いと推測されます。")
                elif predicted_probabilities[1] > 0.65: # 高中設定である確率が65%超
                    st.info("高中設定グループの可能性が高いと推測されます。")
                elif predicted_probabilities[0] > 0.80: # 低中設定である確率が80%超
                    st.success("低中設定グループの可能性が非常に高いと推測されます。")
                elif predicted_probabilities[0] > 0.65: # 低中設定である確率が65%超
                    st.info("低中設定グループの可能性が高いと推測されます。")
                else:
                    st.warning("予測の確信度は中間的です。より多くのゲーム数で再度ご確認ください。")

            except Exception as e:
                st.error(f"予測の実行中にエラーが発生しました: {e}")
                import traceback
                st.text(traceback.format_exc())
        else:
            st.error("特徴量の生成に失敗しました。入力値を確認してください。")
    else:
        st.error("モデルが読み込まれていません。上記のモデルファイルパスを確認し、Streamlitを再起動してください。")

st.sidebar.markdown("---")
st.sidebar.markdown("このアプリは機械学習モデルによる予測であり、実際の設定を保証するものではありません。")