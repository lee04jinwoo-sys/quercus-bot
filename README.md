# 🎓 U of T Quercus Telegram Alert Bot

토론토 대학교(U of T) Canvas LMS(**Quercus**)의 공지사항, 미제출 과제 마감, 성적 발표, 새 강의 자료를 30분 주기로 모니터링하여 **텔레그램으로 자동 발송하는 자율 알림 봇**입니다.

---

## 🚀 주요 기능

1. **📢 새 공지사항 실시간 감지**: 휴강, 게릴라 시험 공지, 강의실 변경 등 긴급 공지 즉시 전송
2. **⏰ 미제출 과제 마감 카운트다운**: `D-3`, `D-1`, `D-Day(12시간 전/마감 직전)` 미제출 과제만 자동 리마인드
3. **🎉 성적 발표 알림**: 퀴즈, 랩, 시험 채점 완료 즉시 점수 및 피드백 알림
4. **📁 새 수업 자료 등록 알림**: 강의 슬라이드, 튜토리얼 솔루션 새 파일 업로드 감지
5. **🛡️ 스마트 중복 방지**: `sent_history.json` 상태 저장소를 통해 이미 발송된 항목 재발송 차단

---

## 💻 로컬 설치 및 테스트

```bash
# 1. 의존성 설치 (uv)
uv sync

# 2. 텔레그램 연동 테스트 메시지 발송
uv run quercus-bot --test-msg

# 3. 1회 단발 검사 (초기 인덱싱)
uv run quercus-bot --once

# 4. 상시 데몬 모드 실행 (30분 주기)
uv run quercus-bot
```

---

## ☁️ 오라클 클라우드(OCI) 3단계 배포 가이드

### 1단계: OCI 인스턴스에 코드 복사 및 .env 세팅
```bash
# 서버 접속 후 디렉토리 이동
git clone <your-repo-url> quercus-bot
# 또는 scp로 전송:
# scp -r ~/Desktop/Projects/quercus-bot ubuntu@<OCI_IP>:~/quercus-bot

cd ~/quercus-bot
cp .env.example .env
nano .env   # QUERCUS_API_TOKEN, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID 확인
chmod 600 .env
```

### 2단계: uv 동기화 및 1회 테스트
```bash
uv sync
uv run quercus-bot --test-msg
uv run quercus-bot --once
```

### 3단계: systemd 서비스 등록 (24/7 상시 가동)
```bash
# 서비스 파일 복사 (User가 opc인 경우 User/경로 수정)
sudo cp quercus-bot.service /etc/systemd/system/

# 서비스 활성화 및 시작
sudo systemctl daemon-reload
sudo systemctl enable quercus-bot
sudo systemctl start quercus-bot

# 상태 및 실시간 로그 확인
sudo systemctl status quercus-bot
sudo journalctl -u quercus-bot -f
```
