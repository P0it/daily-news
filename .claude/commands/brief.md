---
description: 오늘자 아침 브리핑을 알림 없이 생성·배포 (조용한 재배포)
---

오늘자 아침 브리핑을 Discord 알림 없이 생성하고 배포한다.

다음 명령을 실행한다:

```bash
dotenvx run -- python -m news_briefing morning --no-notify
```

- `--no-notify`: 브리핑 생성 + Vercel 배포만 수행하고 Discord 알림은 보내지 않는다.
- 실행 시간이 수 분 걸릴 수 있으므로 백그라운드로 실행하고 완료 후 결과(생성된 브리핑 요약, 배포 여부, 에러 로그)를 보고한다.
- 실패한 수집기가 있으면 로그에서 찾아 함께 보고한다.
