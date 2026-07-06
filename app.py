import json
import os
import base64
import random
import requests
import streamlit as st
from openai import OpenAI
from dotenv import load_dotenv
from pathlib import Path

WORDS_FILE = "words.json"
STATS_FILE = "stats.json"
MEMORIZED_FILE = "memorized.json"

# ▼.envからAPIキーを読み込む
load_dotenv()

# ▼secrets.tomlが存在するか確認（ない環境では st.secrets を呼ばない）
_secrets_available = (
    (Path.home() / ".streamlit" / "secrets.toml").exists()
    or (Path(__file__).parent / ".streamlit" / "secrets.toml").exists()
)

# ▼キーを取得：まずStreamlitのSecrets、なければ.envから
api_key = st.secrets.get("OPENAI_API_KEY", None) if _secrets_available else None
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

# ▼覚えた単語の記録を読み込む（無ければ空から）
if os.path.exists(MEMORIZED_FILE):
    with open(MEMORIZED_FILE, "r", encoding="utf-8") as f:
        memorized = set(json.load(f))
else:
    memorized = set()

def save_memorized():
    with open(MEMORIZED_FILE, "w", encoding="utf-8") as f:
        json.dump(list(memorized), f, ensure_ascii=False, indent=2)

def save_memorized_to_github():
    if _secrets_available:
        token = st.secrets.get("GITHUB_TOKEN")
        repo = st.secrets.get("GITHUB_REPO")
        branch = st.secrets.get("GITHUB_BRANCH", "main")
    else:
        token, repo, branch = None, None, "main"

    if not token or not repo:
        return False

    api_url = f"https://api.github.com/repos/{repo}/contents/{MEMORIZED_FILE}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
    }

    res = requests.get(api_url, headers=headers, params={"ref": branch})
    sha = res.json().get("sha") if res.status_code == 200 else None

    content_str = json.dumps(list(memorized), ensure_ascii=False, indent=2)
    content_b64 = base64.b64encode(content_str.encode("utf-8")).decode("utf-8")

    payload = {
        "message": "覚えた単語を更新（アプリから自動保存）",
        "content": content_b64,
        "branch": branch,
    }
    if sha:
        payload["sha"] = sha

    put_res = requests.put(api_url, headers=headers, json=payload)
    return put_res.status_code in (200, 201)

# ▼words.jsonをGitHubリポジトリ本体に書き込んで、次回起動しても残るようにする
def save_words_to_github():
    if _secrets_available:
        token = st.secrets.get("GITHUB_TOKEN")
        repo = st.secrets.get("GITHUB_REPO")
        branch = st.secrets.get("GITHUB_BRANCH", "main")
    else:
        token, repo, branch = None, None, "main"

    if not token or not repo:
        if _secrets_available:
            st.warning("GitHubの保存設定（Secrets）が見つかりません。ローカルには保存されましたが、再起動すると消える可能性があります。")
        return False

    api_url = f"https://api.github.com/repos/{repo}/contents/{WORDS_FILE}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
    }

    # 今のファイルのSHA（更新には必須）を取得
    res = requests.get(api_url, headers=headers, params={"ref": branch})
    sha = res.json().get("sha") if res.status_code == 200 else None

    content_str = json.dumps(words, ensure_ascii=False, indent=2)
    content_b64 = base64.b64encode(content_str.encode("utf-8")).decode("utf-8")

    payload = {
        "message": "単語を追加（アプリから自動保存）",
        "content": content_b64,
        "branch": branch,
    }
    if sha:
        payload["sha"] = sha

    put_res = requests.put(api_url, headers=headers, json=payload)
    return put_res.status_code in (200, 201)

# ▼AIに単語を頼んで words.json に追加する部品
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
    save_words_to_github()

    return added

# ▼シャッフルした順番を作る部品（覚えた単語は除外）
def make_deck():
    deck = [w for w in words.keys() if w not in memorized]
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

if len(st.session_state.deck) == 0:
    st.success(f"🎉 全単語（{len(memorized)}語）を覚えました！おめでとうございます！")
    if st.button("🔄 「覚えた」をリセットして最初からやり直す"):
        memorized.clear()
        save_memorized()
        save_memorized_to_github()
        st.session_state.deck = make_deck()
        st.session_state.index = 0
        st.rerun()
    st.stop()

word = st.session_state.deck[st.session_state.index]

st.caption(f"{st.session_state.index + 1} / {len(st.session_state.deck)}（登録 {len(words)}語 ／ 覚えた {len(memorized)}語）")
st.header(word)

if st.button("答えを見る"):
    st.success(words[word])

if st.button("✓ 覚えた（出題から外す）"):
    memorized.add(word)
    save_memorized()
    save_memorized_to_github()
    next_word()
    st.rerun()

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
    st.success(f"{added}個の新しい単語を追加しました。（合計 {len(words)}語）GitHubにも保存しました。")
    st.session_state.deck = make_deck()
    st.session_state.index = 0

st.write("---")

# ▼表形式でまとめて単語を追加
st.subheader("✍️ まとめて単語を追加")
st.caption("左に英単語、右に意味を入力してください。行は下の＋で増やせます。")

if "input_table" not in st.session_state:
    st.session_state.input_table = [{"英単語": "", "意味": ""} for _ in range(5)]

edited = st.data_editor(
    st.session_state.input_table,
    num_rows="dynamic",
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
        if w == "" or m == "":
            continue
        if w in words:
            skipped += 1
            continue
        words[w] = m
        added += 1

    if added == 0:
        st.warning("追加できる単語がありませんでした。（空欄・重複のみ）")
    else:
        with open(WORDS_FILE, "w", encoding="utf-8") as f:
            json.dump(words, f, ensure_ascii=False, indent=2)
        save_words_to_github()
        msg = f"{added}個の単語を追加しました。（合計 {len(words)}語）GitHubにも保存しました。"
        if skipped > 0:
            msg += f"／重複のため{skipped}個はスキップしました。"
        st.success(msg)
        st.session_state.input_table = [{"英単語": "", "意味": ""} for _ in range(5)]
        st.session_state.deck = make_deck()
        st.session_state.index = 0
        st.rerun()