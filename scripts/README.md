# Scheduling

## macOS (production)

1. 프로젝트를 `~/dev/daily-news` 에 두거나 `com.user.news-briefing.morning.plist`
   의 `cd "$HOME/dev/daily-news"` 경로를 환경에 맞게 수정
2. 가상환경 생성 및 의존성 설치:

   ```bash
   uv venv
   uv pip install --python .venv/bin/python -e ".[dev]"
   ```

3. `.env` 작성 (`.env.example` 복사 후 실제 키 입력)

4. 카카오 OAuth 1회 실행:

   ```bash
   ./.venv/bin/python -m news_briefing.delivery.kakao_auth
   ```

   브라우저가 뜨면 로그인 → '동의하고 계속하기' → `.kakao_tokens.json` 자동 생성 확인

5. dry-run 으로 한 번 검증:

   ```bash
   ./.venv/bin/python -m news_briefing morning --dry-run
   ```

6. plist 복사 후 로드:

   ```bash
   cp scripts/com.user.news-briefing.morning.plist ~/Library/LaunchAgents/
   launchctl load ~/Library/LaunchAgents/com.user.news-briefing.morning.plist
   launchctl list | grep news-briefing
   ```

7. mac 이 sleep 중이어도 깨어나게 (평일 05:55 wake):

   ```bash
   sudo pmset repeat wakeorpoweron MTWRF 05:55:00
   pmset -g sched
   ```

8. 즉시 실행 테스트:

   ```bash
   launchctl start com.user.news-briefing.morning
   tail -f /tmp/news-briefing.morning.out.log
   ```

### 제거

```bash
launchctl unload ~/Library/LaunchAgents/com.user.news-briefing.morning.plist
rm ~/Library/LaunchAgents/com.user.news-briefing.morning.plist
sudo pmset repeat cancel
```

## Windows (development only)

Windows 에서는 production 스케줄링을 하지 않는다 (`docs/DECISIONS.md` #5).
수동 실행만:

```powershell
.\.venv\Scripts\python.exe -m news_briefing morning --dry-run
.\.venv\Scripts\python.exe -m news_briefing status
```

정기 실행이 필요하면 작업 스케줄러로:

```powershell
$Action = New-ScheduledTaskAction `
    -Execute "C:\GitHub\daily-news\.venv\Scripts\python.exe" `
    -Argument "-m news_briefing morning" `
    -WorkingDirectory "C:\GitHub\daily-news"
$Trigger = New-ScheduledTaskTrigger -Daily -At 6am
Register-ScheduledTask -TaskName "NewsBriefingMorning" -Action $Action -Trigger $Trigger
```

(단, 이 경로는 문서화된 production path 가 아니다. mac 이관이 기본.)
