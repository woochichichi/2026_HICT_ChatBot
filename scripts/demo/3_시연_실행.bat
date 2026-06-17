@echo off
setlocal enabledelayedexpansion
chcp 949 >nul
title AI 코치 - 시연 실행

pushd "%~dp0..\.."
set "ROOT=%CD%"
popd
set "PY=%ROOT%\.venv\Scripts\python.exe"

echo ============================================================
echo  AI 코치 - 시연 실행  [서버 기동 + 브라우저]
echo ============================================================
echo.

rem === 환경설정 됐는지 확인 ===
if exist "%PY%" goto :ready
echo   [오류] 가상환경(.venv)이 없습니다.
echo          먼저 2_시연_환경설정.bat 을 실행하세요.
pause
exit /b 1
:ready
if not exist "%ROOT%\data\chroma_db\chroma.sqlite3" echo   [경고] ChromaDB 없음 - 검색이 빈 결과. demo_bundle 배치/환경설정을 확인하세요.
echo.

rem === 1. 서버 기동 - 새 창 2개 ===
echo [1/2] 백엔드/프론트엔드 기동
start "AI코치 백엔드" cmd /k "cd /d %ROOT% && set EMBEDDING_PROVIDER=local && %PY% -m uvicorn backend.main:app --host 127.0.0.1 --port 8000"
start "AI코치 프론트" cmd /k "cd /d %ROOT%\frontend && npm run dev"
echo.

rem === 2. 브라우저 ===
echo [2/2] 서버 기동 대기 후 브라우저 열기
timeout /t 8 /nobreak >nul
start "" http://localhost:3000/
echo.
echo ============================================================
echo  완료! 브라우저에서 http://localhost:3000 확인
echo  첫 질문은 bge-m3 로딩으로 잠깐 걸릴 수 있습니다.
echo  종료하려면 백엔드/프론트 창 2개를 닫으세요.
echo ============================================================
echo.
pause
endlocal
