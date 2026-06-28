import json
import os
import random
import streamlit as st
from openai import OpenAI
from dotenv import load_dotenv

WORDS_FILE = "words.json"
STATS_FILE = "stats.json"

# ▼.envからAPIキーを読み込む
load_dotenv()

# ▼キーを取得：まずStreamlitのSecrets、なければ.envから
api_key = st.secrets.get("OPENAI_API_KEY", None) if hasattr(st, "secrets") else None
if not api_key:
    api_key = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=api_key)

# ▼単語データを読み込む
with open(WORDS_FILE, "r", encoding="utf-8") as f:
    words = json.load(f)

# ▼間違い回数の記録を読み込む（無ければ空から）
if os.path.exists(STATS_FILE):
    with open(STATS_FILE, "r", encoding="utf-8") as f:
        stats = json.load(f)
else:
    stats = {}

def save_stats():
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

# ▼AIに単語を頼んで words.json に追加する部品（昨日のadd_words.pyの中身）
def fetch_new_words():
    existing = "、".join(words.keys())
    prompt = f"""TOEIC900点レベルの英単語を10個、JSON形式で出してください。
形式は {{"単語": "日本語の意味"}} の辞書だけ。
説明や前置き、コードブロックの記号は一切付けず、JSONそのものだけを返してください。

ただし、次の単語はすでに持っているので、これらとは重複しないものを選んでください：
{existing}"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
    )
    new_words = json.loads(response.choices[0].message.content)

    added = 0
    for w, meaning in new_words.items():
        if w not in words:
            words[w] = meaning
            added += 1

    with open(WORDS_FILE, "w", encoding="utf-8") as f:
        json.dump(words, f, ensure_ascii=False, indent=2)

    return added

# ▼シャッフルした順番を作る部品
def make_deck():
    deck = list(words.keys())
    random.shuffle(deck)
    return deck

st.title("英単語フラッシュカード")

# ▼セッションの初期化
if "deck" not in st.session_state:
    st.session_state.deck = make_deck()
    st.session_state.index = 0
if "score" not in st.session_state:
    st.session_state.score = 0
if "total" not in st.session_state:
    st.session_state.total = 0

def next_word():
    st.session_state.index += 1
    if st.session_state.index >= len(st.session_state.deck):
        st.session_state.deck = make_deck()
        st.session_state.index = 0

word = st.session_state.deck[st.session_state.index]

st.caption(f"{st.session_state.index + 1} / {len(st.session_state.deck)}（登録 {len(words)}語）")
st.header(word)

if st.button("答えを見る"):
    st.success(words[word])

st.write("---")

col1, col2 = st.columns(2)

with col1:
    if st.button("⭕️ 正解"):
        st.session_state.score += 1
        st.session_state.total += 1
        if stats.get(word, 0) > 0:
            stats[word] = stats[word] - 1
        save_stats()
        next_word()
        st.rerun()

with col2:
    if st.button("❌ 不正解"):
        st.session_state.total += 1
        stats[word] = stats.get(word, 0) + 1
        save_stats()
        next_word()
        st.rerun()

st.write(f"**成績：{st.session_state.total}問中 {st.session_state.score}問正解**")

st.write("---")

# ▼単語追加ボタン（AI連携）
if st.button("🤖 AIで単語を追加"):
    with st.spinner("AIに単語を頼んでいます…"):
        added = fetch_new_words()
    st.success(f"{added}個の新しい単語を追加しました。（合計 {len(words)}語）")
    # 新しい単語を反映するため、山札を作り直す
    st.session_state.deck = make_deck()
    st.session_state.index = 0

st.write("---")

# ▼表形式でまとめて単語を追加
st.subheader("✍️ まとめて単語を追加")
st.caption("左に英単語、右に意味を入力してください。行は下の＋で増やせます。")

# ▼空の表を用意（最初は5行分）
if "input_table" not in st.session_state:
    st.session_state.input_table = [{"英単語": "", "意味": ""} for _ in range(5)]

# ▼編集できる表を表示
edited = st.data_editor(
    st.session_state.input_table,
    num_rows="dynamic",        # 行を自由に増やせる
    use_container_width=True,
    column_config={
        "英単語": st.column_config.TextColumn("英単語", width="medium"),
        "意味": st.column_config.TextColumn("意味", width="large"),
    },
    key="word_editor",
)

if st.button("➕ 表の単語をまとめて追加"):
    added = 0
    skipped = 0
    for row in edited:
        w = str(row.get("英単語", "")).strip()
        m = str(row.get("意味", "")).strip()
        if w == "" or m == "":        # 空の行は飛ばす
            continue
        if w in words:                # すでにある単語は飛ばす
            skipped += 1
            continue
        words[w] = m
        added += 1

    if added == 0:
        st.warning("追加できる単語がありませんでした。（空欄・重複のみ）")
    else:
        with open(WORDS_FILE, "w", encoding="utf-8") as f:
            json.dump(words, f, ensure_ascii=False, indent=2)
        msg = f"{added}個の単語を追加しました。（合計 {len(words)}語）"
        if skipped > 0:
            msg += f"／重複のため{skipped}個はスキップしました。"
        st.success(msg)
        # 入力表を空に戻し、山札も作り直す
        st.session_state.input_table = [{"英単語": "", "意味": ""} for _ in range(5)]
        st.session_state.deck = make_deck()
        st.session_state.index = 0
        st.rerun()