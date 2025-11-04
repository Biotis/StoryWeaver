import os
import re
import base64
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import google.generativeai as genai
from dotenv import load_dotenv
import markdown

# ✅ 환경 변수 로드
load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

app = FastAPI()

# ✅ 정적 폴더 연결
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="static")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/generate", response_class=HTMLResponse)
async def generate(request: Request, prompt: str = Form(...)):
    try:
        story_model = genai.GenerativeModel("gemini-2.5-flash")

        # ✅ Gemini에 보낼 프롬프트 (한국어 스토리 + 삽화 설명 포함)
        story_prompt = f"""
        아래 주제를 바탕으로 어린이용 그림책 스타일의 스토리를 작성하세요.
        - 주제: "{prompt}"
        - 스토리는 총 8페이지로 구성하세요.
        - 각 페이지는 아래 형식을 반드시 따르세요:

          1. 페이지 (삽화: [한국어로 된 삽화 장면 설명])
          [해당 페이지의 한국어 스토리 본문, 짧고 동화체로 작성]

        - 삽화 설명은 실제로 그림을 그릴 수 있을 정도로 구체적으로 써주세요.
        - 전체 이야기의 분위기는 따뜻하고 희망적으로 마무리하세요.
        - 출력 형식(페이지 번호, 괄호, 줄바꿈 등)은 그대로 유지하세요.
        """

        story_response = story_model.generate_content(story_prompt)
        story_text = story_response.text.strip()

        # ✅ 페이지별 분리
        page_blocks = re.split(r'(?=\d+\.\s*페이지)', story_text)
        pages = []

        for block in page_blocks:
            if not block.strip():
                continue

            # 삽화 설명 추출 (한국어)
            match = re.search(r'삽화:\s*(.*)\)', block)
            image_prompt_ko = match.group(1).strip() if match else None

            # 스토리 본문 추출
            story_part = re.sub(r'.*?\)\s*', '', block, count=1, flags=re.S).strip()

            image_base64 = None
            if image_prompt_ko:
                try:
                    image_model = genai.GenerativeModel("gemini-2.5-flash-image")

                    # ✅ 한국어 프롬프트 그대로 전달 (명확히 스타일 지정)
                    img_response = image_model.generate_content([
                        f"동화책 스타일의 일러스트, 따뜻한 색감, 수채화 느낌, {image_prompt_ko}"
                    ])

                    for part in img_response.candidates[0].content.parts:
                        if getattr(part, "inline_data", None):
                            image_base64 = base64.b64encode(part.inline_data.data).decode("utf-8")
                            break

                except Exception as e:
                    print("⚠️ 이미지 생성 실패:", e)
                    image_base64 = None

            pages.append({
                "page_title": block.split(")")[0] + ")",  # "1. 페이지 (삽화: ...)"
                "image_desc": image_prompt_ko,
                "story_text": story_part,
                "image_base64": image_base64
            })

        return templates.TemplateResponse("index.html", {
            "request": request,
            "result": {
                "prompt": prompt,
                "pages": pages
            }
        })

    except Exception as e:
        return templates.TemplateResponse("index.html", {
            "request": request,
            "error": str(e)
        })
