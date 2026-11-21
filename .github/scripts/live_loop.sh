#!/usr/bin/env bash
# 競走成績の速報・直前展示: 1回の実行の中で、1分おきに「取得 → 載せる」を約55分くり返し、終わる前に次の回を予約する
# （GitHub の定期実行は1時間に1回ほどしか動かないことがあるため。2026/11/19）
# Pages リポジトリの .github/scripts/live_loop.sh に置き、.github/workflows/live-results.yml から呼ぶ。
# 元は AI作業場\自動化スクリプト\live\live_loop.sh。間隔などはここを直せば、設定ファイル（yml）は直さなくてよい。
#
# 載せる先（2026/11/21 変更。直前展示が遅すぎたため。それまでは10分おきに main だけ）
#   1) live-data ブランチ … 3分おき。履歴なしの1コミットを強制で置き換える（このジョブだけが書く）。
#      Pages の作り直しが要らず、各ページは raw.githubusercontent.com からすぐ読む（site_nav.py の DLive）
#   2) main（Pages の live/）… 今までどおり。10分に1回だけ（Pages の作り直しは1時間10回までの目安があるため）。
#      古いページと、live-data が読めないときの控え
# main への載せ方: パソコン側の公開（publish_dashboard.py）は履歴なしの強制書き換えなので、こちらは強制しない push にして、
#         弾かれたら最新を取り直して live/ だけ載せ直す（パソコン側の公開を消さないため）。
#
# 直前展示を締切に間に合わせる（2026/11/21 追加）
#   - 1分おきに回る。3分に1回は全体の取得（live_results.py：結果・払戻・水面気象・直前情報・オリ展。1回40件ほど）、
#     そのあいだの回は live_pre_fast.py（締切25分前〜結果が出るまでで、直前情報がまだそろっていないレースだけ。1回数件）
#   - live-data には中身が変わったときだけ載せる
#   - 終わる CHAIN_BEFORE 秒前に、次の回を自分で予約する（workflow_dispatch。GitHub の定期実行は1時間に1回ほどしか
#     動かず、回と回のあいだに切れ目ができていたため）。同じ group なので、今の回が終わるとすぐ次の回が始まる。
#     定期実行（yml の cron）は、つながりが切れたときと朝いちばんの起動のための予備として残す
set -u
LOOP_MINUTES=${LOOP_MINUTES:-55}   # 1回の実行で続ける長さ（分）。設定ファイルの上限 60分 より短く
INTERVAL=${LOOP_INTERVAL:-60}      # くり返しの間隔（秒）。直前情報だけを取る回の間隔
FULL_EVERY=${FULL_EVERY:-180}      # 全体の取得の間隔（秒）。ボートキャストに1回40件ほど(0.7秒あけて)取りに行くので、
                                   # 止められないよう3分のまま(boatrace.jp は取りすぎで止められた。project-live-results)
MAIN_EVERY=${MAIN_EVERY:-600}      # main（Pages）に載せる間隔（秒）
CHAIN_BEFORE=${CHAIN_BEFORE:-300}  # 終わるこの秒数前に次の回を予約する
DATA_BRANCH=live-data
END=$(( $(date +%s) + LOOP_MINUTES * 60 ))
BRANCH=${GITHUB_REF_NAME:-main}

git config user.name "live-results"
git config user.email "live-results@localhost.invalid"

# 前の回の続き: live-data のほうが新しいので、あればその live/ から始める（取り直しを減らす）
if git fetch -q --depth=1 origin "${DATA_BRANCH}" 2>/dev/null; then
  rm -rf /tmp/ld_prev && mkdir -p /tmp/ld_prev
  if git --work-tree=/tmp/ld_prev checkout -q FETCH_HEAD -- live 2>/dev/null; then
    cp -r /tmp/ld_prev/live/. live/ && echo "live-data の続きから始めます"
  fi
  git reset -q    # checkout で変わった index を元に戻す
fi

last_tree=""
push_data() {
  # live/ だけの木を作り、履歴なしの1コミットで live-data を置き換える（作業中のファイルと index は触らない）
  local idx=/tmp/ld.idx tree commit
  rm -f "$idx"
  GIT_INDEX_FILE="$idx" git add -A live || return 1
  tree=$(GIT_INDEX_FILE="$idx" git write-tree) || return 1
  if [ "$tree" = "$last_tree" ]; then return 0; fi   # 前に載せた中身と同じなら載せない
  last_tree=$tree
  commit=$(git commit-tree "$tree" -m "速報・直前展示 $(TZ=Asia/Tokyo date '+%Y-%m-%d %H:%M:%S')") || return 1
  if git push -q -f origin "${commit}:refs/heads/${DATA_BRANCH}"; then echo "live-data に載せました"; else echo "live-data に載せられませんでした"; fi
}

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

chain_next() {
  # 次の回を予約する（yml で GH_TOKEN・GITHUB_REPOSITORY と permissions の actions: write を渡す）
  [ -n "${GH_TOKEN:-}" ] && [ -n "${GITHUB_REPOSITORY:-}" ] || { echo "次の回を予約できません（GH_TOKEN なし）"; return 1; }
  if curl -fsS -X POST -H "Authorization: Bearer ${GH_TOKEN}" -H "Accept: application/vnd.github+json" \
       "https://api.github.com/repos/${GITHUB_REPOSITORY}/actions/workflows/live-results.yml/dispatches" \
       -d "{\"ref\":\"${BRANCH}\"}" >/dev/null; then
    echo "次の回を予約しました"
  else
    echo "次の回を予約できませんでした（定期実行の起動を待ちます）"
  fi
}

last_main=0
last_full=0
chained=0
while :; do
  start=$(date +%s)
  h=$((10#$(TZ=Asia/Tokyo date +%H)))
  # 日本時間 7〜23時だけ動く（2026/11/20 8時→7時。GitHub の起動が遅れても朝いちばんのレースの直前展示に間に合うように）
  if [ "$h" -ge 23 ] || [ "$h" -lt 7 ]; then echo "日本時間 7〜23時の外なので終わります"; break; fi
  if [ $(( start - last_full )) -ge "$FULL_EVERY" ]; then
    echo "=== $(TZ=Asia/Tokyo date '+%H:%M:%S') 全体 ==="
    python3 .github/scripts/live_results.py --out . || echo "取得に失敗しました（次の回にまた試します）"
    last_full=$start
  else
    echo "=== $(TZ=Asia/Tokyo date '+%H:%M:%S') 直前情報だけ ==="
    python3 .github/scripts/live_pre_fast.py --out . || echo "直前情報の取得に失敗しました（次の回にまた試します）"
  fi
  push_data || true
  if [ "$chained" -eq 0 ] && [ $(( END - $(date +%s) )) -le "$CHAIN_BEFORE" ] && [ "$h" -lt 22 -o $((10#$(TZ=Asia/Tokyo date +%M))) -lt 50 ]; then
    chain_next || true; chained=1
  fi
  if [ $(( start - last_main )) -ge "$MAIN_EVERY" ]; then push_live || true; last_main=$start; fi
  next=$(( start + INTERVAL ))
  if [ "$next" -ge "$END" ]; then
    push_live || true    # 終わる前に main にも今の分を載せておく
    echo "続ける長さ（${LOOP_MINUTES}分）に達したので終わります"; break
  fi
  wait=$(( next - $(date +%s) ))
  if [ "$wait" -gt 0 ]; then sleep "$wait"; fi
done
