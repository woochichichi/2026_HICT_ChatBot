@echo off
setlocal enabledelayedexpansion
chcp 949 >nul
title AI코치 - 개발 테스트 서버

rem %~dp0 는 이 bat 파일이 있는 폴더(=프로젝트 루트)
pushd "%~dp0."
set "ROOT=%CD%"
popd

rem 8.3 짧은이름 변환 - 한글/공백 경로 CMD 파서 안전
for %%d in ("%ROOT%") do set "ROOT=%%~sd"

set "PY=%ROOT%\.venv\Scripts\python.exe"

echo ============================================================
echo  AI코치 개발 테스트 서버 기동
echo  백엔드   http://localhost:8000
echo  프론트   http://localhost:3000
echo ============================================================
echo.

rem === 사전 체크 ===
if not exist "%ROOT%\.env" (
    echo   [경고] .env 파일 없음. .env.example 복사 후 API 키를 채워주세요.
    pause
    exit /b 1
)

if not exist "%PY%" (
    echo   [오류] 가상환경 없음. scripts\demo\2_시연_환경설정.bat 를 먼저 실행하세요.
    pause
    exit /b 1
)

where npm >nul 2>nul
if !errorlevel! neq 0 (
    echo   [오류] npm 없음. nodejs.org 에서 LTS 설치 후 재실행하세요.
    pause
    exit /b 1
)

echo   [OK] 환경 확인 완료
echo.

rem === 백엔드 기동 (새 창) ===
echo [1/3] 백엔드 uvicorn 기동...
start "AI코치-백엔드" cmd /k "cd /d %ROOT% && %PY% -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload"

rem === 프론트엔드 기동 (새 창) ===
echo [2/3] 프론트엔드 npm run dev 기동...
start "AI코치-프론트" cmd /k "cd /d %ROOT%\frontend && npm run dev"

rem === 브라우저 오픈 ===
echo [3/3] 서버 기동 대기 ^(8초^)...
timeout /t 8 /nobreak >nul
start "" http://localhost:3000/

echo.
echo ============================================================
echo  완료! 브라우저에서 http://localhost:3000 을 확인하세요.
echo  첫 실행 시 bge-m3 로드로 30~60초 더 걸릴 수 있습니다.
echo  종료: 백엔드/프론트엔드 창 2개를 닫으세요.
echo ============================================================
echo.
pause
endlocal
