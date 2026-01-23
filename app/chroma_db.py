# chroma_db.py
from __future__ import annotations

import uuid
from typing import List, Optional, Dict, Any

import requests
import chromadb

import fitz  # PyMuPDF

class ChromaRAG:
####################
# 1. 설정부분
    # ollama 설정
    # 올라마 url : http://localhost:11434,
    # 임베딩 모델 : nomic-embed-text
    # 생성형 모델 : llama3:1b, gemma3:1b

    def __init__(self,
                 chroma_dir : str = './chroma_data',
                 collection_name : str = 'rag_docs',
                 ollama_base_url : str = 'http://localhost:11434',
                 embed_model : str = 'nomic-embed-text',
                 gen_model : str = 'gemma3:1b'):

        # Ollama 설정
        self.ollama_base_url = ollama_base_url
        self.embed_model = embed_model
        self.gen_model = gen_model

        # chroma 설정
        # 폴더 만든 것에 chroma db연결함.
        # --> chroma_data
        # collection(table, 폴더)를 생성함.
        # --> rag_docs
        self.client = chromadb.PersistentClient(path=chroma_dir)
        self.collection = self.client.get_or_create_collection(name=collection_name)    # rag_docs
        self.collection2 = self.client.get_or_create_collection(name=collection_name + str(2))   # rag_docs2

    def __str__(self):
        return str(self.client) + " " + self.embed_model + " " + self.gen_model + " " + str(self.collection) + " " + str(self.collection2)

####################
# 2. 임베딩하고 ollama 요청해서 답변 받아오는 부분
    # 임베딩 embed
    def embed(self, text : str) -> List[float]: # 리턴타입!!
        # ollama에 주소로 임베딩해달라고 요청합시다.
        url = self.ollama_base_url + '/api/embeddings'
        resp = requests.post(url, json={'model':self.embed_model, 'prompt':text}, timeout=120)
        print(resp.json())  # dict형태로 만들어서 프린트.
        data = resp.json()  # {"embedding" : [0.1232, 0.234324]}
        return data['embedding']

    # 답생성 generate
    def generate(self, prompt : str) -> str:
        url = self.ollama_base_url + '/api/generate'
        payload = {
            "model": self.gen_model,  # gemma3:1b
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.0, # 네가 찾은것 중에서 아주 정확한 것만!!
                "num_predict": 64,  # 짧게, 한글은 한 글자에 2바이트임, 30글자 정도, 문장2-3개
                # 환경에 따라 지원되는 옵션이 다를 수 있음
                # "repeat_penalty": 1.1,
            }
        }
        r = requests.post(url, json=payload, timeout=120)
        print(r.json())
        data = r.json()
        return data['response']

####################
# 3. chuck만드는 부분
    # 통으로 읽은 text를 작게 자르자.(chunk, 조각)
    def chunk_text(text: str, max_chars: int = 1200, overlap_chars: int = 150) -> List[str]:
        text = (text or "").strip()
        if not text:
            return []

        chunks = []
        start = 0
        n = len(text)

        while start < n:
            end = min(start + max_chars, n)
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            if end == n:
                break

            start = max(0, end - overlap_chars)

        return chunks
    # pdf를 읽어서 text로 만들자.

    # collection에 몇 개 들어있는지 확인하는 함수
    def count(self) -> int:
        return self.collection.count()

    def get_collection(self):
        results = self.collection.get(include=["documents", "metadatas"], limit=10)
        return results

####################
# 4. 크로마 db에 적재하는 부분
    # 텍스트를 크로마db 에 적재하자.(ingest)
    def ingest_texts(self, texts: List[str], source: str="manual") -> int:
        if not texts:
            return 0

        for i, t in enumerate(texts):
            self.collection.add(
                ids=[str(uuid.uuid4())],
                documents=[t],
                embeddings=[self.embed(t)],
                metadatas=[{"chunk": i, "source": source}],
            )
        return len(texts)

####################
# 5. 질문하고 답변 만들어오는 부분
    # 질의하고 답변을 만드는 것과 관련된 함수 정의.

import os
from glob import glob

if __name__ == '__main__':
    # rag = ChromaRAG()   # def __init__() 호출됨.
    # # print(rag)  # def __str__() 호출됨.
    # # rag.embed(text='hello')
    # # rag.embed(text='world')
    # # print(rag.generate(prompt="저녁 뭐먹냐"))
    # # print(rag.generate(prompt="한식"))
    # text = "전 웹툰작가 겸 크리에이터 침착맨이 생일을 맞아 1,000만 원을 기부했다. 12월 26일 사랑의열매 사회복지공동모금회는 침착맨이 ‘침착맨과 침투부 전문시청팀’ 이름으로 1,000만 원을 기부, 연말연시 집중모금캠페인 ‘희망2026나눔캠페인’에 동참했다고 전했다. 이번 기부는 침착맨의 생일(12월 5일)을 기념해 진행됐다. 침착맨은 “생일을 맞아 침투부를 함께 만들어가는 시청자들과 의미 있는 일을 해보고 싶었다”라며 “이 마음이 도움이 필요한 분들께 전해졌으면 한다”라고 기부 이유를 밝혔다. 이말년이라는 이름으로 웹툰 작가로 활동한 침착맨은 총 4개 채널을 운영하는 크리에이터로, 본 채널 구독자 수는 304만 명에 달하며, 대중적 영향력을 바탕으로 새로운 콘텐츠 활동과 함께 사회공헌에도 꾸준히 참여하고 있다."
    #
    # result = ChromaRAG.chunk_text(text)
    # print(result)

# # embedding test
#     result2 = rag.embed(text=result[0])
#     print(result2)
#
# # gemma3:1b test
#     print(rag.generate(prompt=text))

# # chunk한거 chromadb에 적재
#     result3 = rag.ingest_texts(result)
#     print(result3)
#
# # 적재한거 몇개인지 test
#     print(rag.count())
#     print(rag.get_collection())

    """
    연예기사 3개를 크로마db의 컬렉션인 rag_docs에 집어 넣음.
    
    rag-docs에 있는 documents, metadatas를 출력
    
    text --> chunk --> embedding --> chroma db --> 검색
    """
    text1 = "영화 '아바타: 불과 재'(이하 '아바타 3')가 300만 관객을 돌파한 가운데 이번 주말에도 1위 자리를 지킬 것으로 보인다. 26일 영화관입장권 통합전산망에 따르면 크리스마스인 전날 '아바타 3'는 64만여 명(매출액 점유율 50.6%)이 관람하며 국내 박스오피스 1위를 기록했다. 지난 17일 개봉 이후 줄곧 1위를 유지한 '아바타 3'의 누적 관객 수는 이날 오전 7시 기준 313만 8천여 명이다. 디즈니 애니메이션 '주토피아 2'는 '아바타 3' 개봉 이후 박스오피스 순위는 2위로 밀려났지만 꾸준하게 관객몰이하고 있다. '주토피아 2'는 전날 43만1천여 명의 관객을 모으며 누적 관객 수 703만명을 기록했다. 이 영화는 올해 국내 개봉작 가운데 처음으로 600만 관객을 돌파한 데 이어 700만 고지도 넘었다. 동명 일본 소설을 원작으로 한 영화 '오늘 밤, 세계에서 이 사랑이 사라진다 해도'(이하 '오세이사')는 3위를 차지했다. 전날 11만5천여명(매출액 점유율 8.0%)이 관람했다. 애니메이션을 영화화한 '극장판 짱구는 못말려: 초화려! 작열하는 떡잎마을 댄서즈'와 '뽀로로 극장판 스위트캐슬 대모험'은 각각 4위(11만3천여명)와 5위(2만8천여명)를 차지했다. 이날 오전 9시 기준 예매율은 '아바타 3'가 61.9%로 압도적인 1위를 지키고 있다. 51만9천여명이 관람을 기다리고 있다. '주토피아 2'는 예매율 12.0%(예매 관객 10만1천여명)로 2위를 차지했고, 한국 멜로영화 '오세이사'와 '만약에 우리'는 각각 예매율 3·4위를 기록했다."
    text2 = "최근 공개된 유튜브 채널 뜬뜬의 ‘제3회 핑계고 시상식’이 일반적인 연말 시상식의 관성에서 비켜섰다는 평가다. 연말 시상식의 화려한 무대 대신 사람의 이야기를 택했다. 결과는 단순했다. 웃음이 먼저였다. 감동은 뒤따라왔다. 공개 3일 만에 조회수 800만 회를 넘겼다. ‘핑계고 시상식’의 공기는 축제라기보다 모임에 가까웠다. 배우와 방송인, 가수와 제작진이 한 테이블에 섞여 앉았다. 서로의 근황을 묻고, 지난 회차의 뒷이야기를 꺼냈다. 카메라는 현장의 온도를 그대로 옮겨 담았다. 사회를 맡은 유재석의 진행은 절제돼 있었다. 웃음을 밀어붙이지도 않았다. 순간의 침묵도 서사로 남겼다. 시상식이 ‘보여주는 행사’가 아니라 ‘함께 나누는 시간’이 될 수 있음을 증명한 대목이다. 대상의 순간은 ‘핑계고 시상식’만의 색깔을 또렷하게 했다. 트로피의 주인공은 지석진이었다. 온라인 투표로 모인 9만여 표 중 과반이 그의 이름을 택했다. 수상 소감은 간결하면서도 분명했다. 오래 버텼다는 고백, 그리고 함께 견뎌준 동료들에 대한 감사였다. ‘첫 대상’이라는 수식어보다, 그가 지나온 시간이 자연스럽게 무대 위에 놓였다. ‘핑계고 시상식’의 울림은 부재를 품으면서 더 깊어졌다. 대상 후보에 올랐지만 참석하지 못한 조세호의 이름이 호명됐을 때, 유재석은 짧게 박수를 청했다. 설명은 없었다. 그러나 그 배려는 충분했다. 시상식은 성취를 축하하는 자리이면서, 서로의 시간을 존중하는 공간임을 분명히 했다. 이어 송은이가 건넨 위로의 말과 눈빛은 최근의 소란을 지나온 동료에게 보내는 사적인 연대였다. 과장 없는 위로가 오히려 오래 남았다. 구성도 눈에 띄었다. 불필요한 부문을 늘리지 않았다. 전문 심사와 네티즌 투표라는 두 축을 분명히 세웠다. ‘참석상’은 없었다. 축하 무대 역시 이벤트가 아니라 하나 되는 순간이었다. 황정민의 시상은 권위를 빌리지 않았고, 이효리의 수상 소감은 연말의 감정선을 과장 없이 다뤘다. 웃음은 자연스럽게 터졌고, 감동은 천천히 번졌다. 매년 반복되는 지상파 시상식과의 비교는 불가피하다. ‘핑계고’는 작았지만 정확했다. 규모를 줄이는 대신 맥락을 키웠고, 트로피의 수를 덜어내는 대신 이야기의 밀도를 높였다. 마지막 인사는 과장 없이 정리됐다. 유재석은 지난 한 해가 쉽지 않았음을 인정하면서도 무탈을 바랐고, 다음을 이어가겠다는 최소한의 약속만 남겼다. 화려한 수식이나 감정의 과잉은 없었다. ‘핑계고’ 시상식은 규모나 형식보다 태도가 성패를 가른다는 점을 분명히 했다. 과하지 않았기에 오래 남는다는 사실을, 차분히 증명했다."
    text3 = "OTT를 통해 확산된 K-콘텐츠가 이제 단순한 시청 경험을 넘어, 글로벌 공동체와 생활 양식을 형성하는 문화로 진화하고 있다. 글로벌 스트리밍 플랫폼 넷플릭스는 23일 서울 성수 앤더슨씨에서 ‘넷플릭스 인사이트’ 행사를 열고, K-콘텐츠가 만들어낸 글로벌 문화 지형의 변화를 짚었다. 홍익대학교 건축도시대학 교수는 이날 ‘경계 없는 OTT 시대, 건축·도시학적 관점에서 OTT는 한국을 어떻게 바꿨나’를 주제로 강연을 진행했다. 유 교수는 공간을 단순한 물리적 장소가 아닌, 인간의 인식과 시선이 만들어내는 결과로 정의했다. 그는 “고대 그리스에서는 약 1만 2000명이 극장에 모여 연극을 보며 공통의 감정 상태를 형성했고, 그 경험이 공동체를 만들었다”며 “현대 사회에서는 TV가 그 역할을 했고, 지금은 스마트폰과 넷플릭스 같은 OTT가 이를 대체하고 있다”고 말했다. 이어 “‘오징어 게임’, ‘케이팝 데몬 헌터스’ 같은 한국 콘텐츠가 넷플릭스를 통해 전 세계에 동시에 소비되면서, 우리는 국경을 넘어 전 세계인과 공통의 감정과 대화를 공유하게 됐다”며 “이 플랫폼들이 글로벌 공동체를 연결하는 매개체로 작동하고 있다”고 분석했다. 유 교수는 ‘시선이 모이는 공간이 힘을 가진다’는 원리를 들어 K-콘텐츠의 영향력을 설명했다. 그는 “과거에는 계단식 건축물 꼭대기에 선 제사장이 수천 명의 시선을 받으며 권력을 가졌듯, 현대 사회에서도 미디어를 통해 시선이 집중되는 대상이 힘을 갖는다”며 “한국 콘텐츠 속 배경으로 등장하는 대한민국의 일상 공간에 전 세계 수억 명의 시선이 모이면서, 한국은 ‘힙한 공간’, 선망의 공간으로 인식되고 있다”고 했다. 또한 그는 과거 도자기 무역이 문화를 확산시킨 역사적 사례를 언급하며 “과거에는 도자기에 그려진 그림이 타국의 정원과 예술 양식에 영향을 미쳤다면, 지금은 넷플릭스를 통해 드라마 속 공간과 생활 방식이 실시간으로 전 세계에 전달된다”며 OTT를 현대판 문화 전파 장치로 비유했다. 유 교수는 한국 사회가 겪어온 ‘공간의 혁명’에도 주목했다. 그는 아파트를 통한 도시화, 초고속 인터넷망 구축으로 형성된 가상 공간을 잇는 흐름 속에서 “한국은 기술 혁명을 통해 누구보다 빠르게 새로운 공간을 활용해 왔고, 이 기반 위에서 K-콘텐츠가 글로벌 영향력을 갖게 됐다”고 진단했다. 마지막으로 그는 “오늘날 전 세계 시청자들이 한국 콘텐츠를 소비하며 보내는 시간은 곧 한국의 공간에 체류하는 것과 유사한 효과를 낳는다”며 “OTT는 콘텐츠를 넘어, 국가의 공간과 라이프스타일까지 함께 수출하는 플랫폼으로 기능하고 있다”고 강조했다."

    rag = ChromaRAG()
    list = [text1, text2, text3]

    for text in list:
        result = ChromaRAG.chunk_text(text)
        print(result)
        result2 = rag.ingest_texts(result)
        print(result2)

        print(rag.count())
        print(rag.get_collection())

        print("==============================")