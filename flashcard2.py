import json     # JSONファイルを読み書きする道具
import random   # ランダムに選ぶ道具
import os       # ファイルの有無を確認する道具

WORDS_FILE = "words.json"      # 単語データのファイル
STATS_FILE = "stats.json"      # 間違い回数を記録するファイル
NUM_QUESTIONS = 10             # 1回の出題数
NUM_REVIEW = 3                 # そのうち復習（間違えた単語）の数
NUM_NEW = 7                    # そのうち新規（まだ出していない単語）の数

# ▼単語データを読み込む
with open(WORDS_FILE, "r", encoding="utf-8") as f:
    words = json.load(f)

# ▼間違い回数の記録を読み込む（まだ無ければ空っぽから始める）
if os.path.exists(STATS_FILE):
    with open(STATS_FILE, "r", encoding="utf-8") as f:
        stats = json.load(f)
else:
    stats = {}

# ▼各単語の間違い回数を返す（記録が無ければ0）
def miss_count(word):
    return stats.get(word, 0)

# ▼単語を「出題済み（復習組）」と「初登場（新規組）」に分ける
seen_words = [w for w in words if w in stats]      # 記録あり＝過去に出題済み
new_words = [w for w in words if w not in stats]   # 記録なし＝初登場

# ▼復習組は間違いが多い順、新規組はランダムに並べる
seen_sorted = sorted(seen_words, key=miss_count, reverse=True)
random.shuffle(new_words)

# ▼復習3個・新規7個を取る
review_part = seen_sorted[:NUM_REVIEW]
new_part = new_words[:NUM_NEW]
quiz_words = review_part + new_part

# ▼もし合計が10個に満たなければ、余っている単語から補う
if len(quiz_words) < NUM_QUESTIONS:
    used = set(quiz_words)
    leftover = [w for w in seen_sorted + new_words if w not in used]
    quiz_words += leftover[: NUM_QUESTIONS - len(quiz_words)]

# ▼出題の順番をシャッフルする
random.shuffle(quiz_words)

# ▼出題ループ
correct = 0
for word in quiz_words:
    input(f"\n【{word}】の意味は？（Enterで答えを表示）")
    print(f"答え: {words[word]}")
    judge = input("合ってた？ (y/n): ")

    if judge.strip().lower() == "y":
        correct += 1
        # 正解したら間違い回数を1減らす（0より下にはしない）
        if stats.get(word, 0) > 0:
            stats[word] = stats[word] - 1
    else:
        # 間違えたら間違い回数を1増やす
        stats[word] = stats.get(word, 0) + 1

# ▼結果を表示
print(f"\n今回の結果: {len(quiz_words)}問中 {correct}問 正解！")

# ▼間違い回数の記録を保存（次回に引き継ぐ）
with open(STATS_FILE, "w", encoding="utf-8") as f:
    json.dump(stats, f, ensure_ascii=False, indent=2)

print("結果を記録しました。間違えた単語は次回優先的に出題します。")