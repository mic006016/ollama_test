## Local LLM & RAG API Server 🚀

FastAPI, Ollama, ChromaDB를 활용하여 구축한 **로컬 LLM 기반 비동기 API 서버 및 RAG(검색증강생성) 파이프라인**입니다. 외부 API 의존 없이 로컬 환경에서 안전하고 빠르게 동작하며, Redis를 활용한 세션 관리와 문서 기반 질의응답 기능을 제공합니다.

### 🛠 Tech Stack

- **Backend Framework:** `FastAPI`, `Uvicorn`
- **LLM Engine:** `Ollama` (`gemma3:1b`, `nomic-embed-text`)
- **Vector Database:** `ChromaDB`
- **In-Memory Store:** `Redis` (Session / Chat History Management)
- **HTTP Client:** `httpx` (Async), `requests` (Sync)

### ✨ Key Features

1. **로컬 LLM 연동 및 비동기 추론 서버 구축 (`main.py`)**
   - FastAPI를 활용한 비동기(Async) API 엔드포인트 설계
   - Ollama API와 연동하여 텍스트 생성, 요약, 번역, 감성 분석 등 다양한 자연어 처리 기능 제공
   - Server-Sent Events(SSE)를 활용한 실시간 스트리밍 응답 (`/stream`) 지원
   - 앱 기동 시 모델을 메모리에 영구 적재(Preload)하여 추론 지연 시간 최소화

2. **Redis 기반 대화 세션 관리 (`main.py`)**
   - 사용자 Session ID를 기준으로 대화 기록(Chat History)을 Redis에 캐싱
   - 문맥을 유지하는 멀티턴(Multi-turn) 챗봇 인터페이스 구현

3. **ChromaDB 기반 RAG 파이프라인 (`chroma_db.py`)**
   - 대용량 텍스트 문서의 Chunking 및 Embedding (`nomic-embed-text` 모델 활용)
   - ChromaDB를 활용한 벡터 적재(Ingest) 및 유사도 기반 문서 검색
   - 검색된 문서를 컨텍스트로 활용하여 할루시네이션(Hallucination)이 최소화된 답변 생성

### 🏗 System Architecture

1. **Client Request:** 클라이언트가 FastAPI 엔드포인트로 JSON 데이터 전송
2. **Session Context:** Redis에서 사용자의 이전 대화 기록을 조회하여 프롬프트 구성
3. **Retrieval (RAG):** RAG 모듈 호출 시, 입력된 텍스트를 임베딩하고 ChromaDB에서 관련 문서를 추출
4. **LLM Generation:** 구성된 프롬프트와 컨텍스트를 로컬 Ollama 서버로 전달하여 답변 생성
5. **Response:** 결과를 Client에게 반환 (동기/비동기 스트리밍 지원) 및 Redis에 대화 내역 업데이트
