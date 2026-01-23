import json

import httpx
import ollama
from fastapi import FastAPI, Request
from fastapi import HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from redis.asyncio import Redis  # redis-py의 async 클라이언트


# 응답을 JSON으로 해주는 부품(class)을 만들자.
# BaseModel의 모든 변수 + 함수를 다 가지고 와서 확장해라.(상속)
# Taxi(Car) : Car가 가지고 있는 모든 변수+함수를 다 가지고 와서 확장해라.
# Truck(Car)

class HealthResponse(BaseModel):
    status : str
    ollama_status : str
    message : str

app = FastAPI()

# Redis 설정 (로컬 개발 기준, 프로덕션에서는 환경변수로 관리)
REDIS_URL = "redis://localhost:6379"
# 앱 상태에 Redis 클라이언트 저장
app.state.redis = None  # 아직 연결안됨. fastapi 시작할 때 redis도 연결해두려고 함.

# Static 파일 설정 (CSS, JS, 이미지 등)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates 설정
templates = Jinja2Templates(directory="templates")

# Ollama 기본 설정
OLLAMA_BASE_URL = "http://localhost:11434"  # Ollama 기본 포트

# 사용할 모델 이름 (미리 ollama pull <model>로 다운로드 필요, 예: ollama pull llama3.2)
MODEL = "gemma3:1b"


@app.get("/health")
async def health_check():
    """FastAPI와 Ollama의 health 상태를 확인하는 엔드포인트"""
    try:
        # Ollama health check
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5.0)

        if response.status_code == 200:
            ollama_status = "healthy"
            message = "fastapi & ollama 제대로 동작중"
        else:
            ollama_status = "unhealthy"
            message = f"Ollama returned status code: {response.status_code}"

    except httpx.ConnectError:
        ollama_status = "연결불가"
        message = "Ollama 연결할 수 없음."
    except httpx.TimeoutException:
        ollama_status = "타임아웃"
        message = "Ollama 타임 아웃"
    except Exception as e:
        ollama_status = "error"
        message = f"Error checking Ollama: {str(e)}"

    return HealthResponse(
        status = "ok",
        ollama_status = ollama_status,
        message = message
    )


# 앱 시작 시 모델 미리 로드 (preload)
@app.on_event("startup")
async def preload_model():
    try:
        # 빈 프롬프트로 모델 로드 + 영구 유지
        await ollama.AsyncClient().generate(
            model=MODEL,
            prompt=" ",  # 빈 프롬프트 (또는 "preload" 같은 더미 텍스트)
            keep_alive=-1  # -1: 영구적으로 메모리에 유지
        )
        print(f"{MODEL} 모델이 미리 로드되었습니다. (메모리에 영구 유지)")

        app.state.redis = Redis.from_url(url=REDIS_URL, decode_responses=True)
        # decode_responses=True --> 바이트스트림으로 도착한 데이터 utf-8로 자동으로 변환

        print(f"{REDIS_URL}로 Redis서버 미리 연결됨.")

    except Exception as e:
        print(f"모델 preload 실패 또는 Redis연결 실패 : {e}")

# fastapi 서버가 종료(재부팅) 되었을 때 자동 호출됨.
@app.on_event("shutdown")
async def shutdown_event():
    if app.state.redis:
        await app.state.redis.close()
        print("redis 연결 종료됨....")


@app.get("/")
def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


"""
# 일반 generate 엔드포인트 (스트리밍 없이 전체 응답)
@app.get("/chat")
async def generate(word : str, request : Request):
    try:
        response = await ollama.AsyncClient().generate(
            model=MODEL,
            prompt=word,
            options={"temperature": 1},
            keep_alive=-1  # 필요 시 후속 요청에서도 유지
        )
        return templates.TemplateResponse("chat.html",
                                      context={"request": request,
                                               "result" : response["response"]
                                               })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
"""
# 기존 /chat 엔드포인트 수정
########## redis 연결 후
class ChatRequest(BaseModel):
    message : str
    session_id : str = "default"    # 로그인한 아이디
    # redis에 키를 chat_history:로그인id로 만들어줄 예정.
    # id가 apple인 경우 키는 chat_history:apple
    # id가 default인 경우 키는 chat_history:default
    # chat_history:apple, chat_history:default는 키이므로 unique 해야함.

@app.post("/chat")
async def chat(request : ChatRequest):
    print(f"서버로 전달된 값은 {request.message}, {request.session_id}")
    history = []
    # prompt를 user_message에 만들자.
    user_message = f"채팅중임. '{request.message}'를 읽고 적당히 답장해줘."
    # ollama.AsyncClient().chat() 쓸때는
    # - 내가 쓴 것은 role:user가 되어야만 함.
    # - 응답받은 것은 role:assistant가 됨.
    # ollama에게 질문을 줄 때는 [{}]로 주어야함.

    history.append({"role": "user", "content": request.message})
    print(user_message)

    # ollama연결해서 응답받고, 리턴
    response = await ollama.AsyncClient().chat(
        model=MODEL,
        messages=history,
        keep_alive=-1
    )
    print("-------------------------")
    print(response)  # dict

    # 올라마의 결과는 dict로 온다.
    # response변수에 저장함. --> {message : {content : 응답내용}}
    ai_message = response["message"]["content"]
    history.append({"role": "assistant", "content": ai_message})

    print("chat_histories >>", history)

    ## redis에 넣자.!
    session_key = "chat_history:" + request.session_id
    # history가 있으면 넣자.!!
    redis = app.state.redis

    if history:
        # redis에는 json으로 넣어주어야한다.
        # 우리는 dict를 가지고 있다. --> json으로 바꾸어주어야함.
        # json.dumps(dict)
        await redis.rpush(session_key, *[json.dumps(one) for one in history])

    return {"response" : response['message']['content']}


@app.get("/chat-history/{session_id}")
async def chat_history(session_id : str):

    # 1. redis가 연결이 안되어있으면 500번 에러
    redis = app.state.redis
    if not redis : # redis가 None이면
        raise HTTPException(status_code=500, detail="Redis 연결 안됨.")
        # http응답을 보내버림(code, detail을 http 헤더에 넣어서 브라우저에 응답함.)
        # http 만들어서 응답하고 끝!

    # 2. redis가 연결이 되어있으면
    session_key = 'chat_history:' + session_id

    #   redis.lrange() 리스트를 불러오자.
    history_json = await redis.lrange(session_key, 0, -1)
    print("-------------------------")
    print(history_json)     ## [ '{}', '{}', ... ] ==> [{}, {}, {}, ...]
    # for문 돌려서 '{}' 이렇게 생긴 string을 빼서 json으로 바꿔서,
    # json의 리스트로 만들어주어야함.
    history = [json.loads(msg) for msg in history_json]
    # [{}, {}, {}, ...]
    print("********************")
    print(history)

    return {"history" : history}



# 스트리밍 엔드포인트 (실시간 토큰 반환, 더 빠른 체감)
from fastapi.responses import StreamingResponse

@app.get("/stream")
async def stream(word : str):
    return StreamingResponse(stream_generate(word), media_type="text/event-stream")

async def stream_generate(prompt: str):
    stream = await ollama.AsyncClient().generate(
        model=MODEL,
        prompt=prompt,
        stream=True,
        keep_alive=-1
    )
    async for part in stream:
        # "이 값을 내보내고, 여기서 잠깐 멈춰. 다음에 다시 불러주면 이어서 할게!"
        # ollama로 부터 받은 조각마다 보내..
        yield part["response"]  # return은 한번 보내고 끝. yield는 오는대로 전달

@app.get("/ollama-test")
def ollama_test(request : Request):
    return templates.TemplateResponse("ollama-test.html", context={"request": request})


## 파라미터 전달용 class를 만들자.
## 파라미터 이름 똑같은거 자동으로 변수에 들어감.
## 다른 옵션값들 설정 가능
## BaseModel이라는 클래스를 상속받아서 만들어야 자동으로 이런 처리들을 해줌.

class SummarizeRequest(BaseModel):
    ## BaseModel(변수+함수) + 내가 추가한 변수
    text : str
    max_length : int = 200


@app.post("/summarize")
async def summarize(request : SummarizeRequest):
    # http://localhost:11434/api/generate, json=payload
    # post방식으로 http요청을 해줌.
    prompt = f"{request.text}를 {request.max_length}자로 요약해주세요."
    print(prompt)
    response = await ollama.AsyncClient().generate(
        model = MODEL,
        prompt = prompt,
        keep_alive = -1
    )
    print("-------------------------")
    print(response) # dict
    return {'summary' : response["response"].strip()}


class TranslateRequest(BaseModel):
    text : str

@app.post("/translate")
async def translate(request : TranslateRequest):
    prompt = f"{request.text}를 한국어로 자연스럽게 번역해주고, 번역본만 출력해줘."
    print(prompt)
    response = await ollama.AsyncClient().generate(
        model = MODEL,
        prompt = prompt,
        keep_alive = -1
    )
    print("--------------------------")
    print(response)
    return {"translation" : response["response"].strip()}


class SentimentRequest(BaseModel):
    text : str

@app.post("/sentiment")
async def sentiment(request : SentimentRequest):
    prompt = f"{request.text}를 감정 분석해주고, 답변은 반드시 '긍정', '부정', '중립' 셋 중 하나만 출력해줘."
    print(prompt)
    response = await ollama.AsyncClient().generate(
        model=MODEL,
        prompt=prompt,
        keep_alive=-1
    )
    print("--------------------------")
    print(response)
    return {"sentiment": response["response"].strip()}


class BrainstormRequest(BaseModel):
    topic : str
    count : int

@app.post("/brainstorm")
async def brainstorm(request : BrainstormRequest):
    prompt = f"""
    '{request.topic}'에 대해 창의적이고 실현 가능한 아이디어를 {request.count}개 제안해줘.
    각 아이디어는 번호를 붙이고 한 문장으로 간단히 설명해줘.
    """
    print(prompt)
    response = await ollama.AsyncClient().generate(
        model=MODEL,
        prompt=prompt,
        keep_alive=-1
    )
    print("--------------------------")
    print(response)
    return {"ideas": response["response"].strip()}


class PoemRequest(BaseModel):
    topic: str
    style: str

@app.post("/poem")
async def poem(request: PoemRequest):
    prompt = f"""
    '{request.topic}' 주제에 맞게 한국어로 근사한 시 한 편 지어줘.
    스타일은 {request.style}로 부탁해. 감성적이고 운율이 살아있게 해줘.
    제목도 같이 붙여줘.
    """
    print(prompt)
    response = await ollama.AsyncClient().generate(
        model=MODEL,
        prompt=prompt,
        keep_alive=-1
    )
    print("--------------------------")
    print(response)
    return {"poem": response["response"].strip()}


class RecipeRequest(BaseModel):
    ingredients : str
    servings : int
    difficulty : str

@app.post("/recipe")
async def recipe(request : RecipeRequest):
    prompt = f"""
    다음 재료를 사용해서 {request.servings}인분 요리를 만들어줘.
    난이도는 '{request.difficulty}' 수준으로, 단계별로 자세히 설명해줘.
    재료: {request.ingredients}
    요리 이름도 알려주고, 필요한 추가 재료(조미료 등)는 최소한으로 제안해줘.
    """
    print(prompt)
    response = await ollama.AsyncClient().generate(
        model=MODEL,
        prompt=prompt,
        keep_alive=-1
    )
    print("--------------------------")
    print(response)
    return {"recipe": response["response"].strip()}


class NameRequest(BaseModel):
    # axios.post로 전달될 때 키와 이름이 같아야 한다.
    # {category : "아기", gender : "여성", ....}
    category : str = "카페"
    gender : str = "중성"
    count : int = 5     # 최신 문법
    vibe : str = "따듯한"

@app.post("/names")
async def names(request : NameRequest):
    prompt = f"""{request.category}이름을 
                 {request.gender}, {request.vibe}느낌으로 
                 {request.count}개만 추천해줘."
                 
            결과 화면은 다음과 같이 만들어줘.
            
            1. 이름 - 간단설명
            2. 이름 - 간단설명
            3. 이름 - 간단설명
            """
    print(prompt)
    response = await ollama.AsyncClient().generate(
        model=MODEL,
        prompt=prompt,
        keep_alive=-1
    )

    print("------------------------")
    print(response) # dict
    return {'names': response["response"].strip()}

# if __name__ == '__main__':
#     uvicorn.run("app.main:app", host='127.0.0.1', port=8000, reload=True)