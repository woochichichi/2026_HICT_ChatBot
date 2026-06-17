@echo off
setlocal enabledelayedexpansion
chcp 949 >nul
title AI 코치 - 시연 환경설정

pushd "%~dp0..\.."
set "ROOT=%CD%"
popd
set "ZIP=%ROOT%\demo_bundle.zip"
set "TMP=%ROOT%\_bundle_tmp"
set "PY=%ROOT%\.venv\Scripts\python.exe"
set "TAR=%WINDIR%\System32\tar.exe"

echo ============================================================
echo  AI 코치 - 시연 환경설정  [최초 1회 · 설치만]
echo  끝나면 3_시연_실행.bat 으로 서버를 띄웁니다.
echo ============================================================
echo  프로젝트 루트: %ROOT%
echo.

rem === 1. demo_bundle.zip 압축 해제 + 파일 배치 ===
echo [1/5] 전달받은 zip 압축 해제 및 배치
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

rem === 2. Python 확인 ===
echo [2/5] Python 확인
where python >nul 2>nul
if errorlevel 1 (
    echo   [오류] Python 미설치. python.org 에서 3.12 설치 후 다시 실행.
    pause
    exit /b 1
)
echo   [OK] Python 있음
echo.

rem === 3. 가상환경 + 패키지 ===
echo [3/5] 가상환경/패키지  - 처음만 수 분 소요
if not exist "%PY%" python -m venv "%ROOT%\.venv"
if exist "%PY%" echo   [OK] .venv 준비됨
"%PY%" -m pip install --upgrade pip >nul
echo   [설치] torch CPU 버전
"%PY%" -m pip install torch --index-url https://download.pytorch.org/whl/cpu
echo   [설치] requirements.txt
"%PY%" -m pip install -r "%ROOT%\requirements.txt"
echo.

rem === 4. bge-m3 임베딩 모델 다운로드 (최초 1회, 인터넷 필요, 약 2.2GB) ===
echo [4/5] bge-m3 모델 준비  - 최초만 다운로드, 수 분 소요
if exist "%USERPROFILE%\.cache\huggingface\hub\models--BAAI--bge-m3" goto :modeldone
echo   [다운로드] bge-m3 ... 인터넷 필요. 시연 중 끊기지 않게 지금 받아둡니다.
"%PY%" -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-m3')"
:modeldone
echo   [OK] bge-m3 모델 준비됨
echo.

rem === 5. Node / 프론트엔드 ===
echo [5/5] 프론트엔드 패키지
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

echo ============================================================
echo  환경설정 완료!
echo  시연하려면  scripts\demo\3_시연_실행.bat  을 실행하세요.
echo ============================================================
echo.
pause
endlocal
