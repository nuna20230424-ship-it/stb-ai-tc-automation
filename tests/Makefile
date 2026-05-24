.PHONY: install env health seed test report clean

PYTHON ?= python3
PIP    ?= $(PYTHON) -m pip

install:
	$(PIP) install -r requirements.txt

env:
	@test -f .env || (cp .env.example .env && echo ".env 생성됨. 값을 채워주세요.")

health:
	@echo "── Gateway ──"
	-curl -sf http://localhost:8001/health && echo
	-curl -sf http://localhost:8002/health && echo
	-curl -sf http://localhost:8003/health && echo
	-curl -sf http://localhost:8004/health && echo
	@echo "── Backend ──"
	-curl -sf $${BASELINE_MCP_URL:-http://10.0.10.50:8101}/health && echo
	-curl -sf $${EMBEDDING_MCP_URL:-http://10.0.10.50:8102}/health && echo
	-curl -sf $${DETECTION_MCP_URL:-http://10.0.10.50:8103}/health && echo
	-curl -sf $${REPORT_MCP_URL:-http://10.0.10.50:8104}/health && echo

seed:
	@test -n "$(FW)" || (echo "사용: make seed FW=v1.2.3 [ITER=10]"; exit 1)
	$(PYTHON) -m baselines.seed_channel_zap --firmware $(FW) --iterations $${ITER:-10}

preflight:
	$(PYTHON) -m pytest -m preflight

preflight-stage3:
	@echo "── 하드웨어 스모크 검증 (수동 확인 필요) ──"
	@echo "1) Capture: curl -X POST http://localhost:8001/capture -d '{\"target\":\"ref\",\"duration_sec\":1}'"
	@echo "2) IR:      curl -X POST http://localhost:8002/send -d '{\"codeset\":\"ref_remote\",\"key\":\"POWER\"}'"
	@echo "3) UART:    curl -X POST http://localhost:8003/sessions -d '{\"target\":\"ref\",\"label\":\"preflight\"}'"
	@echo "4) Power:   curl -X POST http://localhost:8004/cycle?target=dut&off_sec=3"
	@echo "5) Voice:   curl -X POST http://localhost:8005/speak -d '{\"text\":\"테스트\"}'"
	@echo "6) BT:      curl -X POST http://localhost:8006/scan -d '{\"duration_sec\":5}'"

test:
	$(PYTHON) -m pytest -m channel_zap

report:
	@open reports/report.html 2>/dev/null || xdg-open reports/report.html 2>/dev/null || echo "see reports/report.html"

clean:
	rm -rf data/frames data/captures reports __pycache__ */__pycache__
