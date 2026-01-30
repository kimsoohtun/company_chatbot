import streamlit as st
import pandas as pd
import pdfplumber
from docx import Document
import google.generativeai as genai
import os

# --- 1. 관리자 설정 ---
try:
    api_key = st.secrets["GEMINI_API_KEY"]
    gsheet_url = st.secrets["GSHEET_URL"]
except:
    api_key = "" 
    gsheet_url = "" 

if api_key:
    genai.configure(api_key=api_key)

# --- 2. 텍스트 추출 로직 ---
def extract_text_from_folder(folder_path, g_url):
    text_data = ""
    sources = []
    if os.path.exists(folder_path):
        for filename in os.listdir(folder_path):
            file_path = os.path.join(folder_path, filename)
            content = ""
            try:
                if filename.endswith('.pdf'):
                    with pdfplumber.open(file_path) as pdf:
                        content = "\n".join([p.extract_text() for p in pdf.pages if p.extract_text()])
                elif filename.endswith('.docx'):
                    content = "\n".join([p.text for p in Document(file_path).paragraphs])
                elif filename.endswith('.xlsx'):
                    content = pd.read_excel(file_path).to_string()
                
                if content:
                    text_data += f"\n\n[출처: {filename}]\n{content}"
                    sources.append(filename)
            except Exception as e:
                st.error(f"파일 {filename} 읽기 실패: {e}")

    if g_url:
        try:
            csv_url = g_url.replace('/edit#gid=', '/export?format=csv&gid=') if "edit" in g_url else g_url
            df = pd.read_csv(csv_url)
            text_data += f"\n\n[출처: 구글 시트]\n{df.to_string()}"
            sources.append("구글 시트")
        except: pass
    return text_data, sources

# --- 3. UI 및 지식 로드 ---
st.set_page_config(page_title="사내 규정 챗봇", layout="centered")
st.title("🤖 사내 규정 안내 챗봇")
st.markdown("---")

# 지식 구축 (data 폴더 읽기)
knowledge_base, source_list = extract_text_from_folder("data", gsheet_url)

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- 4. 질문 처리 ---
# 사용자가 입력을 넣었을 때만 이 블록이 실행되므로 'prompt' 정의 오류가 발생하지 않습니다.
if prompt := st.chat_input("궁금한 규정을 물어보세요."):
    if not api_key:
        st.error("관리자 설정(API Key)이 필요합니다.")
    else:
        # 사용자 질문 표시 및 기록
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            try:
                # 404 오류 해결: 모델 경로를 'models/gemini-1.5-flash'로 명확히 지정
                model = genai.GenerativeModel('models/gemini-1.5-flash')
                
                # 429 오류 해결: 지식 베이스의 양을 안전한 범위(약 7만 자)로 제한
                safe_context = knowledge_base[:70000]
                
                full_query = f"""너는 사내 규정 전문가야. 아래 제공된 [지식 베이스]를 바탕으로 답변해줘.
답변 끝에 '참고 문서: [문서명]'을 꼭 적어줘. 
모르는 내용은 반드시 '인사팀에 문의하세요'라고 답변해.

[지식 베이스(일부)]
{safe_context}

질문: {prompt}"""
                
                # 답변 생성 및 출력
                response = model.generate_content(full_query)
                st.markdown(response.text)
                
                # 답변 기록 저장
                st.session_state.messages.append({"role": "assistant", "content": response.text})
                
            except Exception as e:
                # 상세 에러 메시지 분석 및 안내
                error_msg = str(e)
                if "429" in error_msg:
                    st.error("⚠️ 요청 한도를 초과했습니다. 약 1분 뒤에 다시 시도해 주세요.")
                elif "404" in error_msg:
                    # 여전히 404가 날 경우를 대비해 대안 모델명 시도 안내
                    st.error("⚠️ 모델을 찾을 수 없습니다. 모델명을 'gemini-1.5-flash' 또는 'gemini-pro'로 변경해 보세요.")
                else:
                    st.error(f"오류가 발생했습니다: {error_msg}")
