@echo off
setlocal enabledelayedexpansion
chcp 949 >nul
title AI 코치 - 시연 번들 내보내기

rem 이 bat은 scripts\demo\ 안에 있음. 상위 2단계가 프로젝트 루트.
pushd "%~dp0..\.."
set "ROOT=%CD%"
popd
set "BUNDLE=%ROOT%\demo_bundle"
set "ZIP=%ROOT%\demo_bundle.zip"
set "TAR=%WINDIR%\System32\tar.exe"

echo ============================================================
echo  AI 코치 - 시연 번들 내보내기
echo  소스 PC에서 실행. demo_bundle.zip 한 파일을 USB로 옮기세요.
echo ============================================================
echo.
echo  프로젝트 루트: %ROOT%
echo.

if exist "%TAR%" goto :tarok
echo   [오류] Windows tar 를 찾을 수 없습니다: %TAR%
echo          Windows 10 1809 이상이 필요합니다.
pause
exit /b 1
:tarok

rem === staging 폴더 정리 ===
if exist "%BUNDLE%" rmdir /s /q "%BUNDLE%"
mkdir "%BUNDLE%"

rem === 1. ChromaDB 복사 - 필수 ===
echo [1/4] ChromaDB 수집...
if not exist "%ROOT%\data\chroma_db\chroma.sqlite3" echo   [경고] ChromaDB가 비어있음. 인제스트 먼저 하세요.
robocopy "%ROOT%\data\chroma_db" "%BUNDLE%\data\chroma_db" /E /NFL /NDL /NJH /NJS /NC /NS /NP >nul
echo   [완료] data\chroma_db
echo.

rem === 2. .env 복사 - API 키 포함, 취급 주의 ===
echo [2/4] .env 수집...
if exist "%ROOT%\.env" copy /y "%ROOT%\.env" "%BUNDLE%\.env" >nul
if exist "%BUNDLE%\.env" echo   [완료] .env  - 주의: API 키 포함, 외부 유출 금지
if not exist "%ROOT%\.env" echo   [건너뜀] .env 없음
echo.

rem === 3. meta.db - 재인제스트용, 선택 ===
echo [3/4] meta.db 수집...
if exist "%ROOT%\data\meta.db" copy /y "%ROOT%\data\meta.db" "%BUNDLE%\data\meta.db" >nul
if exist "%BUNDLE%\data\meta.db" echo   [완료] data\meta.db
if not exist "%ROOT%\data\meta.db" echo   [건너뜀] meta.db 없음
echo.

rem === 4. bge-m3 모델 캐시 - 폐쇄망/인터넷 없는 PC용, 약 2.2GB ===
echo [4/4] bge-m3 모델 캐시 포함 여부
echo   시연 PC에 인터넷이 없으면 Y  [약 2.2GB, 시간 걸림]
echo   인터넷이 되면 N  [첫 실행 시 자동 다운로드]
set "INCMODEL=N"
set /p "INCMODEL=  포함할까요? Y/N [기본 N]: "
if /i not "!INCMODEL!"=="Y" goto :skipmodel
set "HFHUB=%USERPROFILE%\.cache\huggingface\hub\models--BAAI--bge-m3"
if not exist "!HFHUB!" goto :nomodel
echo   [수집] bge-m3 모델 캐시... 잠시만 기다리세요
robocopy "!HFHUB!" "%BUNDLE%\hf_cache\hub\models--BAAI--bge-m3" /E /NFL /NDL /NJH /NJS /NC /NS /NP >nul
echo   [완료] hf_cache\hub\models--BAAI--bge-m3
goto :skipmodel
:nomodel
echo   [경고] 모델 캐시 없음: !HFHUB!
:skipmodel
echo.

rem === 안내문 생성 ===
set "RM=%BUNDLE%\READ_ME_먼저.txt"
>"%RM%" echo [AI 코치 시연 번들]
>>"%RM%" echo.
>>"%RM%" echo 1. 시연 PC에서 git pull 로 소스를 최신화
>>"%RM%" echo 2. demo_bundle.zip 을 프로젝트 루트에 복사
>>"%RM%" echo 3. scripts\demo\2_시연_설치_및_실행.bat 더블클릭
>>"%RM%" echo 4. 브라우저가 열리면 시연 시작

rem === zip 압축 + staging 삭제 ===
echo [압축] demo_bundle.zip 생성 중... 모델 포함 시 수 분 소요
if exist "%ZIP%" del /q "%ZIP%"
"%TAR%" -a -c -f "%ZIP%" -C "%BUNDLE%" .
if not exist "%ZIP%" (
    echo   [오류] zip 생성 실패
    pause
    exit /b 1
)
rmdir /s /q "%BUNDLE%"
echo.
echo ============================================================
echo  완료! 아래 zip 한 파일을 USB 등으로 시연 PC에 옮기세요:
echo    %ZIP%
echo ============================================================
echo.
pause
endlocal
