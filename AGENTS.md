# Repository Guidelines

## 프로젝트 목적
- 포트폴리오 관리를 위해 현재 포트폴리오의 리스크를 측정하고, 매크로 상황 변화에 맞춰 다양한 팩터 노출도를 조절해 포트폴리오 비중을 조정합니다.

## 프로젝트 구조 및 모듈 구성
- `main.py`에 토큰 발급, 잔고 조회, Supabase 저장까지 전체 워크플로가 포함됩니다.
- `README.md`는 최소한의 안내만 있으며, 프로젝트 수준 메모는 여기에서 관리합니다.
- 현재 `tests/`나 `assets/` 디렉터리는 없습니다.

## 팩터 회귀 정책
- 베타 회귀는 `ret`만 사용하고 `level`은 검증/감사용으로만 둡니다.
- `factor_returns.lag_policy`를 우선 적용하고, 없으면 0(당일)으로 처리합니다.
- `method` 컬럼에 `OLS_MULTI`/`OLS_SINGLE`을 둘 다 계산해 저장합니다.
- 금리/크레딧 계열은 레벨 변화(Δy, ΔOAS)를 duration 기반 가격형 `ret`로 변환해 사용합니다. (US10Y=8.5, KR10Y=8.5, HY OAS=4.5)
- 월간 팩터(`F_INFL_KR_CPI`)는 일단 베타 계산에서 제외합니다. 재도입 시 `record_date`를 1개월 시프트한 날짜를 발표일로 간주하고, 해당 날짜에만 `ret`를 반영하며 그 외 일자는 0으로 처리합니다.
- 원시 관측일(`observed_date`)과 국내 적용일(`effective_kr_date`)을 분리해 저장합니다.
- 정규화는 별도 뷰 `view_factor_returns_zscore`에 저장합니다.
- `FACTOR_ZSCORE_WINDOW_DAYS`(.env)로 롤링 윈도우 길이를 설정합니다.
- 비영일(`ret != 0`)만으로 평균/표준편차를 계산하고, `ret=0`은 `ret_z=0`으로 둡니다.

## 멀티 vs 단일 팩터 회귀 기준
- 멀티 팩터 회귀는 다른 팩터를 통제한 순수 노출(부분효과), 단일 팩터 회귀는 공분산이 섞인 총 노출(마진효과)로 해석합니다.
- 멀티 팩터 장점: 공분산 통제, 팩터 간 중복 노출 분리, 리스크 분해/헤지 설계에 유리, 설명력 높음.
- 멀티 팩터 단점: 공선성 시 베타 불안정/해석 어려움, 직관과 다른 결과 가능, 표본 짧거나 팩터 수 많으면 추정 흔들림.
- 단일 팩터 장점: 직관적, 짧은 데이터에서도 비교적 안정적, 리포팅에 적합.
- 단일 팩터 단점: 누락 변수 편향, 공통 노출 과대/과소 추정 가능, 리스크 관리/헤지에 부정확.
- 추천: 리스크 관리/헤지/정교한 분해는 멀티, 커뮤니케이션/직관 리포팅은 단일 병행. 단일=총노출, 멀티=순수노출로 병기하면 이해가 쉬움.
- 멀티가 불안정하면 Ridge/Lasso, 팩터 축소(PCA), 최소 관측치 강화, 공선성 체크(VIF) 등을 고려합니다.

## 파일별 요약
- `main.py`: 한국투자 API 토큰/잔고 조회 → Supabase 저장 메인 워크플로
- `main_local.py`: 로컬 실행용 변형(`dotenv`, `keyring` 사용)
- `init_schema.sql`: 전체 스키마 초기화 + 테이블/뷰 생성 + RLS 해제
- `view_macro_exposure.sql`: 태그/통화 기반 매크로 노출도 뷰 생성
- `migration_factor_returns.sql`: `factor_returns` 테이블 재생성 SQL
- `update_mappings.sql`: `ticker_category_map` 시드/업데이트 SQL
- `factor_returns_loader.py`: 팩터 데이터 수집/수익률 계산 후 `factor_returns` 업서트
- `ticker_factor_beta_loader.py`: 티커 수익률 + 팩터 수익률로 베타 계산 후 업서트/리포트 생성
- `create_factor_returns_zscore_view.py`: 팩터 수익률 z-score 뷰 SQL 생성(윈도우 길이 .env)
- `view_factor_returns_zscore.sql`: z-score 뷰 생성 SQL(스크립트 출력물)
- `test_ticker.py`: yfinance 심볼 가용성 점검 + 결과 write-back/리포트 생성
- `debug_factor_presence.py`: `factor_returns` 데이터 존재/기간/결측 점검
- `inspect_schema.py`: `factor_returns` 샘플 조회로 컬럼 확인
- `apply_migration.py`: `factor_returns` 관련 SQL 실행 안내 스크립트
- `requirements.txt`: 파이썬 의존성 목록
- `beta_run_report.csv`: 베타 계산 결과 리포트(출력물)
- `yf_symbol_report_*.csv`: yfinance 심볼 점검 리포트(출력물)
- `README.md`: 최소 안내 문서
- `AGENTS.md`: 프로젝트 가이드라인/메모

## 빌드, 테스트, 개발 명령어
- `python main.py`로 전체 작업을 실행합니다(환경 변수 필요, 보안/설정 참고).
- 빌드 단계는 없으며 단일 파이썬 스크립트로 동작합니다.
- 테스트 러너는 아직 구성되어 있지 않습니다.

## 코딩 스타일 및 네이밍 규칙
- PEP 8 기준, 4칸 들여쓰기를 사용합니다.
- 함수/변수는 `snake_case`, 상수는 `UPPER_SNAKE_CASE`를 사용합니다.
- 로그는 간결하고 사용자 친화적으로 작성하고, 과도한 디버그 출력은 피합니다.

## 테스트 가이드라인
- 테스트 프레임워크는 아직 없습니다.
- 테스트를 추가한다면 `pytest`를 권장하며 `tests/`에 `test_<feature>.py` 형태로 작성합니다.
- API 오류 처리와 데이터 매핑의 엣지 케이스를 우선적으로 커버합니다.

## 커밋 및 PR 가이드라인
- 커밋 히스토리가 짧고 혼합 언어이므로, 메시지는 간결하고 명확하게 작성합니다.
- `fix: ...` 같은 관례적인 포맷은 선택 사항입니다.
- PR에는 다음을 포함하세요:
  - 변경 내용과 필요 이유에 대한 간단한 설명
  - 필요한 환경/설정 변경 사항
  - 동작 변경이 있을 경우 샘플 출력 또는 로그

## 보안 및 설정 팁
- 필수 환경 변수: `SUPABASE_URL`, `SUPABASE_KEY`, `ACCOUNTS_JSON`.
- `ACCOUNTS_JSON` 예시(계좌 객체 배열):
  ```json
  [{"name":"Broker A","acc_no":"12345678-90","app_key":"...","app_secret":"..."}]
  ```
- 비밀 정보는 커밋하지 말고 GitHub Actions 시크릿이나 로컬 환경 변수를 사용하세요.
