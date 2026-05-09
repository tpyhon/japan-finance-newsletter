@echo off
:: ─────────────────────────────────────────────
:: Note毎日自動投稿 - ローカル実行バッチ
:: ─────────────────────────────────────────────
cd /d C:\Users\takum\Desktop\code\japan-finance-newsletter

:: ログファイル（日付別）
set LOGFILE=logs\daily_%date:~0,4%%date:~5,2%%date:~8,2%.log
if not exist logs mkdir logs

echo ========================================= >> %LOGFILE%
echo 開始: %date% %time% >> %LOGFILE%
echo ========================================= >> %LOGFILE%

:: .venv の Python を使う
set PYTHON=.venv\Scripts\python.exe

:: ── 1. 市場データ収集 ──────────────────────────
echo [1/4] 市場データ収集中... >> %LOGFILE%
%PYTHON% src\collect_data.py >> %LOGFILE% 2>&1
if %errorlevel% neq 0 (
    echo ❌ collect_data.py 失敗 >> %LOGFILE%
    goto :error
)

:: ── 2. 海外インテル収集 ────────────────────────
echo [2/4] 海外・国内ニュース収集中... >> %LOGFILE%
%PYTHON% src\collect_overseas_intel.py >> %LOGFILE% 2>&1
if %errorlevel% neq 0 (
    echo ❌ collect_overseas_intel.py 失敗 >> %LOGFILE%
    goto :error
)

:: ── 3. 記事生成（曜日でモード自動切替） ────────
echo [3/4] Note記事生成中... >> %LOGFILE%
%PYTHON% src\generate_note_jp.py >> %LOGFILE% 2>&1
if %errorlevel% neq 0 (
    echo ❌ generate_note_jp.py 失敗 >> %LOGFILE%
    goto :error
)

:: ── 4. Note下書き保存 ─────────────────────────
echo [4/4] Note下書き保存中... >> %LOGFILE%
%PYTHON% src\post_to_note.py >> %LOGFILE% 2>&1
if %errorlevel% neq 0 (
    echo ❌ post_to_note.py 失敗 >> %LOGFILE%
    goto :error
)

echo ✅ 全処理完了: %time% >> %LOGFILE%
exit /b 0

:error
echo 🚨 エラーで終了: %time% >> %LOGFILE%
exit /b 1
