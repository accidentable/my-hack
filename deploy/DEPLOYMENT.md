# ComplianceLens — AWS 배포 런북 (EC2 + CloudFront)

> 목표: 프론트(Next.js) + 백엔드(FastAPI + LangGraph)를 **단일 EC2**에 Docker로 올리고,
> 그 앞에 **CloudFront**를 세워서 `https://dXXXXXX.cloudfront.net` 으로 데모용 HTTPS URL을 무료(크레딧)로 발급받는다.
> 도메인 별도 구매 불필요. AWS 크레딧 100% 적용.

## 0. 사전 준비물

- AWS 계정 + 크레딧
- 로컬에 SSH 키 1개 (없으면 EC2 콘솔에서 생성)
- 작업 PC에 git, ssh, scp(또는 git clone) 사용 가능
- OpenAI API key

---

## 1. EC2 인스턴스 생성

콘솔 → EC2 → **인스턴스 시작**

| 항목 | 값 |
|---|---|
| 이름 | `compliancelens` |
| AMI | Ubuntu Server 24.04 LTS (x86_64) |
| 인스턴스 타입 | **t3.small** (2 vCPU, 2 GiB) — Chroma + 두 컨테이너 띄울 최소선 |
| 키 페어 | 새로 생성 → `.pem` 다운로드 (Windows면 .ppk 같이) |
| 네트워크 | 기본 VPC, 퍼블릭 IP **자동 할당 ON** |
| 보안 그룹 | 새로 만들기 — 아래 인바운드 규칙 추가 |
| 스토리지 | gp3 30 GiB (모델 캐시·Chroma 여유분 포함) |

**보안 그룹 인바운드:**

| 타입 | 포트 | 소스 | 비고 |
|---|---|---|---|
| SSH | 22 | 내 IP 만 | 작업용 |
| HTTP | 80 | 0.0.0.0/0 | CloudFront origin이 여기로 들어옴 |

> HTTPS(443)는 EC2에 뚫을 필요 없음. CloudFront ↔ EC2 구간은 HTTP origin으로 가고, 클라이언트 ↔ CloudFront 구간만 HTTPS면 됨.

---

## 2. EC2 SSH 접속 + Docker 설치

```bash
# 로컬 PowerShell
ssh -i path\to\key.pem ubuntu@<EC2_PUBLIC_IP>
```

EC2 안에서:

```bash
# Docker + compose plugin
sudo apt update
sudo apt install -y docker.io docker-compose-v2 git
sudo usermod -aG docker $USER
exit  # 그룹 적용 위해 재접속
```

다시 SSH 들어가서 동작 확인:

```bash
docker version
docker compose version
```

---

## 3. 코드 배포

옵션 A — git 사용 (권장):

```bash
git clone <YOUR_REPO_URL> JB_Hack
cd JB_Hack
```

옵션 B — 로컬에서 scp (저장소 안 올렸을 때):

```bash
# 로컬 PowerShell, 프로젝트 루트에서:
scp -i path\to\key.pem -r . ubuntu@<EC2_IP>:/home/ubuntu/JB_Hack
```

---

## 4. 환경변수 설정

EC2의 `~/JB_Hack` 에서:

```bash
cp deploy/.env.example .env
nano .env   # OPENAI_API_KEY 채우기
```

---

## 5. 컨테이너 빌드 & 기동

```bash
docker compose build           # 첫 빌드 ~5분 (frontend npm + backend pip)
docker compose up -d
docker compose ps              # backend / frontend / nginx 셋 다 Up 확인
docker compose logs -f --tail=50
```

브라우저에서 `http://<EC2_PUBLIC_IP>` 접속 → 메인 페이지가 떠야 한다.
이 시점에 카드뉴스 업로드 → 단계별 로그 스트리밍까지 동작하면 EC2 쪽은 완료.

> **첫 OpenAI 호출 전에 Chroma 임베딩 인덱스가 비어있을 수 있다.**
> 컨테이너 안에서 한 번 시드:
>
> ```bash
> docker compose exec backend python -m app.knowledge.ingest_regs
> ```

---

## 6. CloudFront 배포 (HTTPS 입히기)

콘솔 → CloudFront → **배포 생성**.

### 6.1 Origin 설정

| 항목 | 값 |
|---|---|
| Origin domain | `<EC2_PUBLIC_IP>` (또는 EC2 퍼블릭 DNS `ec2-...compute.amazonaws.com`) |
| Protocol | **HTTP only** |
| HTTP port | 80 |
| Origin response timeout | **60초** (가능한 최대치) |

> **권장:** Origin domain에 IP 대신 EC2 퍼블릭 DNS 쓰기. 인스턴스 재시작으로 IP 바뀌어도 DNS가 따라가서 CloudFront 수정 안 해도 된다.

### 6.2 기본 Cache Behavior

| 항목 | 값 |
|---|---|
| Viewer protocol policy | **Redirect HTTP to HTTPS** |
| Allowed HTTP methods | `GET, HEAD, OPTIONS, PUT, POST, PATCH, DELETE` (업로드 POST 필요) |
| Cache policy | **CachingDisabled** (managed) |
| Origin request policy | **AllViewer** (managed, 모든 헤더·쿠키·쿼리 전달) |
| Compress objects | Yes |

> Cache를 끄는 이유: API는 캐싱하면 안 되고, Next.js는 이미 자체 ETag/캐시 제어를 함. SSE 스트림은 캐싱되면 영영 응답이 안 옴.

### 6.3 추가 Cache Behavior — SSE 전용 (선택이지만 권장)

Path pattern: `/api/review/*/stream`

| 항목 | 값 |
|---|---|
| Origin | 위와 동일 |
| Cache policy | CachingDisabled |
| Origin request policy | AllViewer |
| Response headers policy | (없음) |

이 behavior가 명시적으로 캐싱 회피 + chunked 통과를 보장한다.

### 6.4 배포

- Price class: **Use only North America and Europe** (한국 데모면 비용 최저)
- WAF: 일단 끔 (데모 후 고려)
- **Create distribution**

생성 후 ~5분 대기 → "Deployed" 상태가 되면 **Distribution domain name** (예: `d1a2b3c4d5e6f7.cloudfront.net`) 확인.

### 6.5 CORS / 호스트 헤더 확인 + 옵션 보강

CloudFront → EC2 origin 으로 가면 Host 헤더가 EC2 도메인으로 들어가서 Nginx가 그대로 받는다. 추가 설정 불필요.

CloudFront 도메인을 한 번 더 명시적으로 허용 리스트에 박고 싶으면 EC2 `.env`:

```bash
ALLOWED_ORIGINS=https://d1a2b3c4d5e6f7.cloudfront.net,http://localhost
```

그리고:

```bash
docker compose up -d backend   # env 재주입
```

---

## 7. 검증 체크리스트

브라우저로 `https://dXXXX.cloudfront.net` 접속해서:

- [ ] 메인 페이지 정상 로드 (좌물쇠 아이콘 → 안전)
- [ ] 카드뉴스 업로드 → POST 200, thread_id 받음
- [ ] `/review/<thread_id>` 로 이동, AgentLog 가 단계별로 채워짐 (ingest → retrieve → assess → verify → generate)
- [ ] 사람 검토 패널에서 approve/reject → 최종 리포트 마크다운 출력
- [ ] 새로고침 후 같은 URL 들어가도 snapshot으로 상태 복원

문제 생기면:

```bash
# EC2에서
docker compose logs -f backend
docker compose logs -f nginx
# CloudFront에서
콘솔 → CloudFront → Distribution → Monitoring 탭 → 4xx/5xx 추이
```

---

## 8. 데모 후 정리 (비용 누수 막기)

```bash
# 컨테이너 끄기 (EBS는 남음)
docker compose down
```

콘솔에서:
- CloudFront Distribution → **Disable** → 한참 후 **Delete**
- EC2 인스턴스 → **Stop**(다시 데모할 거면) 또는 **Terminate**(완전 종료)
- EBS 볼륨도 같이 삭제되는지 확인 (Terminate 시 기본 옵션)

---

## 부록 A — 코드 업데이트 재배포

```bash
ssh -i key.pem ubuntu@<EC2_IP>
cd JB_Hack
git pull          # 또는 scp로 덮어쓰기
docker compose build
docker compose up -d
```

CloudFront는 캐싱을 껐기 때문에 별도 invalidation 불필요. 그래도 정적 청크가 한 번씩 박혀 보이면:

```
CloudFront → Distribution → Invalidations → Create
Paths: /*
```

## 부록 B — 알아두면 좋은 함정

1. **CloudFront origin 타임아웃 60초.** SSE 첫 응답(`event: start`)을 백엔드가 즉시 발사해서 통과. `runner()`가 이미 그렇게 짜여 있음 (`backend/app/api/review.py:228`).
2. **EC2 stop → 퍼블릭 IP 바뀜.** Elastic IP 할당하거나 CloudFront origin을 퍼블릭 DNS로 잡아라.
3. **t3.small에서 빌드가 OOM 나면** 빌드는 로컬에서 하고 `docker save | scp | docker load` 또는 ECR push/pull로 우회.
4. **Chroma 시드를 안 하면** retrieve 단계에서 결과 0건. 6번 단계 끝의 ingest_regs 한 번 잊지 말 것.
5. **OpenAI 모델명 (`gpt-5.4`)** — `.env.example` 기본값이 그대로 있는지 확인. 실제 사용 가능한 모델로 교체 필요할 수도 있음.
