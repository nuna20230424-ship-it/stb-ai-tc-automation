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

test:
	$(PYTHON) -m pytest -m channel_zap

report:
	@open reports/report.html 2>/dev/null || xdg-open reports/report.html 2>/dev/null || echo "see reports/report.html"

clean:
	rm -rf data/frames data/captures reports __pycache__ */__pycache__
