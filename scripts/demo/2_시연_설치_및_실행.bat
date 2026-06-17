@echo off
setlocal enabledelayedexpansion
chcp 949 >nul
title AI 코치 - 시연 설치 및 실행

pushd "%~dp0..\.."
set "ROOT=%CD%"
popd
set "ZIP=%ROOT%\demo_bundle.zip"
set "TMP=%ROOT%\_bundle_tmp"
set "PY=%ROOT%\.venv\Scripts\python.exe"
set "TAR=%WINDIR%\System32\tar.exe"

echo ============================================================
echo  AI 코치 - 시연 설치 및 실행  [시연 PC에서 실행]
echo ============================================================
echo  프로젝트 루트: %ROOT%
echo.

rem === 0. demo_bundle.zip 압축 해제 + 파일 배치 ===
echo [0/6] 전달받은 zip 압축 해제 및 배치
set "SRC="
if exist "%ZIP%" goto :unzip
if exist "%ROOT%\demo_bundle\data\chroma_db\chroma.sqlite3" goto :usefolder
echo   [경고] demo_bundle.zip 도 demo_bundle 폴더도 없음. DB 없이 진행하면 검색이 빈 결과.
goto :placedone
:usefolder
set "SRC=%ROOT%\demo_bundle"
goto :place
:unzip
rmdir /s /q "%TMP%" 2>nul
mkdir "%TMP%"
"%TAR%" -x -f "%ZIP%" -C "%TMP%"
set "SRC=%TMP%"
echo   [완료] 압축 해제
:place
if exist "!SRC!\data\chroma_db\chroma.sqlite3" robocopy "!SRC!\data\chroma_db" "%ROOT%\data\chroma_db" /E /NFL /NDL /NJH /NJS /NC /NS /NP >nul
if exist "%ROOT%\data\chroma_db\chroma.sqlite3" echo   [완료] ChromaDB 배치
if exist "!SRC!\.env" copy /y "!SRC!\.env" "%ROOT%\.env" >nul
if exist "!SRC!\data\meta.db" copy /y "!SRC!\data\meta.db" "%ROOT%\data\meta.db" >nul
:placedone
echo.

rem === .env 점검 ===
if exist "%ROOT%\.env" goto :envok
echo   [중요] .env 가 없습니다. 루트에 .env 파일을 만들고 아래 2줄을 넣으세요:
echo         GOOGLE_API_KEY=여기에_본인_키
echo         EMBEDDING_PROVIDER=local
echo.
:envok

rem === 1. Python 확인 ===
echo [1/6] Python 확인
where python >nul 2>nul
if errorlevel 1 (
    echo   [오류] Python 미설치. python.org 에서 3.12 설치 후 다시 실행.
    pause
    exit /b 1
)
echo   [OK] Python 있음
echo.

rem === 2. 가상환경 + 패키지 ===
echo [2/6] 가상환경/패키지  - 처음만 수 분 소요
if not exist "%PY%" python -m venv "%ROOT%\.venv"
if exist "%PY%" echo   [OK] .venv 준비됨
"%PY%" -m pip install --upgrade pip >nul
echo   [설치] torch CPU 버전
"%PY%" -m pip install torch --index-url https://download.pytorch.org/whl/cpu
echo   [설치] requirements.txt
"%PY%" -m pip install -r "%ROOT%\requirements.txt"
echo.

rem === 3. bge-m3 임베딩 모델 다운로드 (최초 1회, 인터넷 필요, 약 2.2GB) ===
echo [3/6] bge-m3 모델 준비  - 최초만 다운로드, 수 분 소요
if exist "%USERPROFILE%\.cache\huggingface\hub\models--BAAI--bge-m3" goto :modeldone
echo   [다운로드] bge-m3 ... 인터넷 필요. 시연 중 끊기지 않게 지금 받아둡니다.
"%PY%" -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-m3')"
:modeldone
echo   [OK] bge-m3 모델 준비됨
echo.

rem === 4. Node / 프론트엔드 ===
echo [4/6] 프론트엔드 패키지
where npm >nul 2>nul
if errorlevel 1 (
    echo   [오류] Node.js npm 미설치. nodejs.org 에서 LTS 설치 후 다시 실행.
    pause
    exit /b 1
)
if not exist "%ROOT%\frontend\node_modules" goto :npminstall
echo   [건너뜀] node_modules 이미 있음
goto :npmdone
:npminstall
pushd "%ROOT%\frontend"
call npm install
popd
echo   [완료] node_modules 설치
:npmdone
echo.

rem === 정리 ===
if exist "%TMP%" rmdir /s /q "%TMP%" 2>nul

rem === 5. 서버 기동 - 새 창 2개 ===
echo [5/6] 백엔드/프론트엔드 기동
start "AI코치 백엔드" cmd /k "cd /d %ROOT% && set EMBEDDING_PROVIDER=local && %PY% -m uvicorn backend.main:app --host 127.0.0.1 --port 8000"
start "AI코치 프론트" cmd /k "cd /d %ROOT%\frontend && npm run dev"
echo.

rem === 6. 브라우저 ===
echo [6/6] 서버 기동 대기 후 브라우저 열기
timeout /t 8 /nobreak >nul
start "" http://localhost:3000/
echo.
echo ============================================================
echo  완료! 브라우저에서 http://localhost:3000 확인
echo  첫 질문은 bge-m3 로딩으로 잠깐 걸릴 수 있습니다.
echo ============================================================
echo.
pause
endlocal
