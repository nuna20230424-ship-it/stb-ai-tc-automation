"""console_data — 운영 콘솔(docs/console.html) 데이터 빌더.

catalog + InfluxDB catalog_runs + tc_selector deferred/quarantined를 머지해
docs/console-data.json 생성. console.html이 fetch로 동적 로딩.

N/T·N/A 사유는 classifier.py가 결정론 분류 — precondition 미충족 / 베이스라인 미시드 /
펌웨어 범위 밖 / flake 격리 / 시간 부족 / MCP 미가동.
"""
