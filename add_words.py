import os
import json
from openai import OpenAI
from dotenv import load_dotenv

WORDS_FILE = "words.json"

# ▼.envからAPIキーを読み込む
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ▼今ある単語ファイルを読み込む（無ければ空から）
if os.path.exists(WORDS_FILE):
    with open(WORDS_FILE, "r", encoding="utf-8") as f:
        words = json.load(f)
else:
    words = {}

# ▼今持っている単語を、カンマ区切りの一覧にする
existing = "、".join(words.keys())

# ▼AIへの注文（持っている単語を渡して「避けて」と伝える）
prompt = f"""TOEIC900点レベルの英単語を10個、JSON形式で出してください。
形式は {{"単語": "日本語の意味"}} の辞書だけ。
説明や前置き、コードブロックの記号は一切付けず、JSONそのものだけを返してください。

ただし、次の単語はすでに持っているので、これらとは重複しないものを選んでください：
{existing}"""

print("AIに単語を頼んでいます…")
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": prompt}],
)
answer = response.choices[0].message.content

# ▼AIの返事を辞書に変換
new_words = json.loads(answer)

# ▼新しい単語を追加（万一かぶっても二重登録しない）
added = 0
for word, meaning in new_words.items():
    if word not in words:
        words[word] = meaning
        added += 1

# ▼ファイルに保存
with open(WORDS_FILE, "w", encoding="utf-8") as f:
    json.dump(words, f, ensure_ascii=False, indent=2)

print(f"{added}個の新しい単語を追加しました。（合計 {len(words)}個）")