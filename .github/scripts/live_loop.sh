#!/usr/bin/env bash
# 競走成績の速報: 1回の実行の中で、10分おきに「取得 → live/ を載せる」を約50分くり返す
# （GitHub の定期実行は1時間に1回ほどしか動かないことがあるため。2026/11/19）
# Pages リポジトリの .github/scripts/live_loop.sh に置き、.github/workflows/live-results.yml から呼ぶ。
# 元は AI作業場\自動化スクリプト\live\live_loop.sh。間隔などはここを直せば、設定ファイル（yml）は直さなくてよい。
#
# 載せ方: パソコン側の公開（publish_dashboard.py）は履歴なしの強制書き換えなので、こちらは強制しない push にして、
#         弾かれたら最新を取り直して live/ だけ載せ直す（パソコン側の公開を消さないため）。
set -u
LOOP_MINUTES=${LOOP_MINUTES:-50}   # 1回の実行で続ける長さ（分）。設定ファイルの上限 60分 より短く
INTERVAL=${LOOP_INTERVAL:-600}     # くり返しの間隔（秒）
END=$(( $(date +%s) + LOOP_MINUTES * 60 ))
BRANCH=${GITHUB_REF_NAME:-main}

git config user.name "live-results"
git config user.email "live-results@localhost.invalid"

push_live() {
  git add -A live
  if git diff --cached --quiet; then echo "変化なし"; return 0; fi
  git commit -q -m "競走成績の速報 $(TZ=Asia/Tokyo date '+%Y-%m-%d %H:%M')"
  for i in 1 2 3 4; do
    if git push -q origin "HEAD:${BRANCH}"; then echo "載せました"; return 0; fi
    echo "弾かれたので最新を取り直します（${i}回目）"
    sleep $((i * 10))
    rm -rf /tmp/live && cp -r live /tmp/live
    git fetch -q --depth=1 origin "${BRANCH}"
    git reset -q --hard FETCH_HEAD
    rm -rf live && cp -r /tmp/live live
    git add -A live
    if git diff --cached --quiet; then echo "変化なし"; return 0; fi
    git commit -q -m "競走成績の速報 $(TZ=Asia/Tokyo date '+%Y-%m-%d %H:%M')"
  done
  echo "載せられませんでした"
  return 1
}

while :; do
  start=$(date +%s)
  h=$((10#$(TZ=Asia/Tokyo date +%H)))
  # 日本時間 7〜23時だけ動く（2026/11/20 8時→7時。GitHub の起動が遅れても朝いちばんのレースの直前展示に間に合うように）
  if [ "$h" -ge 23 ] || [ "$h" -lt 7 ]; then echo "日本時間 7〜23時の外なので終わります"; break; fi
  echo "=== $(TZ=Asia/Tokyo date '+%H:%M:%S') ==="
  python3 .github/scripts/live_results.py --out . || echo "取得に失敗しました（次の回にまた試します）"
  push_live || true
  next=$(( start + INTERVAL ))
  if [ "$next" -ge "$END" ]; then echo "続ける長さ（${LOOP_MINUTES}分）に達したので終わります"; break; fi
  wait=$(( next - $(date +%s) ))
  if [ "$wait" -gt 0 ]; then sleep "$wait"; fi
done
